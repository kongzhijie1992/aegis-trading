import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from trading_contracts.models import Bar, SafetyError


def signal(bars: list[Bar], now: datetime, fast: int = 20, slow: int = 50) -> int:
    """20/50 SMA target: one share when fast > slow, otherwise zero."""
    if type(fast) is not int or type(slow) is not int or not 1 <= fast < slow:
        raise SafetyError("Require integer SMA windows 1 <= fast < slow")
    if now.tzinfo is None or any(b.time.tzinfo is None for b in bars):
        raise SafetyError("Timezone-aware times required")
    completed = [b for b in bars if b.time + timedelta(minutes=5) <= now]
    if len(completed) < slow:
        raise SafetyError(f"Need {slow} completed five-minute bars")
    if any(b.time.tzinfo is None or not math.isfinite(b.close) or b.close <= 0 for b in completed):
        raise SafetyError("Invalid historical bars")
    if any(a.time >= b.time for a, b in zip(completed, completed[1:], strict=False)):
        raise SafetyError("Historical bars must be strictly ordered")
    if now - (completed[-1].time + timedelta(minutes=5)) > timedelta(minutes=6):
        raise SafetyError("Historical bars are stale")
    return int(
        sum(b.close for b in completed[-fast:]) / fast
        > sum(b.close for b in completed[-slow:]) / slow
    )


@dataclass(frozen=True)
class SmaStrategy:
    fast: int = 20
    slow: int = 50
    name: str = "sma"

    def target(self, bars: list[Bar], now: datetime) -> int:
        return signal(bars, now, self.fast, self.slow)
