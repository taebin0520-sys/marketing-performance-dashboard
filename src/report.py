"""규칙 기반(if/else)으로 자동 요약 리포트를 만드는 모듈.

주의: LLM(생성형 AI)을 전혀 사용하지 않습니다.
이미 계산된 KPI/증감/채널/콘텐츠 결과를 미리 정해둔 문장 틀에 끼워 넣는 방식입니다.
그래서 결과가 항상 예측 가능하고, "왜 이 문장이 나왔는지"를 코드로 설명할 수 있습니다.

이 파일이 받는 재료 (전부 다른 모듈이 이미 계산해둔 결과를 재사용합니다)
- kpi.calculate_kpis()                     -> 이번 기간 KPI
- analysis.calculate_period_over_period()  -> 전기 대비 증감
- analysis.aggregate_by_channel()          -> 채널별 집계
- analysis.summarize_channel_ranking()     -> 1위 채널
- analysis.top_n_content()                 -> 콘텐츠 TOP N

이 파일도 streamlit을 import하지 않습니다. 문자열(Markdown)만 돌려주면
화면(app.py)이든 파일 저장이든 원하는 곳에 그대로 쓸 수 있습니다.
"""

from src import config, formatting

# 증감을 "가장 크게 움직인 지표"로 뽑을 때 후보로 삼을 지표들.
# row_count 나 원본 합계성 지표(광고비 등)는 스토리텔링에 덜 중요해서 제외했습니다.
HEADLINE_CANDIDATE_METRICS = [
    "views", "reach", "clicks", "inquiries", "conversions",
    "ctr", "conversion_rate", "roas",
]


def _find_biggest_mover(period_over_period: dict) -> dict:
    """전기 대비 증감 중 '변화율의 절댓값'이 가장 큰 지표 1개를 찾습니다.

    왜 절댓값 기준인가?
    "가장 많이 오른 지표"만 보면 큰 폭으로 떨어진 위험 신호를 놓칠 수 있습니다.
    변화의 크기(오르든 내리든) 자체가 리포트에서 가장 먼저 언급할 가치가 있는 정보입니다.
    """
    best_metric = None
    best_abs_change = -1

    for metric in HEADLINE_CANDIDATE_METRICS:
        info = period_over_period.get(metric)
        if not info or info["percent_change"] is None:
            continue

        abs_change = abs(info["percent_change"])
        if abs_change > best_abs_change:
            best_abs_change = abs_change
            best_metric = metric

    if best_metric is None:
        return {}

    info = period_over_period[best_metric]
    return {
        "metric": best_metric,
        "percent_change": info["percent_change"],
        "direction": "증가" if info["percent_change"] > 0 else "감소",
    }


def _build_period_section(start_date, end_date, previous_start=None, previous_end=None) -> str:
    """1) 분석 기간 및 비교 기간 문장."""
    lines = ["## 분석 기간", "", "- 이번 기간: {} ~ {}".format(start_date, end_date)]

    if previous_start is not None and previous_end is not None:
        lines.append("- 비교 기간: {} ~ {} (직전 동일 길이 기간)".format(previous_start, previous_end))
    else:
        lines.append("- 비교 기간: 없음 (데이터 시작일 이전이라 비교할 이전 기간이 없습니다)")

    return "\n".join(lines)


def _build_kpi_section(kpis: dict) -> str:
    """2) 핵심 지표 요약 문장."""
    lines = ["## 핵심 지표 요약", ""]

    for metric in config.KPI_CARD_METRICS:
        lines.append("- {}: {}".format(
            config.get_metric_label(metric), formatting.format_metric(metric, kpis[metric])
        ))

    for metric in ["ctr", "conversion_rate", "roas"]:
        lines.append("- {}: {}".format(
            config.get_metric_label(metric), formatting.format_metric(metric, kpis[metric])
        ))

    return "\n".join(lines)


def _build_mover_section(period_over_period: dict) -> str:
    """3) 전기 대비 가장 많이 움직인 지표 문장."""
    if not period_over_period:
        return (
            "## 전기 대비 변화\n\n"
            "- 비교 기간 데이터가 없어 증감을 계산하지 않았습니다."
        )

    mover = _find_biggest_mover(period_over_period)

    if not mover:
        return (
            "## 전기 대비 변화\n\n"
            "- 직전 기간과 비교할 수 있는 지표가 없습니다."
        )

    metric_label = config.get_metric_label(mover["metric"])
    # format_delta는 이미 +/- 부호로 방향을 나타내므로("-27.8%"),
    # 뒤에 "증가/감소"를 또 붙이면 "감소했습니다"처럼 방향이 중복 표현됩니다.
    # 그래서 부호 없는 절댓값 퍼센트 + "증가/감소했습니다"로 문장을 만듭니다.
    abs_percent_text = "{:.1f}%".format(abs(mover["percent_change"]) * 100)

    return (
        "## 전기 대비 변화\n\n"
        "- 이번 기간 가장 크게 변한 지표는 **{}**입니다. "
        "직전 기간 대비 **{} {}**했습니다.".format(
            metric_label, abs_percent_text, mover["direction"]
        )
    )


