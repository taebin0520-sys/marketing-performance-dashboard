"""KPI 계산 테스트.

이 파일의 핵심은 test_ratio_uses_totals_not_row_average 입니다.
"비율 지표를 어떻게 계산해야 하는가"라는 이 프로젝트의 가장 중요한 규칙을
코드로 못 박아두는 테스트입니다.
"""

import math

import pandas as pd

from src import kpi


def test_safe_divide_normal_case():
    """정상적인 나눗셈은 그대로 계산합니다."""
    assert kpi.safe_divide(50, 200) == 0.25


def test_safe_divide_returns_none_for_zero_denominator():
    """0으로 나누면 에러가 아니라 None을 돌려줘야 합니다.

    광고비가 0원인 오가닉 채널(네이버 블로그 등)에서 실제로 발생하는 상황입니다.
    여기서 ZeroDivisionError가 나면 대시보드 전체가 멈춥니다.
    """
    assert kpi.safe_divide(50, 0) is None


def test_safe_divide_returns_none_for_missing_values():
    """None이나 NaN이 섞여 있어도 None을 돌려줘야 합니다."""
    assert kpi.safe_divide(None, 100) is None
    assert kpi.safe_divide(100, None) is None
    assert kpi.safe_divide(float("nan"), 100) is None


def test_sum_metrics_adds_all_numeric_columns(clean_frame):
    """합계 지표가 정확히 더해져야 합니다."""
    totals = kpi.sum_metrics(clean_frame)

    # 전처리 후 남은 3행의 노출: 1000 + 2000 + 500
    assert totals["impressions"] == 3500
    # clicks는 -5가 0으로 보정되었으므로 50 + 100 + 0
    assert totals["clicks"] == 150


def test_ratio_uses_totals_not_row_average():
    """비율 지표는 '합계 ÷ 합계'로 계산해야 합니다. (행별 비율의 평균이 아님)

    노출 10 / 클릭 1  -> 행별 CTR 10%
    노출 10000 / 클릭 100 -> 행별 CTR 1%

    - 잘못된 방법(행별 평균): (10% + 1%) / 2 = 5.5%
    - 올바른 방법(합계 기준): 101 / 10010 = 약 1.01%

    노출이 적은 행의 극단값 때문에 전체 지표가 5배 이상 부풀려지는 것을 막습니다.
    """
    df = pd.DataFrame({"impressions": [10, 10000], "clicks": [1, 100]})

    kpis = kpi.calculate_kpis(df)

    expected = 101 / 10010
    assert math.isclose(kpis["ctr"], expected, rel_tol=1e-9)
    # 행별 평균(0.055)과 확실히 다른 값이어야 합니다.
    assert kpis["ctr"] < 0.02


def test_calculate_ratios_full_funnel():
    """CTR, 문의율, 전환율, CPA, ROAS가 정의대로 계산되어야 합니다."""
    df = pd.DataFrame(
        {
            "impressions": [10000],
            "clicks": [300],
            "inquiries": [30],
            "conversions": [9],
            "cost": [900000],
            "revenue": [2700000],
        }
    )

    kpis = kpi.calculate_kpis(df)

    assert math.isclose(kpis["ctr"], 300 / 10000)                    # 3%
    assert math.isclose(kpis["inquiry_rate"], 30 / 300)              # 10%
    assert math.isclose(kpis["conversion_rate"], 9 / 300)            # 3%
    assert math.isclose(kpis["inquiry_to_conversion_rate"], 9 / 30)  # 30%
    assert math.isclose(kpis["cpc"], 900000 / 300)                   # 3,000원
    assert math.isclose(kpis["cpa"], 900000 / 9)                     # 100,000원
    assert math.isclose(kpis["roas"], 2700000 / 900000)              # 3배


def test_calculate_kpis_handles_zero_cost():
    """광고비가 0원이면 CPA/ROAS는 None이어야 합니다. (오가닉 채널)"""
    df = pd.DataFrame(
        {
            "impressions": [1000],
            "clicks": [50],
            "inquiries": [5],
            "conversions": [2],
            "cost": [0],
            "revenue": [100000],
        }
    )

    kpis = kpi.calculate_kpis(df)

    assert kpis["cpa"] is None
    assert kpis["roas"] is None
    # 광고비와 무관한 지표는 정상 계산되어야 합니다.
    assert math.isclose(kpis["ctr"], 50 / 1000)


