MOCK_DATABASE = {
    "user_101": {"items": [{"id": "item_1", "price": 25.0}, {"id": "item_2", "price": 40.0}]},
    "user_102": {"items": [{"id": "item_3", "price": 15.5}]}
}

def get_user_cart(user_id: str):
    return MOCK_DATABASE.get(user_id, None)
