from __future__ import annotations

from decimal import Decimal

from app.config import Settings
from app.db.database import init_db
from app.db.repositories import DealRepository, IgnoredItemRepository, ScanLogRepository, TradingStateRepository
from app.markets.types import BuyOrder, MarketOffer, PriceHistory
from app.services.scanner import ArbitrageScanner


ITEM_NAME = "StatTrak™ AK-47 | Nightwish (Battle-Scarred)"


class FakeDMarket:
    async def fetch_offers(self, titles):
        return [
            _offer("listing-expensive", Decimal("3915.78")),
            _offer("listing-cheaper", Decimal("3915.65")),
        ]


class FakeCSGOMarket:
    def __init__(self) -> None:
        self.history_calls = 0

    async def fetch_buy_orders(self):
        return [
            BuyOrder(
                item_name=ITEM_NAME,
                market_hash_name=ITEM_NAME,
                price=Decimal("4614.52"),
                currency="RUB",
                price_rub=Decimal("4614.52"),
                count=68,
                raw_payload={},
            )
        ]

    async def fetch_price_history(self, market_hash_name, current_price):
        self.history_calls += 1
        return PriceHistory(
            avg_7d_price=Decimal("4949.90"),
            avg_30d_price=Decimal("4986.12"),
            sales_7d=68,
            sales_30d=220,
            min_sell_price=Decimal("5200"),
            buy_order_count=68,
        )


async def test_scanner_returns_only_best_offer_for_same_skin_per_scan(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'scanner-dedupe.db'}",
        telegram_enabled=False,
        min_profit_absolute=Decimal("1"),
        min_profit_percent=Decimal("0"),
        min_liquidity_score=0,
        dmarket_fee_percent=Decimal("0"),
        csgo_market_fee_percent=Decimal("0"),
        withdrawal_fee_percent=Decimal("0"),
    )
    session_factory = init_db(settings.database_url)
    deals = DealRepository(session_factory)
    trading = TradingStateRepository(session_factory)
    trading.initialize("DEMO", Decimal("100000"), "RUB")
    csgo_market = FakeCSGOMarket()
    scanner = ArbitrageScanner(
        settings=settings,
        dmarket=FakeDMarket(),  # type: ignore[arg-type]
        csgo_market=csgo_market,  # type: ignore[arg-type]
        deals=deals,
        ignored_items=IgnoredItemRepository(session_factory),
        scan_logs=ScanLogRepository(session_factory),
        trading=trading,
    )

    rows = await scanner.scan_once(notify=False)

    assert len(rows) == 1
    assert rows[0].item_name == ITEM_NAME
    assert rows[0].dmarket_listing_id == "listing-cheaper"
    assert rows[0].dmarket_price == Decimal("3915.6500")
    assert csgo_market.history_calls == 1

    rows_again = await scanner.scan_once(notify=False)

    assert rows_again == []
    assert deals.count_recent(minutes=60) == 1


def test_deal_repository_lists_unique_skins_and_hides_open_duplicates(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'repo-dedupe.db'}", telegram_enabled=False)
    repo = DealRepository(init_db(settings.database_url))
    first, _ = repo.upsert(_deal_payload("old-1", Decimal("3915.78")))
    second, _ = repo.upsert(_deal_payload("old-2", Decimal("3915.65")))

    rows = repo.latest(limit=10)

    assert len(rows) == 1
    assert rows[0].market_hash_name == ITEM_NAME

    hidden_count = repo.hide_open_duplicates_for_item(ITEM_NAME, keep_id=second.id)

    assert hidden_count == 1
    assert repo.get(first.id).status == "hidden"  # type: ignore[union-attr]
    assert repo.get(second.id).status == "new"  # type: ignore[union-attr]


def _offer(listing_id: str, price_rub: Decimal) -> MarketOffer:
    return MarketOffer(
        listing_id=listing_id,
        item_name=ITEM_NAME,
        market_hash_name=ITEM_NAME,
        price=price_rub / Decimal("100"),
        currency="USD",
        price_rub=price_rub,
        exterior="Battle-Scarred",
        is_stattrak=True,
        raw_payload={},
    )


def _deal_payload(dedupe_key: str, dmarket_price: Decimal) -> dict:
    return {
        "dedupe_key": dedupe_key,
        "item_name": ITEM_NAME,
        "market_hash_name": ITEM_NAME,
        "exterior": "Battle-Scarred",
        "is_stattrak": True,
        "float_value": None,
        "dmarket_listing_id": dedupe_key,
        "dmarket_price": dmarket_price,
        "csgo_buy_order_price": Decimal("4614.52"),
        "buy_price_with_fees": dmarket_price,
        "sell_price_after_fees": Decimal("4614.52"),
        "profit": Decimal("100"),
        "roi": Decimal("2"),
        "liquidity_score": 83,
        "risk_score": 20,
        "source_mode": "DEMO",
        "status": "new",
        "details": {},
    }
