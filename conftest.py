"""pytest 실행 준비 파일.

pytest는 tests/ 폴더를 기준으로 코드를 찾기 때문에
`from src import ...` 가 바로 동작하지 않을 수 있습니다.
프로젝트 루트를 파이썬 모듈 검색 경로에 추가해 이 문제를 막습니다.

이 파일이 있으면 프로젝트 루트에서 `pytest` 만 입력해도 테스트가 돌아갑니다.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
