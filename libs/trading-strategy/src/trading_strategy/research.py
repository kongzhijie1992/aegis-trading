"""Chronological, purged forward-return studies. Not an execution backtester."""

import csv
import hashlib
import json
import math
import platform
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from statistics import fmean

from trading_contracts import Bar, SafetyError

from .signals import MarketFrame, SignalModel, validate_signal


def load_bars(path: Path) -> tuple[Bar, ...]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not {"time", "close"}.issubset(reader.fieldnames or []):
            raise SafetyError("CSV requires time,close columns; time is the bar START in ISO UTC")
        bars = tuple(
            Bar(datetime.fromisoformat(row["time"]), float(row["close"])) for row in reader
        )
    if not bars or any(
        b.time.tzinfo is None or not math.isfinite(b.close) or b.close <= 0 for b in bars
    ):
        raise SafetyError("Dataset needs timezone-aware timestamps and positive finite closes")
    if any(a.time >= b.time for a, b in zip(bars, bars[1:], strict=False)):
        raise SafetyError("Dataset timestamps must be strictly increasing")
    return bars


@dataclass(frozen=True)
class StudyConfig:
    train_fraction: float = 0.7
    horizon: int = 3
    round_trip_bps: float = 10.0
    bar_minutes: int = 5

    def validate(self) -> None:
        if not 0 < self.train_fraction < 1:
            raise SafetyError("train_fraction must be strictly between zero and one")
        if type(self.horizon) is not int or self.horizon < 1:
            raise SafetyError("horizon must be a positive integer")
        if type(self.bar_minutes) is not int or self.bar_minutes < 1:
            raise SafetyError("bar_minutes must be a positive integer")
        if (
            isinstance(self.round_trip_bps, bool)
            or not math.isfinite(self.round_trip_bps)
            or self.round_trip_bps < 0
        ):
            raise SafetyError("Nonnegative finite round-trip costs required")


@dataclass(frozen=True)
class Observation:
    symbol: str
    as_of: str
    split: str
    score: float
    target: int
    entry_time: str
    exit_time: str
    forward_return: float
    net_opportunity_return: float
    features_json: str
    reason: str
    expires_at: str


def evaluate(
    model: SignalModel, symbol: str, bars: tuple[Bar, ...], config: StudyConfig
) -> tuple[Observation, ...]:
    config.validate()
    if len(bars) < model.lookback + config.horizon + 3:
        raise SafetyError("Insufficient dataset for warm-up and forward labels")
    size = timedelta(minutes=config.bar_minutes)
    # Validate the entire dataset once; each model call receives only a prefix.
    MarketFrame(symbol, bars, bars[-1].time + size, size).completed(len(bars))
    boundary = int(len(bars) * config.train_fraction)
    observations = []
    for i in range(model.lookback - 1, len(bars) - config.horizon - 1):
        entry = i + 1
        exit_index = entry + config.horizon
        if i < boundary <= exit_index:
            continue  # Purge all training labels that touch the test period.
        # Only contiguous intervals are eligible; no accidental overnight labels.
        if any(bars[j + 1].time - bars[j].time != size for j in range(i, exit_index)):
            continue
        as_of = bars[i].time + size
        frame = MarketFrame(symbol, bars[i + 1 - model.lookback : i + 1], as_of, size)
        signal = model.evaluate(frame)
        validate_signal(signal, frame, model)
        forward = bars[exit_index].close / bars[entry].close - 1
        observations.append(
            Observation(
                symbol,
                as_of.isoformat(),
                "train" if i < boundary else "test",
                signal.score,
                signal.target,
                (bars[entry].time + size).isoformat(),
                (bars[exit_index].time + size).isoformat(),
                forward,
                signal.target * (forward - config.round_trip_bps / 10000),
                json.dumps(dict(signal.features), sort_keys=True, allow_nan=False),
                signal.reason,
                signal.expires_at.isoformat(),
            )
        )
    if not {"train", "test"}.issubset({o.split for o in observations}):
        raise SafetyError(
            "Both train and test require eligible observations after purging/gap checks"
        )
    return tuple(observations)


def summarize(rows: tuple[Observation, ...]) -> dict[str, object]:
    active = [r for r in rows if r.target == 1]
    return {
        "observations": len(rows),
        "active_observations": len(active),
        "mean_forward_return": fmean(r.forward_return for r in rows) if rows else None,
        "mean_net_opportunity_return": fmean(r.net_opportunity_return for r in active)
        if active
        else None,
        "active_hit_rate": sum(r.net_opportunity_return > 0 for r in active) / len(active)
        if active
        else None,
    }


def save_study(
    output: Path,
    dataset: Path,
    model: SignalModel,
    config: StudyConfig,
    rows: tuple[Observation, ...],
    parameters: dict[str, object],
    *,
    expected_dataset_hash: str | None = None,
) -> Path:
    if not rows or len({r.symbol for r in rows}) != 1:
        raise SafetyError("Export requires nonempty observations for exactly one symbol")
    dataset_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
    if expected_dataset_hash is not None and dataset_hash != expected_dataset_hash:
        raise SafetyError("Dataset changed during the experiment; results were not exported")
    source_hash = hashlib.sha256(
        "".join(
            Path(__file__).with_name(n).read_text(encoding="utf-8")
            for n in ("research.py", "signals.py", "features.py")
        ).encode()
    ).hexdigest()
    provenance = {
        "symbol": rows[0].symbol,
        "python_version": platform.python_version(),
        "library_version": version("trading-strategy"),
        "model": model.name,
        "version": model.version,
        "parameters": parameters,
        "study": asdict(config),
        "dataset_sha256": dataset_hash,
        "source_sha256": source_hash,
        "observations_sha256": hashlib.sha256(
            json.dumps([asdict(r) for r in rows], sort_keys=True, allow_nan=False).encode()
        ).hexdigest(),
    }
    run_id = hashlib.sha256(json.dumps(provenance, sort_keys=True).encode()).hexdigest()[:16]
    folder = output / run_id
    folder.mkdir(parents=True, exist_ok=True)
    report = {
        **provenance,
        "run_id": run_id,
        "dataset_file": dataset.name,
        "train": summarize(tuple(r for r in rows if r.split == "train")),
        "test": summarize(tuple(r for r in rows if r.split == "test")),
        "interpretation": "Overlapping forward-return opportunities; not portfolio returns or an execution backtest. No profitability/deployment conclusion.",
    }
    (folder / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    with (folder / "observations.csv").open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(Observation.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(asdict(r) for r in rows)
    return folder
