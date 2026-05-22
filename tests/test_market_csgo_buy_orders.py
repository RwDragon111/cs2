from decimal import Decimal

from app.config import Settings
from app.markets.market_csgo import MarketCsgoBuyOrderConnector
from app.markets.csgo_market_client import CSGOMarketClient


async def test_market_csgo_buy_order_connector_parses_public_orders(monkeypatch):
    connector = MarketCsgoBuyOrderConnector()

    async def fake_get_json(endpoint, params=None):
        return {
            "success": True,
            "currency": "RUB",
            "items": [
                {
                    "market_hash_name": "AWP | Asiimov (Field-Tested)",
                    "price": 9123.45,
                    "volume": 7,
                }
            ],
        }

    monkeypatch.setattr(connector, "_get_json", fake_get_json)
    listings = await connector.fetch_listings()

    assert len(listings) == 1
    assert listings[0].market_name == "Market.CSGO.BuyOrder"
    assert listings[0].price_rub == Decimal("9123.45")
    assert listings[0].raw_payload["buy_order"] is True


async def test_csgo_market_client_parses_public_price_history(tmp_path, monkeypatch):
    item_name = "\u2605 Kukri Knife | Blue Steel (Battle-Scarred)"
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'history.db'}",
        telegram_enabled=False,
        use_mock_markets=False,
        dmarket_extra_titles="",
    )
    client = CSGOMarketClient(settings)

    async def fake_get_json(endpoint, params=None):
        if endpoint == settings.csgo_market_sell_prices_endpoint:
            return {"items": [{"market_hash_name": item_name, "price": "6300.00", "volume": "18"}]}
        if endpoint == settings.csgo_market_price_history_index_endpoint:
            return {"history": {item_name: 582057}}
        if endpoint == settings.csgo_market_price_history_item_endpoint.format(item_id=582057):
            return {
                "time": 1779455032,
                "data": {
                    "average7d": {"RUB": 7240.34},
                    "average30d": {"RUB": 7573.99},
                    "sales7d": {"RUB": 59},
                    "sales30d": {"RUB": 232},
                    "history": [],
                },
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(client, "_get_json", fake_get_json)

    history = await client.fetch_price_history(item_name, Decimal("6218.70"))

    assert history.avg_7d_price == Decimal("7240.34")
    assert history.avg_30d_price == Decimal("7573.99")
    assert history.sales_7d == 59
    assert history.sales_30d == 232
    assert history.min_sell_price == Decimal("6300.00")
    assert history.is_fallback is False
