"""마케팅 성과 분석 대시보드 - Streamlit 화면.

실행:
    streamlit run app.py

이 파일의 역할은 '화면 구성'뿐입니다.
계산은 모두 src/ 폴더의 함수를 불러서 처리합니다.

왜 이렇게 나눴나요?
- 계산 코드가 화면 코드에 섞이면 테스트를 할 수 없습니다.
  (테스트 코드에서 streamlit 화면을 띄울 수는 없으니까요)
- 나중에 이 프로젝트를 웹이 아닌 배치 스크립트로 바꿀 때도 src/를 그대로 재사용할 수 있습니다.
"""

import io
from datetime import timedelta

import pandas as pd
import streamlit as st

from src import analysis, charts, config, data_loader, formatting, kpi, report
from src.data_loader import DataValidationError

# ---------------------------------------------------------------------------
# 페이지 기본 설정 (반드시 다른 st.* 호출보다 먼저 와야 합니다)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="마케팅 성과 분석 대시보드",
    page_icon="📊",
    layout="wide",
)


# ---------------------------------------------------------------------------
# 데이터 로딩 (캐시 사용)
# ---------------------------------------------------------------------------
# @st.cache_data 를 붙이면 같은 입력에 대해 계산 결과를 기억해둡니다.
# 필터를 바꿀 때마다 CSV를 다시 읽지 않아서 화면이 훨씬 빠릿해집니다.
@st.cache_data
def load_sample_data():
    """저장소에 포함된 샘플 데이터를 불러옵니다."""
    return data_loader.load_and_prepare(None)


@st.cache_data
def load_uploaded_data(file_content: bytes):
    """업로드된 파일(bytes)을 불러옵니다.

    파일 객체가 아니라 bytes를 인자로 받는 이유:
    캐시는 '입력값이 같은지'를 비교해서 동작하는데, 파일 객체는 비교가 어렵습니다.
    bytes로 바꿔서 넘기면 같은 파일을 다시 올렸을 때 캐시가 제대로 동작합니다.
    """
    return data_loader.load_and_prepare(io.BytesIO(file_content))


def format_table(df: pd.DataFrame, base_columns: list, metric_columns: list) -> pd.DataFrame:
    """표를 '한국어 컬럼명 + 읽기 쉬운 숫자'로 바꿉니다.

    Parameters
    ----------
    base_columns : list of (컬럼명, 표시이름)
        콘텐츠 제목, 채널처럼 그대로 보여줄 컬럼
    metric_columns : list of str
        숫자 형식을 적용할 지표 컬럼
    """
    display = pd.DataFrame(index=df.index)

    for column, label in base_columns:
        if column in df.columns:
            display[label] = df[column]

    for metric in metric_columns:
        if metric in df.columns:
            display[config.get_metric_label(metric)] = df[metric].map(
                lambda value, m=metric: formatting.format_metric(m, value)
            )

    return display


# ---------------------------------------------------------------------------
# 1. 사이드바 - 데이터 업로드
# ---------------------------------------------------------------------------
st.sidebar.header("1. 데이터")

uploaded_file = st.sidebar.file_uploader(
    "마케팅 성과 CSV 업로드",
    type=["csv"],
    help="업로드하지 않으면 샘플 데이터로 대시보드를 체험할 수 있습니다.",
)

# 데이터를 불러옵니다. 실패하면 화면에 원인을 보여주고 여기서 멈춥니다.
try:
    if uploaded_file is None:
        df, load_info = load_sample_data()
    else:
        df, load_info = load_uploaded_data(uploaded_file.getvalue())
except DataValidationError as error:
    st.error("데이터를 불러오지 못했습니다.\n\n{}".format(error))
    st.info("아래 형식에 맞춰 CSV를 준비해주세요.")
    st.code(",".join(config.REQUIRED_COLUMNS), language="text")
    st.stop()
except FileNotFoundError:
    st.error(
        "샘플 데이터 파일이 없습니다.\n\n"
        "터미널에서 아래 명령으로 샘플 데이터를 먼저 만들어주세요.\n"
        "python scripts/generate_sample_data.py"
    )
    st.stop()

