"""Small deterministic close-price features, reusable by custom signal models."""

import math
from collections.abc import Sequence
from statistics import fmean, pstdev

from trading_contracts import SafetyError


def validate_closes(closes: Sequence[float]) -> None:
    if len(closes) < 2 or any(not math.isfinite(c) or not 0 < c < 1e100 for c in closes):
        raise SafetyError("Features require at least two positive finite closes")


def trend(closes: Sequence[float], fast: int) -> tuple[float, float, float]:
    validate_closes(closes)
    if type(fast) is not int or not 1 <= fast < len(closes):
        raise SafetyError("Fast window must be smaller than the close window")
    fast_mean, slow_mean = fmean(closes[-fast:]), fmean(closes)
    return fast_mean / slow_mean - 1, fast_mean, slow_mean


def momentum(closes: Sequence[float]) -> float:
    validate_closes(closes)
    value = closes[-1] / closes[0] - 1
    if not math.isfinite(value):
        raise SafetyError("Momentum overflow")
    return value


def mean_reversion(closes: Sequence[float]) -> tuple[float, float, float]:
    validate_closes(closes)
    mean, deviation = fmean(closes), pstdev(closes)
    return (mean - closes[-1]) / deviation if deviation else 0.0, mean, deviation
