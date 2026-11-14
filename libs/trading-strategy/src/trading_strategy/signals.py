"""Broker-independent signal contracts, features and built-in research models."""

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol, cast

from trading_contracts import Bar, SafetyError

from .features import mean_reversion, momentum, trend


@dataclass(frozen=True)
class MarketFrame:
    symbol: str
    bars: tuple[Bar, ...]
    as_of: datetime
    bar_size: timedelta = timedelta(minutes=5)

    def completed(self, lookback: int) -> tuple[Bar, ...]:
        if not re.fullmatch(r"[A-Z][A-Z0-9.]{0,15}", self.symbol):
            raise SafetyError("Invalid symbol")
        if self.as_of.tzinfo is None or any(b.time.tzinfo is None for b in self.bars):
            raise SafetyError("Timezone-aware signal timestamps required")
        if self.bar_size <= timedelta(0) or type(lookback) is not int or lookback < 2:
            raise SafetyError("Positive bar size and lookback >= 2 required")
        bars = tuple(b for b in self.bars if b.time + self.bar_size <= self.as_of)
        if len(bars) < lookback:
            raise SafetyError(f"Warm-up: need {lookback} completed bars")
        if any(not math.isfinite(b.close) or b.close <= 0 for b in bars):
            raise SafetyError("Signal prices must be positive and finite")
        if any(a.time >= b.time for a, b in zip(bars, bars[1:], strict=False)):
            raise SafetyError("Signal bars must be strictly ordered")
        if self.as_of - (bars[-1].time + self.bar_size) > self.bar_size:
            raise SafetyError("Signal input is stale")
        return bars[-lookback:]


@dataclass(frozen=True)
class SignalRecord:
    symbol: str
    model: str
    version: str
    as_of: datetime
    bar_end: datetime
    expires_at: datetime
    score: float
    target: int
    features: tuple[tuple[str, float], ...]
    reason: str

    def valid_at(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise SafetyError("Timezone-aware evaluation time required")
        return self.as_of <= now < self.expires_at


class SignalModel(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def lookback(self) -> int: ...

    def evaluate(self, frame: MarketFrame) -> SignalRecord: ...


def validate_signal(result: SignalRecord, frame: MarketFrame, model: SignalModel) -> None:
    bars = frame.completed(model.lookback)
    if (
        any(t.tzinfo is None for t in (result.as_of, result.bar_end, result.expires_at))
        or not result.valid_at(frame.as_of)
        or type(result.target) is not int
        or result.target not in (0, 1)
        or not math.isfinite(result.score)
        or not -1 <= result.score <= 1
        or result.symbol != frame.symbol
        or result.model != model.name
        or result.version != model.version
        or result.as_of != frame.as_of
        or result.bar_end != bars[-1].time + frame.bar_size
        or any(not math.isfinite(value) for _, value in result.features)
    ):
        raise SafetyError("Model emitted an invalid or mismatched signal")


@dataclass(frozen=True)
class CloseSignal:
    """Scores are directional features, never probabilities or position sizes."""

    kind: Literal["sma_trend", "momentum", "mean_reversion"] = "sma_trend"
    lookback: int = 50
    fast: int = 20
    threshold: float = 0.0
    ttl_seconds: int = 30
    version: str = "1.0.0"

    def __post_init__(self) -> None:
        if self.kind not in ("sma_trend", "momentum", "mean_reversion"):
            raise SafetyError("Unknown signal model")
        if type(self.lookback) is not int or self.lookback < 2:
            raise SafetyError("lookback must be an integer >= 2")
        if (
            type(self.fast) is not int
            or self.fast < 1
            or self.kind == "sma_trend"
            and self.fast >= self.lookback
        ):
            raise SafetyError("Require 1 <= fast < lookback")
        if type(self.ttl_seconds) is not int or self.ttl_seconds <= 0:
            raise SafetyError("Positive integer signal TTL required")
        if (
            isinstance(self.threshold, bool)
            or not math.isfinite(self.threshold)
            or self.threshold < 0
        ):
            raise SafetyError("Nonnegative finite threshold required")

    @property
    def name(self) -> str:
        return self.kind

    def evaluate(self, frame: MarketFrame) -> SignalRecord:
        bars = frame.completed(self.lookback)
        closes = [b.close for b in bars]
        features: tuple[tuple[str, float], ...]
        if self.kind == "sma_trend":
            feature, fast_mean, slow_mean = trend(closes, self.fast)
            features = (("fast_mean", fast_mean), ("slow_mean", slow_mean))
        elif self.kind == "momentum":
            feature = momentum(closes)
            features = (("lookback_return", feature),)
        else:
            feature, mean, deviation = mean_reversion(closes)
            features = (("negative_zscore", feature), ("mean", mean), ("stddev", deviation))
        score = math.tanh(feature)
        return SignalRecord(
            symbol=frame.symbol,
            model=self.name,
            version=self.version,
            as_of=frame.as_of,
            bar_end=bars[-1].time + frame.bar_size,
            expires_at=frame.as_of + timedelta(seconds=self.ttl_seconds),
            score=score,
            target=int(feature > self.threshold),
            features=features,
            reason=f"{self.name}: feature {feature:.8f} > threshold {self.threshold:.8f}",
        )


class SignalRegistry:
    def __init__(self) -> None:
        self._models: dict[str, SignalModel] = {}

    def register(self, model: SignalModel) -> None:
        if model.name in self._models:
            raise SafetyError(f"Signal already registered: {model.name}")
        self._models[model.name] = model

    def get(self, name: str) -> SignalModel:
        try:
            return self._models[name]
        except KeyError as exc:
            raise SafetyError(f"Unknown signal: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._models))


def make_model(name: str, parameters: dict[str, object]) -> CloseSignal:
    if name not in ("sma_trend", "momentum", "mean_reversion"):
        raise SafetyError("Unknown built-in signal")
    if set(parameters) - {"lookback", "fast", "threshold", "ttl_seconds"}:
        raise SafetyError("Unknown signal parameter")
    integers = []
    for key, default in (("lookback", 50), ("fast", 20), ("ttl_seconds", 30)):
        value = parameters.get(key, default)
        if type(value) is not int:
            raise SafetyError(f"{key} must be an integer")
        integers.append(value)
    threshold = parameters.get("threshold", 0.0)
    if isinstance(threshold, bool) or not isinstance(threshold, (float, int)):
        raise SafetyError("threshold must be numeric")
    return CloseSignal(
        cast(Literal["sma_trend", "momentum", "mean_reversion"], name),
        integers[0],
        integers[1],
        float(threshold),
        integers[2],
    )


@dataclass(frozen=True)
class SignalStrategy:
    """Decision-time adapter; execution's proposal expiry remains independent."""

    model: SignalModel
    symbol: str
    name: str = "research_signal_adapter"

    def target(self, bars: list[Bar], now: datetime) -> int:
        frame = MarketFrame(self.symbol, tuple(bars), now)
        result = self.model.evaluate(frame)
        validate_signal(result, frame, self.model)
        return result.target
