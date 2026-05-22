from __future__ import annotations

from decimal import Decimal

import pytest

from app.config import Settings
from app.db.database import init_db
from app.db.repositories import SettingsRepository
from app.services.runtime_settings import apply_runtime_settings, set_runtime_setting


def test_set_runtime_setting_updates_settings_and_database(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'runtime.db'}", telegram_enabled=False)
    repo = SettingsRepository(init_db(settings.database_url))

    spec, value = set_runtime_setting(settings, repo, "MIN_PROFIT_PERCENT", "2.5")

    assert spec.key == "MIN_PROFIT_PERCENT"
    assert value == Decimal("2.5")
    assert settings.min_profit_percent == Decimal("2.5")
    assert repo.get("runtime.MIN_PROFIT_PERCENT") == "2.5"

    fresh_settings = Settings(database_url=f"sqlite:///{tmp_path / 'runtime.db'}", telegram_enabled=False)
    apply_runtime_settings(fresh_settings, repo)
    assert fresh_settings.min_profit_percent == Decimal("2.5")


def test_set_runtime_setting_rejects_unknown_or_out_of_range(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'runtime-errors.db'}", telegram_enabled=False)
    repo = SettingsRepository(init_db(settings.database_url))

    with pytest.raises(ValueError):
        set_runtime_setting(settings, repo, "UNKNOWN_SETTING", "1")

    with pytest.raises(ValueError):
        set_runtime_setting(settings, repo, "MIN_LIQUIDITY_SCORE", "101")