if load_info["is_sample"]:
    st.sidebar.info("샘플 데이터를 사용 중입니다. (가상 데이터)")
else:
    st.sidebar.success("업로드한 데이터를 사용 중입니다.")

# ---------------------------------------------------------------------------
# 2. 사이드바 - 필터
# ---------------------------------------------------------------------------
st.sidebar.header("2. 분석 조건")

min_date = df[config.DATE_COLUMN].min().date()
max_date = df[config.DATE_COLUMN].max().date()

# 기본값은 '가장 최근 4주'로 둡니다.
# 전체 기간을 기본값으로 하면 첫 화면이 너무 뭉뚱그려져 보이기 때문입니다.
default_start = max(min_date, max_date - timedelta(days=27))

selected_range = st.sidebar.date_input(
    "분석 기간",
    value=(default_start, max_date),
    min_value=min_date,
    max_value=max_date,
)

# date_input은 날짜를 하나만 고른 순간에는 값 1개만 돌려줍니다.
# 이 경우를 처리하지 않으면 "tuple index out of range" 에러가 납니다.
if isinstance(selected_range, (list, tuple)):
    if len(selected_range) < 2:
        st.warning("종료일을 선택해주세요.")
        st.stop()
    start_date, end_date = selected_range[0], selected_range[1]
else:
    start_date, end_date = selected_range, selected_range

# 채널 필터 (화면에는 한국어, 내부적으로는 영문 코드를 사용)
channel_codes = sorted(df["channel"].unique().tolist())
selected_channels = st.sidebar.multiselect(
    "채널",
    options=channel_codes,
    default=channel_codes,
    format_func=config.get_channel_label,
)

# 콘텐츠 유형 필터
content_type_codes = sorted(df["content_type"].unique().tolist())
selected_content_types = st.sidebar.multiselect(
    "콘텐츠 유형",
    options=content_type_codes,
    default=content_type_codes,
    format_func=config.get_content_type_label,
)

# 집계 단위
period_name = st.sidebar.radio(
    "집계 단위",
    options=list(config.PERIOD_OPTIONS.keys()),
    index=1,  # 기본값: 주간
    horizontal=True,
    help="주간은 {} 기준입니다.".format(config.WEEK_START_LABEL),
)
period_code = config.PERIOD_OPTIONS[period_name]

# ---------------------------------------------------------------------------
# 3. 필터 적용
# ---------------------------------------------------------------------------
filtered_df = data_loader.filter_data(
    df,
    start_date=start_date,
    end_date=end_date,
    channels=selected_channels,
    content_types=selected_content_types,
)

st.title("📊 마케팅 성과 분석 대시보드")
st.caption(
    "분석 기간 {} ~ {}  |  집계 단위 {}  |  대상 {}행".format(
        start_date, end_date, period_name, formatting.format_int(len(filtered_df))
    )
)

# 필터를 전부 해제한 경우를 먼저 구분해 안내합니다.
# 이 경우를 '전체 선택'으로 처리하면, 아무것도 선택하지 않았는데 전체 KPI가
# 표시되어 사용자가 잘못된 숫자를 읽게 됩니다. (data_loader.filter_data 주석 참고)
if not selected_channels or not selected_content_types:
    empty_filters = []
    if not selected_channels:
        empty_filters.append("채널")
    if not selected_content_types:
        empty_filters.append("콘텐츠 유형")

    st.warning(
        "{} 필터에서 선택된 항목이 없습니다. 최소 1개를 선택해주세요. "
        "선택된 항목이 없으면 집계할 데이터가 없으므로 KPI를 표시하지 않습니다.".format(
            " / ".join(empty_filters)
        )
    )
    st.stop()

if filtered_df.empty:
    st.warning(
        "선택한 조건에 해당하는 데이터가 없습니다. 기간이나 채널 필터를 다시 확인해주세요."
    )
    st.stop()

# ---------------------------------------------------------------------------
# 3-1. 직전 동일 기간 데이터 준비 (전기 대비 증감용)
# ---------------------------------------------------------------------------
# 선택한 기간과 같은 길이의 바로 이전 기간을 자동으로 계산합니다.
# 예) 7일을 선택했다면 바로 이전 7일과 비교합니다.
previous_start, previous_end = analysis.get_previous_period(start_date, end_date)

