from decimal import Decimal

from app.config import Settings
from app.db.database import init_db
from app.db.repositories import DealRepository, IgnoredItemRepository, ScanLogRepository, TradingStateRepository
from app.markets.types import BuyOrder, MarketBalance, MarketOffer, PriceHistory
from app.services.scanner import ArbitrageScanner


class FakeBuyMarket:
    async def fetch_offers(self) -> list[MarketOffer]:
        return [
            MarketOffer(
                listing_id="lis-a",
                item_name="AK-47 | Redline (Field-Tested)",
                market_hash_name="AK-47 | Redline (Field-Tested)",
                price=Decimal("10"),
                currency="USD",
                price_rub=Decimal("1000"),
                raw_payload={"buy_market": "LIS-SKINS", "source_url": "https://lis-skins.com/a"},
            ),
            MarketOffer(
                listing_id="lis-b",
                item_name="AWP | Asiimov (Field-Tested)",
                market_hash_name="AWP | Asiimov (Field-Tested)",
                price=Decimal("20"),
                currency="USD",
                price_rub=Decimal("2000"),
                raw_payload={"buy_market": "LIS-SKINS", "source_url": "https://lis-skins.com/b"},
            ),
        ]

    async def get_balance(self) -> MarketBalance:
        return MarketBalance(market_name="LIS-SKINS")

    async def buy_item(self, listing_id: str) -> None:
        raise AssertionError("real buy must not be called by scanner")


class FakeCsgoMarket:
    async def fetch_buy_orders(self) -> list[BuyOrder]:
        return [
            BuyOrder(
                item_name="AK-47 | Redline (Field-Tested)",
                market_hash_name="AK-47 | Redline (Field-Tested)",
                price=Decimal("1300"),
                currency="RUB",
                price_rub=Decimal("1300"),
                count=15,
                raw_payload={"source_url": "https://market.csgo.com/a"},
            ),
            BuyOrder(
                item_name="AWP | Asiimov (Field-Tested)",
                market_hash_name="AWP | Asiimov (Field-Tested)",
                price=Decimal("2600"),
                currency="RUB",
                price_rub=Decimal("2600"),
                count=15,
                raw_payload={"source_url": "https://market.csgo.com/b"},
            ),
        ]

    async def fetch_price_history(self, market_hash_name: str, current_price: Decimal) -> PriceHistory:
        return PriceHistory(
            avg_7d_price=current_price,
            avg_30d_price=current_price,
            sales_7d=10,
            sales_30d=40,
            min_sell_price=current_price * Decimal("1.05"),
            buy_order_count=15,
        )


async def test_scanner_sends_highest_profit_lisskins_deal(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        telegram_enabled=False,
        min_profit_absolute=Decimal("0"),
        min_profit_percent=Decimal("0"),
        min_liquidity_score=0,
        min_item_price=Decimal("0"),
        max_item_price=Decimal("10000"),
        max_deals_per_scan=1,
        csgo_market_fee_percent=Decimal("5"),
        withdrawal_fee_percent=Decimal("0"),
        lis_skins_fee_percent=Decimal("0"),
    )
    session_factory = init_db(settings.database_url)
    trading = TradingStateRepository(session_factory)
    trading.initialize(settings.default_trading_mode, settings.demo_initial_balance, settings.demo_currency)
    scanner = ArbitrageScanner(
        settings=settings,
        dmarket=FakeBuyMarket(),
        csgo_market=FakeCsgoMarket(),
        deals=DealRepository(session_factory),
        ignored_items=IgnoredItemRepository(session_factory),
        scan_logs=ScanLogRepository(session_factory),
        trading=trading,
    )

    deals = await scanner.scan_once(notify=False)

    assert len(deals) == 1
    assert deals[0].item_name == "AWP | Asiimov (Field-Tested)"
    assert deals[0].profit == Decimal("470.0000") or deals[0].profit == Decimal("470.00")
    assert deals[0].details["markets"]["buy_market"] == "LIS-SKINS"
    assert deals[0].details["links"]["buy_market"] == "https://lis-skins.com/b"
