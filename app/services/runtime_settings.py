from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from app.config import Settings


SettingType = Literal["decimal", "int", "bool"]


@dataclass(frozen=True, slots=True)
class RuntimeSettingSpec:
    key: str
    attr: str
    value_type: SettingType
    min_value: Decimal | int | None = None
    max_value: Decimal | int | None = None
    description: str = ""


EDITABLE_SETTINGS: dict[str, RuntimeSettingSpec] = {
    "USE_MOCK_MARKETS": RuntimeSettingSpec("USE_MOCK_MARKETS", "use_mock_markets", "bool", description="Тестовые рынки вместо реальных API."),
    "MIN_PROFIT_PERCENT": RuntimeSettingSpec("MIN_PROFIT_PERCENT", "min_profit_percent", "decimal", Decimal("0"), Decimal("100"), "Минимальный ROI, %."),
    "MIN_PROFIT_ABSOLUTE": RuntimeSettingSpec("MIN_PROFIT_ABSOLUTE", "min_profit_absolute", "decimal", Decimal("0"), None, "Минимальная чистая прибыль, RUB."),
    "MIN_ITEM_PRICE": RuntimeSettingSpec("MIN_ITEM_PRICE", "min_item_price", "decimal", Decimal("0"), None, "Минимальная цена предмета, RUB."),
    "MAX_ITEM_PRICE": RuntimeSettingSpec("MAX_ITEM_PRICE", "max_item_price", "decimal", Decimal("1"), None, "Максимальная цена предмета, RUB."),
    "MIN_LIQUIDITY_SCORE": RuntimeSettingSpec("MIN_LIQUIDITY_SCORE", "min_liquidity_score", "int", 0, 100, "Минимальная ликвидность 0-100."),
    "MAX_PRICE_SPIKE_PERCENT": RuntimeSettingSpec("MAX_PRICE_SPIKE_PERCENT", "max_price_spike_percent", "decimal", Decimal("0"), Decimal("500"), "Максимальный скачок цены, %."),
    "PRICE_HISTORY_DAYS": RuntimeSettingSpec("PRICE_HISTORY_DAYS", "price_history_days", "int", 1, 365, "Период анализа истории цены, дней."),
    "SCAN_INTERVAL_SECONDS": RuntimeSettingSpec("SCAN_INTERVAL_SECONDS", "scan_interval_seconds", "int", 30, 86400, "Пауза между сканами, сек."),
    "MAX_DEALS_PER_SCAN": RuntimeSettingSpec("MAX_DEALS_PER_SCAN", "max_deals_per_scan", "int", 1, 50, "Сколько лучших сделок сохранять за один скан."),
    "LIS_SKINS_FEE_PERCENT": RuntimeSettingSpec("LIS_SKINS_FEE_PERCENT", "lis_skins_fee_percent", "decimal", Decimal("0"), Decimal("50"), "Комиссия покупки LIS-SKINS, %."),
    "CSGO_MARKET_FEE_PERCENT": RuntimeSettingSpec("CSGO_MARKET_FEE_PERCENT", "csgo_market_fee_percent", "decimal", Decimal("0"), Decimal("50"), "Комиссия продажи CSGO Market, %."),
    "WITHDRAWAL_FEE_PERCENT": RuntimeSettingSpec("WITHDRAWAL_FEE_PERCENT", "withdrawal_fee_percent", "decimal", Decimal("0"), Decimal("50"), "Комиссия вывода, %."),
    "LIS_SKINS_ONLY_UNLOCKED": RuntimeSettingSpec("LIS_SKINS_ONLY_UNLOCKED", "lis_skins_only_unlocked", "bool", description="Брать цену unlocked_price из LIS-SKINS export."),
    "LIS_SKINS_MIN_COUNT": RuntimeSettingSpec("LIS_SKINS_MIN_COUNT", "lis_skins_min_count", "int", 1, 100000, "Минимальное количество предметов в LIS-SKINS export."),
}


class RuntimeSettingsStore:
    def __init__(self, settings: Settings, path: str | Path | None = None) -> None:
        self.settings = settings
        self.path = Path(path or settings.runtime_settings_file)

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError(f"Runtime settings file must contain a JSON object: {self.path}")
        changed = False
        for key, raw_value in data.items():
            clean_key = str(key).strip().upper()
            spec = EDITABLE_SETTINGS.get(clean_key)
            if spec is None:
                continue
            parsed = parse_runtime_value(spec, raw_value)
            setattr(self.settings, spec.attr, parsed)
            changed = True
        if changed:
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            key: _json_value(getattr(self.settings, spec.attr))
            for key, spec in EDITABLE_SETTINGS.items()
        }
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")

    def set(self, key: str, raw_value: str) -> tuple[RuntimeSettingSpec, Decimal | int | bool]:
        clean_key = key.strip().upper()
        spec = EDITABLE_SETTINGS.get(clean_key)
        if spec is None:
            raise ValueError("Unknown setting")
        parsed = parse_runtime_value(spec, raw_value)
        setattr(self.settings, spec.attr, parsed)
        self.save()
        return spec, parsed


def format_editable_settings_help(path: str | Path | None = None) -> str:
    lines = ["Изменяемые настройки:", ""]
    for index, spec in enumerate(EDITABLE_SETTINGS.values(), start=1):
        current_range = _range_text(spec)
        lines.extend([f"{index}. {spec.key}{current_range}", spec.description, ""])
    lines.extend(["Примеры:", "/set MIN_PROFIT_PERCENT 2", "/set MAX_ITEM_PRICE 15000", "/set USE_MOCK_MARKETS false"])
    if path is not None:
        lines.extend(["", f"Файл настроек: {path}"])
    return "\n".join(lines)


def parse_runtime_value(spec: RuntimeSettingSpec, raw_value: object) -> Decimal | int | bool:
    if spec.value_type == "bool":
        return _parse_bool(raw_value)
    text = str(raw_value).strip().replace(",", ".")
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


def _parse_bool(raw_value: object) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    text = str(raw_value).strip().lower()
    if text in {"1", "true", "yes", "y", "on", "да"}:
        return True
    if text in {"0", "false", "no", "n", "off", "нет"}:
        return False
    raise ValueError("Boolean value must be true/false")


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    return value


def _range_text(spec: RuntimeSettingSpec) -> str:
    if spec.min_value is None and spec.max_value is None:
        return ""
    if spec.max_value is None:
        return f" (>= {spec.min_value})"
    return f" ({spec.min_value}-{spec.max_value})"
