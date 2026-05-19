from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.currency.currency_engine import CurrencyEngine
from app.markets.base import BaseMarketConnector, MarketFees, MarketListing, SaleRecord
from app.markets.dmarket_stats import DMarketConnector, DMarketStatsConnector
from app.markets.market_csgo import MarketCsgoBuyOrderConnector
from app.markets.mock_market import MockMarketConnector
from app.markets.optional_third import OptionalThirdMarketConnector
from app.pricing.fees import get_default_fees
from app.utils.money import quantize_money

logger = logging.getLogger(__name__)


def build_connectors(settings: Settings) -> dict[str, BaseMarketConnector]:
    connectors: dict[str, BaseMarketConnector] = {}
    if settings.use_mock_markets:
        logger.info("Using mock market connectors")
        connectors["Mock.DMarket"] = MockMarketConnector("Mock.DMarket", price_side="buy")
        connectors["Mock.Market.CSGO.BuyOrder"] = MockMarketConnector("Mock.Market.CSGO.BuyOrder", price_side="sell")
    elif settings.enable_market_csgo:
        if not settings.market_csgo_api_key:
            logger.warning("MARKET_CSGO_API_KEY is empty; only public Market.CSGO endpoints will be used")
        connectors["Market.CSGO.BuyOrder"] = MarketCsgoBuyOrderConnector(
            api_key=settings.market_csgo_api_key,
            base_url=settings.market_csgo_base_url,
            timeout_seconds=settings.request_timeout_seconds,
        )
    if not settings.use_mock_markets and settings.enable_dmarket:
        connectors["DMarket"] = DMarketConnector(
            base_url=settings.dmarket_api_base_url,
            limit=settings.dmarket_stats_limit,
            currency=settings.dmarket_stats_currency,
            tracked_titles=settings.dmarket_tracked_titles,
            timeout_seconds=settings.request_timeout_seconds,
        )
    if settings.enable_third_market:
        connectors["OptionalThirdMarket"] = OptionalThirdMarketConnector()
    if settings.enable_dmarket_stats:
        connectors["DMarket.Stats"] = DMarketStatsConnector(
            base_url=settings.dmarket_api_base_url,
            limit=settings.dmarket_stats_limit,
            currency=settings.dmarket_stats_currency,
            tracked_titles=settings.dmarket_tracked_titles,
            timeout_seconds=settings.request_timeout_seconds,
        )
    return connectors


async def fetch_all_listings(
    connectors: dict[str, BaseMarketConnector],
    currency_engine: CurrencyEngine,
) -> dict[str, list[MarketListing]]:
    async def fetch_one(connector: BaseMarketConnector) -> tuple[str, list[MarketListing]]:
        try:
            listings = await connector.fetch_listings()
            return connector.market_name, [with_prices(listing, currency_engine) for listing in listings]
        except Exception as exc:
            logger.warning("Failed to fetch listings from %s: %s", connector.market_name, exc)
            return connector.market_name, []

    results = await asyncio.gather(*(fetch_one(connector) for connector in connectors.values()))
    return dict(results)


async def fetch_fees(connectors: dict[str, BaseMarketConnector]) -> dict[str, MarketFees]:
    result: dict[str, MarketFees] = {}
    for name, connector in connectors.items():
        try:
            result[name] = await connector.get_fees()
        except Exception as exc:
            logger.warning("Failed to fetch fees from %s: %s", name, exc)
            result[name] = get_default_fees(name)
    return result


async def fetch_sales_history_sample(
    connectors: dict[str, BaseMarketConnector],
    normalized_names: set[str],
    limit: int = 50,
) -> dict[str, list[SaleRecord]]:
    histories: dict[str, list[SaleRecord]] = {}
    for normalized_name in list(normalized_names)[:limit]:
        records: list[SaleRecord] = []
        for connector in connectors.values():
            try:
                records.extend(await connector.fetch_sales_history(normalized_name))
            except Exception as exc:
                logger.debug("Sales history failed for %s on %s: %s", normalized_name, connector.market_name, exc)
        histories[normalized_name] = records
    return histories


def with_prices(listing: MarketListing, currency_engine: CurrencyEngine) -> MarketListing:
    price_rub = listing.price_rub
    price_usd = listing.price_usd
    if price_rub is None:
        price_rub = currency_engine.to_rub(listing.price, listing.currency)
    if price_usd is None:
        price_usd = currency_engine.to_usd(price_rub, "RUB")
    return listing.model_copy(update={"price_rub": quantize_money(price_rub), "price_usd": quantize_money(price_usd)})