# 비교 기간은 채널/콘텐츠 유형 필터는 동일하게 적용하되, 원본 df 전체에서 찾습니다.
# (filtered_df 는 이미 현재 기간으로 좁혀져 있어서 그 안에는 이전 기간 데이터가 없습니다)
previous_df = data_loader.filter_data(
    df,
    start_date=previous_start,
    end_date=previous_end,
    channels=selected_channels,
    content_types=selected_content_types,
)

# 직전 기간을 비교에 쓸 수 있는지는 '판정 규칙'이므로 src/ 에서 처리합니다.
# (화면 없이 테스트할 수 있어야 하는 로직입니다)
has_previous_period = analysis.has_comparable_previous_period(
    previous_df, previous_start, min_date
)

# ---------------------------------------------------------------------------
# 4. 데이터 검증 결과 안내
# ---------------------------------------------------------------------------
with st.expander("데이터 검증 결과 보기", expanded=False):
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("불러온 행", formatting.format_int(load_info["rows_before"]))
    col_b.metric("분석 가능한 행", formatting.format_int(load_info["rows_after"]))
    col_c.metric("제외된 행(날짜 오류)", formatting.format_int(load_info["invalid_date_rows"]))

    messages = []
    if load_info["missing_numeric_cells"]:
        messages.append(
            "비어 있던 숫자 칸 {}개를 0으로 채웠습니다.".format(
                formatting.format_int(load_info["missing_numeric_cells"])
            )
        )
    # 빈칸과 '읽을 수 없는 값'은 원인이 다르므로 따로 알려줍니다.
    # 이 숫자가 크면 숫자 형식이 잘못 읽힌 것이므로 원본 파일을 확인해야 합니다.
    if load_info.get("invalid_numeric_cells"):
        messages.append(
            "숫자로 읽을 수 없는 값 {}개를 0으로 처리했습니다. "
            "원본 파일의 숫자 형식(문자 섞임 등)을 확인해주세요.".format(
                formatting.format_int(load_info["invalid_numeric_cells"])
            )
        )
    if load_info["negative_value_cells"]:
        messages.append(
            "음수였던 값 {}개를 0으로 보정했습니다.".format(
                formatting.format_int(load_info["negative_value_cells"])
            )
        )
    if load_info["funnel_violation_rows"]:
        messages.append(
            "퍼널 순서(노출 ≥ 도달 ≥ 조회수 ≥ 클릭 ≥ 문의 ≥ 전환)가 어긋난 행이 "
            "{}개 있습니다. 계산은 그대로 진행했습니다.".format(
                formatting.format_int(load_info["funnel_violation_rows"])
            )
        )
    if not load_info["has_cost"]:
        messages.append("cost(광고비) 컬럼이 없어 CPC/CPA/ROAS는 계산하지 않습니다.")
    if not load_info["has_revenue"]:
        messages.append("revenue(매출) 컬럼이 없어 ROAS는 계산하지 않습니다.")

    if messages:
        for message in messages:
            st.write("- " + message)
    else:
        st.write("- 특별히 보정한 내용이 없습니다. 데이터 상태가 양호합니다.")

# ---------------------------------------------------------------------------
# 5. KPI 요약 카드 (+ 전기 대비 증감)
# ---------------------------------------------------------------------------
kpis = kpi.calculate_kpis(filtered_df)

# 비교 기간 데이터가 있을 때만 증감을 계산합니다.
period_over_period = {}
if has_previous_period:
    previous_kpis = kpi.calculate_kpis(previous_df)
    period_over_period = analysis.calculate_period_over_period(kpis, previous_kpis)

st.subheader("핵심 지표 요약")

if has_previous_period:
    st.caption(
        "직전 기간({} ~ {}) 대비 증감을 함께 표시합니다.".format(
            previous_start.date(), previous_end.date()
        )
    )
else:
    st.caption("비교할 직전 기간 데이터가 없어 증감은 표시하지 않습니다.")


