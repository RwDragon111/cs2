from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import timedelta
from decimal import Decimal

import httpx

from app.config import Settings
from app.utils.money import to_decimal
from app.utils.time import utc_now

logger = logging.getLogger(__name__)


class CurrencyRateProvider:
    """USD/RUB rate provider.

    The default source is the official Bank of Russia daily XML feed. Manual
    rate remains only as an explicit fallback so market scans can continue when
    the CBR endpoint is temporarily unavailable.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cached_rate: Decimal | None = None
        self._cached_until = utc_now()
        self._cached_source = ""

    @property
    def source(self) -> str:
        return self._cached_source or self.settings.rub_usd_rate_source

    async def usd_to_rub(self) -> Decimal:
        if self.settings.rub_usd_rate_source == "MANUAL":
            self._cached_source = "manual"
            return self.settings.manual_rub_usd_rate

        now = utc_now()
        if self._cached_rate is not None and now < self._cached_until:
            return self._cached_rate

        try:
            rate = await self._fetch_cbr_usd_rate()
        except Exception as exc:
            if not self.settings.currency_rate_fallback_to_manual:
                raise
            logger.warning("CBR USD/RUB rate request failed, using manual fallback: %s", exc)
            rate = self.settings.manual_rub_usd_rate
            self._cached_source = "manual_fallback"
        else:
            self._cached_source = "CBR"

        self._cached_rate = rate
        self._cached_until = now + timedelta(seconds=max(60, self.settings.currency_rate_cache_seconds))
        return rate

    async def _fetch_cbr_usd_rate(self) -> Decimal:
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(self.settings.cbr_daily_url)
            response.raise_for_status()

        root = ET.fromstring(response.content)
        for valute in root.findall("Valute"):
            if (valute.findtext("CharCode") or "").upper() != "USD":
                continue
            value = to_decimal((valute.findtext("Value") or "0").replace(",", "."))
            nominal = to_decimal((valute.findtext("Nominal") or "1").replace(",", "."), Decimal("1"))
            if value <= 0 or nominal <= 0:
                break
            return (value / nominal).quantize(Decimal("0.0001"))
        raise RuntimeError("USD rate was not found in CBR response")
