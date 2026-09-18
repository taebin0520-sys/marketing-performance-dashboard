"""테스트에서 공통으로 사용하는 데이터를 만들어주는 파일.

pytest의 fixture는 "테스트 함수가 인자로 이름만 적으면 자동으로 넣어주는 준비물"입니다.
같은 테스트 데이터를 여러 파일에서 다시 만들지 않도록 여기에 모았습니다.
"""

import pandas as pd
import pytest


@pytest.fixture
def raw_frame() -> pd.DataFrame:
    """전처리 전의 '지저분한' 원본 데이터.

    일부러 아래 문제를 섞어 두었습니다. (전처리 함수를 검증하기 위한 재료)
    - 날짜가 아닌 값       : 'invalid-date'
    - 광고비 빈칸          : ''
    - 음수 클릭            : -5
    - 채널 이름 앞뒤 공백  : ' instagram '
    - 콘텐츠 유형 결측     : None
    """
    return pd.DataFrame(
        {
            "date": [
                "2026-09-07",     # 월요일
                "2026-09-09",     # 수요일 (같은 주)
                "2026-09-14",     # 다음 주 월요일
                "invalid-date",   # 날짜 변환 실패 -> 제외 대상
            ],
            "channel": ["instagram", " instagram ", "kakao", "kakao"],
            "content_id": ["C0001", "C0001", "C0002", "C0002"],
            "content_title": ["가을 코디 추천", "가을 코디 추천", "쿠폰 안내", "쿠폰 안내"],
            "content_type": ["reels", "reels", None, "image"],
            "impressions": [1000, 2000, 500, 100],
            "reach": [800, 1500, 400, 90],
            "views": [600, 1000, 300, 80],
            "clicks": [50, 100, -5, 10],   # 음수 -> 0으로 보정 대상
            "inquiries": [5, 10, 0, 1],
            "conversions": [2, 3, 0, 1],
            "cost": [100000, "", 50000, 10000],  # 빈칸 -> 0으로 채움
            "revenue": [300000, 400000, 0, 50000],
        }
    )


@pytest.fixture
def clean_frame(raw_frame) -> pd.DataFrame:
    """전처리를 끝낸 데이터. 집계 함수 테스트에 사용합니다."""
    from src import data_loader

    cleaned, _ = data_loader.clean_data(raw_frame)
    return cleaned
