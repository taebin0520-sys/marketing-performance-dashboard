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



# ---------------------------------------------------------------------------
# 표현 정확성 / 과도한 단정 방지 테스트
# ---------------------------------------------------------------------------

def test_mover_section_states_relative_basis():
    """증감이 상대 증감률 기준임을 문장에 명시해야 합니다. (%p 와의 혼동 방지)"""
    pop = {"conversions": {"current": 90, "previous": 100, "delta": -10,
                            "percent_change": -0.1, "is_new": False}}

    section = report._build_mover_section(pop)

    assert "상대 증감률" in section


def test_mover_section_adds_percentage_point_for_ratio_metric():
    """비율 지표가 최대 변화 지표면 실제 수치와 %p를 함께 표기해야 합니다.

    CTR이 3.22% -> 3.43% 인 경우, 상대 +6.5% 만 적으면
    읽는 사람이 +6.5%p 로 오해할 수 있습니다.
    """
    pop = {"ctr": {"current": 0.0343, "previous": 0.0322,
                    "delta": 0.0021, "percent_change": 0.0652, "is_new": False}}

    section = report._build_mover_section(pop)

    assert "%p" in section
    assert "3.22%" in section   # 이전 값
    assert "3.43%" in section   # 현재 값


def test_mover_section_omits_percentage_point_for_count_metric():
    """전환처럼 개수 지표는 %p 개념이 없으므로 표기하지 않아야 합니다."""
    pop = {"conversions": {"current": 90, "previous": 100, "delta": -10,
                            "percent_change": -0.1, "is_new": False}}

    section = report._build_mover_section(pop)

    assert "%p" not in section


def test_action_section_avoids_prescriptive_wording():
    """자동 제안이 단정적 처방("늘려야/줄여야 한다")을 쓰지 않아야 합니다.

    한 기간의 집계만으로 예산 증감을 단정하면 위험합니다.
    규모를 키우면 효율이 떨어질 수 있고, 낮은 ROAS는 전환 추적 누락일 수도 있습니다.
    """
    mover = {"metric": "roas", "percent_change": 0.16, "direction": "증가"}
    best_channel = {"channel_label": "카카오", "metric": "conversions", "value": 1055}

    section = report._build_action_section(mover, best_channel)

    for forbidden in ["늘려야", "줄여야", "중단해야", "가장 좋습니다"]:
        assert forbidden not in section, forbidden


def test_action_section_suggests_verification_not_conclusion():
    """제안은 결론이 아니라 '무엇을 확인할지'를 담아야 합니다."""
    mover = {"metric": "roas", "percent_change": -0.2, "direction": "감소"}

    section = report._build_action_section(mover, {})

    # 점검 대상(소재/타겟팅/랜딩/추적) 중 하나 이상이 언급되어야 합니다.
    assert any(word in section for word in ["소재", "타겟팅", "랜딩", "추적"])


def test_channel_section_uses_observational_wording():
    """채널 성과는 '가장 좋다'가 아니라 '이 기간에 높게 나타났다'로 표현해야 합니다."""
    best_channel = {"channel_label": "카카오", "metric": "conversions",
                     "value": 1055, "conversion_rate": 0.0161}

    section = report._build_channel_section(best_channel)

    assert "최상위 채널" in section
    assert "가장 좋습니다" not in section


def test_channel_section_avoids_broken_korean_particle():
    """지표 라벨 뒤에 조사를 붙이지 않아 '전환가' 같은 비문이 생기지 않아야 합니다.

    한국어 조사(이/가)는 앞 글자 종성에 따라 달라지므로,
    지표 라벨을 문장에 그대로 끼워 넣으면 틀린 조사가 나옵니다.
    """
    section = report._build_channel_section(
        {"channel_label": "카카오", "metric": "conversions", "value": 1055}
    )

    assert "전환가" not in section
