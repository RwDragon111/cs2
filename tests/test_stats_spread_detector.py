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
        price=price_usd if market_name == "DMarket.Stats" else price_rub,
        currency="USD" if market_name == "DMarket.Stats" else "RUB",
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
            listing("DMarket.Stats", Decimal("10500"), Decimal("105")),
        ]
    )

    assert len(signals) == 1
    assert signals[0].cheaper_market == "Market.CSGO"
    assert signals[0].expensive_market == "DMarket.Stats"
    assert signals[0].spread_rub == Decimal("1500.00")

