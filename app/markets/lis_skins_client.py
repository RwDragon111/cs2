from __future__ import annotations

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


class LisSkinsClient:
    """Read-only LIS-SKINS market client.

    The public export is enough for manual signal generation. Authenticated buy
    calls are deliberately disabled in this variant: the bot only sends links
    and lets the user buy manually on the marketplace.
    """

    market_name = "LIS-SKINS"

    def __init__(self, settings: Settings, rate_provider: CurrencyRateProvider | None = None) -> None:
        self.settings = settings
        self.api_key = settings.lis_skins_api_key
        self.api_base_url = settings.lis_skins_api_base_url.rstrip("/")
        self.rate_provider = rate_provider or CurrencyRateProvider(settings)

    async def fetch_offers(self) -> list[MarketOffer]:
        if self.settings.use_mock_markets:
            return self._mock_offers()

        data = await self._get_export_json()
        raw_items = self._extract_items(data)
        usd_to_rub = await self.rate_provider.usd_to_rub()
        offers = [offer for item in raw_items if (offer := self._parse_offer(item, usd_to_rub)) is not None]
        offers.sort(key=lambda offer: offer.price_rub)
        logger.info("LIS-SKINS returned %s offers", len(offers))
        return offers

    async def get_balance(self) -> MarketBalance:
        if not self.api_key:
            return MarketBalance(market_name=self.market_name)
        try:
            data = await self._get_api_json(self.settings.lis_skins_balance_endpoint)
            if not isinstance(data, dict):
                raise RuntimeError("Unexpected LIS-SKINS balance response")
            raw_balance = data.get("data", {}).get("balance") if isinstance(data.get("data"), dict) else data.get("balance")
            balance_usd = to_decimal(raw_balance)
            rate = await self.rate_provider.usd_to_rub()
        except Exception as exc:
            logger.warning("LIS-SKINS balance request failed: %s", exc)
            return MarketBalance(market_name=self.market_name)
        return MarketBalance(
            market_name=self.market_name,
            available=quantize_money(balance_usd * rate),
            currency="RUB",
            raw_payload={"balance_usd": str(balance_usd), "rate_source": self.rate_provider.source, "raw": data},
        )

    async def buy_item(self, listing_id: str) -> None:
        raise RealTradingDisabledError(
            "LIS-SKINS real buy is disabled in this branch. Open the link and buy manually on the marketplace."
        )

    @async_retry(attempts=3, retry_exceptions=(httpx.HTTPError,))
    async def _get_export_json(self) -> Any:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(self.settings.lis_skins_market_export_url)
            if response.status_code in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            response.raise_for_status()
            return response.json()

    @async_retry(attempts=3, retry_exceptions=(httpx.HTTPError,))
    async def _get_api_json(self, endpoint: str) -> Any:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(base_url=self.api_base_url, timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(endpoint, headers=headers)
            if response.status_code in {429, 500, 502, 503, 504}:
                response.raise_for_status()
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _extract_items(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if not isinstance(data, dict):
            return []
        candidates = data.get("items") or data.get("data") or data.get("skins")
        if isinstance(candidates, list):
            return [item for item in candidates if isinstance(item, dict)]
        return []

    def _parse_offer(self, item: dict[str, Any], usd_to_rub: Decimal) -> MarketOffer | None:
        title = str(item.get("name") or item.get("market_hash_name") or item.get("hash_name") or "").strip()
        if not title:
            return None

        count = int(to_decimal(item.get("count") or item.get("quantity") or 1))
        if count < self.settings.lis_skins_min_count:
            return None

        raw_unlocked_price = item.get("unlocked_price")
        raw_price = raw_unlocked_price if self.settings.lis_skins_only_unlocked else item.get("price", raw_unlocked_price)
        price_usd = to_decimal(raw_price)
        if price_usd <= 0:
            return None

        normalized = normalize_item_name(title)
        url = str(item.get("url") or "").strip()
        listing_id = str(item.get("id") or item.get("skin_id") or item.get("item_id") or url or normalized)
        price_rub = quantize_money(price_usd * usd_to_rub)
        raw_payload = dict(item)
        raw_payload.update(
            {
                "buy_market": self.market_name,
                "source_url": url,
                "price_usd": str(price_usd),
                "usd_to_rub_rate": str(usd_to_rub),
                "rate_source": self.rate_provider.source,
            }
        )
        return MarketOffer(
            listing_id=listing_id,
            item_name=title,
            market_hash_name=normalized,
            price=price_usd,
            currency="USD",
            price_rub=price_rub,
            exterior=extract_exterior(normalized),
            is_stattrak="StatTrak" in normalized,
            raw_payload=raw_payload,
        )

    def _mock_offers(self) -> list[MarketOffer]:
        return [
            MarketOffer(
                listing_id="mock-lis-ak-redline",
                item_name="AK-47 | Redline (Field-Tested)",
                market_hash_name="AK-47 | Redline (Field-Tested)",
                price=Decimal("12.00"),
                currency="USD",
                price_rub=Decimal("1200"),
                exterior="Field-Tested",
                raw_payload={
                    "mock": True,
                    "buy_market": self.market_name,
                    "source_url": "https://lis-skins.com/market/csgo/ak-47-redline-field-tested/",
                },
            ),
            MarketOffer(
                listing_id="mock-lis-awp-asiimov",
                item_name="AWP | Asiimov (Field-Tested)",
                market_hash_name="AWP | Asiimov (Field-Tested)",
                price=Decimal("80.00"),
                currency="USD",
                price_rub=Decimal("8000"),
                exterior="Field-Tested",
                raw_payload={
                    "mock": True,
                    "buy_market": self.market_name,
                    "source_url": "https://lis-skins.com/market/csgo/awp-asiimov-field-tested/",
                },
            ),
        ]
