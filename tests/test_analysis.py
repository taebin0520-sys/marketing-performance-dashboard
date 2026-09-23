"""집계(추세/채널/콘텐츠) 테스트.

집계에서 가장 흔한 실수는 두 가지입니다.
1) 주간 기준이 하루씩 어긋난다 (월요일 시작인지 일요일 시작인지)
2) 집계 과정에서 값이 사라지거나 중복된다
그래서 이 두 가지를 반드시 확인하는 테스트를 넣었습니다.
"""

from datetime import date

import pandas as pd
import pytest

from src import analysis


def test_weekly_period_starts_on_monday(clean_frame):
    """주간 집계의 기준일은 항상 그 주의 월요일이어야 합니다.

    pandas의 to_period('W-MON')은 '월요일에 끝나는 주'라서 하루가 어긋납니다.
    이 테스트가 그 실수를 잡아줍니다. (weekday: 월=0)
    """
    result = analysis.aggregate_by_period(clean_frame, "W")

    assert (result["period"].dt.weekday == 0).all()


def test_weekly_aggregation_groups_same_week_together(clean_frame):
    """같은 주(9/7 월, 9/9 수)는 한 줄로 묶이고, 다음 주(9/14)는 분리되어야 합니다."""
    result = analysis.aggregate_by_period(clean_frame, "W")

    assert len(result) == 2


def test_period_aggregation_preserves_totals(clean_frame):
    """집계 전과 후의 합계가 같아야 합니다. (데이터가 새거나 중복되지 않았는지 확인)"""
    for period_code in ["D", "W", "M"]:
        result = analysis.aggregate_by_period(clean_frame, period_code)

        assert result["clicks"].sum() == clean_frame["clicks"].sum()
        assert result["impressions"].sum() == clean_frame["impressions"].sum()
        assert result["conversions"].sum() == clean_frame["conversions"].sum()


def test_monthly_period_starts_on_first_day(clean_frame):
    """월간 집계의 기준일은 항상 그 달의 1일이어야 합니다."""
    result = analysis.aggregate_by_period(clean_frame, "M")

    assert (result["period"].dt.day == 1).all()
    assert len(result) == 1  # 테스트 데이터는 모두 2026년 9월


def test_daily_period_keeps_each_date(clean_frame):
    """일간 집계는 날짜 개수만큼 행이 나와야 합니다."""
    result = analysis.aggregate_by_period(clean_frame, "D")

    assert len(result) == clean_frame["date"].nunique()


def test_invalid_period_code_raises():
    """잘못된 집계 단위를 넣으면 조용히 넘어가지 않고 에러를 내야 합니다."""
    import pandas as pd

    df = pd.DataFrame({"date": pd.to_datetime(["2026-09-07"])})

    with pytest.raises(ValueError):
        analysis.add_period_column(df, "Y")


def test_period_label_is_human_readable(clean_frame):
    """기간 라벨이 화면에 바로 쓸 수 있는 형태여야 합니다."""
    weekly = analysis.aggregate_by_period(clean_frame, "W")
    monthly = analysis.aggregate_by_period(clean_frame, "M")

    assert weekly["period_label"].iloc[0].endswith("주")
    assert monthly["period_label"].iloc[0] == "2026-09"


def test_aggregate_by_channel_sorted_by_conversions(clean_frame):
    """채널별 집계는 전환이 많은 순으로 정렬되어야 합니다."""
    result = analysis.aggregate_by_channel(clean_frame)

    assert len(result) == 2
    # 인스타그램 전환 5건(2+3) > 카카오 0건
    assert result.iloc[0]["channel_label"] == "인스타그램"
    assert result.iloc[0]["conversions"] == 5


def test_aggregate_by_channel_adds_ratio_columns(clean_frame):
    """채널별 집계에도 비율 지표가 붙어야 합니다."""
    result = analysis.aggregate_by_channel(clean_frame)

    for column in ["ctr", "inquiry_rate", "conversion_rate"]:
        assert column in result.columns


def test_aggregate_by_content_merges_same_content(clean_frame):
    """같은 콘텐츠가 여러 날에 나뉘어 있으면 하나로 합쳐야 합니다."""
    result = analysis.aggregate_by_content(clean_frame)

    # C0001은 2행(9/7, 9/9) -> 1행으로 합쳐지고, C0002는 1행
    assert len(result) == 2

    c0001 = result[result["content_id"] == "C0001"].iloc[0]
    assert c0001["impressions"] == 3000   # 1000 + 2000
    assert c0001["conversions"] == 5      # 2 + 3


