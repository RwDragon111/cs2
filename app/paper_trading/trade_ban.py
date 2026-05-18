from __future__ import annotations

from datetime import datetime, timedelta

from app.utils.time import ensure_aware


def trade_ban_until(bought_at: datetime, days: int = 7) -> datetime:
    return bought_at + timedelta(days=days)


def can_sell(now: datetime, ban_until: datetime) -> bool:
    return ensure_aware(now) >= ensure_aware(ban_until)
