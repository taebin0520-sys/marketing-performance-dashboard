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

    metric = mover["metric"]
    metric_label = config.get_metric_label(metric)
    # format_delta는 이미 +/- 부호로 방향을 나타내므로("-27.8%"),
    # 뒤에 "증가/감소"를 또 붙이면 "감소했습니다"처럼 방향이 중복 표현됩니다.
    # 그래서 부호 없는 절댓값 퍼센트 + "증가/감소했습니다"로 문장을 만듭니다.
    abs_percent_text = "{:.1f}%".format(abs(mover["percent_change"]) * 100)

    line = (
        "- 이번 기간 가장 크게 변한 지표는 **{}**입니다. "
        "직전 기간 대비 **{} {}**했습니다. (상대 증감률 기준)".format(
            metric_label, abs_percent_text, mover["direction"]
        )
    )

    # 비율 지표(CTR, 전환율 등)는 상대 증감률과 퍼센트포인트가 전혀 다른 값이므로
    # 오해를 막기 위해 실제 수치 변화와 %p를 함께 적어줍니다.
    # 예) "3.22% -> 3.43% (+0.21%p)"
    if config.METRIC_FORMATS.get(metric) == "percent":
        info = period_over_period[metric]
        line += "\n  - 실제 수치: {} → {} ({})".format(
            formatting.format_metric(metric, info["previous"]),
            formatting.format_metric(metric, info["current"]),
            formatting.format_point_delta(info["delta"]),
        )

    return "## 전기 대비 변화\n\n" + line


def _build_channel_section(best_channel: dict) -> str:
    """4) 가장 성과가 좋은 채널 문장."""
    if not best_channel:
        return "## 채널 성과\n\n- 채널 데이터가 없어 순위를 계산하지 않았습니다."

    metric_label = config.get_metric_label(best_channel["metric"])
    value_text = formatting.format_metric(best_channel["metric"], best_channel["value"])

    lines = [
        "## 채널 성과",
        "",
        # '가장 좋다'는 단정 대신 '이 기간 데이터에서 최상위였다'는 관찰로 적습니다.
        # 한 기간의 수치가 채널의 항구적인 우열을 뜻하지는 않기 때문입니다.
        #
        # 문장에서 지표 라벨 뒤에 조사(이/가)를 붙이지 않는 이유:
        # 한국어 조사는 앞 글자의 종성에 따라 달라집니다('전환이' vs '조회수가').
        # 지표 라벨을 그대로 끼워 넣으면 '전환가'처럼 틀린 조사가 나오므로,
        # '{지표} 기준'이라는 형태로 조사를 피했습니다.
        "- 이번 기간 데이터 기준 {} 최상위 채널은 **{}**입니다. ({}: {})".format(
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
    """6) 검토 제안 문장.

    표현 원칙: '관찰 -> 근거 -> 검토 제안' 순서로 쓰고, 단정하지 않습니다.

    왜 단정하지 않는가?
    - 이 리포트는 한 기간의 집계 수치만 보고 만든 것입니다.
      "ROAS가 높으니 예산을 늘려라"는 제안은 '예산을 늘려도 같은 효율이 유지된다'는
      가정을 깔고 있는데, 실제로는 규모를 키우면 효율이 떨어지는 경우가 흔합니다.
    - 반대로 ROAS가 낮다고 바로 "예산을 줄여라"고 하면, 전환 추적이 누락된 것인지
      소재가 문제인지 구분하지 않고 채널을 없애는 잘못된 결정이 될 수 있습니다.
    그래서 결론을 내리는 대신 '무엇을 먼저 확인할지'를 제안합니다.
    """
    suggestions = []

    if mover:
        metric = mover["metric"]
        direction = mover["direction"]

        if metric == "roas" and direction == "증가":
            suggestions.append(
                "ROAS가 상승했습니다. 예산 확대를 검토하기 전에, 규모를 키웠을 때도 "
                "동일한 효율이 유지되는지 소액 증액으로 먼저 확인해보세요."
            )
        elif metric == "roas" and direction == "감소":
            suggestions.append(
                "ROAS가 하락했습니다. 예산 조정을 판단하기 전에 소재 피로도, 타겟팅 범위, "
                "랜딩페이지 이탈, 전환 추적 누락 여부를 우선 점검해보세요."
            )
        elif metric == "conversions" and direction == "감소":
            suggestions.append(
                "전환이 감소했습니다. 유입(노출·클릭)이 함께 줄었는지, 아니면 유입은 유지되는데 "
                "전환율만 떨어졌는지 구분하면 원인 범위를 좁힐 수 있습니다."
            )
        elif metric == "conversions" and direction == "증가":
            suggestions.append(
                "전환이 증가했습니다. 이번 기간의 소재·캠페인·시즌 요인을 기록해두면 "
                "이후 재현 가능성을 검토할 때 근거로 쓸 수 있습니다."
            )

    if best_channel:
        suggestions.append(
            "{} 채널이 이번 기간 전환 성과가 상대적으로 높게 나타났습니다. "
            "다만 단일 기간 수치이므로, 다른 기간에서도 같은 경향이 유지되는지 "
            "함께 확인한 뒤 예산 배분을 검토하는 것이 안전합니다.".format(
                best_channel["channel_label"]
            )
        )

    if not suggestions:
        suggestions.append("이번 기간에는 두드러진 변화가 관찰되지 않았습니다.")

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
