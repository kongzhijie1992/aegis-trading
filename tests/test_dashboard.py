import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from trading_monitoring.dashboard import (
    DashboardStore,
    demo_snapshot,
    finite,
    make_handler,
    start_server,
)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DashboardStore(Path(self.tmp.name) / "history.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def test_history_is_account_mode_currency_scoped_and_failure_retains_values(self):
        self.assertEqual(self.store.snapshot()["history"], [])
        data = demo_snapshot()
        self.store.update(data)
        self.store.update({**data, "account": "OTHER", "net_liquidation": 1})
        self.store.update({**data, "net_liquidation": None})
        self.assertEqual(len(self.store.snapshot()["history"]), 1)
        self.assertEqual(self.store.snapshot()["history"][0]["value"], data["net_liquidation"])
        self.store.fail("disconnected")
        result = self.store.snapshot()
        self.assertEqual(result["status"], "disconnected")
        self.assertEqual(result["positions"], data["positions"])
        self.assertIsNotNone(result["age_seconds"])
        for value in (None, "unknown", float("nan"), float("inf"), 1e300):
            self.assertIsNone(finite(value))
        self.assertEqual(finite("10.5"), 10.5)
        with self.assertRaises(ValueError):
            self.store.update({**data, "cash": float("nan")})

    def handler(self, path, host="127.0.0.1:8765"):
        cls = make_handler(self.store)
        handler = cls.__new__(cls)
        handler.server = NS(server_port=8765)
        handler.headers = {"Host": host}
        handler.path = path
        handler.wfile = io.BytesIO()
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.send_error = Mock()
        return handler

    def test_readonly_routes_headers_and_host_rejection(self):
        for path in ("/", "/api/snapshot?refresh=1"):
            h = self.handler(path)
            h.do_GET()
            h.send_response.assert_called_once_with(200)
            self.assertTrue(h.wfile.getvalue())
            h.send_header.assert_any_call("Cache-Control", "no-store")
            h.log_message("ignored")
        for path, host, status in [("/orders", "127.0.0.1:8765", 404), ("/", "evil.example", 403)]:
            h = self.handler(path, host)
            h.do_GET()
            h.send_error.assert_called_once_with(status)

    def test_server_only_binds_loopback_and_runs_in_background(self):
        with (
            patch("trading_monitoring.dashboard.ThreadingHTTPServer") as server,
            patch("trading_monitoring.dashboard.threading.Thread") as thread,
        ):
            result = start_server(self.store, 8765)
            self.assertIs(result, server.return_value)
            self.assertEqual(server.call_args.args[0], ("127.0.0.1", 8765))
            thread.return_value.start.assert_called_once()
