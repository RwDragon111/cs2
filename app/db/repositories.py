from __future__ import annotations

import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import PaperPositionStatus
from app.db.models import (
    ArbitrageOpportunityORM,
    DealORM,
    DemoAccountORM,
    DemoTransactionORM,
    IgnoredItemORM,
    InventoryORM,
    MarketListingORM,
    MarketPaymentProfileORM,
    PaperAccountORM,
    PaperBalanceEventORM,
    PaperPositionORM,
    PaperTradeORM,
    PriceSnapshotORM,
    ScanLogORM,
    SettingORM,
    TradingModeORM,
)
from app.markets.base import MarketListing
from app.markets.payment_profile import MarketPaymentProfile
from app.opportunities.models import ArbitrageOpportunity
from app.utils.time import utc_now


class ListingRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def replace_market_listings(self, market_name: str, listings: Iterable[MarketListing]) -> None:
        with self.session_factory() as session:
            session.execute(delete(MarketListingORM).where(MarketListingORM.market_name == market_name))
            for listing in listings:
                session.add(
                    MarketListingORM(
                        listing_id=listing.id,
                        market_name=listing.market_name,
                        item_name=listing.item_name,
                        normalized_name=listing.normalized_name,
                        price=listing.price,
                        currency=listing.currency,
                        price_rub=listing.price_rub,
                        price_usd=listing.price_usd,
                        available=listing.available,
                        tradable=listing.tradable,
                        raw_payload=listing.raw_payload,
                        created_at=listing.created_at,
                    )
                )
                if listing.price_rub is not None:
                    session.add(
                        PriceSnapshotORM(
                            market_name=listing.market_name,
                            normalized_name=listing.normalized_name,
                            price_rub=listing.price_rub,
                        )
                    )
            session.commit()

    def latest_listings(self) -> list[MarketListingORM]:
        with self.session_factory() as session:
            return list(session.scalars(select(MarketListingORM).where(MarketListingORM.available.is_(True))).all())

    def latest_by_market(self, market_name: str, limit: int = 10) -> list[MarketListingORM]:
        with self.session_factory() as session:
            stmt = (
                select(MarketListingORM)
                .where(MarketListingORM.market_name == market_name, MarketListingORM.available.is_(True))
                .order_by(MarketListingORM.price_rub.asc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())

    def count_by_market(self, market_name: str) -> int:
        with self.session_factory() as session:
            rows = session.scalars(
                select(MarketListingORM.listing_id).where(
                    MarketListingORM.market_name == market_name,
                    MarketListingORM.available.is_(True),
                )
            ).all()
            return len(list(rows))

    def latest_by_markets(self, market_names: list[str], limit_per_market: int = 200) -> list[MarketListingORM]:
        rows: list[MarketListingORM] = []
        with self.session_factory() as session:
            for market_name in market_names:
                stmt = (
                    select(MarketListingORM)
                    .where(MarketListingORM.market_name == market_name, MarketListingORM.available.is_(True))
                    .order_by(MarketListingORM.price_rub.asc())
                    .limit(limit_per_market)
                )
                rows.extend(session.scalars(stmt).all())
        return rows


class PaymentProfileRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def upsert_profiles(self, profiles: Iterable[MarketPaymentProfile]) -> None:
        with self.session_factory() as session:
            for profile in profiles:
                row = session.scalar(
                    select(MarketPaymentProfileORM).where(MarketPaymentProfileORM.market_name == profile.market_name)
                )
                data = profile.model_dump()
                if row is None:
                    session.add(MarketPaymentProfileORM(**data))
                else:
                    for key, value in data.items():
                        setattr(row, key, value)
            session.commit()


class OpportunityRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def save_many(self, opportunities: Iterable[ArbitrageOpportunity]) -> int:
        count = 0
        with self.session_factory() as session:
            for opportunity in opportunities:
                existing = session.get(ArbitrageOpportunityORM, opportunity.id)
                data = opportunity.model_dump()
                data["is_active"] = opportunity.expires_at is None
                if existing is None:
                    session.add(ArbitrageOpportunityORM(**data))
                    count += 1
                else:
                    for key, value in data.items():
                        setattr(existing, key, value)
            session.commit()
        return count

    def get(self, opportunity_id: str) -> ArbitrageOpportunityORM | None:
        with self.session_factory() as session:
            return session.get(ArbitrageOpportunityORM, opportunity_id)

    def active(self, limit: int = 20) -> list[ArbitrageOpportunityORM]:
        with self.session_factory() as session:
            stmt: Select[tuple[ArbitrageOpportunityORM]] = (
                select(ArbitrageOpportunityORM)
                .where(ArbitrageOpportunityORM.is_active.is_(True))
                .order_by(ArbitrageOpportunityORM.detected_at.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())

    def expire_missing(self, active_ids: set[str]) -> int:
        with self.session_factory() as session:
            rows = list(session.scalars(select(ArbitrageOpportunityORM).where(ArbitrageOpportunityORM.is_active.is_(True))))
            changed = 0
            now = utc_now()
            for row in rows:
                if row.id not in active_ids:
                    row.is_active = False
                    row.expires_at = now
                    changed += 1
            session.commit()
            return changed


class PaperRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get_or_create_account(
        self,
        initial_rub: Decimal,
        initial_usd: Decimal,
        reset: bool = False,
    ) -> PaperAccountORM:
        with self.session_factory() as session:
            account = session.scalar(select(PaperAccountORM).where(PaperAccountORM.name == "default"))
            if account is None:
                account = PaperAccountORM(
                    name="default",
                    initial_balance_rub=initial_rub,
                    current_balance_rub=initial_rub,
                    initial_balance_usd=initial_usd,
                    current_balance_usd=initial_usd,
                )
                session.add(account)
                session.flush()
                session.add(
                    PaperBalanceEventORM(
                        account_id=account.id,
                        event_type="INITIAL_DEPOSIT",
                        amount_rub=initial_rub,
                        balance_after_rub=initial_rub,
                    )
                )
            elif reset:
                session.execute(delete(PaperBalanceEventORM).where(PaperBalanceEventORM.account_id == account.id))
                session.execute(delete(PaperTradeORM))
                session.execute(delete(PaperPositionORM).where(PaperPositionORM.account_id == account.id))
                account.initial_balance_rub = initial_rub
                account.current_balance_rub = initial_rub
                account.initial_balance_usd = initial_usd
                account.current_balance_usd = initial_usd
                session.add(
                    PaperBalanceEventORM(
                        account_id=account.id,
                        event_type="RESET",
                        amount_rub=initial_rub,
                        balance_after_rub=initial_rub,
                    )
                )
            session.commit()
            session.refresh(account)
            return account

    def account(self) -> PaperAccountORM:
        with self.session_factory() as session:
            account = session.scalar(select(PaperAccountORM).where(PaperAccountORM.name == "default"))
            if account is None:
                raise RuntimeError("Paper account is not initialized")
            return account

    def has_open_position_for_listing(self, buy_market: str, source_listing_id: str) -> bool:
        with self.session_factory() as session:
            row = session.scalar(
                select(PaperPositionORM).where(
                    PaperPositionORM.buy_market == buy_market,
                    PaperPositionORM.source_listing_id == source_listing_id,
                    PaperPositionORM.status.in_(
                        [
                            PaperPositionStatus.PENDING_BUY.value,
                            PaperPositionStatus.BOUGHT.value,
                            PaperPositionStatus.TRADE_LOCKED.value,
                            PaperPositionStatus.READY_TO_SELL.value,
                            PaperPositionStatus.LISTED_FOR_SALE.value,
                        ]
                    ),
                )
            )
            return row is not None

    def create_position(self, position: PaperPositionORM, total_cost: Decimal) -> PaperPositionORM:
        with self.session_factory() as session:
            account = session.get(PaperAccountORM, position.account_id)
            if account is None:
                raise RuntimeError("Paper account is not initialized")
            account.current_balance_rub -= total_cost
            session.add(position)
            session.flush()
            session.add(
                PaperTradeORM(
                    position_id=position.id,
                    side="BUY",
                    price_rub=position.buy_price_rub,
                    fees_rub=position.buy_fees_rub,
                )
            )
            session.add(
                PaperBalanceEventORM(
                    account_id=account.id,
                    event_type="PAPER_BUY",
                    amount_rub=-total_cost,
                    balance_after_rub=account.current_balance_rub,
                    position_id=position.id,
                )
            )
            session.commit()
            session.refresh(position)
            return position

    def get_position(self, position_id: str) -> PaperPositionORM | None:
        with self.session_factory() as session:
            return session.get(PaperPositionORM, position_id)

    def positions(self, statuses: list[str] | None = None) -> list[PaperPositionORM]:
        with self.session_factory() as session:
            stmt = select(PaperPositionORM).order_by(PaperPositionORM.created_at.desc())
            if statuses:
                stmt = stmt.where(PaperPositionORM.status.in_(statuses))
            return list(session.scalars(stmt).all())

    def update_trade_locked_to_ready(self, now: datetime) -> list[PaperPositionORM]:
        ready: list[PaperPositionORM] = []
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(PaperPositionORM).where(
                        PaperPositionORM.status == PaperPositionStatus.TRADE_LOCKED.value,
                        PaperPositionORM.trade_ban_until <= now,
                    )
                )
            )
            for row in rows:
                row.status = PaperPositionStatus.READY_TO_SELL.value
                ready.append(row)
            session.commit()
            for row in ready:
                session.refresh(row)
            return ready

    def mark_sold(
        self,
        position_id: str,
        sell_price_rub: Decimal,
        sell_fee_rub: Decimal,
        net_revenue_rub: Decimal,
        actual_profit_rub: Decimal,
        actual_roi_percent: Decimal,
    ) -> PaperPositionORM:
        with self.session_factory() as session:
            position = session.get(PaperPositionORM, position_id)
            if position is None:
                raise RuntimeError("Paper position not found")
            account = session.get(PaperAccountORM, position.account_id)
            if account is None:
                raise RuntimeError("Paper account is not initialized")
            account.current_balance_rub += net_revenue_rub
            position.status = PaperPositionStatus.SOLD.value
            position.sold_at = utc_now()
            position.virtual_sell_price_rub = sell_price_rub
            position.actual_profit_rub = actual_profit_rub
            position.actual_roi_percent = actual_roi_percent
            session.add(
                PaperTradeORM(
                    position_id=position.id,
                    side="SELL",
                    price_rub=sell_price_rub,
                    fees_rub=sell_fee_rub,
                )
            )
            session.add(
                PaperBalanceEventORM(
                    account_id=account.id,
                    event_type="PAPER_SELL",
                    amount_rub=net_revenue_rub,
                    balance_after_rub=account.current_balance_rub,
                    position_id=position.id,
                )
            )
            session.commit()
            session.refresh(position)
            return position


class DealRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def upsert(self, payload: dict) -> tuple[DealORM, bool]:
        with self.session_factory() as session:
            existing = session.scalar(select(DealORM).where(DealORM.dedupe_key == payload["dedupe_key"]))
            created = existing is None
            if existing is None:
                existing = DealORM(**payload)
                session.add(existing)
            else:
                for key, value in payload.items():
                    if key in {"id", "created_at"}:
                        continue
                    setattr(existing, key, value)
            session.commit()
            session.refresh(existing)
            return existing, created

    def get(self, deal_id: int) -> DealORM | None:
        with self.session_factory() as session:
            return session.get(DealORM, deal_id)

    def latest(self, limit: int = 10, include_hidden: bool = False) -> list[DealORM]:
        with self.session_factory() as session:
            stmt = select(DealORM).order_by(DealORM.updated_at.desc(), DealORM.created_at.desc()).limit(limit)
            if not include_hidden:
                stmt = stmt.where(DealORM.status != "hidden")
            return list(session.scalars(stmt).all())

    def best(self, limit: int = 10) -> list[DealORM]:
        with self.session_factory() as session:
            stmt = (
                select(DealORM)
                .where(DealORM.status != "hidden")
                .order_by(DealORM.roi.desc(), DealORM.profit.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt).all())

    def search(self, query: str, limit: int = 10, include_hidden: bool = False) -> list[DealORM]:
        terms = [term for term in re.split(r"[^0-9A-Za-zА-Яа-я™★-]+", query) if len(term) > 1]
        with self.session_factory() as session:
            stmt = select(DealORM).order_by(DealORM.updated_at.desc(), DealORM.created_at.desc()).limit(limit)
            if not include_hidden:
                stmt = stmt.where(DealORM.status != "hidden")
            for term in terms[:8]:
                stmt = stmt.where(DealORM.item_name.ilike(f"%{term}%"))
            return list(session.scalars(stmt).all())

    def mark_status(self, deal_id: int, status: str) -> DealORM | None:
        with self.session_factory() as session:
            row = session.get(DealORM, deal_id)
            if row is None:
                return None
            row.status = status
            session.commit()
            session.refresh(row)
            return row

    def count_recent(self, minutes: int = 60) -> int:
        since = utc_now() - timedelta(minutes=minutes)
        with self.session_factory() as session:
            return len(list(session.scalars(select(DealORM.id).where(DealORM.created_at >= since)).all()))


class InventoryRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def create(self, payload: dict) -> InventoryORM:
        with self.session_factory() as session:
            row = InventoryORM(**payload)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def get(self, inventory_id: int) -> InventoryORM | None:
        with self.session_factory() as session:
            return session.get(InventoryORM, inventory_id)

    def list(self, statuses: list[str] | None = None, is_demo: bool | None = None, limit: int = 50) -> list[InventoryORM]:
        with self.session_factory() as session:
            stmt = select(InventoryORM).order_by(InventoryORM.created_at.desc()).limit(limit)
            if statuses:
                stmt = stmt.where(InventoryORM.status.in_(statuses))
            if is_demo is not None:
                stmt = stmt.where(InventoryORM.is_demo.is_(is_demo))
            return list(session.scalars(stmt).all())

    def mark_ready_items(self, now: datetime | None = None) -> list[InventoryORM]:
        now = now or utc_now()
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(InventoryORM).where(
                        InventoryORM.status.in_(["bought", "trade_locked"]),
                        InventoryORM.trade_lock_until <= now,
                    )
                )
            )
            for row in rows:
                row.status = "ready_to_sell"
            session.commit()
            for row in rows:
                session.refresh(row)
            return rows

    def mark_sold(self, inventory_id: int, sell_price: Decimal, actual_profit: Decimal, actual_roi: Decimal) -> InventoryORM:
        with self.session_factory() as session:
            row = session.get(InventoryORM, inventory_id)
            if row is None:
                raise RuntimeError("Inventory item not found")
            row.status = "sold"
            row.sold_at = utc_now()
            row.sell_price = sell_price
            row.actual_profit = actual_profit
            row.actual_roi = actual_roi
            session.commit()
            session.refresh(row)
            return row


class SettingsRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get(self, key: str, default: str | None = None) -> str | None:
        with self.session_factory() as session:
            row = session.get(SettingORM, key)
            return row.value if row is not None else default

    def set(self, key: str, value: str) -> None:
        with self.session_factory() as session:
            row = session.get(SettingORM, key)
            if row is None:
                session.add(SettingORM(key=key, value=value))
            else:
                row.value = value
            session.commit()

    def delete(self, key: str) -> None:
        with self.session_factory() as session:
            row = session.get(SettingORM, key)
            if row is not None:
                session.delete(row)
                session.commit()


class IgnoredItemRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def add(self, item_name: str, reason: str = "") -> IgnoredItemORM:
        with self.session_factory() as session:
            row = IgnoredItemORM(item_name=item_name, reason=reason)
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def names(self) -> set[str]:
        with self.session_factory() as session:
            return {str(name).lower() for name in session.scalars(select(IgnoredItemORM.item_name)).all()}


class ScanLogRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def start(self) -> ScanLogORM:
        with self.session_factory() as session:
            row = ScanLogORM(started_at=utc_now())
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def finish(self, scan_id: int, found_deals_count: int, error_message: str | None = None) -> ScanLogORM | None:
        with self.session_factory() as session:
            row = session.get(ScanLogORM, scan_id)
            if row is None:
                return None
            row.finished_at = utc_now()
            row.found_deals_count = found_deals_count
            row.error_message = error_message
            session.commit()
            session.refresh(row)
            return row

    def latest(self) -> ScanLogORM | None:
        with self.session_factory() as session:
            return session.scalar(select(ScanLogORM).order_by(ScanLogORM.started_at.desc()).limit(1))


class TradingStateRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def initialize(self, default_mode: str, demo_balance: Decimal, demo_currency: str) -> None:
        with self.session_factory() as session:
            mode = session.get(TradingModeORM, 1)
            if mode is None:
                session.add(TradingModeORM(id=1, mode=default_mode))
            account = session.get(DemoAccountORM, 1)
            if account is None:
                account = DemoAccountORM(
                    id=1,
                    initial_balance=demo_balance,
                    balance=demo_balance,
                    currency=demo_currency,
                )
                session.add(account)
                session.flush()
                session.add(
                    DemoTransactionORM(
                        type="reset",
                        amount=demo_balance,
                        balance_before=Decimal("0"),
                        balance_after=demo_balance,
                        comment="Initial demo balance",
                    )
                )
            session.commit()

    def get_mode(self) -> str:
        with self.session_factory() as session:
            row = session.get(TradingModeORM, 1)
            return row.mode if row is not None else "DEMO"

    def set_mode(self, mode: str) -> str:
        clean_mode = mode.upper()
        if clean_mode not in {"DEMO", "REAL"}:
            raise ValueError("Mode must be DEMO or REAL")
        with self.session_factory() as session:
            row = session.get(TradingModeORM, 1)
            if row is None:
                row = TradingModeORM(id=1, mode=clean_mode)
                session.add(row)
            else:
                row.mode = clean_mode
            session.commit()
            return clean_mode

    def demo_account(self) -> DemoAccountORM:
        with self.session_factory() as session:
            account = session.get(DemoAccountORM, 1)
            if account is None:
                raise RuntimeError("Demo account is not initialized")
            return account

    def apply_demo_transaction(
        self,
        transaction_type: str,
        amount: Decimal,
        item_name: str | None = None,
        related_inventory_id: int | None = None,
        comment: str = "",
    ) -> DemoAccountORM:
        with self.session_factory() as session:
            account = session.get(DemoAccountORM, 1)
            if account is None:
                raise RuntimeError("Demo account is not initialized")
            before = Decimal(account.balance)
            after = before + Decimal(amount)
            account.balance = after
            session.add(
                DemoTransactionORM(
                    type=transaction_type,
                    item_name=item_name,
                    amount=amount,
                    balance_before=before,
                    balance_after=after,
                    related_inventory_id=related_inventory_id,
                    comment=comment,
                )
            )
            session.commit()
            session.refresh(account)
            return account

    def set_demo_balance(self, balance: Decimal, comment: str = "Manual set balance") -> DemoAccountORM:
        with self.session_factory() as session:
            account = session.get(DemoAccountORM, 1)
            if account is None:
                raise RuntimeError("Demo account is not initialized")
            before = Decimal(account.balance)
            account.balance = balance
            session.add(
                DemoTransactionORM(
                    type="manual_set_balance",
                    amount=balance - before,
                    balance_before=before,
                    balance_after=balance,
                    comment=comment,
                )
            )
            session.commit()
            session.refresh(account)
            return account

    def reset_demo(self, balance: Decimal, currency: str) -> DemoAccountORM:
        with self.session_factory() as session:
            session.execute(delete(DemoTransactionORM))
            session.execute(delete(InventoryORM).where(InventoryORM.is_demo.is_(True)))
            account = session.get(DemoAccountORM, 1)
            if account is None:
                account = DemoAccountORM(id=1, initial_balance=balance, balance=balance, currency=currency)
                session.add(account)
                session.flush()
            else:
                account.initial_balance = balance
                account.balance = balance
                account.currency = currency
            session.add(
                DemoTransactionORM(
                    type="reset",
                    amount=balance,
                    balance_before=Decimal("0"),
                    balance_after=balance,
                    comment="Demo account reset",
                )
            )
            session.commit()
            session.refresh(account)
            return account

    def demo_transactions(self, limit: int = 1000) -> list[DemoTransactionORM]:
        with self.session_factory() as session:
            stmt = select(DemoTransactionORM).order_by(DemoTransactionORM.created_at.desc()).limit(limit)
            return list(session.scalars(stmt).all())
