from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.config import Settings
from app.core.exceptions import RealTradingDisabledError
from app.markets.types import BuyOrder, MarketBalance, PriceHistory
from app.normalizer.item_normalizer import normalize_item_name
from app.utils.money import quantize_money, to_decimal
from app.utils.retry import async_retry
from app.utils.time import utc_now

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
        self._history_index: dict[str, int] = {}
        self._history_cache: dict[str, PriceHistory] = {}
        self._sell_prices: dict[str, dict[str, Any]] = {}

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

        key = normalize_item_name(market_hash_name)
        if key in self._history_cache:
            return replace(self._history_cache[key])

        min_sell_price = await self._current_sell_price(key)
        try:
            history_index = await self._load_history_index()
            item_id = history_index.get(key)
            if not item_id:
                history = self._fallback_history(current_price, min_sell_price)
            else:
                endpoint = self.settings.csgo_market_price_history_item_endpoint.format(item_id=item_id)
                data = await self._get_json(endpoint)
                history = self._parse_price_history(data, current_price=current_price, min_sell_price=min_sell_price)
        except Exception as exc:
            logger.warning("CSGO Market price history failed for %s: %s", market_hash_name, exc)
            history = self._fallback_history(current_price, min_sell_price)

        self._history_cache[key] = history
        return replace(history)

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
        return BuyOrder(
            item_name=name,
            market_hash_name=normalized,
            price=price,
            currency="RUB",
            price_rub=price,
            count=count,
            raw_payload=item,
        )

    @staticmethod
    def _extract_price_rub(item: dict[str, Any]) -> Decimal:
        raw = item.get("price") or item.get("buy_order_price") or item.get("best_order") or item.get("max_price") or 0
        price = to_decimal(raw)
        if price > Decimal("1000000"):
            price = price / Decimal("100")
        return quantize_money(price)

    async def _load_history_index(self) -> dict[str, int]:
        if self._history_index:
            return self._history_index
        data = await self._get_json(self.settings.csgo_market_price_history_index_endpoint)
        raw_index = data.get("history", {}) if isinstance(data, dict) else {}
        self._history_index = {
            normalize_item_name(str(name)): int(item_id)
            for name, item_id in raw_index.items()
            if str(name).strip() and str(item_id).isdigit()
        }
        logger.info("CSGO Market price history index loaded: %s items", len(self._history_index))
        return self._history_index

    async def _load_sell_prices(self) -> dict[str, dict[str, Any]]:
        if self._sell_prices:
            return self._sell_prices
        try:
            data = await self._get_json(self.settings.csgo_market_sell_prices_endpoint)
        except Exception as exc:
            logger.warning("CSGO Market sell prices failed: %s", exc)
            self._sell_prices = {}
            return self._sell_prices
        raw_items = self._extract_items(data)
        prices: dict[str, dict[str, Any]] = {}
        for item in raw_items:
            name = str(item.get("market_hash_name") or item.get("name") or item.get("hash_name") or "").strip()
            price = self._extract_price_rub(item)
            if name and price > 0:
                prices[normalize_item_name(name)] = {"price": price, "raw": item}
        self._sell_prices = prices
        logger.info("CSGO Market sell prices loaded: %s items", len(prices))
        return self._sell_prices

    async def _current_sell_price(self, normalized_name: str) -> Decimal | None:
        prices = await self._load_sell_prices()
        row = prices.get(normalized_name)
        return row["price"] if row else None

    def _parse_price_history(
        self,
        data: Any,
        current_price: Decimal,
        min_sell_price: Decimal | None,
    ) -> PriceHistory:
        payload = data.get("data", data) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            return self._fallback_history(current_price, min_sell_price)

        history_rows = payload.get("history", [])
        now_ts = int(to_decimal(data.get("time") or utc_now().timestamp())) if isinstance(data, dict) else int(utc_now().timestamp())
        avg_7d = self._money_from_currency_map(payload.get("average7d"))
        avg_30d = self._money_from_currency_map(payload.get("average30d"))
        sales_7d = self._int_from_currency_map(payload.get("sales7d"))
        sales_30d = self._int_from_currency_map(payload.get("sales30d"))

        if (avg_7d is None or avg_30d is None or sales_7d == 0 or sales_30d == 0) and isinstance(history_rows, list):
            computed = self._history_stats_from_rows(history_rows, now_ts)
            avg_7d = avg_7d or computed.avg_7d_price
            avg_30d = avg_30d or computed.avg_30d_price
            sales_7d = sales_7d or computed.sales_7d
            sales_30d = sales_30d or computed.sales_30d

        return PriceHistory(
            avg_7d_price=avg_7d or current_price,
            avg_30d_price=avg_30d or avg_7d or current_price,
            sales_7d=sales_7d,
            sales_30d=sales_30d,
            min_sell_price=min_sell_price or self._money_from_currency_map(payload.get("min")),
            buy_order_count=1,
            is_fallback=False,
        )

    @staticmethod
    def _history_stats_from_rows(rows: list[Any], now_ts: int) -> PriceHistory:
        now = datetime.fromtimestamp(now_ts, tz=utc_now().tzinfo)
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)
        prices_7d: list[Decimal] = []
        prices_30d: list[Decimal] = []
        for row in rows:
            if not isinstance(row, list | tuple) or len(row) < 2:
                continue
            sold_at = datetime.fromtimestamp(int(to_decimal(row[0])), tz=utc_now().tzinfo)
            price = quantize_money(to_decimal(row[1]))
            if price <= 0:
                continue
            if sold_at >= cutoff_30d:
                prices_30d.append(price)
            if sold_at >= cutoff_7d:
                prices_7d.append(price)

        def average(values: list[Decimal]) -> Decimal | None:
            return quantize_money(sum(values, Decimal("0")) / Decimal(len(values))) if values else None

        return PriceHistory(
            avg_7d_price=average(prices_7d),
            avg_30d_price=average(prices_30d),
            sales_7d=len(prices_7d),
            sales_30d=len(prices_30d),
        )

    @staticmethod
    def _money_from_currency_map(value: Any) -> Decimal | None:
        if isinstance(value, dict):
            value = value.get("RUB")
        amount = quantize_money(to_decimal(value or 0))
        return amount if amount > 0 else None

    @staticmethod
    def _int_from_currency_map(value: Any) -> int:
        if isinstance(value, dict):
            value = value.get("RUB")
        return int(to_decimal(value or 0))

    @staticmethod
    def _fallback_history(current_price: Decimal, min_sell_price: Decimal | None = None) -> PriceHistory:
        return PriceHistory(
            avg_7d_price=current_price,
            avg_30d_price=current_price,
            sales_7d=0,
            sales_30d=0,
            min_sell_price=min_sell_price,
            buy_order_count=1,
            is_fallback=True,
        )

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
