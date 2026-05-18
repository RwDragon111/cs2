from __future__ import annotations

from app.config import Settings
from app.db.repositories import PaperRepository
from app.paper_trading.paper_pnl import PaperAnalytics, calculate_paper_analytics


class PaperAccountService:
    def __init__(self, settings: Settings, repository: PaperRepository) -> None:
        self.settings = settings
        self.repository = repository

    def initialize(self) -> None:
        self.repository.get_or_create_account(
            initial_rub=self.settings.paper_trading_initial_balance_rub,
            initial_usd=self.settings.paper_trading_initial_balance_usd,
            reset=self.settings.paper_trading_reset_on_start,
        )

    def analytics(self) -> PaperAnalytics:
        return calculate_paper_analytics(self.repository.account(), self.repository.positions())

