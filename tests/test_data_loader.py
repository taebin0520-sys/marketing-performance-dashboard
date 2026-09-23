"""데이터 로딩/검증/전처리 테스트.

전처리는 "눈에 안 보이는데 틀리면 모든 숫자가 틀어지는" 부분이라
테스트를 가장 먼저 붙였습니다.
"""

import pandas as pd
import pytest

from src import config, data_loader


def test_validate_columns_returns_missing_list(raw_frame):
    """필수 컬럼이 빠졌을 때 그 이름들을 정확히 알려줘야 합니다."""
    broken = raw_frame.drop(columns=["clicks", "conversions"])

    missing = data_loader.validate_columns(broken)

    assert missing == ["clicks", "conversions"]


def test_validate_columns_passes_when_all_present(raw_frame):
    """필수 컬럼이 모두 있으면 빈 리스트를 돌려줘야 합니다."""
    assert data_loader.validate_columns(raw_frame) == []


def test_clean_data_drops_rows_with_invalid_date(raw_frame):
    """날짜로 변환할 수 없는 행은 제외하고, 몇 건을 제외했는지 알려줘야 합니다."""
    cleaned, info = data_loader.clean_data(raw_frame)

    assert info["rows_before"] == 4
    assert info["rows_after"] == 3
    assert info["invalid_date_rows"] == 1
    # 날짜 컬럼이 문자열이 아니라 진짜 날짜 타입으로 바뀌었는지 확인
    assert pd.api.types.is_datetime64_any_dtype(cleaned[config.DATE_COLUMN])


def test_clean_data_fills_missing_and_fixes_negative(raw_frame):
    """빈 숫자 칸은 0으로 채우고, 음수는 0으로 보정해야 합니다."""
    cleaned, info = data_loader.clean_data(raw_frame)

    assert info["missing_numeric_cells"] == 1   # cost의 빈칸 1개
    assert info["negative_value_cells"] == 1    # clicks의 -5
    assert cleaned["clicks"].min() >= 0
    assert cleaned["cost"].min() >= 0


def test_clean_data_normalizes_text_columns(raw_frame):
    """채널 이름의 앞뒤 공백을 제거하고, 빈 값은 '미분류'로 채워야 합니다."""
    cleaned, _ = data_loader.clean_data(raw_frame)

    # ' instagram ' 과 'instagram' 이 같은 채널로 합쳐져야 합니다.
    assert set(cleaned["channel"].unique()) == {"instagram", "kakao"}
    # content_type이 None이던 행은 '미분류'가 됩니다.
    assert config.UNKNOWN_LABEL in set(cleaned["content_type"].unique())


def test_clean_data_adds_korean_labels(raw_frame):
    """화면 표시용 한국어 라벨 컬럼이 추가되어야 합니다."""
    cleaned, _ = data_loader.clean_data(raw_frame)

    assert "channel_label" in cleaned.columns
    assert "인스타그램" in set(cleaned["channel_label"].unique())


def test_clean_data_creates_optional_columns_when_absent(raw_frame):
    """광고비/매출 컬럼이 없어도 에러 없이 동작하고, 없다는 사실이 기록되어야 합니다."""
    without_cost = raw_frame.drop(columns=["cost", "revenue"])

    cleaned, info = data_loader.clean_data(without_cost)

    assert info["has_cost"] is False
    assert info["has_revenue"] is False
    # 뒤쪽 계산 코드가 컬럼 유무를 매번 확인하지 않도록 컬럼 자체는 만들어 둡니다.
    assert "cost" in cleaned.columns
    assert "revenue" in cleaned.columns


def test_clean_data_fills_absent_optional_columns_with_nan_not_zero(raw_frame):
    """없는 선택 컬럼은 0이 아니라 NaN('알 수 없음')으로 채워야 합니다.

    0으로 채우면 '매출 0원'과 '매출 데이터 없음'을 구분할 수 없어
    revenue 컬럼이 없는 CSV에서도 ROAS가 0.00배로 계산됩니다.
    """
    without_revenue = raw_frame.drop(columns=["revenue"])

    cleaned, info = data_loader.clean_data(without_revenue)

    assert info["has_revenue"] is False
    assert cleaned["revenue"].isna().all()
    # cost는 원본에 있었으므로 실제 값이 남아 있어야 합니다.
    assert info["has_cost"] is True
    assert cleaned["cost"].notna().any()


