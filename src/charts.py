"""Plotly 차트를 만드는 모듈.

차트를 만드는 코드는 설정값이 많아서 app.py에 그대로 두면 화면 코드가 금방 지저분해집니다.
그래서 "데이터를 받아 그림(Figure) 객체를 돌려주는 함수"만 이 파일에 모았습니다.

주의: 이 파일도 streamlit을 import하지 않습니다.
      화면에 그리는 일(st.plotly_chart)은 app.py가 담당합니다.
"""

import plotly.express as px

from src import config

# 차트에 공통으로 적용할 색상 팔레트
COLOR_SEQUENCE = px.colors.qualitative.Set2


def _apply_common_layout(fig, metric: str):
    """모든 차트에 공통으로 적용하는 레이아웃 설정.

    비율 지표(CTR, 전환율)는 y축을 퍼센트(%)로 바꿔야 읽기 쉽습니다.
    0.0336 처럼 소수로 표시되면 해석에 시간이 걸립니다.
    """
    if config.METRIC_FORMATS.get(metric) == "percent":
        fig.update_yaxes(tickformat=".2%")
    elif config.METRIC_FORMATS.get(metric) in ("int", "won"):
        fig.update_yaxes(tickformat=",")

    fig.update_layout(
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        legend_title_text="",
    )
    return fig


def trend_line_chart(trend_df, metric: str, period_label: str = "기간"):
    """기간별 추세를 선 그래프로 그립니다.

    Parameters
    ----------
    trend_df : pd.DataFrame
        analysis.aggregate_by_period()의 결과
    metric : str
        그릴 지표 (예: 'conversions')
    period_label : str
        '일간' / '주간' / '월간' — 차트 제목에 사용
    """
    metric_label = config.get_metric_label(metric)

    fig = px.line(
        trend_df,
        x="period",           # 날짜형 x축을 쓰면 간격이 실제 시간 간격대로 그려집니다.
        y=metric,
        markers=True,         # 점을 찍어야 데이터가 있는 시점을 알 수 있습니다.
        title="{} {} 추세".format(period_label, metric_label),
        labels={"period": "기간", metric: metric_label},
        hover_data={"period_label": True, "period": False},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    return _apply_common_layout(fig, metric)


def trend_by_channel_chart(trend_df, metric: str, period_label: str = "기간"):
    """기간별 추세를 채널별로 나눠 그립니다.

    trend_df는 analysis.aggregate_by_period_and_channel()의 결과여야 합니다.
    """
    metric_label = config.get_metric_label(metric)

    fig = px.line(
        trend_df,
        x="period",
        y=metric,
        color="channel_label",   # 채널마다 다른 색 선으로 나눕니다.
        markers=True,
        title="{} 채널별 {} 추세".format(period_label, metric_label),
        labels={"period": "기간", metric: metric_label, "channel_label": "채널"},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    return _apply_common_layout(fig, metric)


def channel_bar_chart(channel_df, metric: str):
    """채널별 성과를 막대 그래프로 비교합니다.

    막대는 값이 큰 순서로 정렬합니다.
    정렬하지 않으면 채널 이름 순으로 그려져서 비교가 어렵습니다.
    """
    metric_label = config.get_metric_label(metric)

    plot_df = channel_df.sort_values(metric, ascending=False, na_position="last")

    fig = px.bar(
        plot_df,
        x="channel_label",
        y=metric,
        color="channel_label",
        title="채널별 {} 비교".format(metric_label),
        labels={"channel_label": "채널", metric: metric_label},
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    # 막대 위에 값을 직접 표시하면 축을 눈으로 따라가지 않아도 됩니다.
    if config.METRIC_FORMATS.get(metric) == "percent":
        fig.update_traces(texttemplate="%{y:.2%}", textposition="outside")
    else:
        fig.update_traces(texttemplate="%{y:,.0f}", textposition="outside")

    fig.update_layout(showlegend=False)
    return _apply_common_layout(fig, metric)


def content_bar_chart(content_df, metric: str, title: str = "콘텐츠 성과 TOP"):
    """콘텐츠 TOP N을 가로 막대로 그립니다.

    콘텐츠 제목은 길어서 세로 막대에 넣으면 글자가 겹칩니다.
    그래서 orientation='h'(가로 막대)를 사용합니다.

    y축에 content_title 이 아니라 content_label(제목 + ID)을 쓰는 이유는
    제목이 같은 다른 콘텐츠가 한 막대로 합쳐지는 것을 막기 위해서입니다.
    """
    metric_label = config.get_metric_label(metric)

    # 가로 막대는 아래에서 위로 그려지므로, 1위를 맨 위에 두려면 거꾸로 정렬합니다.
    plot_df = content_df.sort_values(metric, ascending=True, na_position="first")

    fig = px.bar(
        plot_df,
        x=metric,
        y="content_label",
        orientation="h",
        title=title,
        labels={"content_label": "콘텐츠", metric: metric_label},
        hover_data=["channel_label", "content_type_label"],
        color_discrete_sequence=COLOR_SEQUENCE,
    )

    if config.METRIC_FORMATS.get(metric) == "percent":
        fig.update_xaxes(tickformat=".2%")
    else:
        fig.update_xaxes(tickformat=",")

    fig.update_layout(
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False,
        yaxis_title="",
    )
    return fig
