from decimal import Decimal

from app.currency.currency_engine import CurrencyEngine


def test_currency_engine_manual_rate(settings):
    engine = CurrencyEngine(settings)
    assert engine.to_rub(Decimal("10"), "USD") == Decimal("1010.00")
    assert engine.to_usd(Decimal("1000"), "RUB") == Decimal("10.10")

