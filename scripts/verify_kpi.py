"""대시보드가 계산한 KPI가 맞는지 '독립적으로' 다시 계산해 검산하는 스크립트.

실행:
    python scripts/verify_kpi.py                       # 대시보드 기본 기간(최근 28일)
    python scripts/verify_kpi.py 2026-08-01 2026-08-31 # 기간 직접 지정

왜 이 스크립트가 필요한가
-------------------------
"대시보드 숫자가 맞는지 확인했다"고 말하려면, 확인하는 방법이 검증 대상과
달라야 합니다. src/kpi.py 의 함수를 다시 호출해서 비교하면
같은 계산식을 두 번 실행하는 것이므로, 그 계산식 자체가 틀렸을 때
똑같이 틀린 값이 나와 검산이 되지 않습니다.

그래서 이 스크립트는 의도적으로 아래 원칙을 지킵니다.

1) src/ 의 어떤 함수도 import 하지 않습니다. (pandas도 쓰지 않습니다)
2) 표준 라이브러리 csv 로 원본 CSV를 직접 읽고, 합계와 비율을 처음부터 다시 계산합니다.
3) 계산 결과를 화면에 출력해, 사용자가 대시보드 화면 값과 눈으로 대조할 수 있게 합니다.

즉 "같은 답을 다른 길로 구해서 맞는지 본다"는 것이 이 스크립트의 목적입니다.

검산 대상 규칙
-------------
- 비율 지표는 '합계 ÷ 합계' (행별 비율의 평균이 아님)
- 광고비가 0원이면 CPC/CPA 는 계산 불가로 처리
- 전기 대비 증감은 '같은 길이의 직전 기간'과 비교
- 증감률은 (현재 - 이전) / 이전  = 상대 증감률(%)  (퍼센트포인트가 아님)
"""

import csv
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

# 원본 데이터 경로 (scripts/ 의 부모 폴더가 프로젝트 루트)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "sample_marketing_data.csv"

# 합계로 구하는 지표들
SUM_COLUMNS = [
    "impressions", "reach", "views", "clicks", "inquiries", "conversions",
    "cost", "revenue",
]

# 대시보드 기본 분석 기간 길이 (app.py 와 동일: 최근 4주 = 28일)
DEFAULT_PERIOD_DAYS = 28


def load_rows():
    """CSV를 표준 라이브러리로 읽어 행 목록을 돌려줍니다.

    encoding='utf-8-sig' 를 쓰는 이유: 파일 맨 앞에 BOM이 있어서
    그냥 utf-8로 읽으면 첫 컬럼명이 '\ufeffdate' 가 되어 키를 못 찾습니다.
    """
    with DATA_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_int(value):
    """빈 칸과 소수점을 안전하게 정수로 바꿉니다.

    대시보드는 빈 칸을 0으로 채우므로(미집계로 간주), 검산도 같은 전제를 씁니다.
    전제가 다르면 숫자가 달라지는 게 당연하므로, 전제만은 일치시켜야 합니다.
    """
    if value is None or value == "":
        return 0
    return int(float(value))


def filter_rows(rows, start, end):
    """기간으로 행을 걸러냅니다. (양쪽 끝 포함)"""
    start_text, end_text = start.isoformat(), end.isoformat()
    return [r for r in rows if start_text <= r["date"] <= end_text]


def sum_metrics(rows):
    """합계 지표를 더합니다."""
    totals = Counter()
    for row in rows:
        for column in SUM_COLUMNS:
            totals[column] += to_int(row.get(column))
    return totals


def safe_divide(numerator, denominator):
    """0으로 나누기를 막습니다. 계산 불가면 None."""
    if not denominator:
        return None
    return numerator / denominator


def calculate_ratios(totals):
    """비율 지표를 '합계 ÷ 합계'로 계산합니다.

    행별로 비율을 구해 평균내지 않는 이유:
    노출 10회에 클릭 1회(10%)인 행과 노출 10,000회에 클릭 100회(1%)인 행이 있을 때
    행별 평균은 5.5%가 되어 규모가 작은 행의 극단값이 전체를 부풀립니다.
    합계 기준으로는 101 / 10,010 = 약 1.01% 로 실제 성과가 나옵니다.
    """
    cost = totals["cost"]
    return {
        "ctr": safe_divide(totals["clicks"], totals["impressions"]),
        "inquiry_rate": safe_divide(totals["inquiries"], totals["clicks"]),
        "conversion_rate": safe_divide(totals["conversions"], totals["clicks"]),
        # 광고비가 0원이면 '클릭당 비용'이라는 개념 자체가 없으므로 None
        "cpc": safe_divide(cost, totals["clicks"]) if cost else None,
        "cpa": safe_divide(cost, totals["conversions"]) if cost else None,
        "roas": safe_divide(totals["revenue"], cost),
    }


def format_value(metric, value):
    """지표에 맞는 표시 형식으로 바꿉니다. (대시보드 화면과 같은 형태)"""
    if value is None:
        return "-"
    if metric in ("ctr", "inquiry_rate", "conversion_rate"):
        return "{:.2f}%".format(value * 100)
    if metric in ("cpc", "cpa", "cost", "revenue"):
        return "{:,.0f}원".format(value)
    if metric == "roas":
        return "{:.2f}배".format(value)
    return "{:,}".format(int(value))


