from decimal import Decimal

from app.markets.market_csgo import MarketCsgoBuyOrderConnector


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
