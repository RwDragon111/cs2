from __future__ import annotations

from decimal import Decimal

from app.config import Settings
from app.currency.rate_provider import CurrencyRateProvider
from app.utils.money import percent_of, quantize_money, to_decimal


class CurrencyEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.rate_provider = CurrencyRateProvider(settings)

    @property
    def rub_usd_rate(self) -> Decimal:
        return self.rate_provider.usd_to_rub_sync()

    def to_rub(self, amount: Decimal, currency: str, include_spread: bool = True) -> Decimal:
        currency = currency.upper()
        amount = to_decimal(amount)
        if currency == "RUB":
            result = amount
        elif currency == "USD":
            result = amount * self.rub_usd_rate
        else:
            raise ValueError(f"Unsupported currency: {currency}")
        if include_spread and currency != "RUB":
            result += percent_of(result, self.settings.currency_spread_percent)
        return quantize_money(result)

    def to_usd(self, amount: Decimal, currency: str, include_spread: bool = True) -> Decimal:
        currency = currency.upper()
        amount = to_decimal(amount)
        if currency == "USD":
            result = amount
        elif currency == "RUB":
            result = amount / self.rub_usd_rate
        else:
            raise ValueError(f"Unsupported currency: {currency}")
        if include_spread and currency != "USD":
            result += percent_of(result, self.settings.currency_spread_percent)
        return quantize_money(result)

    def conversion_fee_rub(self, amount_rub: Decimal, conversion_required: bool) -> Decimal:
        if not conversion_required:
            return Decimal("0.00")
        return percent_of(amount_rub, self.settings.currency_spread_percent)
