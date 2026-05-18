from app.config import Settings
from app.scheduler.jobs import build_connectors


def test_use_mock_false_does_not_fallback_to_mock_without_keys(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        use_mock_markets=False,
        market_csgo_api_key="",
        lis_skins_api_key="",
    )

    connectors = build_connectors(settings)

    assert "Mock.LIS-SKINS" not in connectors
    assert "Mock.Market.CSGO" not in connectors
    assert "Market.CSGO" in connectors
    assert "LIS-SKINS" in connectors

