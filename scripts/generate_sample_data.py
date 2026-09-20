"""가상 마케팅 성과 샘플 데이터를 생성하는 스크립트.

실행:
    python scripts/generate_sample_data.py

특징
----
1) 표준 라이브러리(csv, random, datetime)만 사용합니다.
   -> pandas 설치 전에도 데이터를 만들 수 있어 학습 초기에 편합니다.
2) 난수 시드를 고정했습니다. 몇 번을 실행해도 항상 같은 CSV가 나옵니다(재현성).
3) 실제 회사/고객 정보는 전혀 들어 있지 않은 100% 가상 데이터입니다.
4) 분석할 거리가 있도록 의도적인 패턴을 넣었습니다.
   - 주말 성과 하락
   - 채널별 CTR / 전환율 차이
   - 8월 중순 캠페인 기간 성과 급증
   - 광고비 일부 결측치(전처리 연습용)
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------------------------

# 시드를 고정하면 난수가 항상 같은 순서로 나와서 결과가 재현됩니다.
RANDOM_SEED = 42

# 분석 기간: 2026-05-18(월) ~ 2026-09-13(일) = 17주(119일)
# 일부러 "월요일 시작 ~ 일요일 종료"로 맞춰서 주간 집계가 깔끔하게 나오도록 했습니다.
START_DATE = date(2026, 5, 18)
END_DATE = date(2026, 9, 13)

# 캠페인 기간(이 기간에는 노출이 크게 늘어납니다)
CAMPAIGN_START = date(2026, 8, 10)
CAMPAIGN_END = date(2026, 8, 23)
CAMPAIGN_CHANNELS = {"instagram", "google_ads"}
CAMPAIGN_BOOST = 1.6

# 출력 경로 (scripts/ 의 부모 폴더가 프로젝트 루트)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "sample_marketing_data.csv"

# CSV 컬럼 순서
COLUMNS = [
    "date",
    "channel",
    "content_id",
    "content_title",
    "content_type",
    "impressions",
    "reach",
    "views",
    "clicks",
    "inquiries",
    "conversions",
    "cost",
    "revenue",
]

# ---------------------------------------------------------------------------
# 2. 채널별 특성 정의
# ---------------------------------------------------------------------------
# base_impressions : 하루 평균 노출 규모
# ctr              : 클릭 / 노출 (채널마다 다르게 두어 비교할 거리를 만듭니다)
# inquiry_rate     : 문의 / 클릭
# inq_to_conv      : 전환 / 문의
# cpm              : 노출 1,000회당 광고비(원). 0이면 무료(오가닉) 채널
# content_types    : 해당 채널에서 쓰는 콘텐츠 형식
CHANNELS = {
    "instagram": {
        "base_impressions": 12000,
        "ctr": 0.035,
        "inquiry_rate": 0.024,
        "inq_to_conv": 0.32,
        "cpm": 6500,
        "content_types": ["image", "carousel", "reels", "story"],
    },
    "naver_blog": {
        "base_impressions": 4200,
        "ctr": 0.055,          # 검색 유입이라 클릭률이 높음
        "inquiry_rate": 0.035,
        "inq_to_conv": 0.38,
        "cpm": 0,              # 오가닉 채널이라 광고비 없음
        "content_types": ["blog_post"],
    },
    "youtube": {
        "base_impressions": 21000,
        "ctr": 0.018,          # 노출은 많지만 클릭률은 낮음
        "inquiry_rate": 0.015,
        "inq_to_conv": 0.24,
        "cpm": 4200,
        "content_types": ["video", "reels"],
    },
    "kakao": {
        "base_impressions": 6300,
        "ctr": 0.045,
        "inquiry_rate": 0.042,  # 문의 전환이 가장 좋은 채널
        "inq_to_conv": 0.42,
        "cpm": 7500,
        "content_types": ["image", "carousel"],
    },
    "google_ads": {
        "base_impressions": 15500,
        "ctr": 0.028,
        "inquiry_rate": 0.028,
        "inq_to_conv": 0.35,
        "cpm": 9000,           # 단가가 가장 비싼 채널
        "content_types": ["image", "video"],
    },
    "facebook": {
        "base_impressions": 9000,
        "ctr": 0.021,
        "inquiry_rate": 0.017,
        "inq_to_conv": 0.22,
        "cpm": 5000,
        "content_types": ["image", "carousel", "video"],
    },
}

# 콘텐츠 제목을 조합해서 만들기 위한 단어 목록 (모두 가상)
TITLE_PREFIX = [
    "가을 신상", "여름 클리어런스", "베스트셀러", "신규 입고", "리뷰 이벤트",
    "한정 수량", "직원 추천", "재입고 알림", "시즌오프", "브랜드 협업",
]
TITLE_MIDDLE = [
    "코디", "기획전", "패키지", "세트", "단독 특가", "체험단", "쿠폰", "룩북",
]
TITLE_SUFFIX = [
    "안내", "모음", "추천", "소개", "총정리", "후기", "가이드",
]

# 콘텐츠 개수
NUM_CONTENTS = 60

# 한 콘텐츠가 하루에 데이터를 남길 확률 (매일 성과가 잡히지는 않는다고 가정)
DAILY_ACTIVE_RATE = 0.85

# 광고비를 비워둘 비율 (결측치 전처리 연습용)
MISSING_COST_RATE = 0.015


# ---------------------------------------------------------------------------
# 3. 보조 함수
# ---------------------------------------------------------------------------

def daterange(start: date, end: date):
    """start부터 end까지(끝 포함) 날짜를 하루씩 생성합니다."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def weekday_factor(day: date) -> float:
    """요일에 따른 성과 보정값.

    실제 마케팅 데이터는 주말에 성과가 떨어지는 경우가 많아
    그 패턴을 일부러 재현했습니다. (월=0 ... 일=6)
    """
    factors = {0: 1.05, 1: 1.08, 2: 1.06, 3: 1.02, 4: 0.95, 5: 0.78, 6: 0.72}
    return factors[day.weekday()]


