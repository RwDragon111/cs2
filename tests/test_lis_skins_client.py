from decimal import Decimal

from app.config import Settings
from app.markets.lis_skins_client import LisSkinsClient


class StaticRateProvider:
    source = "test"

    async def usd_to_rub(self) -> Decimal:
        return Decimal("90")


async def test_lis_skins_client_parses_public_export(monkeypatch):
    settings = Settings(
        telegram_enabled=False,
        use_mock_markets=False,
        lis_skins_only_unlocked=True,
        lis_skins_min_count=2,
    )
    client = LisSkinsClient(settings, rate_provider=StaticRateProvider())

    async def fake_export():
        return [
            {
                "name": "AK-47 | Redline (Field-Tested)",
                "price": 9.99,
                "unlocked_price": 10.50,
                "url": "https://lis-skins.com/market/csgo/ak-47-redline-field-tested/",
                "count": 3,
            },
            {
                "name": "AWP | Asiimov (Field-Tested)",
                "price": 80,
                "unlocked_price": 0,
                "count": 5,
            },
        ]

    monkeypatch.setattr(client, "_get_export_json", fake_export)

    offers = await client.fetch_offers()

    assert len(offers) == 1
    assert offers[0].item_name == "AK-47 | Redline (Field-Tested)"
    assert offers[0].price == Decimal("10.5")
    assert offers[0].price_rub == Decimal("945.00")
    assert offers[0].raw_payload["buy_market"] == "LIS-SKINS"
    assert offers[0].raw_payload["source_url"].startswith("https://lis-skins.com/")
