"""집계(추세/채널/콘텐츠) 테스트.

집계에서 가장 흔한 실수는 두 가지입니다.
1) 주간 기준이 하루씩 어긋난다 (월요일 시작인지 일요일 시작인지)
2) 집계 과정에서 값이 사라지거나 중복된다
그래서 이 두 가지를 반드시 확인하는 테스트를 넣었습니다.
"""

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
