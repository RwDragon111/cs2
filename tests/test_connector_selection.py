from app.config import Settings
from app.scheduler.jobs import build_connectors


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
