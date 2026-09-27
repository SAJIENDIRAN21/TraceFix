from sample_app.pricing_service import apply_discount


def test_apply_discount_with_rate():
    """Normal path: both keys present → correct discount amount."""
    result = apply_discount({"discount_rate": 0.1, "base_amount": 200.0})
    assert result == 20.0


def test_apply_discount_missing_key():
    """Bug reproduction: missing 'discount_rate' → KeyError."""
    # Fixed behaviour: should return 0.0 when discount_rate is absent
    result = apply_discount({"base_amount": 200.0})
    assert result == 0.0
