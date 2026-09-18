"""숫자를 화면에 보기 좋게 바꿔주는 모듈.

숫자 포맷을 app.py 안에 흩어놓으면 "여기는 콤마가 있고 저기는 없는" 문제가 생깁니다.
그래서 표시 규칙을 이 파일 한 곳에 모았습니다.

규칙
----
- 정수  : 1,406,758   (천 단위 콤마)
- 금액  : 246,786,807원
- 비율  : 3.36%       (소수 2자리)
- 배수  : 2.95배      (ROAS)
- 값이 없거나 계산 불가(None/NaN)면 '-'

이 파일은 pandas도 streamlit도 import하지 않습니다.
표준 파이썬만 쓰기 때문에 어디서든 재사용할 수 있습니다.
"""

from src import config

# 값이 없을 때 화면에 표시할 문자
EMPTY_MARK = "-"


def is_empty(value) -> bool:
    """None 또는 NaN인지 확인합니다.

    NaN은 "자기 자신과 비교해도 같지 않다"는 독특한 성질이 있어서
    value != value 로 판별할 수 있습니다. (pandas 없이 확인하는 방법)
    """
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    return False


def format_int(value) -> str:
    """정수를 천 단위 콤마 형식으로 바꿉니다. 예) 1406758 -> '1,406,758'"""
    if is_empty(value):
        return EMPTY_MARK
    return "{:,.0f}".format(value)


def format_won(value) -> str:
    """금액을 '원' 단위로 표시합니다. 예) 246786807 -> '246,786,807원'"""
    if is_empty(value):
        return EMPTY_MARK
    return "{:,.0f}원".format(value)


def format_percent(value, decimals: int = 2) -> str:
    """비율(0~1 사이 값)을 퍼센트로 바꿉니다. 예) 0.0336 -> '3.36%'"""
    if is_empty(value):
        return EMPTY_MARK
    return "{:.{d}f}%".format(value * 100, d=decimals)


def format_ratio(value, decimals: int = 2) -> str:
    """배수를 표시합니다. 예) 2.9535 -> '2.95배'"""
    if is_empty(value):
        return EMPTY_MARK
    return "{:.{d}f}배".format(value, d=decimals)


def format_metric(metric: str, value) -> str:
    """지표 이름에 맞는 형식으로 자동 변환합니다.

    config.METRIC_FORMATS에 정의된 형식('int', 'won', 'percent', 'ratio')을 보고
    알맞은 함수를 골라 적용합니다. 호출하는 쪽에서는 지표가 비율인지 금액인지
    신경 쓰지 않아도 됩니다.
    """
    metric_format = config.METRIC_FORMATS.get(metric, "int")

    if metric_format == "won":
        return format_won(value)
    if metric_format == "percent":
        return format_percent(value)
    if metric_format == "ratio":
        return format_ratio(value)
    return format_int(value)


def format_big_number(value) -> str:
    """큰 숫자를 만/억 단위로 짧게 줄입니다. (KPI 카드처럼 공간이 좁을 때)

    예) 41880305 -> '4,188만'  /  4033856736 -> '40.3억'
    """
    if is_empty(value):
        return EMPTY_MARK

    number = float(value)
    if abs(number) >= 100_000_000:
        return "{:,.1f}억".format(number / 100_000_000)
    if abs(number) >= 10_000:
        return "{:,.0f}만".format(number / 10_000)
    return "{:,.0f}".format(number)
