from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.enums import PaperPositionStatus
from app.db.models import (
    ArbitrageOpportunityORM,
    MarketListingORM,
    MarketPaymentProfileORM,
    PaperAccountORM,
    PaperBalanceEventORM,
    PaperPositionORM,
    PaperTradeORM,
    PriceSnapshotORM,
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

