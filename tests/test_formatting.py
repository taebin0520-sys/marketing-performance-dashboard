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



def test_format_delta_positive_change():
    """양수 증감은 + 부호와 함께 표시되어야 합니다."""
    assert formatting.format_delta(0.125) == "+12.5%"


def test_format_delta_negative_change():
    """음수 증감은 - 부호와 함께 표시되어야 합니다."""
    assert formatting.format_delta(-0.083) == "-8.3%"


def test_format_delta_new_takes_priority():
    """is_new=True 이면 퍼센트 값과 무관하게 '신규'를 돌려줘야 합니다."""
    assert formatting.format_delta(None, is_new=True) == "신규"


def test_format_delta_none_returns_none():
    """비교할 수 없는 경우 None을 돌려줘야 합니다. (st.metric이 delta를 숨기게 됨)"""
    assert formatting.format_delta(None, is_new=False) is None



def test_build_filename_with_date_objects():
    """date 객체를 넘기면 YYYYMMDD 형식으로 파일명이 만들어져야 합니다."""
    from datetime import date

    filename = formatting.build_filename(
        "report", date(2026, 8, 17), date(2026, 9, 13), "md"
    )

    assert filename == "report_20260817_20260913.md"


def test_build_filename_with_string_dates():
    """'YYYY-MM-DD' 문자열을 넘겨도 하이픈이 빠진 형식으로 만들어져야 합니다.

    app.py에서 start_date가 상황에 따라 date 객체 또는 문자열일 수 있어서
    두 타입을 모두 지원해야 합니다.
    """
    filename = formatting.build_filename("raw_data", "2026-08-17", "2026-09-13", "csv")

    assert filename == "raw_data_20260817_20260913.csv"


def test_build_filename_includes_extension_without_dot():
    """extension 파라미터에 점(.)을 붙이지 않아도 파일명에는 점이 하나만 들어가야 합니다."""
    filename = formatting.build_filename("test", "2026-01-01", "2026-01-07", "csv")

    assert filename.endswith(".csv")
    assert filename.count(".") == 1



def test_format_point_delta_adds_percentage_point_unit():
    """퍼센트포인트는 반드시 '%p' 단위를 붙여 상대 증감률(%)과 구분해야 합니다.

    CTR 3.22% -> 3.43% 인 경우
      - 상대 증감률 : +6.5%   (format_delta 담당)
      - 퍼센트포인트 : +0.21%p (이 함수 담당)
    """
    assert formatting.format_point_delta(0.0021) == "+0.21%p"


def test_format_point_delta_negative():
    """감소한 경우 - 부호가 붙어야 합니다."""
    assert formatting.format_point_delta(-0.0035) == "-0.35%p"


def test_format_point_delta_empty_returns_dash():
    """계산 불가한 경우 '-'를 돌려줘야 합니다."""
    assert formatting.format_point_delta(None) == "-"


def test_relative_percent_and_point_delta_are_different():
    """같은 변화를 두 방식으로 표현하면 값이 달라야 합니다. (혼동 방지 회귀 테스트)

    3.22% -> 3.43% 변화에서
      상대 증감률은 약 6.5%, 퍼센트포인트는 0.21%p 입니다.
      이 둘을 혼용하면 성과를 30배 과장해 읽게 됩니다.
    """
    previous, current = 0.0322, 0.0343

    relative = formatting.format_delta((current - previous) / previous)
    point = formatting.format_point_delta(current - previous)

    assert relative == "+6.5%"
    assert point == "+0.21%p"
    assert relative != point
