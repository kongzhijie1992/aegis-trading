"""Local dashboard composition. IBKR connection is always read-only/paper."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_contracts import Config
from trading_ibkr import PaperBroker
from trading_monitoring import Journal
from trading_monitoring.dashboard import DashboardStore, demo_snapshot, start_server


async def run_dashboard(args):
    mode = args.source
    folder = Path("runtime/dashboard") / mode
    folder.mkdir(parents=True, exist_ok=True)
    store = DashboardStore(folder / "history.sqlite")
    server = start_server(store, args.port)
    print(f"Aegis {mode} dashboard: http://127.0.0.1:{server.server_port}", flush=True)
    broker = journal = None
    try:
        if mode == "demo":
            # Clearly synthetic demo curve; real history is never backfilled.
            store.update(demo_snapshot())
            if len(store.snapshot()["history"]) < 2:
                for i in range(24):
                    data = demo_snapshot()
                    data["as_of"] = (datetime.now(UTC) - timedelta(hours=23 - i)).isoformat()
                    data["net_liquidation"] = 100000 + i * 100 + (i % 4) * 50
                    store.update(data)
        else:
            config = Config(**json.loads(Path(args.config).read_text(encoding="utf-8")))
            config.validate()
            journal = Journal(folder / "events.sqlite")
            broker = PaperBroker(config, journal, writable=False)
            await broker.connect()
        while True:
            started = asyncio.get_running_loop().time()
            try:
                store.update(
                    demo_snapshot()
                    if mode == "demo"
                    else await broker.account_view(heartbeat_seconds=15)
                )
            except Exception as exc:
                store.fail(f"{type(exc).__name__}: {exc}. Restart after checking paper TWS.")
                print("Dashboard collector stopped; last snapshot retained.", flush=True)
                # Keep serving a stale snapshot; never reconnect automatically.
                await asyncio.Event().wait()
            elapsed = asyncio.get_running_loop().time() - started
            await asyncio.sleep(max(0, 1 - elapsed))
    finally:
        if broker:
            broker.close()
        if journal:
            journal.db.close()
        server.shutdown()
        server.server_close()
