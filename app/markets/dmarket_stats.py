from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import httpx

from app.markets.base import BaseMarketConnector, MarketFees, MarketListing
from app.normalizer.item_normalizer import detect_category, detect_weapon_type, extract_exterior, normalize_item_name
from app.utils.money import to_decimal
from app.utils.retry import async_retry
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class DMarketStatsConnector(BaseMarketConnector):
    market_name = "DMarket.Stats"
    MARKET_ITEMS_ENDPOINT = "/exchange/v1/market/items"
    CSGO_GAME_ID = "a8db"

    def __init__(
        self,
        base_url: str = "https://api.dmarket.com",
        limit: int = 50,
        currency: str = "USD",
        timeout_seconds: float = 20.0,
    ) -> None:
        super().__init__(api_key="", timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self.limit = max(1, min(limit, 100))
        self.currency = currency.upper()
        if self.currency != "USD":
            logger.warning("DMarket stats connector supports USD only for RUB conversion; forcing USD")
            self.currency = "USD"

    @async_retry(attempts=3, retry_exceptions=(httpx.HTTPError,))
    async def _get_json(self, endpoint: str, params: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()

    async def fetch_listings(self) -> list[MarketListing]:
        params = {
            "gameId": self.CSGO_GAME_ID,
            "currency": self.currency,
            "limit": self.limit,
            "orderBy": "price",
            "orderDir": "asc",
        }
        try:
            data = await self._get_json(self.MARKET_ITEMS_ENDPOINT, params=params)
        except Exception as exc:
            logger.warning("DMarket stats request failed: %s", exc)
            return []

        raw_items = data.get("objects", []) if isinstance(data, dict) else []
        listings = [listing for item in raw_items if (listing := self._parse_item(item)) is not None]
        logger.info("Fetched %s DMarket stats listings", len(listings))
        return listings

    async def get_fees(self) -> MarketFees:
        return MarketFees(market_name=self.market_name, buy_fee_percent=Decimal("0"), sell_fee_percent=Decimal("5"))

    def _parse_item(self, item: dict[str, Any]) -> MarketListing | None:
        title = str(item.get("title") or item.get("extra", {}).get("name") or "").strip()
        price = self._extract_usd_price(item)
        if not title or price <= 0:
            return None

        extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
        normalized = normalize_item_name(title)
        listing_id = str(item.get("itemId") or item.get("offerId") or item.get("slug") or normalized)
        stickers = extra.get("stickers") if isinstance(extra.get("stickers"), list) else None

        return MarketListing(
            id=listing_id,
            market_name=self.market_name,
            item_name=title,
            normalized_name=normalized,
            exterior=extract_exterior(normalized) or extra.get("exterior"),
            weapon_type=detect_weapon_type(normalized),
            category=extra.get("category") or detect_category(normalized),
            is_stattrak="StatTrak" in normalized,
            is_souvenir=normalized.startswith("Souvenir"),
            float_value=float(extra["floatValue"]) if extra.get("floatValue") is not None else None,
            stickers=stickers,
            price=price,
            currency="USD",
            price_usd=price,
            available=bool(item.get("inMarket", True)),
            tradable=bool(extra.get("tradable", True)) if extra else None,
            inspect_link=extra.get("inspectInGame") or extra.get("viewAtSteam"),
            created_at=utc_now(),
            raw_payload={"stats_only": True, **item},
        )

    def _extract_usd_price(self, item: dict[str, Any]) -> Decimal:
        for field in ("price", "instantPrice", "suggestedPrice"):
            value = item.get(field)
            if isinstance(value, dict) and value.get("USD") is not None:
                return self._coin_to_usd(value["USD"])
        return Decimal("0")

    @staticmethod
    def _coin_to_usd(value: Any) -> Decimal:
        text = str(value)
        amount = to_decimal(text)
        if "." in text:
            return amount
        return amount / Decimal("100")
