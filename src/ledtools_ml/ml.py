from .config import ML_SITE_ID
from .http import request_json

BASE = "https://api.mercadolibre.com"

def list_item_ids_public(seller_id: str):
    data = request_json(
        "GET",
        f"{BASE}/sites/{ML_SITE_ID}/search",
        headers={
            "Accept": "application/json",
            "User-Agent": "list_item_ids_public/1.0",
        },
        params={"seller_id": seller_id, "limit": 50},
    )
    return [r["id"] for r in data.get("results", [])]

def list_item_ids_for_user(user_id: str):
    data = request_json(
        "GET",
        f"{BASE}/users/{user_id}/items/search",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "list_item_ids_for_user/1.0",
        },
        params={"limit": 50},
    )
    return data.get("results", [])

def get_item(item_id: str):
    return request_json(
        "GET",
        f"{BASE}/items/{item_id}",
        headers={
            "Accept": "application/json",
            "User-Agent": "get_item/1.0",
        }
    )

_category_cache: dict[str, str] = {}

def get_category_name(category_id: str) -> str | None:
    if not category_id:
        return None

    if category_id in _category_cache:
        return _category_cache[category_id]

    data = request_json("GET", f"{BASE}/categories/{category_id}")
    name = data.get("name")

    if name:
        _category_cache[category_id] = name

    return name

def get_user_product_stock(user_product_id: str):
    return request_json("GET", f"{BASE}/user-products/{user_product_id}/stock")
