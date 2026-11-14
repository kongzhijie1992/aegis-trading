"""Offline signal research command. No broker SDK or execution imports."""

import argparse
import csv
import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_contracts import SafetyError

from .research import StudyConfig, evaluate, load_bars, save_study
from .signals import SignalRegistry, make_model


def demo_data(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.writer(destination)
        writer.writerow(["time", "close"])
        for day in range(3):
            start = datetime(2026, 1, 5 + day, 14, 30, tzinfo=UTC)
            for i in range(78):
                j = day * 78 + i
                writer.writerow(
                    [
                        (start + timedelta(minutes=i * 5)).isoformat(),
                        round(500 + j * 0.03 + 2 * math.sin(j / 7), 6),
                    ]
                )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Aegis offline signal development; never places orders"
    )
    parser.add_argument("command", choices=("list", "demo", "evaluate"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=Path("runtime/signals"))
    args = parser.parse_args(argv)
    registry = SignalRegistry()
    for name in ("sma_trend", "momentum", "mean_reversion"):
        registry.register(make_model(name, {}))
    if args.command == "list":
        print("\n".join(registry.names()))
        return
    if args.command == "demo":
        dataset = args.output / "synthetic-SPY.csv"
        demo_data(dataset)
        config = {
            "symbol": "SPY",
            "model": "momentum",
            "parameters": {"lookback": 20},
            "data": str(dataset),
            "study": {"train_fraction": 0.7, "horizon": 3, "round_trip_bps": 10},
        }
        print(
            "SYNTHETIC DATA: workflow example only, not an IBKR dataset or profitability evidence."
        )
    else:
        if args.config is None:
            parser.error("evaluate requires --config")
        config = json.loads(args.config.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) - {
        "symbol",
        "model",
        "parameters",
        "data",
        "study",
    }:
        raise SafetyError("Unknown experiment fields")
    symbol, model_name, data = config.get("symbol"), config.get("model"), config.get("data")
    parameters, study_values = config.get("parameters", {}), config.get("study", {})
    if (
        not all(isinstance(v, str) for v in (symbol, model_name, data))
        or not isinstance(parameters, dict)
        or not isinstance(study_values, dict)
    ):
        raise SafetyError(
            "Experiment requires symbol/model/data strings and parameter/study objects"
        )
    dataset = Path(str(data))
    if args.command == "evaluate" and not dataset.is_absolute():
        dataset = args.config.resolve().parent / dataset
    model = make_model(str(model_name), parameters)
    study = StudyConfig(**study_values)
    dataset_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
    rows = evaluate(model, str(symbol), load_bars(dataset), study)
    folder = save_study(
        args.output, dataset, model, study, rows, parameters, expected_dataset_hash=dataset_hash
    )
    print(f"Signal study saved: {folder}")
    print((folder / "report.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
