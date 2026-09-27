from sample_app.db import get_user_cart

def calculate_cart_total(user_id: str) -> float:
    cart = get_user_cart(user_id)
    total = 0.0
    for item in cart["items"]:
        total += item["price"]
    return total
