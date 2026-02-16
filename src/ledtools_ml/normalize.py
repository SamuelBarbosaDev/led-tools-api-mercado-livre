
def normalize_item(it: dict) -> dict:
    pics = it.get("pictures") or []
    picture_url = None
    if pics and isinstance(pics, list):
        first = pics[0]
        if isinstance(first, dict):
            picture_url = first.get("url")

    if not picture_url:
        picture_url = it.get("thumbnail")

    shipping = it.get("shipping") or {}

    return {
        "id": it.get("id"),
        "title": it.get("title"),
        "price": it.get("price"),
        "sold_quantity": it.get("sold_quantity"),
        "available_quantity": it.get("available_quantity"),
        "permalink": it.get("permalink"),
        "picture_url": picture_url,
        "free_shipping": shipping.get("free_shipping"),
        "logistic_type": shipping.get("logistic_type"),
    }