def relative_change(current, previous):
    """상대 증감률 = (현재 - 이전) / 이전.

    퍼센트포인트와 혼동하지 않도록 주의합니다.
    CTR 3.22% -> 3.43% 는 상대 +6.5% 이고, 퍼센트포인트로는 +0.21%p 입니다.
    """
    if current is None or previous is None or not previous:
        return None
    return (current - previous) / previous


def print_section(title):
    print("\n" + "=" * 62)
    print(title)
    print("=" * 62)


def main():
    rows = load_rows()
    all_dates = sorted({r["date"] for r in rows})
    data_start = date.fromisoformat(all_dates[0])
    data_end = date.fromisoformat(all_dates[-1])

    # 기간 결정: 인자로 받거나, 없으면 대시보드 기본값(최근 28일)
    if len(sys.argv) == 3:
        start = date.fromisoformat(sys.argv[1])
        end = date.fromisoformat(sys.argv[2])
    else:
        end = data_end
        start = max(data_start, end - timedelta(days=DEFAULT_PERIOD_DAYS - 1))

    # 같은 길이의 직전 기간 (대시보드의 '전기 대비 증감'과 동일한 방식)
    period_days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)

    current_rows = filter_rows(rows, start, end)
    previous_rows = filter_rows(rows, previous_start, previous_end)

    print_section("독립 검산 결과 (src/ 코드를 쓰지 않고 CSV에서 재계산)")
    print("원본 데이터   : {} ({:,}행, {} ~ {})".format(
        DATA_PATH.name, len(rows), data_start, data_end))
    print("분석 기간     : {} ~ {}  ({}일, {:,}행)".format(
        start, end, period_days, len(current_rows)))
    if previous_rows and previous_start >= data_start:
        print("비교 기간     : {} ~ {}  ({}일, {:,}행)".format(
            previous_start, previous_end, period_days, len(previous_rows)))
    else:
        print("비교 기간     : 없음 (데이터 시작일보다 이전이라 비교 불가)")

    totals = sum_metrics(current_rows)
    ratios = calculate_ratios(totals)

    has_previous = bool(previous_rows) and previous_start >= data_start
    if has_previous:
        previous_totals = sum_metrics(previous_rows)
        previous_ratios = calculate_ratios(previous_totals)
    else:
        previous_totals, previous_ratios = Counter(), {}

    print_section("KPI (대시보드 화면 값과 대조하세요)")
    print("{:<16}{:>16}{:>16}{:>12}".format("지표", "이번 기간", "직전 기간", "상대 증감"))
    print("-" * 62)

    display_order = [
        ("views", "조회수"), ("reach", "도달"), ("clicks", "클릭"),
        ("inquiries", "문의"), ("conversions", "전환"),
        ("impressions", "노출"), ("cost", "광고비"), ("revenue", "매출"),
    ]
    for metric, label in display_order:
        current = totals[metric]
        previous = previous_totals.get(metric) if has_previous else None
        change = relative_change(current, previous)
        print("{:<16}{:>16}{:>16}{:>12}".format(
            label,
            format_value(metric, current),
            format_value(metric, previous) if has_previous else "-",
            "{:+.1f}%".format(change * 100) if change is not None else "-",
        ))

    print("-" * 62)
    ratio_order = [
        ("ctr", "CTR"), ("inquiry_rate", "문의율"), ("conversion_rate", "전환율"),
        ("cpc", "CPC"), ("cpa", "CPA"), ("roas", "ROAS"),
    ]
    for metric, label in ratio_order:
        current = ratios[metric]
        previous = previous_ratios.get(metric) if has_previous else None
        change = relative_change(current, previous)
        print("{:<16}{:>16}{:>16}{:>12}".format(
            label,
            format_value(metric, current),
            format_value(metric, previous) if has_previous else "-",
            "{:+.1f}%".format(change * 100) if change is not None else "-",
        ))

    # 비율 지표는 퍼센트포인트도 함께 보여줍니다. (상대 증감률과 혼동 방지)
    if has_previous:
        print_section("비율 지표: 상대 증감률(%) vs 퍼센트포인트(%p)")
        print("같은 변화를 두 방식으로 표현한 것이며, 값이 다릅니다.")
        print()
        for metric, label in [("ctr", "CTR"), ("inquiry_rate", "문의율"),
                               ("conversion_rate", "전환율")]:
            current, previous = ratios[metric], previous_ratios[metric]
            if current is None or previous is None:
                continue
            change = relative_change(current, previous)
            print("  {:<8} {} → {}   상대 {:+.1f}%   포인트 {:+.2f}%p".format(
                label,
                format_value(metric, previous),
                format_value(metric, current),
                change * 100,
                (current - previous) * 100,
            ))

    print_section("퍼널 순서 점검")
    funnel = ["impressions", "reach", "views", "clicks", "inquiries", "conversions"]
    violations = 0
    for row in current_rows:
        values = [to_int(row.get(c)) for c in funnel]
        if any(values[i] < values[i + 1] for i in range(len(values) - 1)):
            violations += 1
    print("노출 >= 도달 >= 조회수 >= 클릭 >= 문의 >= 전환 규칙 위반 행: {}건".format(violations))

    print()
    print("검산 완료. 위 값이 대시보드 화면과 다르면 어느 쪽이 틀렸는지 확인이 필요합니다.")


if __name__ == "__main__":
    main()
