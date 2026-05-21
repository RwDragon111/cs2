from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.config import Settings
from app.markets.types import PriceHistory
from app.utils.money import quantize_percent


@dataclass(slots=True)
class PriceAnalysis:
    avg_7d_price: Decimal | None
    avg_30d_price: Decimal | None
    price_spike_percent: Decimal
    risk_label: str
    warning: str | None = None
    is_history_fallback: bool = False


class PriceAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def analyze(self, current_buy_order_price: Decimal, history: PriceHistory) -> PriceAnalysis:
        avg_30d = history.avg_30d_price or current_buy_order_price
        if avg_30d <= 0:
            spike = Decimal("0")
        else:
            spike = quantize_percent(current_buy_order_price / avg_30d * Decimal("100") - Decimal("100"))

        risk_label = "низкий"
        warning = None
        if spike >= self.settings.max_price_spike_percent:
            risk_label = "высокий"
            warning = "⚠️ Цена выше среднего, возможен временный памп. Сделка рискованная."
        elif spike >= self.settings.max_price_spike_percent * Decimal("0.6"):
            risk_label = "средний"

        if history.is_fallback:
            risk_label = "средний" if risk_label == "низкий" else risk_label
            warning = warning or "⚠️ История цены недоступна, риск оценен по fallback-данным."

        return PriceAnalysis(
            avg_7d_price=history.avg_7d_price,
            avg_30d_price=history.avg_30d_price,
            price_spike_percent=spike,
            risk_label=risk_label,
            warning=warning,
            is_history_fallback=history.is_fallback,
        )
