from app.config import Settings
from app.markets.base import MarketListing
from app.scheduler.jobs import build_connectors, select_dmarket_search_titles_from_buy_orders
from app.utils.time import utc_now


def test_use_mock_false_does_not_fallback_to_mock_without_keys(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        use_mock_markets=False,
        enable_dmarket_stats=False,
        market_csgo_api_key="",
    )

    connectors = build_connectors(settings)

    assert "Mock.DMarket" not in connectors
    assert "Mock.Market.CSGO.BuyOrder" not in connectors
    assert "Market.CSGO.BuyOrder" in connectors
    assert "DMarket" in connectors
    assert "LIS-SKINS" not in connectors


def test_dmarket_stats_connector_is_added_when_enabled(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        use_mock_markets=False,
        enable_dmarket_stats=True,
    )

    connectors = build_connectors(settings)

    assert "DMarket.Stats" in connectors


def test_select_dmarket_titles_from_market_csgo_buy_orders(settings):
    orders = [
        MarketListing(
            id="1",
            market_name="Market.CSGO.BuyOrder",
            item_name="Cheap Case",
            normalized_name="Cheap Case",
            price=50,
            currency="RUB",
            price_rub=50,
            created_at=utc_now(),
            raw_payload={"buy_order": True, "volume": 999},
        ),
        MarketListing(
            id="2",
            market_name="Market.CSGO.BuyOrder",
            item_name="AWP | Asiimov (Field-Tested)",
            normalized_name="AWP | Asiimov (Field-Tested)",
            price=8500,
            currency="RUB",
            price_rub=8500,
            created_at=utc_now(),
            raw_payload={"buy_order": True, "volume": 43},
        ),
    ]

    assert select_dmarket_search_titles_from_buy_orders(orders, settings) == ["AWP | Asiimov (Field-Tested)"]
