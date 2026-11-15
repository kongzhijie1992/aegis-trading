"""Local ingestion commands; no credentials or account configuration in arguments."""

import argparse
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .client import PublicDataClient
from .models import DataError, Observation
from .providers import fred_current_csv, fred_vintages, records_csv, sec_facts
from .store import DataStore


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Aegis local fundamental/macro data store")
    parser.add_argument(
        "command",
        choices=(
            "init",
            "demo",
            "inventory",
            "import-sec",
            "import-fred",
            "import-csv",
            "fetch-sec",
            "fetch-fred",
            "asof",
            "backup",
        ),
    )
    parser.add_argument("--db", type=Path, default=Path("runtime/data/aegis.sqlite"))
    parser.add_argument("--file", type=Path)
    parser.add_argument("--source", default="custom")
    parser.add_argument("--entity", default="US")
    parser.add_argument("--metric")
    parser.add_argument("--series")
    parser.add_argument("--unit")
    parser.add_argument("--cik")
    parser.add_argument("--at")
    parser.add_argument("--knowledge", choices=("system", "source"), default="system")
    parser.add_argument("--vintages", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    store = DataStore(args.db)
    now = datetime.now(UTC)
    if args.command == "init":
        print(f"Local database ready: {store.path.resolve()}")
        return
    if args.command == "inventory":
        print(json.dumps(store.inventory(), indent=2))
        return
    if args.command == "backup":
        if args.output is None:
            parser.error("backup requires --output (a new file)")
        store.backup(args.output)
        print("Database backup complete")
        return
    if args.command == "asof":
        if not args.metric or not args.unit or not args.at:
            parser.error("asof requires --source --entity --metric --unit --at")
        snapshot = store.as_of(
            source=args.source,
            entity=args.entity,
            metric=args.metric,
            unit=args.unit,
            cutoff=datetime.fromisoformat(args.at),
            knowledge=args.knowledge,
        )
        print(json.dumps(snapshot, indent=2))
        return
    if args.command == "demo":
        rows = [
            Observation(
                "demo",
                "US",
                "UNRATE",
                "percent",
                "2026-01-01",
                now - timedelta(days=2),
                "v1",
                "4.0",
            ),
            Observation(
                "demo",
                "US",
                "UNRATE",
                "percent",
                "2026-01-01",
                now - timedelta(days=1),
                "v2",
                "4.1",
            ),
            Observation(
                "demo",
                "DEMO-CO",
                "revenue",
                "USD",
                "2025-12-31",
                now - timedelta(days=1),
                "filing-v1",
                "1000000",
                "2025-01-01",
            ),
        ]
        payload = b'{"synthetic_demo":true}'
        result = store.ingest("demo", "synthetic-fundamental-macro", payload, rows, now)
        print("SYNTHETIC DEMO ONLY")
        print(json.dumps(result, indent=2))
        return
    client = PublicDataClient()
    if args.command.startswith("import-"):
        if args.file is None:
            parser.error("import requires --file")
        payload = args.file.read_bytes()
    elif args.command == "fetch-sec":
        if not args.cik:
            parser.error("fetch-sec requires --cik")
        payload = client.sec(args.cik, os.environ.get("SEC_USER_AGENT", ""))
    else:
        if not args.series or not args.unit:
            parser.error("fetch-fred requires --series and --unit")
        key = os.environ.get("FRED_API_KEY") if args.vintages else None
        if args.vintages and not key:
            raise DataError("Set FRED_API_KEY locally for vintage history")
        payload = client.fred(args.series, key)
    # First-seen means a complete response was collected, not request start.
    now = datetime.now(UTC)
    if args.command.endswith("sec"):
        rows = sec_facts(payload)
        source = "sec"
        dataset = rows[0].entity if rows else "companyfacts"
    elif args.command.endswith("fred"):
        if not args.series or not args.unit:
            parser.error("FRED ingestion requires --series and explicit --unit")
        rows = (
            fred_vintages(payload, args.series, args.unit)
            if args.vintages
            else fred_current_csv(payload, args.series, args.unit, now)
        )
        source = "fred-vintage" if args.vintages else "fred-current"
        dataset = args.series
    else:
        rows = records_csv(payload, args.source)
        source = args.source
        dataset = args.file.name
    print(json.dumps(store.ingest(source, dataset, payload, rows, now), indent=2))


def entrypoint() -> None:
    try:
        main()
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"Data operation failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    entrypoint()
