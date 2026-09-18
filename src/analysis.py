"""데이터를 기준별로 묶어서(집계) 분석하는 모듈.

담당하는 분석은 3가지입니다.
1) 기간별 추세  : 일간 / 주간 / 월간
2) 채널별 성과 비교
3) 콘텐츠별 성과 + TOP N

모든 함수는 "DataFrame을 받아서 DataFrame을 돌려준다"는 형태로 통일했습니다.
입출력이 일정하면 테스트하기 쉽고, 다른 함수와 조합하기도 쉽습니다.
"""

import pandas as pd

from src import config, kpi

# 집계할 때 더할 숫자 컬럼들
SUM_COLUMNS = config.ALL_NUMERIC_COLUMNS


def add_period_column(df: pd.DataFrame, period_code: str) -> pd.DataFrame:
    """집계 단위(일간/주간/월간)에 맞는 'period' 컬럼을 추가합니다.

    Parameters
    ----------
    period_code : str
        'D'(일간), 'W'(주간), 'M'(월간)

    Notes
    -----
    주간/월간을 pandas의 resample이나 to_period로 처리할 수도 있지만,
    여기서는 '날짜 빼기'로 직접 계산했습니다. 이유는 두 가지입니다.
    1) to_period('W-MON')은 '월요일에 끝나는 주'를 의미해서
       우리가 원하는 '월요일에 시작하는 주'와 하루씩 어긋납니다. (실수하기 쉬운 부분)
    2) 초보자가 코드를 읽었을 때 무슨 일이 일어나는지 바로 보입니다.
    """
    df = df.copy()
    dates = df[config.DATE_COLUMN]

    if period_code == "D":
        # 일간: 날짜 그대로
        df["period"] = dates

    elif period_code == "W":
        # 주간: 그 주의 월요일로 맞춥니다.
        # dt.weekday는 월=0, 화=1 ... 일=6 이므로, 그만큼 날짜를 빼면 월요일이 됩니다.
        # 예) 수요일(2) - 2일 = 그 주 월요일
        df["period"] = dates - pd.to_timedelta(dates.dt.weekday, unit="D")

    elif period_code == "M":
        # 월간: 그 달의 1일로 맞춥니다. (예: 8월 17일 - 16일 = 8월 1일)
        df["period"] = dates - pd.to_timedelta(dates.dt.day - 1, unit="D")

    else:
        raise ValueError("period_code는 'D', 'W', 'M' 중 하나여야 합니다: {}".format(period_code))

    df["period_label"] = make_period_labels(df["period"], period_code)
    return df


def make_period_labels(periods: pd.Series, period_code: str) -> pd.Series:
    """차트 x축과 표에 표시할 기간 라벨을 만듭니다.

    예) 일간 '2026-08-17' / 주간 '2026-08-17 주' / 월간 '2026-08'
    """
    if period_code == "D":
        return periods.dt.strftime("%Y-%m-%d")
    if period_code == "W":
        # 주간은 시작일(월요일)을 보여주고 '주'를 붙여 오해를 줄입니다.
        return periods.dt.strftime("%Y-%m-%d") + " 주"
    return periods.dt.strftime("%Y-%m")


def aggregate_by_period(df: pd.DataFrame, period_code: str) -> pd.DataFrame:
    """기간(일/주/월) 단위로 지표를 집계합니다. 추세 차트의 재료가 됩니다.

    Returns
    -------
    pd.DataFrame
        period, period_label + 합계 지표 + 비율 지표
    """
    if df.empty:
        return pd.DataFrame()

    df = add_period_column(df, period_code)

    # as_index=False 를 쓰면 group 기준이 인덱스가 아니라 일반 컬럼으로 남습니다.
    # 차트 라이브러리에 바로 넘기기 편해집니다.
    grouped = df.groupby(["period", "period_label"], as_index=False)[SUM_COLUMNS].sum()

    # 시간 순서대로 정렬해야 선 그래프가 뒤엉키지 않습니다.
    grouped = grouped.sort_values("period").reset_index(drop=True)

    # 집계가 끝난 뒤에 비율을 계산합니다. (kpi.py 규칙 1)
    return kpi.add_ratio_columns(grouped)


