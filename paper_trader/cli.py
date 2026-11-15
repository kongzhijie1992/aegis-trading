import argparse
import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_monitoring import configure_logging

from .core import Bar, Config, Proposal, SafetyError
from .journal import Journal
from .strategy import signal


async def demo(journal):
    """Synthetic paper broker smoke test; never opens a network connection."""
    now = datetime.now(UTC)
    bars = [Bar(now - timedelta(minutes=5 * (60 - i)), 400 + i) for i in range(60)]
    assert signal(bars, now) == 1
    p = Proposal("synthetic-demo", "SPY", "BUY", 1, 459, now)
    journal.event("synthetic_proposal", p.__dict__)
    print("Synthetic paper demo: 20/50 signal=1, proposal=BUY 1 SPY LMT 459.00")
    print("No brokerage connection, no order submitted. Run tests for approval/risk paths.")


async def run(args, journal):
    if args.command == "dashboard":
        from .dashboard import run_dashboard

        await run_dashboard(args)
        return
    if args.command == "demo":
        await demo(journal)
        return
    from dataclasses import asdict, is_dataclass

    from .engine import TradingEngine
    from .strategy import SmaStrategy

    simulation = args.command == "simulate"
    clock = None
    if simulation:
        from .simulator import SimulatedBroker, SimulationClock

        clock = SimulationClock()
        config = Config(account="DU000000", kill_file="runtime/simulation/STOP")
        broker = SimulatedBroker(clock)
        print("OFFLINE FIXTURE: synthetic prices, virtual cash, no IBKR connection.")
    else:
        from trading_ibkr import LiveBroker, PaperBroker

        from .environments import load_config

        config = load_config(args)
        broker_type = LiveBroker if config.mode == "live" else PaperBroker
        broker = broker_type(config, journal, writable=args.command == "trade")
    strategy = SmaStrategy(args.fast, args.slow)
    engine = TradingEngine(config, broker, strategy, journal, clock=clock)
    try:
        await broker.connect()
        if args.command == "check":
            report = await engine.diagnose()

            def encode(value):
                return asdict(value) if is_dataclass(value) else str(value)

            rendered = json.dumps(report, indent=2, default=encode)
            destination = (
                Path("runtime/live") / config.account if config.mode == "live" else Path("runtime")
            ) / "diagnostics.json"
            destination.write_text(rendered)
            print(rendered)
            if not report["ready"]:
                raise SafetyError(
                    f"Diagnostic checks blocked; see {destination}. No orders submitted."
                )
            return
        print(json.dumps(await engine.cycle(), indent=2))
        if simulation:
            print("Offline cash/positions:", await broker.snapshot())
    finally:
        broker.close()


def main():
    parser = argparse.ArgumentParser(description="IBKR trading with per-order manual approval")
    parser.add_argument(
        "command",
        choices=("demo", "check", "trade", "journal", "reconcile", "simulate", "dashboard"),
    )
    parser.add_argument("--config")
    parser.add_argument("--environment", choices=("paper", "live"), default="paper")
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--live-config", default="runtime/config.live.json")
    parser.add_argument("--source", choices=("demo", "ibkr"), default="demo")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--key")
    parser.add_argument("--status", choices=("Filled", "Cancelled", "Rejected"))
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=50)
    args = parser.parse_args()
    if (args.environment == "live" or args.enable_live) and args.command not in (
        "trade",
        "check",
        "journal",
        "reconcile",
    ):
        parser.error(
            "Select environments for trade/check/journal/reconcile; the dashboard has its own account selector"
        )
    args.config = args.config or (
        args.live_config if args.environment == "live" else "config.local.json"
    )
    Path("runtime").mkdir(exist_ok=True)
    configure_logging("runtime/app.log")
    runtime = (
        Path("runtime/simulation")
        if args.command == "simulate"
        else Path("runtime/dashboard")
        if args.command == "dashboard"
        else Path("runtime")
    )
    if args.environment == "live":
        from .environments import load_config

        config = load_config(args)
        runtime = Path("runtime/live") / config.account
    runtime.mkdir(parents=True, exist_ok=True)
    if args.command == "simulate":
        from uuid import uuid4

        journal_path = runtime / f"session-{uuid4().hex}.sqlite"
        print("Offline session journal:", journal_path)
    else:
        journal_path = runtime / "orders.sqlite"
    journal = Journal(journal_path)
    try:
        if args.command == "journal":
            print("Unresolved orders:", journal.unresolved())
        elif args.command == "reconcile":
            if not args.key or not args.status or not journal.seen(args.key):
                raise SafetyError(
                    "Supply an existing --key and terminal --status after checking TWS executions/open orders"
                )
            phrase = f"RECONCILED {args.key} {args.status}"
            if input(f"Confirm TWS executions AND open orders reviewed. Type {phrase}: ") != phrase:
                raise SafetyError("Reconciliation declined")
            journal.event("manual_reconciliation", {"key": args.key, "status": args.status})
            journal.status(args.key, args.status)
        else:
            # Prevent simultaneous processes sharing risk budget/client sessions.
            import os

            lock = runtime / "session.lock"
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError as exc:
                raise SafetyError(
                    "Session lock exists. Stop other process; after a crash inspect TWS before removing lock"
                ) from exc
            try:
                os.write(fd, str(os.getpid()).encode())
                asyncio.run(run(args, journal))
            finally:
                os.close(fd)
                lock.unlink()
    except (Exception, KeyboardInterrupt) as exc:
        journal.event("stopped", {"type": type(exc).__name__, "message": str(exc)})
        logging.error("Stopped safely: %s: %s", type(exc).__name__, exc)
        raise SystemExit(1) from exc
    finally:
        journal.db.close()


if __name__ == "__main__":
    main()