def render_metric_card(column, metric):
    """KPI 카드 1개를 그립니다. 증감 정보가 있으면 delta도 함께 표시합니다."""
    delta_text = None
    if metric in period_over_period:
        info = period_over_period[metric]
        delta_text = formatting.format_delta(info["percent_change"], info["is_new"])

    column.metric(
        config.get_metric_label(metric),
        formatting.format_metric(metric, kpis[metric]),
        delta=delta_text,
        # CPA/CPC 같은 비용 지표는 '감소'가 개선이므로 색 방향을 뒤집습니다.
        # 숫자(delta_text)는 그대로 음수로 두고 색만 바꿉니다.
        delta_color=config.get_delta_color(metric),
    )


# 5-1. 규모 지표 (합계)
volume_columns = st.columns(len(config.KPI_CARD_METRICS))
for column, metric in zip(volume_columns, config.KPI_CARD_METRICS):
    render_metric_card(column, metric)

# 5-2. 효율 지표 (비율)
st.write("")  # 카드 사이 여백
efficiency_columns = st.columns(len(config.EFFICIENCY_CARD_METRICS))
for column, metric in zip(efficiency_columns, config.EFFICIENCY_CARD_METRICS):
    render_metric_card(column, metric)

st.caption(
    "비율 지표는 행별 비율의 평균이 아니라 '합계 ÷ 합계'로 계산했습니다. "
    "노출이 적은 행의 극단값 때문에 전체 지표가 왜곡되는 것을 막기 위한 방식입니다."
)
st.caption(
    "카드의 증감값은 **상대 증감률(%)** 입니다. 퍼센트포인트(%p)가 아닙니다. "
    "예) CTR 3.23% → 3.43% 는 약 상대 +6.2% (화면의 반올림 값 기준, 실제 카드는 반올림 전 값으로 계산해 +6.3%) 이며, 퍼센트포인트로는 +0.20%p 입니다. "
    "CPA·CPC는 값이 낮아지는 것이 개선이므로 감소를 초록색으로 표시합니다."
)

# ---------------------------------------------------------------------------
# 5-3. 탭에서 공통으로 쓰는 집계 (탭 블록 밖에서 미리 계산)
# ---------------------------------------------------------------------------
# 채널 집계는 '채널 비교' 탭과 '요약 리포트' 탭에서 함께 씁니다.
# 탭 블록 안에서 계산하면 리포트 탭이 "채널 탭이 먼저 실행된다"는 사실에
# 의존하게 되어, 탭 순서를 바꾸거나 채널 탭에 중단 코드가 생기면 NameError가 납니다.
# 그래서 탭을 만들기 전에 미리 계산해 둡니다.
channel_df = analysis.aggregate_by_channel(filtered_df)

# 리포트는 항상 '전환' 기준 1위 채널을 씁니다.
# (채널 탭의 비교 지표는 사용자가 바꿀 수 있어서 리포트 기준과 달라질 수 있습니다)
best_channel_for_report = analysis.summarize_channel_ranking(channel_df, "conversions")

# ---------------------------------------------------------------------------
# 6. 탭 구성
# ---------------------------------------------------------------------------
tab_trend, tab_channel, tab_content, tab_report, tab_raw = st.tabs(
    ["📈 추세", "📣 채널 비교", "🏆 콘텐츠 TOP", "📝 요약 리포트", "🗂 원본 데이터"]
)