def aggregate_by_period_and_channel(df: pd.DataFrame, period_code: str) -> pd.DataFrame:
    """기간 × 채널 단위로 집계합니다.

    추세 차트에서 "채널별로 선을 나눠서 보기" 옵션에 사용합니다.
    전체 추세만 보면 어떤 채널이 떨어졌는지 알 수 없어서 이 집계가 필요합니다.
    """
    if df.empty:
        return pd.DataFrame()

    df = add_period_column(df, period_code)

    grouped = df.groupby(
        ["period", "period_label", "channel_label"], as_index=False
    )[SUM_COLUMNS].sum()
    grouped = grouped.sort_values(["period", "channel_label"]).reset_index(drop=True)

    return kpi.add_ratio_columns(grouped)


def aggregate_by_channel(df: pd.DataFrame) -> pd.DataFrame:
    """채널별로 지표를 집계합니다.

    Returns
    -------
    pd.DataFrame
        전환(conversions) 많은 순으로 정렬된 채널별 성과표
    """
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby(["channel", "channel_label"], as_index=False)[SUM_COLUMNS].sum()
    grouped = kpi.add_ratio_columns(grouped)

    return grouped.sort_values("conversions", ascending=False).reset_index(drop=True)


def aggregate_by_content(df: pd.DataFrame) -> pd.DataFrame:
    """콘텐츠별로 지표를 집계합니다.

    같은 콘텐츠가 여러 날에 걸쳐 여러 행으로 나뉘어 있으므로
    content_id 기준으로 합쳐서 "콘텐츠 1개 = 1행"으로 만듭니다.
    """
    if df.empty:
        return pd.DataFrame()

    group_keys = [
        "content_id",
        "content_title",
        "channel_label",
        "content_type_label",
    ]
    grouped = df.groupby(group_keys, as_index=False)[SUM_COLUMNS].sum()

    # 차트 y축에 쓸 표시용 이름을 만듭니다. 제목 뒤에 콘텐츠 ID를 붙입니다.
    # 왜 필요한가: 서로 다른 콘텐츠가 우연히 같은 제목을 쓰는 경우가 실제로 있습니다.
    # 제목만으로 차트를 그리면 다른 콘텐츠가 하나의 막대로 합쳐져 잘못 보입니다.
    grouped["content_label"] = (
        grouped["content_title"] + " (" + grouped["content_id"] + ")"
    )

    return kpi.add_ratio_columns(grouped)


def top_n_content(
    content_df: pd.DataFrame,
    metric: str = "conversions",
    n: int = 5,
    min_impressions: int = 0,
    ascending: bool = False,
) -> pd.DataFrame:
    """콘텐츠 성과 상위 N개를 뽑습니다.

    Parameters
    ----------
    content_df : pd.DataFrame
        aggregate_by_content()의 결과
    metric : str
        정렬 기준 지표 (예: 'conversions', 'ctr')
    n : int
        뽑을 개수
    min_impressions : int
        최소 노출 기준. CTR처럼 비율 지표로 정렬할 때 꼭 필요합니다.
        노출 10회에 클릭 2회면 CTR 20%로 1위가 되지만 의미 없는 수치이므로
        일정 노출 이상인 콘텐츠만 남겨 왜곡을 막습니다.
    ascending : bool
        False면 높은 순(성과 TOP), True면 낮은 순(개선 대상 확인용)
    """
    if content_df.empty or metric not in content_df.columns:
        return pd.DataFrame()

    filtered = content_df
    if min_impressions > 0:
        filtered = filtered[filtered["impressions"] >= min_impressions]

    # na_position="last": 비율이 계산 불가(NaN)인 콘텐츠를 항상 뒤로 보냅니다.
    ranked = filtered.sort_values(metric, ascending=ascending, na_position="last")

    return ranked.head(n).reset_index(drop=True)


def summarize_channel_ranking(channel_df: pd.DataFrame, metric: str = "conversions") -> dict:
    """가장 성과가 좋은 채널 1개를 찾아 요약 정보를 돌려줍니다.

    화면 상단에 "이번 기간 1등 채널"을 한 줄로 보여주는 데 사용합니다.
    """
    if channel_df.empty or metric not in channel_df.columns:
        return {}

    best = channel_df.sort_values(metric, ascending=False, na_position="last").iloc[0]

    return {
        "channel_label": best["channel_label"],
        "metric": metric,
        "value": best[metric],
        "conversion_rate": best.get("conversion_rate"),
        "ctr": best.get("ctr"),
    }
