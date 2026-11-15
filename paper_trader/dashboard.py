"""Read-only portfolio views; separate paper/live collectors never submit orders."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_contracts import Config, SafetyError
from trading_ibkr import LiveBroker, PaperBroker
from trading_monitoring import Journal
from trading_monitoring.dashboard import DashboardStore, demo_snapshot, start_server


def empty_snapshot(mode, message):
    return {
        "mode": mode,
        "status": "not_configured",
        "positions": [],
        "orders": [],
        "history": [],
        "as_of": datetime.now(UTC).isoformat(),
        "account": "",
        "currency": "",
        "net_liquidation": None,
        "error": message,
    }


async def collect_account(store, mode, config_path):
    broker = journal = None
    try:
        config = Config(**json.loads(Path(config_path).read_text(encoding="utf-8")))
        config.validate()
        if config.mode != mode:
            raise SafetyError("Account configuration does not match the selected environment")
        # Keep dashboard clients distinct from explicit trading sessions.
        config = replace(config, client_id=config.client_id + 1_000_000)
        config.validate()
        journal = Journal(Path(store.path).parent / "events.sqlite")
        broker_type = LiveBroker if mode == "live" else PaperBroker
        broker = broker_type(config, journal, writable=False)
        await broker.connect()
        while True:
            started = asyncio.get_running_loop().time()
            store.update(await broker.account_view(heartbeat_seconds=15))
            elapsed = asyncio.get_running_loop().time() - started
            await asyncio.sleep(max(0, 1 - elapsed))
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        store.fail(
            f"{type(exc).__name__}: {exc}. Check the selected account's Gateway and restart."
        )
        print(f"{mode} dashboard collector stopped; no automatic reconnect.", flush=True)
    finally:
        if broker:
            broker.close()
        if journal:
            journal.db.close()


async def collect_demo(store):
    if len(store.snapshot()["history"]) < 2:
        for i in range(24):
            data = demo_snapshot()
            data["as_of"] = (datetime.now(UTC) - timedelta(hours=23 - i)).isoformat()
            data["net_liquidation"] = 100000 + i * 100 + (i % 4) * 50
            store.update(data)
    while True:
        store.update(demo_snapshot())
        await asyncio.sleep(1)


async def run_dashboard(args):
    stores = {}
    for mode in ("paper", "live"):
        name = (
            "demo"
            if mode == "paper" and args.source == "demo"
            else "ibkr"
            if mode == "paper"
            else "live"
        )
        folder = Path("runtime/dashboard") / name
        folder.mkdir(parents=True, exist_ok=True)
        stores[mode] = DashboardStore(folder / "history.sqlite")
        stores[mode].update(empty_snapshot(mode, "Connecting to the selected account…"))
    tasks = []
    server = start_server(stores["paper"], args.port, environments=stores)
    print(f"Aegis dashboard: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        tasks.append(
            asyncio.create_task(
                collect_demo(stores["paper"])
                if args.source == "demo"
                else collect_account(stores["paper"], "paper", args.config)
            )
        )
        live_path = Path(args.live_config)
        if live_path.is_file():
            tasks.append(asyncio.create_task(collect_account(stores["live"], "live", live_path)))
        else:
            stores["live"].update(
                empty_snapshot(
                    "live",
                    "Real account is not configured. Configure a separate live account and Gateway, then restart. No live session is connected.",
                )
            )
        await asyncio.Event().wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        server.shutdown()
        server.server_close()