def campaign_factor(day: date, channel: str) -> float:
    """캠페인 기간 + 대상 채널이면 노출을 크게 올립니다."""
    if CAMPAIGN_START <= day <= CAMPAIGN_END and channel in CAMPAIGN_CHANNELS:
        return CAMPAIGN_BOOST
    return 1.0


def make_contents(rng: random.Random) -> list:
    """가상 콘텐츠 목록을 만듭니다.

    각 콘텐츠는 채널, 형식, 제목, 두 개의 계수, 활동 기간을 가집니다.

    - quality(규모 계수)    : 노출이 얼마나 많이 잡히는지 (도달 규모의 차이)
    - engagement(반응 계수) : 노출 대비 클릭이 얼마나 잘 나오는지 (CTR의 차이)

    두 계수를 나눈 이유: 하나로 합치면 "노출이 많은 콘텐츠 = CTR도 높은 콘텐츠"가 되어
    CTR이 비현실적으로 커집니다. 실제로는 노출 규모와 반응률은 별개이므로 분리했습니다.
    이렇게 하면 "노출은 적지만 CTR이 좋은 콘텐츠"도 생겨 TOP N 분석이 의미를 가집니다.
    """
    channel_names = list(CHANNELS.keys())
    contents = []

    for i in range(1, NUM_CONTENTS + 1):
        channel = channel_names[(i - 1) % len(channel_names)]  # 채널을 골고루 배분
        content_type = rng.choice(CHANNELS[channel]["content_types"])

        title = "{} {} {}".format(
            rng.choice(TITLE_PREFIX),
            rng.choice(TITLE_MIDDLE),
            rng.choice(TITLE_SUFFIX),
        )

        # 콘텐츠가 게시된 날짜와 유지 기간
        total_days = (END_DATE - START_DATE).days
        launch_offset = rng.randint(0, max(total_days - 40, 0))
        lifespan = rng.randint(45, 115)

        launch_date = START_DATE + timedelta(days=launch_offset)
        retire_date = min(launch_date + timedelta(days=lifespan), END_DATE)

        contents.append(
            {
                "content_id": "C{:04d}".format(i),
                "content_title": title,
                "channel": channel,
                "content_type": content_type,
                "quality": round(rng.uniform(0.55, 1.75), 3),
                "engagement": round(rng.uniform(0.7, 1.45), 3),
                "launch_date": launch_date,
                "retire_date": retire_date,
            }
        )

    return contents