def test_top_n_content_returns_requested_count(clean_frame):
    """TOP N은 요청한 개수만큼만 돌려줘야 합니다."""
    content_df = analysis.aggregate_by_content(clean_frame)

    result = analysis.top_n_content(content_df, metric="conversions", n=1)

    assert len(result) == 1
    assert result.iloc[0]["content_id"] == "C0001"


def test_top_n_content_min_impressions_filter(clean_frame):
    """최소 노출 기준을 넘지 못한 콘텐츠는 제외되어야 합니다.

    비율 지표(CTR)로 정렬할 때 노출 10회짜리 콘텐츠가 1위로 올라오는 것을 막는 장치입니다.
    """
    content_df = analysis.aggregate_by_content(clean_frame)

    # 테스트 데이터의 최대 노출은 3,000이므로 기준을 5,000으로 두면 아무것도 남지 않습니다.
    result = analysis.top_n_content(content_df, metric="ctr", n=5, min_impressions=5000)

    assert result.empty


def test_summarize_channel_ranking(clean_frame):
    """1위 채널 요약 정보를 돌려줘야 합니다."""
    channel_df = analysis.aggregate_by_channel(clean_frame)

    best = analysis.summarize_channel_ranking(channel_df, "conversions")

    assert best["channel_label"] == "인스타그램"
    assert best["value"] == 5


def test_empty_dataframe_returns_empty_result(clean_frame):
    """빈 데이터가 들어와도 에러 없이 빈 결과를 돌려줘야 합니다.

    사용자가 필터를 좁게 걸면 실제로 빈 데이터가 들어옵니다.
    """
    empty = clean_frame.iloc[0:0]

    assert analysis.aggregate_by_period(empty, "W").empty
    assert analysis.aggregate_by_channel(empty).empty
    assert analysis.aggregate_by_content(empty).empty



def test_content_label_includes_content_id(clean_frame):
    """차트용 콘텐츠 라벨에는 제목과 함께 ID가 들어가야 합니다."""
    result = analysis.aggregate_by_content(clean_frame)

    assert "가을 코디 추천 (C0001)" in set(result["content_label"])


def test_same_title_different_contents_are_not_merged():
    """제목이 같아도 콘텐츠 ID가 다르면 별도의 행으로 남아야 합니다.

    실제 샘플 데이터에도 제목이 우연히 겹치는 콘텐츠가 존재합니다.
    제목만으로 집계하면 서로 다른 콘텐츠의 성과가 하나로 합쳐져 분석이 틀어집니다.
    """
    import pandas as pd

    from src import data_loader

    raw = pd.DataFrame(
        {
            "date": ["2026-09-07", "2026-09-07"],
            "channel": ["instagram", "instagram"],
            "content_id": ["C0009", "C0012"],          # 서로 다른 콘텐츠
            "content_title": ["한정 수량 세트 후기", "한정 수량 세트 후기"],  # 제목은 동일
            "content_type": ["reels", "reels"],
            "impressions": [1000, 2000],
            "reach": [800, 1600],
            "views": [600, 1200],
            "clicks": [50, 120],
            "inquiries": [5, 12],
            "conversions": [1, 4],
        }
    )
    cleaned, _ = data_loader.clean_data(raw)

    result = analysis.aggregate_by_content(cleaned)

    assert len(result) == 2
    assert result["content_label"].nunique() == 2



# ---------------------------------------------------------------------------
# 전기 대비 증감 테스트
# ---------------------------------------------------------------------------

def test_get_previous_period_same_length():
    """직전 기간은 선택 기간과 반드시 같은 길이여야 합니다.

    09-08 ~ 09-14 는 7일입니다. (양쪽 끝을 포함해서 셈)
    직전 기간도 7일이어야 하므로 09-01 ~ 09-07 이 되어야 합니다.
    """
    prev_start, prev_end = analysis.get_previous_period("2026-09-08", "2026-09-14")

    assert prev_start.strftime("%Y-%m-%d") == "2026-09-01"
    assert prev_end.strftime("%Y-%m-%d") == "2026-09-07"
    # 길이가 정말 같은지 확인 (7일)
    assert (prev_end - prev_start).days + 1 == 7


def test_get_previous_period_single_day():
    """하루만 선택해도(기간 길이 1일) 직전 기간은 바로 전날 하루여야 합니다."""
    prev_start, prev_end = analysis.get_previous_period("2026-09-10", "2026-09-10")

    assert prev_start.strftime("%Y-%m-%d") == "2026-09-09"
    assert prev_end.strftime("%Y-%m-%d") == "2026-09-09"


