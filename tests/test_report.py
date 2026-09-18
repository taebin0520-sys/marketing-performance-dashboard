"""자동 요약 리포트 생성 테스트.

이 리포트는 LLM을 쓰지 않는 규칙 기반이라, "같은 입력이면 항상 같은 결과"가
나와야 합니다. 그래서 테스트에서는 특정 문장이 들어있는지, 필수 섹션이
빠지지 않았는지를 확인합니다.
"""

import pandas as pd

from src import report


def make_kpis(**overrides):
    """테스트용 KPI 딕셔너리. 필요한 값만 덮어써서 씁니다."""
    base = {
        "impressions": 100000, "reach": 80000, "views": 50000,
        "clicks": 3000, "inquiries": 300, "conversions": 90,
        "cost": 900000, "revenue": 2700000,
        "ctr": 0.03, "inquiry_rate": 0.1, "conversion_rate": 0.03,
        "inquiry_to_conversion_rate": 0.3, "cpc": 300, "cpa": 10000, "roas": 3.0,
        "row_count": 500,
    }
    base.update(overrides)
    return base


def test_report_includes_all_six_sections():
    """요구사항의 6개 항목이 모두 리포트에 포함되어야 합니다."""
    kpis = make_kpis()
    pop = {"conversions": {"current": 90, "previous": 100, "delta": -10,
                            "percent_change": -0.1, "is_new": False}}
    best_channel = {"channel_label": "카카오", "metric": "conversions", "value": 50,
                     "conversion_rate": 0.05, "ctr": 0.05}
    content_df = pd.DataFrame({
        "content_title": ["A 콘텐츠", "B 콘텐츠"],
        "channel_label": ["카카오", "인스타그램"],
        "conversions": [30, 20],
        "conversion_rate": [0.05, 0.03],
    })

    text = report.generate_summary_report(
        start_date="2026-09-01", end_date="2026-09-07",
        kpis=kpis, period_over_period=pop, best_channel=best_channel,
        top_content_df=content_df,
        previous_start="2026-08-25", previous_end="2026-08-31",
    )

    assert "# 마케팅 성과 자동 요약 리포트" in text
    assert "## 분석 기간" in text
    assert "## 핵심 지표 요약" in text
    assert "## 전기 대비 변화" in text
    assert "## 채널 성과" in text
    assert "## 콘텐츠 TOP 3" in text
    assert "## 제안" in text


def test_report_mentions_period_dates():
    """분석 기간과 비교 기간 날짜가 실제로 문장에 들어가야 합니다."""
    text = report.generate_summary_report(
        start_date="2026-09-01", end_date="2026-09-07",
        kpis=make_kpis(), period_over_period={}, best_channel={},
        top_content_df=pd.DataFrame(),
        previous_start="2026-08-25", previous_end="2026-08-31",
    )

    assert "2026-09-01" in text
    assert "2026-09-07" in text
    assert "2026-08-25" in text
    assert "2026-08-31" in text


def test_report_without_previous_period_says_no_comparison():
    """비교 기간이 없으면(previous_start=None) 그 사실을 명시해야 합니다."""
    text = report.generate_summary_report(
        start_date="2026-05-19", end_date="2026-05-25",
        kpis=make_kpis(), period_over_period={}, best_channel={},
        top_content_df=pd.DataFrame(),
        previous_start=None, previous_end=None,
    )

    assert "비교 기간: 없음" in text
    assert "비교 기간 데이터가 없어" in text


def test_find_biggest_mover_picks_largest_absolute_change():
    """가장 크게 움직인 지표는 '변화율의 절댓값'이 가장 큰 것이어야 합니다.

    +5%보다 -40%가 훨씬 큰 변화이므로, -40%인 conversions가 선택되어야 합니다.
    """
    pop = {
        "views": {"percent_change": 0.05, "is_new": False},
        "conversions": {"percent_change": -0.40, "is_new": False},
        "roas": {"percent_change": 0.10, "is_new": False},
    }

    mover = report._find_biggest_mover(pop)

    assert mover["metric"] == "conversions"
    assert mover["direction"] == "감소"


def test_find_biggest_mover_ignores_none_percent_change():
    """percent_change가 None인 지표(비교 불가)는 후보에서 제외되어야 합니다."""
    pop = {
        "conversions": {"percent_change": None, "is_new": True},
        "views": {"percent_change": 0.02, "is_new": False},
    }

    mover = report._find_biggest_mover(pop)

    assert mover["metric"] == "views"


def test_find_biggest_mover_returns_empty_when_no_candidates():
    """비교 가능한 지표가 하나도 없으면 빈 딕셔너리를 돌려줘야 합니다."""
    assert report._find_biggest_mover({}) == {}
    assert report._find_biggest_mover(
        {"conversions": {"percent_change": None, "is_new": False}}
    ) == {}


def test_report_content_section_lists_top_three_only():
    """콘텐츠가 3개보다 많아도 TOP 3까지만 리포트에 표시되어야 합니다."""
    content_df = pd.DataFrame({
        "content_title": ["A", "B", "C", "D"],
        "channel_label": ["카카오"] * 4,
        "conversions": [40, 30, 20, 10],
        "conversion_rate": [0.05, 0.04, 0.03, 0.02],
    })

    section = report._build_content_section(content_df)

    assert "1. A" in section
    assert "2. B" in section
    assert "3. C" in section
    assert "D" not in section


def test_report_content_section_handles_empty_dataframe():
    """콘텐츠 데이터가 없으면 에러 대신 안내 문구를 돌려줘야 합니다."""
    section = report._build_content_section(pd.DataFrame())

    assert "표시할 콘텐츠가 없습니다" in section


def test_report_channel_section_handles_empty_dict():
    """1위 채널 정보가 없으면(빈 dict) 안내 문구를 돌려줘야 합니다."""
    section = report._build_channel_section({})

    assert "채널 데이터가 없어" in section


def test_report_is_deterministic_for_same_input():
    """LLM을 쓰지 않으므로, 같은 입력이면 항상 완전히 같은 문자열이 나와야 합니다."""
    kwargs = dict(
        start_date="2026-09-01", end_date="2026-09-07",
        kpis=make_kpis(), period_over_period={}, best_channel={},
        top_content_df=pd.DataFrame(),
        previous_start=None, previous_end=None,
    )

    text_a = report.generate_summary_report(**kwargs)
    text_b = report.generate_summary_report(**kwargs)

    assert text_a == text_b
