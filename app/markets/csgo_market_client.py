from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.core.exceptions import RealTradingDisabledError
from app.markets.types import BuyOrder, MarketBalance, PriceHistory
from app.normalizer.item_normalizer import normalize_item_name
from app.utils.money import quantize_money, to_decimal
from app.utils.retry import async_retry

logger = logging.getLogger(__name__)


class CSGOMarketClient:
    """CSGO Market client focused on existing buy orders.

    Public/low-risk read methods are implemented. Real sell calls are deliberately
    guarded and should be wired only with explicit Telegram confirmation.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.market_csgo_base_url.rstrip("/")
        self.api_key = settings.csgo_market_key

    async def fetch_buy_orders(self) -> list[BuyOrder]:
        if self.settings.use_mock_markets:
            return self._mock_buy_orders()

        data = await self._get_json(self.settings.csgo_market_buy_orders_endpoint)
        raw_items = self._extract_items(data)
        orders: list[BuyOrder] = []
        for item in raw_items:
            order = self._parse_buy_order(item)
            if order is not None:
                orders.append(order)
        logger.info("CSGO Market returned %s buy orders", len(orders))
        return orders

    async def fetch_price_history(self, market_hash_name: str, current_price: Decimal) -> PriceHistory:
        if self.settings.use_mock_markets:
            return self._mock_history(market_hash_name)

        # API history formats vary by CSGO Market mirror and account privileges.
        # Keep a safe fallback so scans continue even when history is unavailable.
        logger.debug("Price history endpoint is not configured for %s; using fallback", market_hash_name)
        return PriceHistory(
            avg_7d_price=current_price,
            avg_30d_price=current_price,
            sales_7d=0,
            sales_30d=0,
            buy_order_count=1,
            is_fallback=True,
        )

    async def get_balance(self) -> MarketBalance:
        if not self.api_key:
            return MarketBalance(market_name="CSGO Market")
        try:
            data = await self._get_json(self.settings.csgo_market_balance_endpoint, params={"key": self.api_key})
        except Exception as exc:
            logger.warning("CSGO Market balance request failed: %s", exc)
            return MarketBalance(market_name="CSGO Market")
        amount = to_decimal(data.get("money") or data.get("rub") or data.get("balance") or 0)
        return MarketBalance(market_name="CSGO Market", available=amount, currency="RUB", raw_payload=data)

    async def sell_item(self, asset_id: str, price: Decimal) -> None:
        raise RealTradingDisabledError(
            "CSGO Market real sell is not implemented. Add endpoint support after manual review."
        )

    @async_retry(attempts=3, retry_exceptions=(httpx.HTTPError,))
    async def _get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(endpoint, params=params)
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
        candidates = data.get("items") or data.get("data") or data.get("prices") or data.get("orders")
        if isinstance(candidates, list):
            return [item for item in candidates if isinstance(item, dict)]
        if isinstance(candidates, dict):
            return [
                dict(value, market_hash_name=key) if isinstance(value, dict) else {"market_hash_name": key, "price": value}
                for key, value in candidates.items()
            ]
        return []

    def _parse_buy_order(self, item: dict[str, Any]) -> BuyOrder | None:
        name = str(item.get("market_hash_name") or item.get("hash_name") or item.get("name") or "").strip()
        if not name:
            return None
        price = self._extract_price_rub(item)
        count = int(to_decimal(item.get("count") or item.get("volume") or item.get("orders") or 1))
        if price <= 0 or count <= 0:
            return None
        normalized = normalize_item_name(name)
        raw_payload = dict(item)
        raw_payload.setdefault("source_url", self.item_url(name))
        return BuyOrder(
            item_name=name,
            market_hash_name=normalized,
            price=price,
            currency="RUB",
            price_rub=price,
            count=count,
            raw_payload=raw_payload,
        )

    @staticmethod
    def item_url(market_hash_name: str) -> str:
        return f"https://market.csgo.com/ru/?search={quote(market_hash_name)}"

    @staticmethod
    def _extract_price_rub(item: dict[str, Any]) -> Decimal:
        raw = item.get("price") or item.get("buy_order_price") or item.get("best_order") or item.get("max_price") or 0
        price = to_decimal(raw)
        if price > Decimal("1000000"):
            price = price / Decimal("100")
        return quantize_money(price)

    def _mock_buy_orders(self) -> list[BuyOrder]:
        return [
            BuyOrder(
                item_name="AK-47 | Redline (Field-Tested)",
                market_hash_name="AK-47 | Redline (Field-Tested)",
                price=Decimal("1480"),
                currency="RUB",
                price_rub=Decimal("1480"),
                count=18,
                raw_payload={"mock": True, "min_sell_price": "1575"},
            ),
            BuyOrder(
                item_name="AWP | Asiimov (Field-Tested)",
                market_hash_name="AWP | Asiimov (Field-Tested)",
                price=Decimal("8250"),
                currency="RUB",
                price_rub=Decimal("8250"),
                count=3,
                raw_payload={"mock": True, "min_sell_price": "9100"},
            ),
        ]

    @staticmethod
    def _mock_history(market_hash_name: str) -> PriceHistory:
        if "Redline" in market_hash_name:
            return PriceHistory(
                avg_7d_price=Decimal("1430"),
                avg_30d_price=Decimal("1390"),
                sales_7d=54,
                sales_30d=220,
                min_sell_price=Decimal("1575"),
                buy_order_count=18,
            )
        return PriceHistory(
            avg_7d_price=Decimal("8100"),
            avg_30d_price=Decimal("7900"),
            sales_7d=16,
            sales_30d=63,
            min_sell_price=Decimal("9100"),
            buy_order_count=3,
        )
