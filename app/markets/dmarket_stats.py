from __future__ import annotations

import logging
import asyncio
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
    stats_only = True
    MARKET_ITEMS_ENDPOINT = "/exchange/v1/market/items"
    CSGO_GAME_ID = "a8db"

    def __init__(
        self,
        base_url: str = "https://api.dmarket.com",
        limit: int = 50,
        currency: str = "USD",
        tracked_titles: list[str] | None = None,
        market_pages: int = 3,
        title_query_limit: int = 3,
        search_concurrency: int = 8,
        title_search_delay_seconds: float = 0.25,
        timeout_seconds: float = 20.0,
    ) -> None:
        super().__init__(api_key="", timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self.limit = max(1, min(limit, 100))
        self.currency = currency.upper()
        self.tracked_titles = tracked_titles or []
        self.dynamic_titles: list[str] = []
        self.market_pages = max(1, min(market_pages, 20))
        self.title_query_limit = max(1, min(title_query_limit, 20))
        self.search_concurrency = max(1, min(search_concurrency, 20))
        self.title_search_delay_seconds = max(0.0, min(title_search_delay_seconds, 5.0))
        if self.currency != "USD":
            logger.warning("DMarket stats connector supports USD only for RUB conversion; forcing USD")
            self.currency = "USD"

    def set_dynamic_titles(self, titles: list[str]) -> None:
        seen: set[str] = set()
        dynamic_titles: list[str] = []
        for title in titles:
            clean = title.strip()
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            dynamic_titles.append(clean)
        self.dynamic_titles = dynamic_titles

    @async_retry(attempts=3, retry_exceptions=(httpx.HTTPError,))
    async def _get_json(self, endpoint: str, params: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()

    async def fetch_listings(self) -> list[MarketListing]:
        listings = await self._fetch_market_pages()
        seen_ids = {listing.id for listing in listings}
        titles = self._combined_titles()

        async def fetch_title(title: str) -> list[MarketListing]:
            return await self._fetch_page(title=title, limit=self.title_query_limit)

        semaphore = asyncio.Semaphore(self.search_concurrency)

        async def guarded_fetch(title: str) -> list[MarketListing]:
            async with semaphore:
                if self.title_search_delay_seconds:
                    await asyncio.sleep(self.title_search_delay_seconds)
                return await fetch_title(title)

        for rows in await asyncio.gather(*(guarded_fetch(title) for title in titles)):
            for listing in rows:
                if listing.id in seen_ids:
                    continue
                seen_ids.add(listing.id)
                listings.append(listing)
        logger.info(
            "Fetched %s %s listings from base page plus %s title searches",
            len(listings),
            self.market_name,
            len(titles),
        )
        return listings

    async def _fetch_market_pages(self) -> list[MarketListing]:
        listings: list[MarketListing] = []
        seen_ids: set[str] = set()
        cursor: str | None = None
        for _ in range(self.market_pages):
            data = await self._fetch_raw_page(limit=self.limit, cursor=cursor)
            raw_items = data.get("objects", []) if isinstance(data, dict) else []
            for item in raw_items:
                listing = self._parse_item(item)
                if listing is None or listing.id in seen_ids:
                    continue
                seen_ids.add(listing.id)
                listings.append(listing)
            next_cursor = data.get("cursor") if isinstance(data, dict) else None
            if not next_cursor or next_cursor == cursor:
                break
            cursor = str(next_cursor)
        return listings

    def _combined_titles(self) -> list[str]:
        seen: set[str] = set()
        titles: list[str] = []
        for title in [*self.dynamic_titles, *self.tracked_titles]:
            clean = title.strip()
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            titles.append(clean)
        return titles

    async def _fetch_page(self, title: str | None = None, limit: int | None = None) -> list[MarketListing]:
        data = await self._fetch_raw_page(title=title, limit=limit)
        raw_items = data.get("objects", []) if isinstance(data, dict) else []
        return [listing for item in raw_items if (listing := self._parse_item(item)) is not None]

    async def _fetch_raw_page(
        self,
        title: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Any:
        params = {
            "gameId": self.CSGO_GAME_ID,
            "currency": self.currency,
            "limit": limit or self.limit,
            "orderBy": "price",
            "orderDir": "asc",
        }
        if title:
            params["title"] = title
        if cursor:
            params["cursor"] = cursor
        try:
            return await self._get_json(self.MARKET_ITEMS_ENDPOINT, params=params)
        except Exception as exc:
            logger.warning("DMarket stats request failed for title=%s: %s", title or "*", exc)
            return {}

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
            raw_payload={"stats_only": self.stats_only, **item},
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


class DMarketConnector(DMarketStatsConnector):
    market_name = "DMarket"
    stats_only = False