def test_check_funnel_consistency_counts_violations():
    """퍼널 순서가 어긋난 행의 개수를 세어야 합니다."""
    df = pd.DataFrame(
        {
            "impressions": [1000, 100],
            "reach": [800, 200],   # 두 번째 행은 도달 > 노출 -> 위반
            "views": [600, 50],
            "clicks": [50, 10],
            "inquiries": [5, 1],
            "conversions": [1, 0],
        }
    )

    assert data_loader.check_funnel_consistency(df) == 1


def test_filter_data_by_date_and_channel(clean_frame):
    """기간과 채널 필터가 동시에 적용되어야 합니다."""
    filtered = data_loader.filter_data(
        clean_frame,
        start_date="2026-09-07",
        end_date="2026-09-09",
        channels=["instagram"],
    )

    assert len(filtered) == 2
    assert set(filtered["channel"].unique()) == {"instagram"}


def test_filter_data_returns_empty_when_no_match(clean_frame):
    """조건에 맞는 데이터가 없으면 빈 DataFrame을 돌려줘야 합니다. (에러가 아님)"""
    filtered = data_loader.filter_data(
        clean_frame,
        start_date="2020-01-01",
        end_date="2020-01-31",
    )

    assert filtered.empty


def test_load_and_prepare_sample_data():
    """저장소에 포함된 샘플 데이터가 정상적으로 로드되어야 합니다."""
    df, info = data_loader.load_and_prepare(None)

    assert info["is_sample"] is True
    assert len(df) > 1000
    # 샘플 데이터는 퍼널 규칙을 지키도록 생성했으므로 위반이 0이어야 합니다.
    assert info["funnel_violation_rows"] == 0
    # 필수 컬럼이 모두 존재해야 합니다.
    for column in config.REQUIRED_COLUMNS:
        assert column in df.columns


def test_load_and_prepare_raises_on_missing_columns(tmp_path):
    """필수 컬럼이 없는 CSV를 넣으면 DataValidationError가 발생해야 합니다."""
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("date,channel\n2026-09-01,instagram\n", encoding="utf-8")

    with pytest.raises(data_loader.DataValidationError) as error:
        data_loader.load_and_prepare(bad_csv)

    # 어떤 컬럼이 없는지 메시지에 들어 있어야 사용자가 고칠 수 있습니다.
    assert "impressions" in str(error.value)



# ---------------------------------------------------------------------------
# B-1. 필터에서 None(전체)과 빈 리스트(선택 없음)를 구분해야 한다
# ---------------------------------------------------------------------------
# 빈 리스트를 '전체'로 처리하면, 사용자가 화면에서 채널을 전부 지웠을 때
# 필터가 사라져 전체 합계가 표시됩니다. 사이드바에는 아무것도 선택되지 않았는데
# 화면에는 전체 KPI가 나오므로 잘못된 숫자를 읽게 됩니다.

def test_filter_data_channels_none_keeps_all_rows(clean_frame):
    """channels=None 이면 채널 필터를 걸지 않고 전체를 유지해야 합니다."""
    filtered = data_loader.filter_data(
        clean_frame, "2026-09-01", "2026-09-30", channels=None
    )

    assert len(filtered) == len(clean_frame)


def test_filter_data_channels_empty_list_returns_no_rows(clean_frame):
    """channels=[] 는 '선택된 채널이 없음'이므로 결과가 0건이어야 합니다."""
    filtered = data_loader.filter_data(
        clean_frame, "2026-09-01", "2026-09-30", channels=[]
    )

    assert filtered.empty


def test_filter_data_content_types_none_keeps_all_rows(clean_frame):
    """content_types=None 이면 콘텐츠 유형 필터를 걸지 않고 전체를 유지해야 합니다."""
    filtered = data_loader.filter_data(
        clean_frame, "2026-09-01", "2026-09-30", content_types=None
    )

    assert len(filtered) == len(clean_frame)


def test_filter_data_content_types_empty_list_returns_no_rows(clean_frame):
    """content_types=[] 는 '선택된 유형이 없음'이므로 결과가 0건이어야 합니다."""
    filtered = data_loader.filter_data(
        clean_frame, "2026-09-01", "2026-09-30", content_types=[]
    )

    assert filtered.empty


