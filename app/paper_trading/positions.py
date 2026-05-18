from __future__ import annotations

from app.core.enums import PaperPositionStatus
from app.db.models import PaperPositionORM


def open_position_statuses() -> list[str]:
    return [
        PaperPositionStatus.PENDING_BUY.value,
        PaperPositionStatus.BOUGHT.value,
        PaperPositionStatus.TRADE_LOCKED.value,
        PaperPositionStatus.READY_TO_SELL.value,
        PaperPositionStatus.LISTED_FOR_SALE.value,
    ]


def is_sell_ready(position: PaperPositionORM) -> bool:
    return position.status == PaperPositionStatus.READY_TO_SELL.value

