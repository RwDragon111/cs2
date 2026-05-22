from decimal import Decimal

from app.config import Settings
from app.services.runtime_settings import RuntimeSettingsStore


def test_runtime_settings_file_updates_settings_and_persists(tmp_path):
    settings = Settings(telegram_enabled=False, runtime_settings_file=str(tmp_path / "settings.json"))
    store = RuntimeSettingsStore(settings)
    store.load()

    spec, value = store.set("MIN_PROFIT_PERCENT", "2.5")

    assert spec.key == "MIN_PROFIT_PERCENT"
    assert value == Decimal("2.5")
    assert settings.min_profit_percent == Decimal("2.5")

    fresh_settings = Settings(telegram_enabled=False, runtime_settings_file=str(tmp_path / "settings.json"))
    RuntimeSettingsStore(fresh_settings).load()
    assert fresh_settings.min_profit_percent == Decimal("2.5")


def test_runtime_settings_file_rejects_unknown_or_out_of_range(tmp_path):
    settings = Settings(telegram_enabled=False, runtime_settings_file=str(tmp_path / "settings.json"))
    store = RuntimeSettingsStore(settings)
    store.load()

    try:
        store.set("UNKNOWN_SETTING", "1")
    except ValueError as exc:
        assert "Unknown setting" in str(exc)
    else:
        raise AssertionError("unknown setting must fail")

    try:
        store.set("MIN_LIQUIDITY_SCORE", "101")
    except ValueError as exc:
        assert "MIN_LIQUIDITY_SCORE" in str(exc)
    else:
        raise AssertionError("out-of-range setting must fail")
