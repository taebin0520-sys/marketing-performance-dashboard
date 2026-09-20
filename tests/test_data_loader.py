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
