from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.config import Settings
from app.db.repositories import SettingsRepository


SettingType = Literal["decimal", "int"]


@dataclass(frozen=True, slots=True)
class RuntimeSettingSpec:
    key: str
    attr: str
    value_type: SettingType
    min_value: Decimal | int | None = None
    max_value: Decimal | int | None = None
    description: str = ""


EDITABLE_SETTINGS: dict[str, RuntimeSettingSpec] = {
    "MIN_PROFIT_PERCENT": RuntimeSettingSpec("MIN_PROFIT_PERCENT", "min_profit_percent", "decimal", Decimal("0"), Decimal("100"), "Минимальный ROI, %."),
    "MIN_PROFIT_ABSOLUTE": RuntimeSettingSpec("MIN_PROFIT_ABSOLUTE", "min_profit_absolute", "decimal", Decimal("0"), None, "Минимальная прибыль, RUB."),
    "MIN_ITEM_PRICE": RuntimeSettingSpec("MIN_ITEM_PRICE", "min_item_price", "decimal", Decimal("0"), None, "Минимальная цена предмета, RUB."),
    "MAX_ITEM_PRICE": RuntimeSettingSpec("MAX_ITEM_PRICE", "max_item_price", "decimal", Decimal("1"), None, "Максимальная цена предмета, RUB."),
    "MIN_LIQUIDITY_SCORE": RuntimeSettingSpec("MIN_LIQUIDITY_SCORE", "min_liquidity_score", "int", 0, 100, "Минимальная ликвидность 0-100."),
    "MAX_PRICE_SPIKE_PERCENT": RuntimeSettingSpec("MAX_PRICE_SPIKE_PERCENT", "max_price_spike_percent", "decimal", Decimal("0"), Decimal("500"), "Максимальный скачок цены, %."),
    "PRICE_HISTORY_DAYS": RuntimeSettingSpec("PRICE_HISTORY_DAYS", "price_history_days", "int", 1, 365, "Период анализа истории цены, дней."),
    "SCAN_INTERVAL_SECONDS": RuntimeSettingSpec("SCAN_INTERVAL_SECONDS", "scan_interval_seconds", "int", 30, 86400, "Пауза между сканами, сек."),
    "DMARKET_DYNAMIC_TITLE_LIMIT": RuntimeSettingSpec("DMARKET_DYNAMIC_TITLE_LIMIT", "dmarket_dynamic_title_limit", "int", 1, 500, "Сколько названий проверять на DMarket."),
    "DMARKET_FEE_PERCENT": RuntimeSettingSpec("DMARKET_FEE_PERCENT", "dmarket_fee_percent", "decimal", Decimal("0"), Decimal("50"), "Комиссия покупки DMarket, %."),
    "CSGO_MARKET_FEE_PERCENT": RuntimeSettingSpec("CSGO_MARKET_FEE_PERCENT", "csgo_market_fee_percent", "decimal", Decimal("0"), Decimal("50"), "Комиссия продажи CSGO Market, %."),
    "WITHDRAWAL_FEE_PERCENT": RuntimeSettingSpec("WITHDRAWAL_FEE_PERCENT", "withdrawal_fee_percent", "decimal", Decimal("0"), Decimal("50"), "Комиссия вывода, %."),
}


def apply_runtime_settings(settings: Settings, repository: SettingsRepository) -> None:
    for spec in EDITABLE_SETTINGS.values():
        raw_value = repository.get(_repo_key(spec.key))
        if raw_value is None:
            continue
        setattr(settings, spec.attr, parse_runtime_value(spec, raw_value))


def set_runtime_setting(settings: Settings, repository: SettingsRepository, key: str, raw_value: str) -> tuple[RuntimeSettingSpec, Decimal | int]:
    clean_key = key.strip().upper()
    spec = EDITABLE_SETTINGS.get(clean_key)
    if spec is None:
        raise ValueError("Unknown setting")
    parsed = parse_runtime_value(spec, raw_value)
    setattr(settings, spec.attr, parsed)
    repository.set(_repo_key(spec.key), str(parsed))
    return spec, parsed


def reset_runtime_settings(settings: Settings, repository: SettingsRepository) -> None:
    for spec in EDITABLE_SETTINGS.values():
        repository.delete(_repo_key(spec.key))


def format_editable_settings_help() -> str:
    lines = ["Изменяемые настройки:", ""]
    for index, spec in enumerate(EDITABLE_SETTINGS.values(), start=1):
        lines.extend([f"{index}. {spec.key}", spec.description, ""])
    lines.extend(["Пример:", "/set MIN_PROFIT_PERCENT 2"])
    return "\n".join(lines)


def parse_runtime_value(spec: RuntimeSettingSpec, raw_value: str) -> Decimal | int:
    text = raw_value.strip().replace(",", ".")
    if not text:
        raise ValueError("Empty value")
    if spec.value_type == "int":
        value: Decimal | int = int(Decimal(text))
    else:
        value = Decimal(text)
    if spec.min_value is not None and value < spec.min_value:
        raise ValueError(f"{spec.key} must be >= {spec.min_value}")
    if spec.max_value is not None and value > spec.max_value:
        raise ValueError(f"{spec.key} must be <= {spec.max_value}")
    return value


def _repo_key(key: str) -> str:
    return f"runtime.{key}"
