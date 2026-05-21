from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import RealTradingDisabledError
from app.markets.types import MarketBalance, MarketOffer
from app.normalizer.item_normalizer import extract_exterior, normalize_item_name
from app.utils.money import quantize_money, to_decimal
from app.utils.retry import async_retry

logger = logging.getLogger(__name__)


class DMarketClient:
    """Read-only DMarket client.

    The public market feed is implemented defensively. Authenticated buy calls are
    intentionally left as a guarded extension point because DMarket signing and
    production order flow should be wired only after manual verification.
    """

    CSGO_GAME_ID = "a8db"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.dmarket_api_base_url.rstrip("/")
        self.api_key = settings.dmarket_public_or_api_key
        self.api_secret = settings.dmarket_secret_or_legacy_key

    async def fetch_offers(self) -> list[MarketOffer]:
        if self.settings.use_mock_markets:
            return self._mock_offers()

        params = {
            "gameId": self.CSGO_GAME_ID,
            "currency": "USD",
            "limit": min(max(self.settings.dmarket_stats_limit, 1), 100),
            "orderBy": "price",
            "orderDir": "asc",
        }
        data = await self._get_json(self.settings.dmarket_items_endpoint, params=params)
        raw_items = data.get("objects", []) if isinstance(data, dict) else []
        offers = [offer for item in raw_items if (offer := self._parse_offer(item)) is not None]
        logger.info("DMarket returned %s offers", len(offers))
        return offers

    async def get_balance(self) -> MarketBalance:
        if not self.api_key or not self.api_secret:
            return MarketBalance(market_name="DMarket")
        logger.info("DMarket balance endpoint is not configured in MVP; returning empty balance")
        return MarketBalance(market_name="DMarket")

    async def buy_item(self, listing_id: str) -> None:
        raise RealTradingDisabledError(
            "DMarket real buy is not implemented. Add signed endpoint support after manual review."
        )

    @async_retry(attempts=3, retry_exceptions=(httpx.HTTPError,))
    async def _get_json(self, endpoint: str, params: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(endpoint, params=params)
            if response.status_code in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            response.raise_for_status()
            return response.json()

    def _parse_offer(self, item: dict[str, Any]) -> MarketOffer | None:
        title = str(item.get("title") or item.get("marketHashName") or item.get("extra", {}).get("name") or "").strip()
        if not title:
            return None
        price_usd = self._extract_usd_price(item)
        if price_usd <= 0:
            return None
        price_rub = quantize_money(price_usd * self.settings.manual_rub_usd_rate)
        extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
        normalized = normalize_item_name(title)
        listing_id = str(item.get("itemId") or item.get("offerId") or item.get("assetId") or normalized)
        float_value = None
        if extra.get("floatValue") is not None:
            float_value = to_decimal(extra.get("floatValue"))
        return MarketOffer(
            listing_id=listing_id,
            item_name=title,
            market_hash_name=normalized,
            price=price_usd,
            currency="USD",
            price_rub=price_rub,
            exterior=extract_exterior(normalized) or extra.get("exterior"),
            is_stattrak="StatTrak" in normalized,
            float_value=float_value,
            raw_payload=item,
        )

    @staticmethod
    def _extract_usd_price(item: dict[str, Any]) -> Decimal:
        for field in ("price", "instantPrice", "suggestedPrice"):
            value = item.get(field)
            if isinstance(value, dict) and value.get("USD") is not None:
                return DMarketClient._coin_to_usd(value["USD"])
            if field == "price" and value is not None and not isinstance(value, dict):
                return DMarketClient._coin_to_usd(value)
        return Decimal("0")

    @staticmethod
    def _coin_to_usd(value: Any) -> Decimal:
        text = str(value)
        amount = to_decimal(text)
        return amount if "." in text else amount / Decimal("100")

    def _mock_offers(self) -> list[MarketOffer]:
        return [
            MarketOffer(
                listing_id="mock-dmarket-ak-redline",
                item_name="AK-47 | Redline (Field-Tested)",
                market_hash_name="AK-47 | Redline (Field-Tested)",
                price=Decimal("12.00"),
                currency="USD",
                price_rub=Decimal("1200"),
                exterior="Field-Tested",
                raw_payload={"mock": True},
            ),
            MarketOffer(
                listing_id="mock-dmarket-awp-asiimov",
                item_name="AWP | Asiimov (Field-Tested)",
                market_hash_name="AWP | Asiimov (Field-Tested)",
                price=Decimal("80.00"),
                currency="USD",
                price_rub=Decimal("8000"),
                exterior="Field-Tested",
                raw_payload={"mock": True},
            ),
        ]
