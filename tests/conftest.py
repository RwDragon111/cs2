from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.config import Settings
from app.currency.currency_engine import CurrencyEngine
from app.db.database import init_db
from app.db.repositories import OpportunityRepository, PaperRepository
from app.liquidity.liquidity_engine import LiquidityEngine
from app.markets.payment_profile import default_payment_profiles
from app.opportunities.detector import OpportunityDetector
from app.paper_trading.account import PaperAccountService
from app.paper_trading.paper_execution import PaperExecutionEngine
from app.pricing.pricing_engine import PricingEngine
from app.risk.risk_filters import RiskFilters
from app.scheduler.jobs import build_connectors, fetch_all_listings, fetch_fees, fetch_sales_history_sample


@dataclass
class TestApp:
    settings: Settings
    session_factory: object
    connectors: dict
    opportunity_repository: OpportunityRepository
    paper_repository: PaperRepository
    paper_account: PaperAccountService
    detector: OpportunityDetector
    paper_engine: PaperExecutionEngine


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        telegram_enabled=False,
        use_mock_markets=True,
        enable_dmarket_stats=False,
        manual_rub_usd_rate=Decimal("100"),
        dmarket_extra_titles="",
        market_poll_interval_seconds=1,
        opportunity_scan_interval_seconds=1,
        paper_position_check_interval_seconds=1,
        paper_trading_trade_ban_days=0,
    )


@pytest.fixture
async def test_app(settings: Settings) -> TestApp:
    session_factory = init_db(settings.database_url)
    connectors = build_connectors(settings)
    currency = CurrencyEngine(settings)
    pricing = PricingEngine(settings)
    liquidity = LiquidityEngine()
    risk = RiskFilters(settings)
    profiles = default_payment_profiles(settings)
    fees = await fetch_fees(connectors)
    opportunity_repository = OpportunityRepository(session_factory)
    paper_repository = PaperRepository(session_factory)
    paper_account = PaperAccountService(settings, paper_repository)
    paper_account.initialize()
    detector = OpportunityDetector(settings, currency, pricing, liquidity, risk, profiles, fees)
    paper_engine = PaperExecutionEngine(
        settings=settings,
        paper_repository=paper_repository,
        opportunity_repository=opportunity_repository,
        connectors=connectors,
        pricing_engine=pricing,
        currency_engine=currency,
        payment_profiles=profiles,
        fees_by_market=fees,
    )
    return TestApp(
        settings=settings,
        session_factory=session_factory,
        connectors=connectors,
        opportunity_repository=opportunity_repository,
        paper_repository=paper_repository,
        paper_account=paper_account,
        detector=detector,
        paper_engine=paper_engine,
    )


async def detect_mock_opportunities(app: TestApp):
    currency = CurrencyEngine(app.settings)
    by_market = await fetch_all_listings(app.connectors, currency)
    listings = [listing for rows in by_market.values() for listing in rows]
    histories = await fetch_sales_history_sample(app.connectors, {listing.normalized_name for listing in listings})
    opportunities = app.detector.detect(listings, histories)
    app.opportunity_repository.save_many(opportunities)
    return opportunities
