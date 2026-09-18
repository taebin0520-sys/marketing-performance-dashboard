"""KPI(핵심 성과 지표)를 계산하는 모듈.

이 프로젝트에서 가장 중요한 규칙이 여기에 들어 있습니다.

[규칙 1] 비율 지표는 '합계를 먼저 구한 뒤 나눈다'
    잘못된 방법: 행마다 CTR을 구한 뒤 그 CTR들의 평균을 낸다
    올바른 방법: 클릭 총합 / 노출 총합

    왜 중요한가?
    노출 10회에 클릭 1회(CTR 10%)인 행과
    노출 10,000회에 클릭 100회(CTR 1%)인 행이 있을 때
    - 행별 평균: (10% + 1%) / 2 = 5.5%  <- 규모가 무시되어 과대평가
    - 합계 기준: 101 / 10,010 = 1.01%   <- 실제 성과
    작은 노출의 극단값이 전체 지표를 왜곡하기 때문에 합계 기준을 사용합니다.

[규칙 2] 0으로 나누는 상황에서 앱이 죽지 않게 한다
    광고비가 0원인 오가닉 채널, 클릭이 0인 날은 실제로 자주 있습니다.
    이때 None을 반환하고 화면에는 '-'로 표시합니다.
"""

import numpy as np
import pandas as pd

from src import config


def safe_divide(numerator, denominator):
    """0으로 나누기와 결측값을 안전하게 처리하는 나눗셈.

    Parameters
    ----------
    numerator : int | float
        분자
    denominator : int | float
        분모

    Returns
    -------
    float | None
        계산이 불가능하면 None (화면에서는 '-'로 표시)

    Examples
    --------
    >>> safe_divide(50, 200)
    0.25
    >>> safe_divide(50, 0) is None
    True
    """
    # None, NaN, 0 은 모두 "나눌 수 없는 분모"로 봅니다.
    if denominator is None or numerator is None:
        return None
    if pd.isna(denominator) or pd.isna(numerator):
        return None
    if float(denominator) == 0.0:
        return None

    return float(numerator) / float(denominator)


def safe_ratio_series(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Series(열) 단위로 비율을 계산합니다. (표/차트용)

    pandas에서 숫자를 0으로 나누면 에러가 아니라 inf(무한대)가 나옵니다.
    inf가 표에 그대로 찍히면 사용자가 혼란스러우므로 NaN(빈 값)으로 바꿉니다.
    """
    ratio = numerator / denominator
    return ratio.replace([np.inf, -np.inf], np.nan)


def _cost_metric(cost, denominator):
    """비용 지표(CPC, CPA)를 계산합니다.

    일반 나눗셈과 다른 점: 광고비(cost)가 0이면 결과를 None으로 봅니다.
    광고비가 0원인 오가닉 채널(네이버 블로그 등)에서 '클릭당/전환당 비용'은
    0원이 아니라 "해당 없음"이 맞기 때문입니다. 0원으로 표시하면
    "비용 없이 성과를 얻었다"는 잘못된 해석을 유도할 수 있습니다.
    """
    if cost is None or pd.isna(cost) or float(cost) == 0.0:
        return None
    return safe_divide(cost, denominator)


def sum_metrics(df: pd.DataFrame) -> dict:
    """합계로 구하는 지표(노출, 클릭, 전환 등)를 더합니다.

    Returns
    -------
    dict
        {'impressions': 41880305, 'clicks': 1406758, ...}
    """
    totals = {}

    for column in config.ALL_NUMERIC_COLUMNS:
        if column in df.columns:
            totals[column] = float(df[column].sum())
        else:
            totals[column] = 0.0

    return totals


def calculate_ratios(totals: dict) -> dict:
    """합계 지표로부터 비율 지표를 계산합니다.

    반드시 '합계 → 나눗셈' 순서입니다. (모듈 상단의 규칙 1 참고)
    """
    return {
        # CTR: 노출된 것 중 몇 %가 클릭되었나
        "ctr": safe_divide(totals["clicks"], totals["impressions"]),
        # 문의율: 클릭한 사람 중 몇 %가 문의까지 했나
        "inquiry_rate": safe_divide(totals["inquiries"], totals["clicks"]),
        # 전환율: 클릭한 사람 중 몇 %가 최종 전환했나
        "conversion_rate": safe_divide(totals["conversions"], totals["clicks"]),
        # 문의→전환율: 문의한 사람 중 몇 %가 구매까지 갔나 (영업 단계 효율)
        "inquiry_to_conversion_rate": safe_divide(totals["conversions"], totals["inquiries"]),
        # CPC: 클릭 1회를 얻는 데 든 비용
        # 광고비가 0원(오가닉 채널)이면 '클릭당 비용'이라는 개념 자체가 없으므로 None.
        # (0원으로 표시하면 "공짜로 클릭을 얻었다"는 잘못된 인상을 줍니다)
        "cpc": _cost_metric(totals["cost"], totals["clicks"]),
        # CPA: 전환 1건을 얻는 데 든 비용 (마찬가지로 광고비 0원이면 None)
        "cpa": _cost_metric(totals["cost"], totals["conversions"]),
        # ROAS: 광고비 1원당 매출 (2.0이면 광고비의 2배를 벌었다는 뜻)
        "roas": safe_divide(totals["revenue"], totals["cost"]),
    }


def calculate_kpis(df: pd.DataFrame) -> dict:
    """합계 지표 + 비율 지표를 한 번에 계산해 하나의 딕셔너리로 반환합니다.

    이 함수 하나만 호출하면 화면에 필요한 모든 KPI가 나옵니다.
    """
    totals = sum_metrics(df)
    ratios = calculate_ratios(totals)

    kpis = dict(totals)
    kpis.update(ratios)
    kpis["row_count"] = len(df)

    return kpis


def add_ratio_columns(df: pd.DataFrame) -> pd.DataFrame:
    """이미 합계로 집계된 표에 비율 지표 컬럼을 추가합니다.

    채널별 표, 콘텐츠별 표, 기간별 표에 공통으로 사용합니다.
    (집계가 끝난 뒤에 나누기 때문에 규칙 1을 지킵니다)
    """
    df = df.copy()

    df["ctr"] = safe_ratio_series(df["clicks"], df["impressions"])
    df["inquiry_rate"] = safe_ratio_series(df["inquiries"], df["clicks"])
    df["conversion_rate"] = safe_ratio_series(df["conversions"], df["clicks"])
    df["inquiry_to_conversion_rate"] = safe_ratio_series(df["conversions"], df["inquiries"])

    # 광고비/매출 컬럼이 있을 때만 비용 지표를 계산합니다.
    # cost가 0인 행은 오가닉으로 보고 비용 지표를 NaN(=화면 '-')으로 둡니다.
    # 이렇게 하지 않으면 광고비 0원 채널의 CPC/CPA가 0원으로 찍혀 오해를 부릅니다.
    if "cost" in df.columns:
        cost = df["cost"]
        cost_or_na = cost.replace([0], np.nan)  # 0원 -> NaN 으로 바꿔 분자에서 제외
        df["cpc"] = safe_ratio_series(cost_or_na, df["clicks"])
        df["cpa"] = safe_ratio_series(cost_or_na, df["conversions"])
    if "cost" in df.columns and "revenue" in df.columns:
        df["roas"] = safe_ratio_series(df["revenue"], df["cost"])

    return df