def test_filter_data_empty_list_is_not_treated_as_select_all(clean_frame):
    """빈 리스트와 None의 결과가 달라야 합니다. (같으면 B-1 버그가 되살아난 것)"""
    all_rows = data_loader.filter_data(
        clean_frame, "2026-09-01", "2026-09-30", channels=None
    )
    no_rows = data_loader.filter_data(
        clean_frame, "2026-09-01", "2026-09-30", channels=[]
    )

    assert len(all_rows) > 0
    assert len(no_rows) == 0


# ---------------------------------------------------------------------------
# B-2. 천 단위 쉼표가 있는 숫자를 0으로 만들지 않아야 한다
# ---------------------------------------------------------------------------
# 엑셀에서 CSV로 내보내면 숫자가 "1,234" 형태로 저장되는 일이 흔합니다.
# 쉼표를 그대로 두면 숫자 변환이 실패해 NaN -> 0 이 되어 모든 지표가 0이 됩니다.

def make_numeric_frame(impressions_values):
    """impressions 컬럼만 바꿔가며 테스트할 최소 프레임을 만듭니다."""
    size = len(impressions_values)
    return pd.DataFrame(
        {
            "date": ["2026-09-01"] * size,
            "channel": ["instagram"] * size,
            "content_id": ["C0001"] * size,
            "content_title": ["테스트 콘텐츠"] * size,
            "content_type": ["image"] * size,
            "impressions": impressions_values,
            "reach": [0] * size,
            "views": [0] * size,
            "clicks": [0] * size,
            "inquiries": [0] * size,
            "conversions": [0] * size,
        }
    )


def test_clean_data_parses_thousand_separator():
    """"1,000" 은 0이 아니라 1000으로 변환되어야 합니다."""
    cleaned, info = data_loader.clean_data(make_numeric_frame(["1,000"]))

    assert cleaned["impressions"].iloc[0] == 1000
    # 정상적으로 읽혔으므로 결측·파싱 실패로 세지 않아야 합니다.
    assert info["missing_numeric_cells"] == 0
    assert info["invalid_numeric_cells"] == 0


def test_clean_data_parses_thousand_separator_with_decimal():
    """"12,345.5" 처럼 소수점이 섞여도 숫자로 변환되어야 합니다.

    impressions는 개수라서 정수로 반올림되므로 12346이 됩니다.
    (원본 값이 0으로 사라지지 않는다는 점이 이 테스트의 핵심입니다)
    """
    cleaned, info = data_loader.clean_data(make_numeric_frame(["12,345.5"]))

    assert cleaned["impressions"].iloc[0] == 12346
    assert info["invalid_numeric_cells"] == 0


def test_clean_data_keeps_plain_numbers_unchanged():
    """쉼표가 없는 정상 숫자는 기존 동작을 그대로 유지해야 합니다."""
    cleaned, info = data_loader.clean_data(make_numeric_frame([1500, 2500]))

    assert cleaned["impressions"].tolist() == [1500, 2500]
    assert info["missing_numeric_cells"] == 0
    assert info["invalid_numeric_cells"] == 0


def test_clean_data_counts_real_missing_as_missing_not_invalid():
    """원래 비어 있던 칸은 '결측'으로 세고 '파싱 실패'로 세지 않아야 합니다."""
    cleaned, info = data_loader.clean_data(make_numeric_frame(["", 100]))

    assert cleaned["impressions"].iloc[0] == 0
    assert info["missing_numeric_cells"] == 1
    assert info["invalid_numeric_cells"] == 0


def test_clean_data_flags_unparsable_text_instead_of_silent_zero():
    """숫자로 읽을 수 없는 값은 조용히 0으로 넘기지 않고 별도로 세어야 합니다.

    값이 0으로 채워지는 동작 자체는 유지하되,
    '빈칸이라서 0'과 '읽을 수 없어서 0'을 구분해 사용자에게 알릴 수 있어야 합니다.
    """
    cleaned, info = data_loader.clean_data(make_numeric_frame(["몰라요", 100]))

    assert cleaned["impressions"].iloc[0] == 0
    # 빈칸이 아니었으므로 결측이 아니라 파싱 실패로 집계되어야 합니다.
    assert info["invalid_numeric_cells"] == 1
    assert info["missing_numeric_cells"] == 0
