from datetime import timedelta

from app.paper_trading.trade_ban import can_sell, trade_ban_until
from app.utils.time import utc_now


def test_trade_ban_blocks_until_7_days():
    bought_at = utc_now()
    ban_until = trade_ban_until(bought_at, 7)
    assert can_sell(bought_at + timedelta(days=6, hours=23), ban_until) is False
    assert can_sell(bought_at + timedelta(days=7), ban_until) is True

