from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from app.core.enums import PaperPositionStatus
from app.db.models import PaperAccountORM, PaperPositionORM


@dataclass(slots=True)
class PaperAnalytics:
    initial_balance_rub: Decimal
    current_balance_rub: Decimal
    open_positions: int
    trade_locked_positions: int
    ready_to_sell_positions: int
    sold_positions: int
    realized_pnl_rub: Decimal
    unrealized_pnl_rub: Decimal
    total_pnl_rub: Decimal
    average_roi_percent: Decimal
    median_roi_percent: Decimal
    winrate_percent: Decimal
    best_trade_rub: Decimal | None
    worst_trade_rub: Decimal | None
    expected_vs_actual_rub: Decimal


def calculate_paper_analytics(account: PaperAccountORM, positions: list[PaperPositionORM]) -> PaperAnalytics:
    sold = [position for position in positions if position.status == PaperPositionStatus.SOLD.value]
    open_positions = [position for position in positions if position.status != PaperPositionStatus.SOLD.value]
    realized = sum((position.actual_profit_rub or Decimal("0")) for position in sold)
    unrealized = sum((position.expected_profit_rub or Decimal("0")) for position in open_positions)
    total = realized + unrealized
    rois = [position.actual_roi_percent for position in sold if position.actual_roi_percent is not None]
    wins = [position for position in sold if (position.actual_profit_rub or Decimal("0")) > 0]
    actual_values = [position.actual_profit_rub or Decimal("0") for position in sold]
    expected_vs_actual = sum(((position.actual_profit_rub or Decimal("0")) - position.expected_profit_rub) for position in sold)

    return PaperAnalytics(
        initial_balance_rub=account.initial_balance_rub,
        current_balance_rub=account.current_balance_rub,
        open_positions=len(open_positions),
        trade_locked_positions=sum(1 for position in positions if position.status == PaperPositionStatus.TRADE_LOCKED.value),
        ready_to_sell_positions=sum(1 for position in positions if position.status == PaperPositionStatus.READY_TO_SELL.value),
        sold_positions=len(sold),
        realized_pnl_rub=realized,
        unrealized_pnl_rub=unrealized,
        total_pnl_rub=total,
        average_roi_percent=sum(rois, Decimal("0")) / len(rois) if rois else Decimal("0"),
        median_roi_percent=Decimal(str(median(rois))) if rois else Decimal("0"),
        winrate_percent=(Decimal(len(wins)) / Decimal(len(sold)) * Decimal("100")) if sold else Decimal("0"),
        best_trade_rub=max(actual_values) if actual_values else None,
        worst_trade_rub=min(actual_values) if actual_values else None,
        expected_vs_actual_rub=expected_vs_actual,
    )

