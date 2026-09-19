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


def format_delta(percent_change, is_new: bool = False):
    """전기 대비 증감률을 st.metric의 delta 파라미터용 문자열로 바꿉니다.

    Parameters
    ----------
    percent_change : float | None
        analysis.calculate_period_over_period() 가 계산한 증감률 (예: 0.125 = 12.5% 증가)
    is_new : bool
        직전 기간에는 0이었다가 새로 생긴 경우

    Returns
    -------
    str | None
        None 을 돌려주면 st.metric이 delta 표시를 하지 않습니다.
        (비교 기간 데이터가 없거나 계산이 불가능한 경우)
    """
    if is_new:
        return "신규"
    if is_empty(percent_change):
        return None
    return "{:+.1f}%".format(percent_change * 100)


def format_point_delta(delta, decimals: int = 2) -> str:
    """비율 지표의 '퍼센트포인트(%p)' 차이를 표시합니다.

    왜 이 함수가 따로 필요한가?
    -------------------------
    비율 지표(CTR, 전환율 등)의 변화는 두 가지로 표현할 수 있고, 둘은 전혀 다릅니다.

    CTR이 3.22% -> 3.43% 로 올랐다면
      - 상대 증감률 : (3.43 - 3.22) / 3.22 = 약 +6.5%   <- format_delta() 담당
      - 퍼센트포인트 : 3.43 - 3.22 = +0.21%p             <- 이 함수 담당

    "CTR이 6.5% 올랐다"와 "CTR이 0.21%p 올랐다"는 같은 사실의 다른 표현입니다.
    이 둘을 혼용하면 성과를 6.5%p 오른 것처럼 30배 과장해 읽게 되므로,
    표기를 분리하고 단위(%, %p)를 반드시 붙입니다.

    Parameters
    ----------
    delta : float | None
        비율의 차이 (예: 0.0343 - 0.0322 = 0.0021)

    Examples
    --------
    >>> format_point_delta(0.0021)
    '+0.21%p'
    """
    if is_empty(delta):
        return EMPTY_MARK
    return "{:+.{d}f}%p".format(delta * 100, d=decimals)


def build_filename(prefix: str, start_date, end_date, extension: str) -> str:
    """다운로드 파일 이름을 만듭니다. 예) build_filename('report', ..., 'md')
       -> 'report_20260817_20260913.md'

    파일명에 분석 기간을 넣는 이유:
    "report.md"라는 이름만 있으면 나중에 여러 번 받아도 어느 기간 것인지
    구분이 안 되고, 다시 받으면 덮어써질 수 있습니다.
    """
    start_text = _format_date_for_filename(start_date)
    end_text = _format_date_for_filename(end_date)
    return "{}_{}_{}.{}".format(prefix, start_text, end_text, extension)


def _format_date_for_filename(value) -> str:
    """날짜를 파일명에 쓸 수 있는 'YYYYMMDD' 형식으로 바꿉니다.

    date 객체든 'YYYY-MM-DD' 문자열이든 둘 다 받을 수 있게 처리합니다.
    (app.py에서 넘기는 start_date가 상황에 따라 둘 중 하나일 수 있어서입니다)
    """
    if hasattr(value, "strftime"):
        return value.strftime("%Y%m%d")
    return str(value).replace("-", "")


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
