from decimal import Decimal

from app.markets.dmarket_stats import DMarketStatsConnector


def test_dmarket_stats_connector_parses_market_item():
    connector = DMarketStatsConnector(limit=10)
    listing = connector._parse_item(
        {
            "itemId": "item-1",
            "title": "AWP | Asiimov (Field-Tested)",
            "inMarket": True,
            "price": {"USD": "91234"},
            "extra": {
                "category": "Sniper Rifles",
                "floatValue": 0.31,
                "tradable": True,
                "inspectInGame": "steam://inspect/test",
            },
        }
    )

    assert listing is not None
    assert listing.market_name == "DMarket.Stats"
    assert listing.normalized_name == "AWP | Asiimov (Field-Tested)"
    assert listing.price == Decimal("912.34")
    assert listing.currency == "USD"
    assert listing.raw_payload["stats_only"] is True


def test_dmarket_stats_connector_accepts_tracked_titles():
    connector = DMarketStatsConnector(limit=10, tracked_titles=["AWP | Asiimov (Field-Tested)"])

    assert connector.tracked_titles == ["AWP | Asiimov (Field-Tested)"]