def test_calculate_period_over_period_basic_increase():
    """전환이 10 -> 15로 늘면 delta=5, percent_change=0.5(50%)여야 합니다."""
    current = {"conversions": 15, "clicks": 100}
    previous = {"conversions": 10, "clicks": 100}

    result = analysis.calculate_period_over_period(current, previous)

    assert result["conversions"]["delta"] == 5
    assert result["conversions"]["percent_change"] == 0.5
    assert result["conversions"]["is_new"] is False


def test_calculate_period_over_period_marks_new_when_previous_zero():
    """직전 기간 값이 0이었다가 생겼으면 '신규'로 표시되어야 합니다. (0으로 나누기 방지)"""
    current = {"conversions": 5}
    previous = {"conversions": 0}

    result = analysis.calculate_period_over_period(current, previous)

    assert result["conversions"]["is_new"] is True
    assert result["conversions"]["percent_change"] is None
    assert result["conversions"]["delta"] == 5


def test_calculate_period_over_period_both_zero_is_not_new():
    """양쪽 다 0이면 '신규'가 아니라 그냥 변화 없음입니다."""
    result = analysis.calculate_period_over_period({"conversions": 0}, {"conversions": 0})

    assert result["conversions"]["is_new"] is False
    assert result["conversions"]["delta"] == 0


def test_calculate_period_over_period_none_values_skip_comparison():
    """계산 자체가 불가능했던 지표(None)는 증감도 계산하지 않아야 합니다.

    예) 광고비가 0원이라 CPA가 None인 경우, 억지로 증감을 만들면 안 됩니다.
    """
    current = {"cpa": None}
    previous = {"cpa": 5000}

    result = analysis.calculate_period_over_period(current, previous)

    assert result["cpa"]["delta"] is None
    assert result["cpa"]["percent_change"] is None


def test_calculate_period_over_period_excludes_row_count():
    """row_count 는 KPI가 아니므로 증감 비교 결과에 포함되지 않아야 합니다."""
    current = {"conversions": 10, "row_count": 100}
    previous = {"conversions": 5, "row_count": 50}

    result = analysis.calculate_period_over_period(current, previous)

    assert "row_count" not in result
    assert "conversions" in result



# ---------------------------------------------------------------------------
# 직전 기간 비교 가능 여부 판정
# ---------------------------------------------------------------------------
# 이 판정이 틀리면 화면에서 증감이 조용히 사라지거나,
# 반대로 데이터가 잘린 기간과 비교해 증감률이 크게 왜곡됩니다.
# 둘 다 에러 없이 잘못된 화면이 나오므로 테스트로 고정합니다.


def test_previous_period_is_comparable_when_data_covers_it(clean_frame):
    """직전 기간에 데이터가 있고 데이터 시작일 이후라면 비교할 수 있습니다."""
    result = analysis.has_comparable_previous_period(
        clean_frame,
        previous_start=pd.Timestamp("2026-09-01"),
        data_min_date=date(2026, 8, 1),
    )

    assert result is True


def test_previous_period_not_comparable_when_no_rows(clean_frame):
    """직전 기간 데이터가 0행이면 비교할 대상이 없습니다."""
    empty = clean_frame.iloc[0:0]

    result = analysis.has_comparable_previous_period(
        empty,
        previous_start=pd.Timestamp("2026-09-01"),
        data_min_date=date(2026, 8, 1),
    )

    assert result is False


def test_previous_period_not_comparable_when_start_precedes_data(clean_frame):
    """직전 기간 시작일이 데이터 최소일보다 이전이면 비교하지 않습니다.

    이 경우 직전 기간의 일부만 데이터에 존재하므로, 그대로 비교하면
    '기간이 잘려서 낮은 값'을 '성과 악화'로 잘못 읽게 됩니다.
    """
    result = analysis.has_comparable_previous_period(
        clean_frame,
        previous_start=pd.Timestamp("2026-07-15"),
        data_min_date=date(2026, 8, 1),
    )

    assert result is False


def test_previous_period_comparable_on_exact_min_date_boundary(clean_frame):
    """직전 기간 시작일이 데이터 최소일과 '같은 날'이면 비교 가능합니다.

    경계값을 > 로 잘못 쓰면 하루 차이로 증감이 사라지므로 >= 를 고정합니다.
    """
    result = analysis.has_comparable_previous_period(
        clean_frame,
        previous_start=pd.Timestamp("2026-08-01"),
        data_min_date=date(2026, 8, 1),
    )

    assert result is True
