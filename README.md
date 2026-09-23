
# 마케팅 성과 분석 대시보드

마케팅 CSV를 업로드하면 KPI 집계·전기 대비 증감·채널/콘텐츠 비교·요약 리포트 생성을 자동으로 처리하는 대시보드

![tests](https://github.com/taebin0520-sys/marketing-performance-dashboard/actions/workflows/tests.yml/badge.svg)

**🚀 [라이브 데모 바로가기](https://taebin0520-sys-marketing-performance-dashboard-app-30zb6r.streamlit.app)** — 설치 없이 브라우저에서 확인할 수 있습니다.

> 무료 티어 배포라 앱이 슬립 상태면 첫 접속에 수십 초가 걸릴 수 있습니다.

**데이터 검증 결과와 핵심 지표 요약** — 직전 동일 기간 대비 증감을 함께 표시합니다.

![데이터 검증 결과와 핵심 지표 요약](docs/images/01_overview.png)

**효율 지표** — CPA는 값이 낮아지는 것이 개선이므로 감소를 초록색으로 표시합니다.

![CTR·문의율·전환율·CPA·ROAS 효율 지표](docs/images/02_kpi_efficiency.png)

**자동 요약 리포트** — 규칙 기반으로 생성하며 생성형 AI를 쓰지 않습니다.

![자동 요약 리포트](docs/images/03_report.png)

---

## 이 프로젝트에서 보여주고 싶은 것

1. **지표 계산의 정확성** — 비율 KPI를 행별 평균이 아니라 `합계 ÷ 합계`로 계산하고, 0으로 나누는 경우를 `None`으로 처리하며, 상대 증감률(%)과 퍼센트포인트(%p)를 구분해 표기했습니다.
2. **관찰과 제안을 분리한 자동 리포트** — 규칙 기반으로 문장을 만들되 "예산을 늘려야 한다"처럼 단정하지 않고, 관찰된 사실과 확인이 필요한 항목을 나눠 씁니다.
3. **계산 결과를 테스트로 고정** — pytest 108개와 GitHub Actions CI로 지표 계산과 표현 규칙이 깨지지 않는지 자동 검증합니다.

---

## 제작 방식

코드 구현에는 AI IDE(Kiro)를 사용했습니다. 제가 맡은 부분은 아래와 같습니다.

- **분석 요구사항과 KPI 정의 결정** — 어떤 지표를 쓸지, 비율을 어떤 기준으로 계산할지(합계 기준), 비교 기간을 어떻게 잡을지 정했습니다.
- **결과 검증** — 로컬에서 `pytest`와 `streamlit run`을 실행하고, 화면 KPI가 맞는지 `scripts/verify_kpi.py`로 **대시보드 코드를 쓰지 않고 원본 CSV에서 다시 계산해** 대조했습니다. ([검산 방법](docs/testing-and-verification.md#검산--대시보드-숫자를-다른-방법으로-다시-계산))
- **문서와 실제 동작 대조** — README 설명이 실제 코드·테스트 결과와 일치하는지 점검하고 수정 범위를 지정했습니다.
- **배포 및 저장소 설정** — Streamlit Community Cloud 배포, default branch 정리, topics 설정을 진행했습니다.

---

## 샘플 데이터 안내

이 저장소의 데이터는 스크립트로 생성한 **가상 데이터**이며, 대시보드 기능을 검증하기 위해 주말 성과 하락·8월 중순 급증 같은 패턴을 의도적으로 넣었습니다.

따라서 아래에 나오는 채널별 수치는 **실제 마케팅 성과가 아니라 기능 시연용 값**입니다.

---

## 문서

- [프로젝트 개요](docs/features.md#프로젝트-개요)
- [구현된 기능](docs/features.md#구현된-기능)
- [화면 구성](docs/features.md#화면-구성)
- [결과 다운로드](docs/features.md#결과-다운로드)
- [다음 단계 (제안)](docs/features.md#다음-단계-제안)
- [입력 CSV 스키마](docs/csv-schema.md)
- [KPI 정의](docs/kpi-definitions.md)
- [전기 대비 증감](docs/period-comparison.md)
- [자동 요약 리포트](docs/auto-report.md)
- [샘플 데이터](docs/sample-data.md)
- [테스트](docs/testing-and-verification.md)
- [데이터 처리에 관한 전제](docs/data-assumptions.md)
- [수동 QA 확인 항목](docs/manual-qa.md)

---

## 빠른 시작

```bash
# 1) 가상환경 (선택)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2) 패키지 설치
pip install -r requirements.txt

# 3) 샘플 데이터 생성 (저장소에 이미 포함되어 있으므로 건너뛰어도 됩니다)
python scripts/generate_sample_data.py

# 4) 대시보드 실행
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 이 열립니다.
**CSV를 업로드하지 않아도** 샘플 데이터로 모든 기능이 바로 동작합니다.

```bash
# 테스트 실행 (프로젝트 루트에서)
pytest -v
```

---

## 폴더 구조

```
marketing-performance-dashboard/
├── app.py                        # Streamlit 화면 구성 및 입력·분석 흐름 연결
├── conftest.py                   # pytest가 src/를 찾을 수 있게 경로 설정
├── src/
│   ├── config.py                 # 컬럼 정의, 한국어 라벨, 지표 표시 형식
│   ├── data_loader.py            # CSV 읽기 · 검증 · 전처리 · 필터
│   ├── kpi.py                    # KPI 계산 (안전한 나눗셈 포함)
│   ├── analysis.py               # 기간/채널/콘텐츠 집계, TOP N, 전기 대비 증감
│   ├── charts.py                 # Plotly 차트 생성
│   ├── report.py                 # 규칙 기반 자동 요약 리포트 생성 (LLM 미사용)
│   └── formatting.py             # 숫자 표시 형식(콤마,%,원,배) + 다운로드 파일명 생성
├── data/sample_marketing_data.csv
├── scripts/
│   ├── generate_sample_data.py   # 표준 라이브러리만으로 샘플 데이터 생성
│   └── verify_kpi.py             # src/를 쓰지 않고 CSV에서 KPI를 재계산하는 검산용
├── tests/                        # pytest 테스트 (108개)
├── requirements.txt
└── README.md
```

### 설계 원칙

1. **`src/`는 `streamlit`을 import하지 않습니다.** 계산 로직이 화면에 묶이면 테스트할 수 없기 때문입니다.
2. 모든 분석 함수는 `DataFrame in → DataFrame/dict out` 형태입니다. 조합과 테스트가 쉬워집니다.
3. 파일은 **역할당 1개**까지만 나눴습니다. 클래스·상속·추상 레이어는 사용하지 않았습니다.
4. `report.py`는 **생성형 AI를 전혀 사용하지 않습니다.** 이미 계산된 결과를 규칙(if/else)으로 문장 틀에 끼워 넣는 방식이라, 같은 데이터면 항상 같은 문장이 나오고 테스트로 검증할 수 있습니다.

---

## 알려진 한계

- 현재는 **단일 CSV 파일** 기준입니다. DB나 광고 플랫폼 API 연동은 없습니다.
- 자동 요약 리포트는 항상 **전환(conversions)** 기준으로 통일되어 있습니다. 탭에서 다른 지표를 선택해도 리포트 내용은 바뀌지 않습니다.
- 리포트는 규칙 기반이라 **데이터에 없는 맥락(시즌 이벤트, 경쟁사 동향 등)은 반영하지 못합니다.** 제안 문장을 결론이 아니라 점검 출발점으로 읽어야 합니다.
- Streamlit Community Cloud 무료 티어 배포이므로, 장시간 미사용 시 앱이 슬립 상태가 되어 첫 접속 시 재시작 로딩이 몇십 초 걸릴 수 있습니다.

---

## 데이터 관련 고지

이 저장소의 모든 데이터는 스크립트로 생성한 **가상 데이터**입니다.
실제 회사·고객·개인정보는 포함되어 있지 않습니다.
`.gitignore`에서 `data/sample_marketing_data.csv` 외의 CSV 커밋을 차단해, 실제 데이터가 실수로 올라가는 것을 막았습니다.