def test_add_ratio_columns_replaces_infinity_with_nan():
    """표에서 0으로 나누는 경우 inf가 아니라 빈 값(NaN)이 되어야 합니다.

    pandas는 5 / 0 을 에러가 아니라 inf로 계산합니다.
    inf가 표에 그대로 찍히면 사용자가 잘못된 값으로 오해하므로 NaN으로 바꿉니다.
    """
    df = pd.DataFrame(
        {
            "impressions": [0, 1000],
            "clicks": [5, 50],
            "inquiries": [1, 5],
            "conversions": [0, 2],
        }
    )

    result = kpi.add_ratio_columns(df)

    assert pd.isna(result.loc[0, "ctr"])          # 노출 0 -> 계산 불가
    assert math.isclose(result.loc[1, "ctr"], 0.05)


def test_calculate_kpis_includes_row_count(clean_frame):
    """몇 행을 기준으로 계산했는지도 함께 돌려줘야 합니다."""
    kpis = kpi.calculate_kpis(clean_frame)

    assert kpis["row_count"] == 3



# ---------------------------------------------------------------------------
# '데이터 없음'과 '값이 0'을 구분하는지 검증
# ---------------------------------------------------------------------------
# 매출이 0원인 것과 매출 데이터를 아예 받지 못한 것은 의미가 전혀 다릅니다.
# 전자는 ROAS = 0배, 후자는 ROAS 계산 불가(None)여야 합니다.

def build_frame(**columns):
    """테스트용 DataFrame을 만듭니다. 넘기지 않은 컬럼은 아예 존재하지 않습니다."""
    return pd.DataFrame(columns)


def test_roas_is_none_when_revenue_column_missing():
    """revenue 컬럼 자체가 없으면 ROAS는 None이어야 합니다. (0배가 아님)

    0으로 처리하면 "광고비를 썼는데 매출이 0원"처럼 보여 성과를 잘못 읽게 됩니다.
    """
    df = build_frame(
        impressions=[10000], clicks=[300], inquiries=[30], conversions=[9],
        cost=[900000],
        # revenue 컬럼 없음
    )

    kpis = kpi.calculate_kpis(df)

    assert kpis["roas"] is None
    # 광고비는 있으므로 비용 지표는 정상 계산되어야 합니다.
    assert math.isclose(kpis["cpa"], 900000 / 9)


def test_roas_is_zero_when_revenue_column_exists_but_zero():
    """revenue 컬럼이 있고 값이 0이면 ROAS는 0이어야 합니다. (None이 아님)

    실제로 매출이 0원인 상황은 '계산 불가'가 아니라 '성과가 0'입니다.
    """
    df = build_frame(
        impressions=[10000], clicks=[300], inquiries=[30], conversions=[9],
        cost=[900000], revenue=[0],
    )

    kpis = kpi.calculate_kpis(df)

    assert kpis["roas"] == 0
    assert kpis["roas"] is not None


def test_cost_metrics_are_none_when_cost_column_missing():
    """cost 컬럼 자체가 없으면 CPC·CPA·ROAS 모두 None이어야 합니다."""
    df = build_frame(
        impressions=[10000], clicks=[300], inquiries=[30], conversions=[9],
        revenue=[2700000],
        # cost 컬럼 없음
    )

    kpis = kpi.calculate_kpis(df)

    assert kpis["cpc"] is None
    assert kpis["cpa"] is None
    assert kpis["roas"] is None
    # 광고비와 무관한 지표는 정상 계산되어야 합니다.
    assert math.isclose(kpis["conversion_rate"], 9 / 300)


def test_sum_metrics_returns_none_for_missing_column():
    """없는 컬럼의 합계는 0.0이 아니라 None이어야 합니다."""
    totals = kpi.sum_metrics(build_frame(impressions=[100], clicks=[10]))

    assert totals["impressions"] == 100
    assert totals["cost"] is None
    assert totals["revenue"] is None


def test_sum_metrics_returns_none_when_all_values_are_nan():
    """값이 전부 비어 있으면(NaN) 합계는 0.0이 아니라 None이어야 합니다.

    data_loader가 '컬럼 없음'을 NaN으로 채우기 때문에 이 규칙이 필요합니다.
    pandas sum()은 NaN을 건너뛰어 0.0을 주므로 그대로 쓰면 구분이 사라집니다.
    """
    df = build_frame(
        impressions=[1000, 2000],
        clicks=[50, 100],
        revenue=[float("nan"), float("nan")],
    )

    totals = kpi.sum_metrics(df)

    assert totals["impressions"] == 3000
    assert totals["revenue"] is None
