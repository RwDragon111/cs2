from datetime import datetime, timedelta
from decimal import Decimal

from app.bot.messages import format_inventory
from app.db.models import InventoryORM


def test_inventory_formatter_accepts_naive_sqlite_datetimes():
    now = datetime.now()
    item = InventoryORM(
        id=1,
        deal_id=1,
        item_name="AK-47 | Redline (Field-Tested)",
        market_hash_name="AK-47 | Redline (Field-Tested)",
        buy_price=Decimal("1000"),
        expected_sell_price=Decimal("1200"),
        expected_profit=Decimal("140"),
        expected_roi=Decimal("14"),
        bought_at=now,
        trade_lock_until=now + timedelta(days=8),
        status="trade_locked",
        is_demo=True,
        raw_payload={},
    )

    text = format_inventory([item])

    assert "AK-47 | Redline" in text
    assert "trade_locked" in text
