from decimal import Decimal

from app.markets.types import BuyOrder, PriceHistory
from app.services.liquidity import LiquidityScorer


def test_service_liquidity_score_varies_with_real_history():
    order = BuyOrder(
        item_name="\u2605 Kukri Knife | Blue Steel (Battle-Scarred)",
        market_hash_name="\u2605 Kukri Knife | Blue Steel (Battle-Scarred)",
        price=Decimal("6218.70"),
        currency="RUB",
        price_rub=Decimal("6218.70"),
        count=103,
        raw_payload={},
    )
    strong_history = PriceHistory(
        avg_7d_price=Decimal("7240.34"),
        avg_30d_price=Decimal("7573.99"),
        sales_7d=59,
        sales_30d=232,
        min_sell_price=Decimal("6300"),
        buy_order_count=103,
    )
    weak_history = PriceHistory(
        avg_7d_price=Decimal("6218.70"),
        avg_30d_price=Decimal("6218.70"),
        sales_7d=0,
        sales_30d=0,
        min_sell_price=Decimal("7200"),
        buy_order_count=3,
        is_fallback=True,
    )

    scorer = LiquidityScorer()
    strong = scorer.score(order, strong_history)
    weak = scorer.score(order, weak_history)

    assert strong.score > weak.score
    assert strong.score >= 80
    assert weak.score < 65