def _build_channel_section(best_channel: dict) -> str:
    """4) 가장 성과가 좋은 채널 문장."""
    if not best_channel:
        return "## 채널 성과\n\n- 채널 데이터가 없어 순위를 계산하지 않았습니다."

    metric_label = config.get_metric_label(best_channel["metric"])
    value_text = formatting.format_metric(best_channel["metric"], best_channel["value"])

    lines = [
        "## 채널 성과",
        "",
        "- 이번 기간 {} 기준 1위 채널은 **{}**입니다. ({}: {})".format(
            metric_label, best_channel["channel_label"], metric_label, value_text
        ),
    ]

    # 근거를 하나 더 붙여줍니다. (숫자 하나만 던지면 "그래서 왜 좋은 건데?"라는 의문이 남습니다)
    conversion_rate = best_channel.get("conversion_rate")
    if conversion_rate is not None and not formatting.is_empty(conversion_rate):
        lines.append("  - 전환율: {}".format(formatting.format_metric("conversion_rate", conversion_rate)))

    return "\n".join(lines)


def _build_content_section(top_content_df) -> str:
    """5) 최고 성과 콘텐츠 TOP 3 문장."""
    if top_content_df is None or top_content_df.empty:
        return "## 콘텐츠 TOP 3\n\n- 표시할 콘텐츠가 없습니다."

    lines = ["## 콘텐츠 TOP 3", ""]

    top3 = top_content_df.head(3)
    for rank in range(len(top3)):
        row = top3.iloc[rank]
        lines.append(
            "{}. {} ({}) - 전환 {}, 전환율 {}".format(
                rank + 1,
                row["content_title"],
                row["channel_label"],
                formatting.format_int(row["conversions"]),
                formatting.format_metric("conversion_rate", row["conversion_rate"]),
            )
        )

    return "\n".join(lines)


def _build_action_section(mover: dict, best_channel: dict) -> str:
    """6) 간단한 액션 제안 문장.

    규칙 기반이라 "정답"을 말하는 게 아니라, 숫자가 이렇게 나왔을 때
    실무에서 흔히 검토하는 방향을 제안 형태로 짧게 던집니다.
    """
    suggestions = []

    if mover:
        if mover["metric"] == "roas" and mover["direction"] == "증가":
            suggestions.append("ROAS가 개선되었습니다. 예산을 확대해도 효율이 유지되는지 검토해보세요.")
        elif mover["metric"] == "roas" and mover["direction"] == "감소":
            suggestions.append("ROAS가 하락했습니다. 소재 교체나 타겟팅 재점검이 필요할 수 있습니다.")
        elif mover["metric"] == "conversions" and mover["direction"] == "감소":
            suggestions.append("전환이 감소했습니다. 유입은 유지되는지, 랜딩 단계에서 이탈이 늘었는지 확인해보세요.")
        elif mover["metric"] == "conversions" and mover["direction"] == "증가":
            suggestions.append("전환이 증가했습니다. 이번 기간에 무엇이 달랐는지(소재/캠페인/시즌) 기록해두면 재현에 도움이 됩니다.")

    if best_channel:
        suggestions.append(
            "{} 채널의 성과가 가장 좋습니다. 예산 배분 시 우선 검토 대상으로 고려해보세요.".format(
                best_channel["channel_label"]
            )
        )

    if not suggestions:
        suggestions.append("특별히 두드러진 변화가 없어 추가 제안 사항이 없습니다.")

    lines = ["## 제안"] + [""] + ["- " + s for s in suggestions]
    return "\n".join(lines)


def generate_summary_report(
    start_date,
    end_date,
    kpis: dict,
    period_over_period: dict,
    best_channel: dict,
    top_content_df,
    previous_start=None,
    previous_end=None,
) -> str:
    """자동 요약 리포트 전체를 Markdown 문자열로 만듭니다.

    Parameters
    ----------
    start_date, end_date : 이번 분석 기간
    kpis : kpi.calculate_kpis() 의 결과
    period_over_period : analysis.calculate_period_over_period() 의 결과.
        비교 기간이 없으면 빈 dict({}) 를 넘기면 됩니다.
    best_channel : analysis.summarize_channel_ranking() 의 결과
    top_content_df : analysis.top_n_content() 의 결과 (콘텐츠 TOP N 표)
    previous_start, previous_end : 비교 기간. 없으면 None.

    Returns
    -------
    str
        화면(st.markdown)이나 파일 저장에 그대로 쓸 수 있는 Markdown 텍스트
    """
    mover = _find_biggest_mover(period_over_period) if period_over_period else {}

    sections = [
        "# 마케팅 성과 자동 요약 리포트",
        "",
        _build_period_section(start_date, end_date, previous_start, previous_end),
        "",
        _build_kpi_section(kpis),
        "",
        _build_mover_section(period_over_period),
        "",
        _build_channel_section(best_channel),
        "",
        _build_content_section(top_content_df),
        "",
        _build_action_section(mover, best_channel),
    ]

    return "\n".join(sections) + "\n"
