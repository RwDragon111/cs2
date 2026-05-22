from __future__ import annotations

from urllib.parse import quote

from app.normalizer.item_normalizer import detect_weapon_type, normalize_item_name
from app.utils.item_titles import strip_decorative_star


def dmarket_item_url(item_name: str) -> str:
    title = strip_decorative_star(normalize_item_name(item_name))
    return "https://dmarket.com/ru/ingame-items/item-list/csgo-skins?title=" + quote(title)


def csgo_market_item_url(item_name: str) -> str:
    title = normalize_item_name(item_name)
    weapon = detect_weapon_type(title)
    if weapon and title.startswith("★") and "Knife" in weapon:
        return "https://market.csgo.com/ru/Knife/" + quote(weapon) + "/" + quote(title)
    return "https://market.csgo.com/ru/?search=" + quote(title)


def deal_links_text(item_name: str) -> str:
    return "\n".join(
        [
            "Ссылки:",
            f"DMarket: {dmarket_item_url(item_name)}",
            f"CSGO Market: {csgo_market_item_url(item_name)}",
        ]
    )
