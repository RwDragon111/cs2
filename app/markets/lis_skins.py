from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import httpx

from app.markets.base import Balance, BaseMarketConnector, MarketFees, MarketListing
from app.normalizer.item_normalizer import detect_category, detect_weapon_type, extract_exterior, normalize_item_name
from app.pricing.fees import get_default_fees
from app.utils.money import to_decimal
from app.utils.retry import async_retry
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class LisSkinsConnector(BaseMarketConnector):
    market_name = "LIS-SKINS"
    LISTINGS_ENDPOINT = "/api/market/listings"
    BALANCE_ENDPOINT = "/api/user/balance"

    def __init__(self, api_key: str = "", base_url: str = "https://lis-skins.com", timeout_seconds: float = 20.0) -> None:
        super().__init__(api_key=api_key, timeout_seconds=timeout_seconds)
        self.base_url = base_url.rstrip("/")

    @async_retry(attempts=3, retry_exceptions=(httpx.HTTPError,))
    async def _get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-Api-Key"] = self.api_key
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds, headers=headers) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            return response.json()

    async def fetch_listings(self) -> list[MarketListing]:
        if not self.api_key:
            logger.info("LIS-SKINS API key is not configured; connector returns no live listings")
            return []
        try:
            data = await self._get_json(self.LISTINGS_ENDPOINT, params={"game": "csgo", "currency": "RUB"})
        except Exception as exc:
            logger.warning(
                "LIS-SKINS listings request failed. Endpoint is isolated in LisSkinsConnector.LISTINGS_ENDPOINT: %s",
                exc,
            )
            return []

        raw_items = self._extract_items(data)
        now = utc_now()
        listings: list[MarketListing] = []
        for index, item in enumerate(raw_items[:5000]):
            name = str(item.get("market_hash_name") or item.get("name") or item.get("item_name") or "").strip()
            price = to_decimal(item.get("price") or item.get("price_rub") or item.get("amount") or 0)
            if not name or price <= 0:
                continue
            currency = str(item.get("currency") or "RUB").upper()
            normalized = normalize_item_name(name)
            listings.append(
                MarketListing(
                    id=str(item.get("id") or item.get("listing_id") or f"lis-skins-{index}-{normalized}"),
                    market_name=self.market_name,
                    item_name=name,
                    normalized_name=normalized,
                    exterior=extract_exterior(normalized),
                    weapon_type=detect_weapon_type(normalized),
                    category=detect_category(normalized),
                    is_stattrak="StatTrak" in normalized,
                    is_souvenir=normalized.startswith("Souvenir"),
                    float_value=float(item["float"]) if item.get("float") is not None else None,
                    paint_seed=int(item["paint_seed"]) if item.get("paint_seed") is not None else None,
                    price=price,
                    currency=currency,
                    price_rub=price if currency == "RUB" else None,
                    price_usd=price if currency == "USD" else None,
                    available=bool(item.get("available", True)),
                    tradable=item.get("tradable", True),
                    inspect_link=item.get("inspect") or item.get("inspect_link"),
                    created_at=now,
                    raw_payload=dict(item),
                )
            )
        logger.info("Fetched %s LIS-SKINS listings", len(listings))
        return listings

    async def get_balance(self) -> Balance:
        if not self.api_key:
            return Balance(market_name=self.market_name)
        try:
            data = await self._get_json(self.BALANCE_ENDPOINT)
            rub = to_decimal(data.get("rub") or data.get("balance_rub") or data.get("balance") or 0)
            usd = to_decimal(data.get("usd") or data.get("balance_usd") or 0)
            return Balance(market_name=self.market_name, rub=rub, usd=usd, raw_payload=data)
        except Exception as exc:
            logger.warning("LIS-SKINS balance request failed: %s", exc)
            return Balance(market_name=self.market_name)

    async def get_fees(self) -> MarketFees:
        return get_default_fees(self.market_name)

    @staticmethod
    def _extract_items(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if not isinstance(data, dict):
            return []
        candidates = data.get("items") or data.get("data") or data.get("listings") or data.get("result")
        if isinstance(candidates, list):
            return [item for item in candidates if isinstance(item, dict)]
        return []


class OptionalThirdMarketConnector(BaseMarketConnector):
    market_name = "OptionalThirdMarket"

    async def fetch_listings(self) -> list[MarketListing]:
        logger.info("Optional third market is disabled until payment compatibility audit is completed")
        return []

    async def get_fees(self) -> MarketFees:
        return MarketFees(market_name=self.market_name)

