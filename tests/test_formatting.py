"""숫자 표시 형식 테스트.

"화면에 어떻게 보이는가"도 결과물의 품질입니다.
전환율이 0.0336으로 찍히는 대시보드와 3.36%로 찍히는 대시보드는 인상이 다릅니다.
"""

from src import formatting


def test_format_int_adds_thousand_separator():
    assert formatting.format_int(1406758) == "1,406,758"


def test_format_won_adds_currency_suffix():
    assert formatting.format_won(246786807) == "246,786,807원"


def test_format_percent_converts_ratio():
    """0~1 사이의 비율을 퍼센트로 바꿔야 합니다."""
    assert formatting.format_percent(0.0336) == "3.36%"


def test_format_ratio_adds_multiplier_suffix():
    assert formatting.format_ratio(2.9535) == "2.95배"


def test_empty_values_become_dash():
    """계산 불가(None/NaN)는 전부 '-'로 표시해야 합니다.

    화면에 'None'이나 'nan'이 찍히면 완성도가 떨어져 보입니다.
    """
    assert formatting.format_int(None) == "-"
    assert formatting.format_percent(None) == "-"
    assert formatting.format_won(float("nan")) == "-"
    assert formatting.format_ratio(float("nan")) == "-"


def test_is_empty_detects_nan_without_pandas():
    """NaN은 자기 자신과 같지 않다는 성질로 판별합니다."""
    assert formatting.is_empty(float("nan")) is True
    assert formatting.is_empty(None) is True
    assert formatting.is_empty(0) is False   # 0은 '값이 없음'이 아닙니다


def test_format_metric_picks_correct_style():
    """지표 이름만 주면 알맞은 형식이 자동으로 적용되어야 합니다."""
    assert formatting.format_metric("clicks", 1500) == "1,500"
    assert formatting.format_metric("ctr", 0.05) == "5.00%"
    assert formatting.format_metric("cpa", 22931) == "22,931원"
    assert formatting.format_metric("roas", 2.95) == "2.95배"


def test_format_big_number_shortens_large_values():
    """큰 숫자는 만/억 단위로 줄여서 표시합니다."""
    assert formatting.format_big_number(41880305) == "4,188만"
    assert formatting.format_big_number(4033856736) == "40.3억"
    assert formatting.format_big_number(3500) == "3,500"
