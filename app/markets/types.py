from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class MarketOffer:
    listing_id: str
    item_name: str
    market_hash_name: str
    price: Decimal
    currency: str
    price_rub: Decimal
    exterior: str | None = None
    is_stattrak: bool = False
    float_value: Decimal | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BuyOrder:
    item_name: str
    market_hash_name: str
    price: Decimal
    currency: str
    price_rub: Decimal
    count: int = 1
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PriceHistory:
    avg_7d_price: Decimal | None = None
    avg_30d_price: Decimal | None = None
    sales_7d: int = 0
    sales_30d: int = 0
    min_sell_price: Decimal | None = None
    buy_order_count: int = 0
    is_fallback: bool = False


@dataclass(slots=True)
class MarketBalance:
    market_name: str
    available: Decimal = Decimal("0")
    currency: str = "RUB"
    raw_payload: dict[str, Any] = field(default_factory=dict)
