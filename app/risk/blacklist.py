from __future__ import annotations

FORBIDDEN_MARKETS = {"cs.money", "csmoney", "cs money", "white.market", "white market"}

DEFAULT_ITEM_BLACKLIST: set[str] = set()
DEFAULT_MARKET_PAIR_BLACKLIST: set[tuple[str, str]] = set()


def is_forbidden_market(market_name: str) -> bool:
    return market_name.strip().lower() in FORBIDDEN_MARKETS


def normalize_pair(buy_market: str, sell_market: str) -> tuple[str, str]:
    return buy_market.strip().lower(), sell_market.strip().lower()

