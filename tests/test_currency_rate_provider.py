from decimal import Decimal

from app.config import Settings
from app.currency.rate_provider import CurrencyRateProvider
from app.markets.dmarket_client import DMarketClient


def test_currency_rate_provider_parses_cbr_usd_rate(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'rates.db'}",
        telegram_enabled=False,
        rub_usd_rate_source="cbr",
    )
    provider = CurrencyRateProvider(settings)
    xml = """<?xml version="1.0" encoding="windows-1251"?>
    <ValCurs Date="22.05.2026" name="Foreign Currency Market">
      <Valute ID="R01235">
        <NumCode>840</NumCode>
        <CharCode>USD</CharCode>
        <Nominal>1</Nominal>
        <Name>Доллар США</Name>
        <Value>79,1234</Value>
      </Valute>
    </ValCurs>
    """.encode("windows-1251")

    rate = provider._parse_cbr_xml(xml)

    assert rate.value == Decimal("79.1234")
    assert rate.source == "cbr"
    assert rate.effective_date == "22.05.2026"


async def test_dmarket_client_uses_rate_provider_for_usd_conversion(tmp_path, monkeypatch):
    class FakeRateProvider:
        async def usd_to_rub(self):
            return Decimal("80")

    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'dmarket-rate.db'}",
        telegram_enabled=False,
        use_mock_markets=False,
        rub_usd_rate_source="cbr",
        dmarket_market_pages=1,
        dmarket_stats_limit=1,
    )
    client = DMarketClient(settings, rate_provider=FakeRateProvider())  # type: ignore[arg-type]

    async def fake_fetch_market_page(cursor=None):
        return {
            "objects": [
                {
                    "itemId": "1",
                    "title": "AK-47 | Redline (Field-Tested)",
                    "price": {"USD": "1234"},
                }
            ]
        }

    monkeypatch.setattr(client, "_fetch_market_page", fake_fetch_market_page)

    offers = await client.fetch_offers()

    assert offers[0].price == Decimal("12.34")
    assert offers[0].price_rub == Decimal("987.20")
