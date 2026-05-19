from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.markets.base import MarketListing
from app.utils.money import quantize_money, quantize_percent
from app.utils.time import utc_now


class MarketStatsSpread(BaseModel):
    id: str
    normalized_name: str
    cheaper_market: str
    expensive_market: str
    cheaper_listing_id: str
    cheaper_price_rub: Decimal
    expensive_price_rub: Decimal
    cheaper_price_usd: Decimal | None = None
    expensive_price_usd: Decimal | None = None
    spread_rub: Decimal
    spread_percent: Decimal
    detected_at: datetime


class StatsSpreadDetector:
    def __init__(
        self,
        min_spread_percent: Decimal,
        min_spread_rub: Decimal,
        max_signals: int,
    ) -> None:
        self.min_spread_percent = min_spread_percent
        self.min_spread_rub = min_spread_rub
        self.max_signals = max_signals

    def detect(self, listings: list[MarketListing]) -> list[MarketStatsSpread]:
        by_name: dict[str, dict[str, list[MarketListing]]] = {}
        for listing in listings:
            if not listing.available or listing.price_rub is None:
                continue
            if listing.market_name not in {"Market.CSGO.BuyOrder", "DMarket"}:
                continue
            by_name.setdefault(listing.normalized_name, {}).setdefault(listing.market_name, []).append(listing)

        spreads: list[MarketStatsSpread] = []
        for normalized_name, markets in by_name.items():
            if "Market.CSGO.BuyOrder" not in markets or "DMarket" not in markets:
                continue
            market_csgo = max(markets["Market.CSGO.BuyOrder"], key=lambda item: item.price_rub or Decimal("0"))
            dmarket = min(markets["DMarket"], key=lambda item: item.price_rub or Decimal("0"))
            signal = self._build(normalized_name, market_csgo, dmarket)
            if signal is not None:
                spreads.append(signal)

        spreads.sort(key=lambda item: (item.spread_percent, item.spread_rub), reverse=True)
        return spreads[: self.max_signals]

    def _build(
        self,
        normalized_name: str,
        first: MarketListing,
        second: MarketListing,
    ) -> MarketStatsSpread | None:
        first_price = first.price_rub or Decimal("0")
        second_price = second.price_rub or Decimal("0")
        if first_price <= 0 or second_price <= 0 or first_price == second_price:
            return None

        cheaper, expensive = (first, second) if first_price < second_price else (second, first)
        cheaper_price = cheaper.price_rub or Decimal("0")
        expensive_price = expensive.price_rub or Decimal("0")
        spread_rub = quantize_money(expensive_price - cheaper_price)
        spread_percent = quantize_percent(spread_rub / cheaper_price * Decimal("100"))
        if spread_rub < self.min_spread_rub or spread_percent < self.min_spread_percent:
            return None

        raw_id = "|".join(
            [
                normalized_name,
                cheaper.market_name,
                expensive.market_name,
                str(cheaper_price),
                str(expensive_price),
            ]
        )
        return MarketStatsSpread(
            id=hashlib.sha1(raw_id.encode("utf-8")).hexdigest(),
            normalized_name=normalized_name,
            cheaper_market=cheaper.market_name,
            expensive_market=expensive.market_name,
            cheaper_listing_id=cheaper.id,
            cheaper_price_rub=quantize_money(cheaper_price),
            expensive_price_rub=quantize_money(expensive_price),
            cheaper_price_usd=cheaper.price_usd,
            expensive_price_usd=expensive.price_usd,
            spread_rub=spread_rub,
            spread_percent=spread_percent,
            detected_at=utc_now(),
        )
