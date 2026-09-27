from sample_app.analytics_service import calculate_average_order


def test_average_order_normal():
    """Normal path: non-zero order count → correct average."""
    assert calculate_average_order(500.0, 5) == 100.0


def test_average_order_zero_count():
    """Bug reproduction: order_count == 0 → ZeroDivisionError."""
    # Fixed behaviour: should return 0.0 instead of raising
    result = calculate_average_order(500.0, 0)
    assert result == 0.0
