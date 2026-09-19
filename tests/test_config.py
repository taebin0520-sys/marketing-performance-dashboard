"""설정값 및 지표 방향성 테스트.

핵심은 "비용 지표는 감소가 개선"이라는 규칙이 코드로 고정되어 있는지 확인하는 것입니다.
이 규칙이 깨지면 화면에서 CPA 개선(-11%)이 빨간색(악화)으로 표시되어
보는 사람에게 정반대 신호를 줍니다.
"""

from src import config


def test_cost_metrics_use_inverse_color():
    """CPA, CPC는 값이 낮아지는 것이 개선이므로 색 방향이 inverse여야 합니다."""
    assert config.get_delta_color("cpa") == "inverse"
    assert config.get_delta_color("cpc") == "inverse"


def test_volume_and_efficiency_metrics_use_normal_color():
    """전환/클릭/ROAS 등은 값이 커지는 것이 개선이므로 기본(normal) 방향입니다."""
    for metric in ["conversions", "clicks", "views", "reach", "inquiries",
                   "ctr", "inquiry_rate", "conversion_rate", "roas"]:
        assert config.get_delta_color(metric) == "normal", metric


def test_unknown_metric_defaults_to_normal():
    """정의되지 않은 지표가 들어와도 에러 없이 기본값을 돌려줘야 합니다."""
    assert config.get_delta_color("some_new_metric") == "normal"


def test_lower_is_better_list_contains_only_cost_metrics():
    """'낮을수록 좋은 지표' 목록에 비용 지표만 들어있는지 확인합니다.

    실수로 전환율 같은 지표가 이 목록에 들어가면 색상이 뒤집혀 표시됩니다.
    """
    assert set(config.LOWER_IS_BETTER_METRICS) == {"cpc", "cpa"}
