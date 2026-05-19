from decimal import Decimal

from app.markets.base import MarketListing
from app.opportunities.stats_spread import StatsSpreadDetector
from app.utils.time import utc_now


def listing(market_name: str, price_rub: Decimal, price_usd: Decimal) -> MarketListing:
    return MarketListing(
        id=f"{market_name}-{price_rub}",
        market_name=market_name,
        item_name="AWP | Asiimov (Field-Tested)",
        normalized_name="AWP | Asiimov (Field-Tested)",
        price=price_usd if market_name == "DMarket" else price_rub,
        currency="USD" if market_name == "DMarket" else "RUB",
        price_rub=price_rub,
        price_usd=price_usd,
        created_at=utc_now(),
        raw_payload={},
    )


def test_stats_spread_detector_compares_market_csgo_and_dmarket():
    detector = StatsSpreadDetector(
        min_spread_percent=Decimal("5"),
        min_spread_rub=Decimal("100"),
        max_signals=5,
    )

    signals = detector.detect(
        [
            listing("Market.CSGO", Decimal("9000"), Decimal("90")),
            listing("Market.CSGO.BuyOrder", Decimal("9000"), Decimal("90")),
            listing("DMarket", Decimal("7500"), Decimal("75")),
        ]
    )

    assert len(signals) == 1
    assert signals[0].cheaper_market == "DMarket"
    assert signals[0].expensive_market == "Market.CSGO.BuyOrder"
    assert signals[0].spread_rub == Decimal("1500.00")
