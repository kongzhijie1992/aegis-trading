"""Read-only dashboard snapshots, history and loopback HTTP presentation."""

import json
import math
import sqlite3
import threading
from contextlib import closing
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and abs(number) < 1e100 else None
    except (ValueError, TypeError):
        return None


class DashboardStore:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.Lock()
        self.current = {"mode": "paper", "status": "starting", "positions": [], "orders": []}
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS nav(time TEXT, account TEXT, mode TEXT, currency TEXT, value REAL)"
            )

    def update(self, data):
        snapshot = json.loads(json.dumps(data, allow_nan=False))
        value = finite(snapshot.get("net_liquidation"))
        with self.lock:
            if value is not None:
                with closing(sqlite3.connect(self.path)) as db, db:
                    db.execute(
                        "INSERT INTO nav VALUES(?,?,?,?,?)",
                        (
                            snapshot["as_of"],
                            snapshot["account"],
                            snapshot["mode"],
                            snapshot["currency"],
                            value,
                        ),
                    )
            self.current = snapshot

    def fail(self, message):
        with self.lock:
            self.current = {**self.current, "status": "disconnected", "error": message}

    def snapshot(self):
        with self.lock:
            data = json.loads(json.dumps(self.current))
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute(
                "SELECT time,value FROM nav WHERE account=? AND mode=? AND currency=? ORDER BY rowid DESC LIMIT 1000",
                (data.get("account", ""), data.get("mode", "paper"), data.get("currency", "")),
            ).fetchall()
        data["history"] = [{"time": t, "value": v} for t, v in reversed(rows)]
        data["age_seconds"] = (
            max(0, (datetime.now(UTC) - datetime.fromisoformat(data["as_of"])).total_seconds())
            if data.get("as_of")
            else None
        )
        return data


def demo_snapshot():
    """Illustrative data only; never mixed into the real paper account history."""
    return {
        "mode": "demo",
        "status": "connected",
        "account": "DEMO",
        "currency": "USD",
        "as_of": datetime.now(UTC).isoformat(),
        "net_liquidation": 102450.25,
        "cash": 64950.25,
        "daily_pnl": 325.40,
        "unrealized_pnl": 1450.25,
        "realized_pnl": 1000,
        "positions": [
            {
                "symbol": "SPY",
                "instrument": "STK",
                "quantity": 50,
                "currency": "USD",
                "market_price": 500,
                "market_value": 25000,
                "average_cost": 482,
                "unrealized_pnl": 900,
                "realized_pnl": 0,
            },
            {
                "symbol": "QQQ",
                "instrument": "STK",
                "quantity": 25,
                "currency": "USD",
                "market_price": 500,
                "market_value": 12500,
                "average_cost": 477.99,
                "unrealized_pnl": 550.25,
                "realized_pnl": 0,
            },
        ],
        "orders": [],
        "notes": ["Illustrative data. Not your brokerage account."],
    }


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Host") not in (
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            ):
                self.send_error(403)
                return
            path = self.path.split("?", 1)[0]
            if path == "/api/snapshot":
                body = json.dumps(store.snapshot(), allow_nan=False).encode()
                content_type = "application/json"
            elif path == "/":
                body = Path(__file__).with_name("dashboard.html").read_bytes()
                content_type = "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    return Handler


def start_server(store, port=8765):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
