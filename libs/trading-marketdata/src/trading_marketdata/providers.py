"""Data access is independent of any broker SDK or order API."""

import math
from datetime import timedelta
from typing import Protocol

from trading_contracts import Bar, Quote, SafetyError
from trading_contracts.interfaces import Clock


class MarketData(Protocol):
    async def bars(self, symbol: str) -> list[Bar]: ...
    async def quote(self, symbol: str) -> Quote: ...


class ValidatedMarketData:
    def __init__(self, provider: MarketData, clock: Clock) -> None:
        self.provider, self.clock = provider, clock

    async def bars(self, symbol: str) -> list[Bar]:
        bars = await self.provider.bars(symbol)
        if not bars:
            raise SafetyError("No historical bars")
        if any(b.time.tzinfo is None or not math.isfinite(b.close) or b.close <= 0 for b in bars):
            raise SafetyError("Invalid historical bar")
        if any(a.time >= b.time for a, b in zip(bars, bars[1:], strict=False)):
            raise SafetyError("Unordered or duplicate historical bars")
        return bars

    async def quote(self, symbol: str) -> Quote:
        quote = await self.provider.quote(symbol)
        if quote.time.tzinfo is None or not all(
            math.isfinite(v) and v > 0 for v in (quote.bid, quote.ask)
        ):
            raise SafetyError("Invalid quote")
        if quote.bid > quote.ask:
            raise SafetyError("Crossed quote")
        if not timedelta(0) <= self.clock.now() - quote.time <= timedelta(seconds=10):
            raise SafetyError("Stale or future quote")
        # Preserve the live/delayed flag. Mandatory execution risk decides eligibility.
        return quote
