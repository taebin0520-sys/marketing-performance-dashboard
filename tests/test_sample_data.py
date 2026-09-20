"""샘플 데이터 생성기의 '의미 규칙'을 검증하는 테스트.

이 테스트가 지키려는 규칙은 하나입니다.

    광고비 빈칸(결측)은 '그날 집행하지 않음 = 0원'을 뜻해야 한다.

전처리(src/data_loader.py)가 빈칸을 0으로 채우기 때문에,
실제로 광고비가 발생한 유료 채널 행을 빈칸으로 만들면
그 광고비가 0원으로 사라져 총 광고비가 줄고
CPA는 실제보다 낮게, ROAS는 실제보다 높게 보이는 왜곡이 생깁니다.

그래서 '광고비가 원래 0원인 행'에서만 결측이 생겨야 합니다.
"""

import csv

from src import config

# CPM이 0인 채널만 광고비가 0원입니다. (오가닉 채널)
ORGANIC_CHANNELS = {"naver_blog"}


def load_sample_rows():
    """저장소에 포함된 샘플 CSV를 표준 라이브러리로 읽습니다.

    pandas를 쓰지 않는 이유: 이 테스트는 '파일에 실제로 무엇이 들어있는지'를
    확인하는 것이므로, 전처리가 끼어들지 않은 원본을 그대로 봐야 합니다.
    """
    with config.SAMPLE_DATA_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_blank_cost_only_appears_on_zero_cost_rows():
    """광고비가 빈칸인 행은 광고비가 원래 0원인 채널(오가닉)이어야 합니다.

    유료 채널 행이 빈칸이면 전처리 후 광고비가 0원으로 사라져 KPI가 왜곡됩니다.
    """
    rows = load_sample_rows()

    blank_cost_channels = {r["channel"] for r in rows if r["cost"] == ""}

    assert blank_cost_channels <= ORGANIC_CHANNELS, (
        "유료 채널에서 광고비 결측이 발생했습니다: {}".format(
            blank_cost_channels - ORGANIC_CHANNELS
        )
    )


def test_paid_channel_cost_is_never_blank():
    """유료 채널 행의 광고비는 절대 빈칸이 아니어야 합니다."""
    rows = load_sample_rows()

    paid_rows = [r for r in rows if r["channel"] not in ORGANIC_CHANNELS]
    blank_paid = [r for r in paid_rows if r["cost"] == ""]

    assert blank_paid == [], "유료 채널 {}건의 광고비가 비어 있습니다".format(len(blank_paid))


def test_paid_channel_cost_is_positive():
    """유료 채널은 광고비가 0보다 커야 합니다. (임의 삭제·0 처리되지 않았는지 확인)"""
    rows = load_sample_rows()

    paid_rows = [r for r in rows if r["channel"] not in ORGANIC_CHANNELS]
    assert paid_rows, "유료 채널 행이 없습니다 (샘플 데이터 확인 필요)"

    zero_cost = [r for r in paid_rows if int(r["cost"]) <= 0]
    assert zero_cost == [], "유료 채널 {}건의 광고비가 0원입니다".format(len(zero_cost))


def test_organic_channel_cost_is_zero_or_blank():
    """오가닉 채널의 광고비는 0원 또는 빈칸이어야 합니다."""
    rows = load_sample_rows()

    organic_rows = [r for r in rows if r["channel"] in ORGANIC_CHANNELS]
    assert organic_rows, "오가닉 채널 행이 없습니다 (샘플 데이터 확인 필요)"

    for row in organic_rows:
        assert row["cost"] == "" or int(row["cost"]) == 0, (
            "오가닉 채널에 광고비가 들어있습니다: {}".format(row["cost"])
        )
