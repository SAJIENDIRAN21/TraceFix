from sample_app.cart_service import calculate_cart_total

def test_existing_user_cart():
    assert calculate_cart_total("user_101") == 65.0

def test_nonexistent_user_cart():
    assert calculate_cart_total("user_999") == 0.0
