from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import RealTradingDisabledError
from app.currency.rate_provider import CurrencyRateProvider
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

    def __init__(self, settings: Settings, rate_provider: CurrencyRateProvider | None = None) -> None:
        self.settings = settings
        self.base_url = settings.dmarket_api_base_url.rstrip("/")
        self.api_key = settings.dmarket_public_or_api_key
        self.api_secret = settings.dmarket_secret_or_legacy_key
        self.rate_provider = rate_provider or CurrencyRateProvider(settings)
        self._rub_usd_rate = Decimal("0")

    async def fetch_offers(self, titles: list[str] | None = None) -> list[MarketOffer]:
        if self.settings.use_mock_markets:
            return self._mock_offers()

        self._rub_usd_rate = await self.rate_provider.usd_to_rub()
        logger.info("DMarket USD prices will be converted with USD/RUB rate %s", self._rub_usd_rate)
        market_offers = await self._fetch_market_pages()
        if titles:
            targeted_offers = await self._fetch_offers_by_titles(titles)
            offers = self._dedupe_offers([*market_offers, *targeted_offers])
            logger.info(
                "DMarket returned %s offers: %s price-filtered offers plus %s targeted offers for %s titles",
                len(offers),
                len(market_offers),
                len(targeted_offers),
                len(titles),
            )
            return offers

        logger.info("DMarket returned %s price-filtered offers", len(market_offers))
        return market_offers

    async def _fetch_market_pages(self) -> list[MarketOffer]:
        offers: list[MarketOffer] = []
        cursor: str | None = None
        seen: set[str] = set()
        for _ in range(max(1, min(self.settings.dmarket_market_pages, 20))):
            data = await self._fetch_market_page(cursor=cursor)
            raw_items = data.get("objects", []) if isinstance(data, dict) else []
            for item in raw_items:
                offer = self._parse_offer(item)
                if offer is None or offer.listing_id in seen:
                    continue
                seen.add(offer.listing_id)
                offers.append(offer)
            next_cursor = data.get("cursor") if isinstance(data, dict) else None
            if not next_cursor or next_cursor == cursor:
                break
            cursor = str(next_cursor)
        return offers

    async def _fetch_market_page(self, cursor: str | None = None) -> dict[str, Any]:
        params = {
            "gameId": self.CSGO_GAME_ID,
            "currency": "USD",
            "limit": min(max(self.settings.dmarket_stats_limit, 1), 100),
            "orderBy": "price",
            "orderDir": "asc",
            "priceFrom": self._rub_to_usd_cents(self.settings.min_item_price),
            "priceTo": self._rub_to_usd_cents(self.settings.max_item_price),
        }
        if cursor:
            params["cursor"] = cursor
        data = await self._get_json(self.settings.dmarket_items_endpoint, params=params)
        return data if isinstance(data, dict) else {}

    async def _fetch_offers_by_titles(self, titles: list[str]) -> list[MarketOffer]:
        seen_titles: set[str] = set()
        clean_titles: list[str] = []
        for title in titles:
            clean = title.strip()
            key = clean.lower()
            if not clean or key in seen_titles:
                continue
            seen_titles.add(key)
            clean_titles.append(clean)

        semaphore = asyncio.Semaphore(max(1, min(self.settings.dmarket_search_concurrency, 10)))

        async def fetch_title(title: str) -> list[MarketOffer]:
            async with semaphore:
                params = {
                    "gameId": self.CSGO_GAME_ID,
                    "currency": "USD",
                    "limit": max(1, min(self.settings.dmarket_title_query_limit, 20)),
                    "orderBy": "price",
                    "orderDir": "asc",
                    "title": title,
                }
                if self.settings.dmarket_title_search_delay_seconds:
                    await asyncio.sleep(self.settings.dmarket_title_search_delay_seconds)
                try:
                    data = await self._get_json(self.settings.dmarket_items_endpoint, params=params)
                except Exception as exc:
                    logger.warning("DMarket title search failed for %s: %s", title, exc)
                    return []
                raw_items = data.get("objects", []) if isinstance(data, dict) else []
                return [offer for item in raw_items if (offer := self._parse_offer(item)) is not None]

        rows = await asyncio.gather(*(fetch_title(title) for title in clean_titles))
        offers: list[MarketOffer] = []
        seen_offers: set[str] = set()
        for group in rows:
            for offer in group:
                if offer.listing_id in seen_offers:
                    continue
                seen_offers.add(offer.listing_id)
                offers.append(offer)
        return offers

    @staticmethod
    def _dedupe_offers(offers: list[MarketOffer]) -> list[MarketOffer]:
        result: list[MarketOffer] = []
        seen: set[str] = set()
        for offer in offers:
            if offer.listing_id in seen:
                continue
            seen.add(offer.listing_id)
            result.append(offer)
        return result

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
        price_rub = quantize_money(price_usd * self._rub_usd_rate)
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

    def _rub_to_usd_cents(self, value_rub: Decimal) -> int:
        if self._rub_usd_rate <= 0:
            return 0
        usd = to_decimal(value_rub) / self._rub_usd_rate
        return max(0, int(usd * Decimal("100")))

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
