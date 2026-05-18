from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.exceptions import MarketApiError
from app.markets.base import Balance, MarketFees, MarketListing, SaleRecord
from app.markets.base import BaseMarketConnector
from app.normalizer.item_normalizer import detect_category, detect_weapon_type, extract_exterior, normalize_item_name
from app.pricing.fees import get_default_fees
from app.utils.money import to_decimal
from app.utils.retry import async_retry
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class MarketCsgoConnector(BaseMarketConnector):
    market_name = "Market.CSGO"
    PRICES_ENDPOINT = "/api/v2/prices/{currency}.json"
    FULL_EXPORT_ENDPOINT = "/api/full-export/{currency}.json"
    SALES_INDEX_ENDPOINT = "/api/v2/full-history/all.json"
    SALES_ITEM_ENDPOINT = "/api/v2/full-history/{item_id}.json"
    BALANCE_ENDPOINT = "/api/v2/get-money"

    def __init__(self, api_key: str = "", base_url: str = "https://market.csgo.com", timeout_seconds: float = 20.0) -> None:
        super().__init__(api_key=api_key, timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip("/")
        self._history_index: dict[str, int] = {}

    @async_retry(attempts=3, retry_exceptions=(httpx.HTTPError, MarketApiError))
    async def _get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()

    async def fetch_listings(self) -> list[MarketListing]:
        endpoint = self.FULL_EXPORT_ENDPOINT.format(currency="RUB")
        try:
            data = await self._get_json(endpoint)
        except Exception as exc:
            logger.warning("Market.CSGO full export failed, trying compact prices endpoint: %s", exc)
            data = await self._get_json(self.PRICES_ENDPOINT.format(currency="RUB"))

        raw_items = self._extract_items(data)
        listings: list[MarketListing] = []
        now = utc_now()
        for index, item in enumerate(raw_items[:5000]):
            name = self._item_name(item)
            price = self._item_price(item)
            if not name or price <= 0:
                continue
            normalized = normalize_item_name(name)
            listing_id = str(item.get("id") or item.get("item_id") or item.get("assetid") or f"market-csgo-{index}-{normalized}")
            listings.append(
                MarketListing(
                    id=listing_id,
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
                    inspect_link=item.get("inspect") or item.get("inspect_link"),
                    created_at=now,
                    raw_payload=dict(item),
                )
            )
        logger.info("Fetched %s Market.CSGO listings", len(listings))
        return listings

    async def fetch_sales_history(self, normalized_name: str) -> list[SaleRecord]:
        if not self._history_index:
            try:
                index_data = await self._get_json(self.SALES_INDEX_ENDPOINT)
                self._history_index = index_data.get("history", {}) if isinstance(index_data, dict) else {}
            except Exception as exc:
                logger.warning("Market.CSGO history index failed: %s", exc)
                return []
        item_id = self._history_index.get(normalized_name)
        if not item_id:
            return []
        try:
            data = await self._get_json(self.SALES_ITEM_ENDPOINT.format(item_id=item_id))
        except Exception as exc:
            logger.warning("Market.CSGO history item failed for %s: %s", normalized_name, exc)
            return []
        rows = data.get("data", []) if isinstance(data, dict) else []
        records: list[SaleRecord] = []
        for row in rows[:200]:
            if not isinstance(row, dict):
                continue
            price = to_decimal(row.get("price") or row.get("price_rub"))
            timestamp = row.get("time") or row.get("date")
            sold_at = datetime.fromtimestamp(timestamp, tz=utc_now().tzinfo) if isinstance(timestamp, (int, float)) else utc_now()
            records.append(
                SaleRecord(
                    market_name=self.market_name,
                    normalized_name=normalized_name,
                    price=price,
                    currency="RUB",
                    price_rub=price,
                    sold_at=sold_at,
                    raw_payload=row,
                )
            )
        return records

    async def get_balance(self) -> Balance:
        if not self.api_key:
            return Balance(market_name=self.market_name)
        try:
            data = await self._get_json(self.BALANCE_ENDPOINT, params={"key": self.api_key})
            rub = to_decimal(data.get("money") or data.get("rub") or 0)
            return Balance(market_name=self.market_name, rub=rub, raw_payload=data)
        except Exception as exc:
            logger.warning("Market.CSGO balance request failed: %s", exc)
            return Balance(market_name=self.market_name)

    async def get_fees(self) -> MarketFees:
        return get_default_fees(self.market_name)

    @staticmethod
    def _extract_items(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if not isinstance(data, dict):
            return []
        candidates = data.get("items") or data.get("data") or data.get("prices")
        if isinstance(candidates, list):
            return [item for item in candidates if isinstance(item, dict)]
        if isinstance(candidates, dict):
            return [dict(value, market_hash_name=key) if isinstance(value, dict) else {"market_hash_name": key, "price": value} for key, value in candidates.items()]
        return []

    @staticmethod
    def _item_name(item: dict[str, Any]) -> str:
        return str(item.get("market_hash_name") or item.get("name") or item.get("hash_name") or "").strip()

    @staticmethod
    def _item_price(item: dict[str, Any]) -> Decimal:
        raw = item.get("price") or item.get("price_rub") or item.get("sell_price") or item.get("min_price") or 0
        return to_decimal(raw)

