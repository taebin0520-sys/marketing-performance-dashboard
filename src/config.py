"""프로젝트 전역 설정값을 모아둔 파일.

컬럼 이름이나 한국어 라벨을 여러 파일에 흩어놓으면
나중에 하나만 바꿔도 여러 파일을 찾아다녀야 합니다.
그래서 "바뀔 가능성이 있는 값"은 모두 이 파일에 모았습니다.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 경로
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DATA_PATH = PROJECT_ROOT / "data" / "sample_marketing_data.csv"

# ---------------------------------------------------------------------------
# 컬럼 정의
# ---------------------------------------------------------------------------

# 날짜 컬럼
DATE_COLUMN = "date"

# 문자(범주형) 컬럼
TEXT_COLUMNS = ["channel", "content_id", "content_title", "content_type"]

# 반드시 있어야 하는 숫자 컬럼
REQUIRED_NUMERIC_COLUMNS = [
    "impressions",
    "reach",
    "views",
    "clicks",
    "inquiries",
    "conversions",
]

# 있으면 좋고 없어도 동작하는 숫자 컬럼 (광고비/매출)
OPTIONAL_NUMERIC_COLUMNS = ["cost", "revenue"]

# 업로드된 CSV에 반드시 있어야 하는 컬럼 전체
REQUIRED_COLUMNS = [DATE_COLUMN] + TEXT_COLUMNS + REQUIRED_NUMERIC_COLUMNS

# 숫자로 변환을 시도할 모든 컬럼
ALL_NUMERIC_COLUMNS = REQUIRED_NUMERIC_COLUMNS + OPTIONAL_NUMERIC_COLUMNS

# 마케팅 퍼널 순서.
# 위에서 아래로 갈수록 숫자가 작아야 정상입니다.
# (노출 >= 도달 >= 조회수 >= 클릭 >= 문의 >= 전환)
FUNNEL_ORDER = [
    "impressions",
    "reach",
    "views",
    "clicks",
    "inquiries",
    "conversions",
]

# 결측 문자값을 채울 기본 문자열
UNKNOWN_LABEL = "미분류"

# ---------------------------------------------------------------------------
# 한국어 라벨 (화면 표시용)
# ---------------------------------------------------------------------------

CHANNEL_LABELS = {
    "instagram": "인스타그램",
    "naver_blog": "네이버 블로그",
    "youtube": "유튜브",
    "kakao": "카카오",
    "google_ads": "구글 애즈",
    "facebook": "페이스북",
}

CONTENT_TYPE_LABELS = {
    "image": "이미지",
    "carousel": "캐러셀",
    "reels": "릴스",
    "video": "동영상",
    "blog_post": "블로그 글",
    "story": "스토리",
}

# 지표 영문명 -> 한국어 라벨
METRIC_LABELS = {
    "impressions": "노출",
    "reach": "도달",
    "views": "조회수",
    "clicks": "클릭",
    "inquiries": "문의",
    "conversions": "전환",
    "cost": "광고비",
    "revenue": "매출",
    "ctr": "CTR(클릭률)",
    "inquiry_rate": "문의율",
    "conversion_rate": "전환율",
    "inquiry_to_conversion_rate": "문의→전환율",
    "cpc": "CPC(클릭당 비용)",
    "cpa": "CPA(전환당 비용)",
    "roas": "ROAS",
}

# 지표의 표시 형식: "int"(정수), "won"(원화), "percent"(퍼센트), "ratio"(배수)
METRIC_FORMATS = {
    "impressions": "int",
    "reach": "int",
    "views": "int",
    "clicks": "int",
    "inquiries": "int",
    "conversions": "int",
    "cost": "won",
    "revenue": "won",
    "ctr": "percent",
    "inquiry_rate": "percent",
    "conversion_rate": "percent",
    "inquiry_to_conversion_rate": "percent",
    "cpc": "won",
    "cpa": "won",
    "roas": "ratio",
}

# KPI 카드에 크게 보여줄 지표 순서
KPI_CARD_METRICS = ["views", "reach", "clicks", "inquiries", "conversions"]

# ---------------------------------------------------------------------------
# 지표의 '좋은 방향' 정의
# ---------------------------------------------------------------------------
# 대부분의 지표는 값이 커지면 좋습니다(전환 증가 = 좋음).
# 그런데 비용 지표는 반대입니다. CPA가 25,000원 -> 22,000원으로 '감소'한 것은
# 전환 1건을 더 싸게 얻었다는 뜻이므로 '개선'입니다.
#
# 이 목록을 따로 두는 이유:
# 화면에서 증감을 색으로 표시할 때 모든 지표에 "증가=초록/감소=빨강"을 적용하면
# CPA가 개선(-11.4%)됐는데 빨간색으로 보여 잘못된 신호를 줍니다.
#
# 중요: 이 값은 '색상 방향'만 바꿉니다. 증감 계산식 자체는 건드리지 않습니다.
#       CPA가 줄었으면 delta 값은 그대로 음수(-11.4%)로 유지하고,
#       색만 개선을 뜻하는 초록으로 보여줍니다. (계산 로직 != 시각적 의미)
LOWER_IS_BETTER_METRICS = ["cpc", "cpa"]


def get_delta_color(metric: str) -> str:
    """지표의 증감을 화면에 어떤 색 방향으로 표시할지 돌려줍니다.

    Streamlit st.metric의 delta_color 파라미터에 그대로 넘기는 값입니다.
    - "normal"  : 증가=초록, 감소=빨강 (기본. 전환/클릭 등 대부분의 지표)
    - "inverse" : 증가=빨강, 감소=초록 (CPA/CPC 같은 비용 지표)

    Returns
    -------
    str
        "normal" 또는 "inverse"
    """
    if metric in LOWER_IS_BETTER_METRICS:
        return "inverse"
    return "normal"

# 추세 차트에서 선택할 수 있는 지표
TREND_METRIC_OPTIONS = [
    "impressions",
    "reach",
    "views",
    "clicks",
    "inquiries",
    "conversions",
    "ctr",
    "conversion_rate",
]

# 콘텐츠 TOP N 정렬 기준으로 쓸 수 있는 지표
CONTENT_SORT_OPTIONS = [
    "conversions",
    "inquiries",
    "clicks",
    "views",
    "impressions",
    "ctr",
    "conversion_rate",
]

# ---------------------------------------------------------------------------
# 집계 단위
# ---------------------------------------------------------------------------
# 화면에 보여줄 이름 -> 내부에서 쓰는 코드
PERIOD_OPTIONS = {
    "일간": "D",
    "주간": "W",
    "월간": "M",
}

# 주간 집계는 '월요일 시작' 기준으로 통일합니다.
# (기준을 정해두지 않으면 보는 사람마다 숫자가 달라집니다)
WEEK_START_LABEL = "월요일 시작"


def get_channel_label(channel: str) -> str:
    """채널 영문 코드를 한국어 라벨로 바꿉니다.

    사전에 없는 채널(사용자가 직접 올린 CSV의 새 채널)은 원래 값을 그대로 씁니다.
    이렇게 해두면 모르는 값이 들어와도 화면이 비지 않습니다.
    """
    return CHANNEL_LABELS.get(channel, channel)


def get_content_type_label(content_type: str) -> str:
    """콘텐츠 유형 영문 코드를 한국어 라벨로 바꿉니다."""
    return CONTENT_TYPE_LABELS.get(content_type, content_type)


def get_metric_label(metric: str) -> str:
    """지표 영문명을 한국어 라벨로 바꿉니다."""
    return METRIC_LABELS.get(metric, metric)
