from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

import httpx

from app.config import Settings
from app.utils.money import to_decimal
from app.utils.time import utc_now

logger = logging.getLogger(__name__)
RATE_QUANT = Decimal("0.0001")


@dataclass(slots=True)
class ExchangeRate:
    value: Decimal
    source: str
    effective_date: str | None = None
    fetched_at: datetime | None = None


class CurrencyRateProvider:
    USD_CHAR_CODE = "USD"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cached: ExchangeRate | None = None

    async def usd_to_rub(self) -> Decimal:
        return (await self.get_usd_to_rub()).value

    async def get_usd_to_rub(self) -> ExchangeRate:
        if self._cached_is_fresh():
            return self._cached  # type: ignore[return-value]

        if self.settings.rub_usd_rate_source == "manual":
            return self._cache_manual()

        try:
            rate = await self._fetch_cbr_async()
            self._cached = rate
            logger.info(
                "Loaded USD/RUB rate from CBR: %s effective_date=%s",
                rate.value,
                rate.effective_date or "unknown",
            )
            return rate
        except Exception as exc:
            if not self.settings.currency_rate_fallback_to_manual:
                raise
            logger.warning("CBR USD/RUB rate request failed, using manual fallback %s: %s", self.settings.manual_rub_usd_rate, exc)
            return self._cache_manual(source="manual_fallback")

    def usd_to_rub_sync(self) -> Decimal:
        return self.get_usd_to_rub_sync().value

    def get_usd_to_rub_sync(self) -> ExchangeRate:
        if self._cached_is_fresh():
            return self._cached  # type: ignore[return-value]

        if self.settings.rub_usd_rate_source == "manual":
            return self._cache_manual()

        try:
            rate = self._fetch_cbr_sync()
            self._cached = rate
            logger.info(
                "Loaded USD/RUB rate from CBR: %s effective_date=%s",
                rate.value,
                rate.effective_date or "unknown",
            )
            return rate
        except Exception as exc:
            if not self.settings.currency_rate_fallback_to_manual:
                raise
            logger.warning("CBR USD/RUB rate request failed, using manual fallback %s: %s", self.settings.manual_rub_usd_rate, exc)
            return self._cache_manual(source="manual_fallback")

    async def _fetch_cbr_async(self) -> ExchangeRate:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(self.settings.cbr_daily_rates_url)
            response.raise_for_status()
            return self._parse_cbr_xml(response.content)

    def _fetch_cbr_sync(self) -> ExchangeRate:
        with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
            response = client.get(self.settings.cbr_daily_rates_url)
            response.raise_for_status()
            return self._parse_cbr_xml(response.content)

    def _cache_manual(self, source: str = "manual") -> ExchangeRate:
        rate = ExchangeRate(
            value=_quantize_rate(self.settings.manual_rub_usd_rate),
            source=source,
            fetched_at=utc_now(),
        )
        self._cached = rate
        return rate

    def _cached_is_fresh(self) -> bool:
        if self._cached is None or self._cached.fetched_at is None:
            return False
        ttl = timedelta(seconds=max(60, self.settings.currency_rate_cache_ttl_seconds))
        return utc_now() - self._cached.fetched_at < ttl

    def _parse_cbr_xml(self, raw_xml: bytes) -> ExchangeRate:
        root = ET.fromstring(raw_xml)
        effective_date = root.attrib.get("Date")
        for valute in root.findall("Valute"):
            char_code = (valute.findtext("CharCode") or "").strip().upper()
            if char_code != self.USD_CHAR_CODE:
                continue
            nominal = to_decimal((valute.findtext("Nominal") or "1").replace(",", "."))
            value = to_decimal((valute.findtext("Value") or "0").replace(",", "."))
            if nominal <= 0 or value <= 0:
                raise ValueError("CBR USD rate has invalid nominal/value")
            return ExchangeRate(
                value=_quantize_rate(value / nominal),
                source="cbr",
                effective_date=effective_date,
                fetched_at=utc_now(),
            )
        raise ValueError("CBR XML_daily response does not contain USD rate")


def _quantize_rate(value: Decimal) -> Decimal:
    return to_decimal(value).quantize(RATE_QUANT)