def build_row(day: date, content: dict, rng: random.Random) -> dict:
    """하루 × 콘텐츠 1건의 성과 데이터를 만듭니다.

    퍼널 규칙(노출 >= 도달 >= 조회 >= 클릭 >= 문의 >= 전환)이 반드시
    지켜지도록 각 단계에서 상위 값을 넘지 않게 제한(min)합니다.
    """
    spec = CHANNELS[content["channel"]]

    # (1) 노출: 채널 기본 규모 × 콘텐츠 품질 × 요일 × 캠페인 × 랜덤 노이즈
    impressions = (
        spec["base_impressions"]
        * content["quality"]
        * weekday_factor(day)
        * campaign_factor(day, content["channel"])
        * rng.uniform(0.75, 1.25)
    )
    impressions = max(int(impressions), 1)

    # (2) 도달: 노출 중 실제로 도달한 순 사용자 (항상 노출보다 작음)
    reach = int(impressions * rng.uniform(0.62, 0.88))

    # (3) 조회수: 도달한 사람 중 실제로 본 수
    views = int(reach * rng.uniform(0.35, 0.72))

    # (4) 클릭: CTR은 "클릭 / 노출"로 정의했으므로 노출을 기준으로 계산합니다.
    #     규모 계수(quality)가 아니라 반응 계수(engagement)를 쓰는 이유는
    #     make_contents() 의 설명을 참고하세요.
    #     단, 조회수보다 많아질 수는 없으므로 min으로 잘라줍니다.
    clicks = int(impressions * spec["ctr"] * content["engagement"] * rng.uniform(0.8, 1.2))
    clicks = min(clicks, views)

    # (5) 문의: 클릭한 사람 중 문의로 이어진 수
    inquiries = int(clicks * spec["inquiry_rate"] * rng.uniform(0.6, 1.4))
    inquiries = min(inquiries, clicks)

    # (6) 전환: 문의 중 실제 구매/가입까지 간 수
    conversions = int(inquiries * spec["inq_to_conv"] * rng.uniform(0.5, 1.5))
    conversions = min(conversions, inquiries)

    # (7) 광고비: CPM(1,000회 노출당 비용) 기준. 오가닉 채널은 0원
    if spec["cpm"] == 0:
        cost = 0
    else:
        cost = int(impressions / 1000 * spec["cpm"] * rng.uniform(0.85, 1.15))

    # (8) 매출: 전환 1건당 평균 구매금액(AOV)을 곱합니다.
    revenue = int(conversions * rng.uniform(40000, 95000)) if conversions else 0

    # (9) 일부 행의 광고비를 비워서 결측치 전처리를 연습할 수 있게 합니다.
    #
    # [중요] 광고비가 0원인 행(오가닉 채널)에서만 빈칸을 만듭니다.
    # 전처리(src/data_loader.py)는 빈칸을 '그날 집행하지 않음 = 0원'으로 보고 0으로 채웁니다.
    # 그런데 실제로 광고비가 발생한 유료 채널 행을 빈칸으로 만들면,
    # 전처리 후 그 광고비가 0원으로 사라져 총 광고비가 줄고
    # CPA는 실제보다 낮게, ROAS는 실제보다 높게 보이는 왜곡이 생깁니다.
    # 따라서 '빈칸 = 0원'이라는 전제가 깨지지 않는 행에서만 결측을 만듭니다.
    if cost == 0 and rng.random() < MISSING_COST_RATE:
        cost_value = ""
    else:
        cost_value = cost

    return {
        "date": day.isoformat(),
        "channel": content["channel"],
        "content_id": content["content_id"],
        "content_title": content["content_title"],
        "content_type": content["content_type"],
        "impressions": impressions,
        "reach": reach,
        "views": views,
        "clicks": clicks,
        "inquiries": inquiries,
        "conversions": conversions,
        "cost": cost_value,
        "revenue": revenue,
    }


# ---------------------------------------------------------------------------
# 4. 메인 로직
# ---------------------------------------------------------------------------

def generate_rows() -> list:
    """전체 기간 × 콘텐츠를 돌면서 데이터 행 목록을 만듭니다."""
    rng = random.Random(RANDOM_SEED)
    contents = make_contents(rng)
    rows = []

    for day in daterange(START_DATE, END_DATE):
        for content in contents:
            # 콘텐츠가 아직 게시 전이거나 이미 종료됐으면 건너뜁니다.
            if not (content["launch_date"] <= day <= content["retire_date"]):
                continue
            # 매일 데이터가 잡히지는 않는다고 가정
            if rng.random() > DAILY_ACTIVE_RATE:
                continue
            rows.append(build_row(day, content, rng))

    return rows


def save_rows(rows: list, output_path: Path) -> None:
    """행 목록을 CSV로 저장합니다.

    encoding='utf-8-sig' 를 쓰는 이유: 엑셀에서 열었을 때 한글이 깨지지 않습니다.
    newline='' 은 윈도우에서 빈 줄이 하나씩 끼는 문제를 막아줍니다.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = generate_rows()
    save_rows(rows, OUTPUT_PATH)

    # 생성 결과를 사람이 확인할 수 있도록 간단한 요약을 출력합니다.
    print("샘플 데이터 생성 완료")
    print("- 저장 위치 : {}".format(OUTPUT_PATH))
    print("- 행 수     : {:,}".format(len(rows)))
    print("- 기간      : {} ~ {}".format(START_DATE, END_DATE))
    print("- 채널 수   : {}".format(len(CHANNELS)))
    print("- 콘텐츠 수 : {}".format(NUM_CONTENTS))


if __name__ == "__main__":
    main()
