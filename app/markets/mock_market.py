from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from app.markets.base import Balance, BaseMarketConnector, MarketFees, MarketListing, SaleRecord
from app.normalizer.item_normalizer import detect_category, detect_weapon_type, extract_exterior, normalize_item_name
from app.pricing.fees import get_default_fees
from app.utils.time import utc_now


MOCK_ITEMS = [
    ("AWP | Asiimov (Field-Tested)", Decimal("780"), Decimal("1020")),
    ("AK-47 | Redline (Field-Tested)", Decimal("650"), Decimal("835")),
    ("M4A1-S | Printstream (Minimal Wear)", Decimal("4200"), Decimal("4700")),
    ("Desert Eagle | Printstream (Field-Tested)", Decimal("2400"), Decimal("2750")),
    ("USP-S | Kill Confirmed (Field-Tested)", Decimal("3100"), Decimal("3500")),
]


class MockMarketConnector(BaseMarketConnector):
    def __init__(
        self,
        market_name: str,
        price_side: str,
        api_key: str = "",
        timeout_seconds: float = 20.0,
    ) -> None:
        super().__init__(api_key=api_key, timeout_seconds=timeout_seconds)
        self.market_name = market_name
        self.price_side = price_side

    async def fetch_listings(self) -> list[MarketListing]:
        now = utc_now()
        listings: list[MarketListing] = []
        for index, (name, lis_price, market_price) in enumerate(MOCK_ITEMS):
            price = lis_price if self.price_side == "buy" else market_price
            normalized = normalize_item_name(name)
            listings.append(
                MarketListing(
                    id=f"{self.market_name.lower().replace('.', '-').replace(' ', '-')}-{index}",
                    market_name=self.market_name,
                    item_name=name,
                    normalized_name=normalized,
                    exterior=extract_exterior(normalized),
                    weapon_type=detect_weapon_type(normalized),
                    category=detect_category(normalized),
                    is_stattrak="StatTrak" in normalized,
                    is_souvenir=normalized.startswith("Souvenir"),
                    price=price,
                    currency="RUB",
                    price_rub=price,
                    price_usd=None,
                    available=True,
                    tradable=True,
                    created_at=now,
                    raw_payload={"mock": True, "index": index},
                )
            )
        return listings

    async def fetch_sales_history(self, normalized_name: str) -> list[SaleRecord]:
        now = utc_now()
        records: list[SaleRecord] = []
        base_price = Decimal("1000")
        for name, lis_price, market_price in MOCK_ITEMS:
            if normalize_item_name(name) == normalized_name:
                base_price = market_price if self.price_side != "buy" else lis_price
                break
        for day in range(30):
            for sale_no in range(1 if day > 2 else 3):
                records.append(
                    SaleRecord(
                        market_name=self.market_name,
                        normalized_name=normalized_name,
                        price=base_price,
                        currency="RUB",
                        price_rub=base_price,
                        sold_at=now - timedelta(days=day, hours=sale_no),
                        raw_payload={"mock": True},
                    )
                )
        return records

    async def get_balance(self) -> Balance:
        return Balance(market_name=self.market_name, rub=Decimal("100000"), usd=Decimal("1000"))

    async def get_fees(self) -> MarketFees:
        return get_default_fees(self.market_name)
