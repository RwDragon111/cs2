from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

RUB_QUANT = Decimal("0.01")
USD_QUANT = Decimal("0.01")
PERCENT_QUANT = Decimal("0.01")


def to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return default


def quantize_money(value: Decimal) -> Decimal:
    return to_decimal(value).quantize(RUB_QUANT, rounding=ROUND_HALF_UP)


def quantize_percent(value: Decimal) -> Decimal:
    return to_decimal(value).quantize(PERCENT_QUANT, rounding=ROUND_HALF_UP)


def percent_of(amount: Decimal, percent: Decimal) -> Decimal:
    return quantize_money(to_decimal(amount) * to_decimal(percent) / Decimal("100"))


def format_rub(value: Decimal | None) -> str:
    value = quantize_money(to_decimal(value))
    return f"{value:,.2f} ₽".replace(",", " ")


def format_usd(value: Decimal | None) -> str:
    value = quantize_money(to_decimal(value))
    return f"${value:,.2f}".replace(",", " ")


def format_percent(value: Decimal | None) -> str:
    value = quantize_percent(to_decimal(value))
    sign = "+" if value > 0 else ""
    return f"{sign}{value}%"