# ---------------------------- 6-1. 추세 탭 ----------------------------
with tab_trend:
    st.subheader("{} 성과 추세".format(period_name))

    left, right = st.columns([2, 1])
    trend_metric = left.selectbox(
        "지표 선택",
        options=config.TREND_METRIC_OPTIONS,
        index=config.TREND_METRIC_OPTIONS.index("conversions"),
        format_func=config.get_metric_label,
        key="trend_metric",
    )
    split_by_channel = right.checkbox("채널별로 나누어 보기", value=False)

    # 기간별 집계는 차트와 표에서 함께 쓰므로 한 번만 계산합니다.
    trend_df = analysis.aggregate_by_period(filtered_df, period_code)

    if split_by_channel:
        channel_trend_df = analysis.aggregate_by_period_and_channel(filtered_df, period_code)
        figure = charts.trend_by_channel_chart(channel_trend_df, trend_metric, period_name)
    else:
        figure = charts.trend_line_chart(trend_df, trend_metric, period_name)

    st.plotly_chart(figure, use_container_width=True)

    if period_name == "주간":
        st.caption("주간 집계는 {} 기준입니다. (x축 날짜 = 해당 주의 월요일)".format(config.WEEK_START_LABEL))

    # 그래프만 있으면 정확한 숫자를 알 수 없으므로 표도 함께 보여줍니다.
    st.dataframe(
        format_table(
            trend_df,
            base_columns=[("period_label", "기간")],
            metric_columns=["impressions", "views", "clicks", "inquiries", "conversions", "ctr", "conversion_rate"],
        ),
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------- 6-2. 채널 탭 ----------------------------
with tab_channel:
    st.subheader("채널별 성과 비교")

    channel_metric = st.selectbox(
        "비교 지표",
        options=["conversions", "inquiries", "clicks", "views", "impressions", "ctr", "conversion_rate", "roas"],
        index=0,
        format_func=config.get_metric_label,
        key="channel_metric",
    )

    st.plotly_chart(
        charts.channel_bar_chart(channel_df, channel_metric),
        use_container_width=True,
    )

    best_channel = analysis.summarize_channel_ranking(channel_df, channel_metric)
    if best_channel:
        st.success(
            "이번 기간 {} 1위 채널은 **{}** 입니다. ({} {})".format(
                config.get_metric_label(channel_metric),
                best_channel["channel_label"],
                config.get_metric_label(channel_metric),
                formatting.format_metric(channel_metric, best_channel["value"]),
            )
        )

    st.dataframe(
        format_table(
            channel_df,
            base_columns=[("channel_label", "채널")],
            metric_columns=[
                "impressions", "reach", "views", "clicks", "inquiries", "conversions",
                "ctr", "inquiry_rate", "conversion_rate", "cost", "cpa", "roas",
            ],
        ),
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------- 6-3. 콘텐츠 탭 ----------------------------
with tab_content:
    st.subheader("콘텐츠 성과 TOP")

    content_df = analysis.aggregate_by_content(filtered_df)

    col1, col2, col3 = st.columns(3)
    content_metric = col1.selectbox(
        "정렬 기준",
        options=config.CONTENT_SORT_OPTIONS,
        index=0,
        format_func=config.get_metric_label,
        key="content_metric",
    )
    top_n = col2.selectbox("표시 개수", options=[5, 10, 20], index=0)

    # 비율 지표로 정렬할 때는 최소 노출 기준이 필요합니다.
    # 노출 10회에 클릭 2회인 콘텐츠가 CTR 20%로 1위가 되는 것을 막습니다.
    is_ratio_metric = config.METRIC_FORMATS.get(content_metric) == "percent"
    min_impressions = 0
    if is_ratio_metric:
        min_impressions = col3.number_input(
            "최소 노출 수",
            min_value=0,
            value=1000,
            step=500,
            help="비율 지표는 노출이 적을 때 크게 왜곡되므로 기준선을 둡니다.",
        )

    top_content_df = analysis.top_n_content(
        content_df,
        metric=content_metric,
        n=int(top_n),
        min_impressions=int(min_impressions),
    )

    if top_content_df.empty:
        st.warning("조건에 맞는 콘텐츠가 없습니다. 최소 노출 수를 낮춰보세요.")
    else:
        st.plotly_chart(
            charts.content_bar_chart(
                top_content_df,
                content_metric,
                title="{} 기준 TOP {}".format(config.get_metric_label(content_metric), top_n),
            ),
            use_container_width=True,
        )

        st.dataframe(
            format_table(
                top_content_df,
                base_columns=[
                    ("content_id", "콘텐츠 ID"),
                    ("content_title", "콘텐츠"),
                    ("channel_label", "채널"),
                    ("content_type_label", "유형"),
                ],
                metric_columns=[
                    "impressions", "views", "clicks", "inquiries", "conversions",
                    "ctr", "conversion_rate",
                ],
            ),
            use_container_width=True,
            hide_index=True,
        )

# ---------------------------- 6-4. 요약 리포트 탭 ----------------------------
with tab_report:
    st.subheader("자동 요약 리포트")
    st.caption(
        "이미 계산된 KPI·증감·채널·콘텐츠 결과를 규칙(if/else)으로 문장에 끼워 넣습니다. "
        "생성형 AI를 사용하지 않으므로 같은 데이터라면 항상 같은 문장이 나옵니다."
    )

    # 리포트는 '전환' 기준으로 통일합니다. (탭마다 사용자가 고른 지표가 달라 기준이 흔들리면
    # 리포트를 볼 때마다 다른 결론처럼 보일 수 있기 때문입니다)
    report_top_content_df = analysis.top_n_content(
        analysis.aggregate_by_content(filtered_df), metric="conversions", n=3
    )

    report_text = report.generate_summary_report(
        start_date=start_date,
        end_date=end_date,
        kpis=kpis,
        period_over_period=period_over_period,
        best_channel=best_channel_for_report,
        top_content_df=report_top_content_df,
        previous_start=previous_start.date() if has_previous_period else None,
        previous_end=previous_end.date() if has_previous_period else None,
    )

    st.markdown(report_text)

    st.divider()
    st.download_button(
        label="⬇️ 요약 리포트 다운로드 (.md)",
        data=report_text.encode("utf-8-sig"),  # 한글이 깨지지 않도록 BOM 포함 인코딩
        file_name=formatting.build_filename("summary_report", start_date, end_date, "md"),
        mime="text/markdown",
    )

# ---------------------------- 6-5. 원본 데이터 탭 ----------------------------
with tab_raw:
    st.subheader("필터가 적용된 원본 데이터")
    st.caption("총 {}행".format(formatting.format_int(len(filtered_df))))

    preview_columns = (
        [config.DATE_COLUMN, "channel_label", "content_id", "content_title", "content_type_label"]
        + config.ALL_NUMERIC_COLUMNS
    )
    st.dataframe(
        filtered_df[preview_columns].head(500),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("화면에는 최대 500행만 표시합니다. (다운로드에는 전체 행이 포함됩니다)")

    st.divider()
    st.subheader("결과 다운로드")

    download_col1, download_col2, download_col3 = st.columns(3)

    # (1) 필터 적용된 원본 데이터 전체 (화면 표시는 500행이지만 다운로드는 전체)
    raw_csv = filtered_df[preview_columns].to_csv(index=False)
    download_col1.download_button(
        label="⬇️ 원본 데이터 (.csv)",
        # utf-8-sig 로 인코딩해야 엑셀에서 열었을 때 한글이 깨지지 않습니다.
        data=raw_csv.encode("utf-8-sig"),
        file_name=formatting.build_filename("raw_data", start_date, end_date, "csv"),
        mime="text/csv",
    )

    # (2) 채널별 집계표
    channel_export_df = format_table(
        analysis.aggregate_by_channel(filtered_df),
        base_columns=[("channel_label", "채널")],
        metric_columns=[
            "impressions", "reach", "views", "clicks", "inquiries", "conversions",
            "ctr", "inquiry_rate", "conversion_rate", "cost", "cpa", "roas",
        ],
    )
    download_col2.download_button(
        label="⬇️ 채널별 집계표 (.csv)",
        data=channel_export_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=formatting.build_filename("channel_summary", start_date, end_date, "csv"),
        mime="text/csv",
    )

    # (3) 콘텐츠별 집계표
    content_export_df = format_table(
        analysis.aggregate_by_content(filtered_df),
        base_columns=[
            ("content_id", "콘텐츠 ID"),
            ("content_title", "콘텐츠"),
            ("channel_label", "채널"),
            ("content_type_label", "유형"),
        ],
        metric_columns=[
            "impressions", "views", "clicks", "inquiries", "conversions",
            "ctr", "conversion_rate",
        ],
    )
    download_col3.download_button(
        label="⬇️ 콘텐츠별 집계표 (.csv)",
        data=content_export_df.to_csv(index=False).encode("utf-8-sig"),
        file_name=formatting.build_filename("content_summary", start_date, end_date, "csv"),
        mime="text/csv",
    )
