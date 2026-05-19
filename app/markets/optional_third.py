from __future__ import annotations

import logging

from app.markets.base import BaseMarketConnector, MarketListing

logger = logging.getLogger(__name__)


class OptionalThirdMarketConnector(BaseMarketConnector):
    market_name = "OptionalThirdMarket"

    async def fetch_listings(self) -> list[MarketListing]:
        logger.info("Optional third market is disabled until a separate audit is completed")
        return []
