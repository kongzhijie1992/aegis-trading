"""Live capability tests use in-memory fake brokers; never contact IBKR."""

import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from test_system import NOW, PROP, FakeBroker, FrozenDateTime
from trading_approval.console import ConsoleApproval
from trading_contracts import Config, SafetyError
from trading_engine import TradingEngine
from trading_execution import Execution
from trading_ibkr import LiveBroker, PaperBroker
from trading_monitoring import Journal
from trading_monitoring.dashboard import DashboardStore
from trading_simulation import SimulatedBroker, SimulationClock
from trading_strategy import SmaStrategy

from paper_trader.dashboard import collect_account, empty_snapshot
from paper_trader.environments import load_config

LIVE = Config(mode="live", port=4001, account="U123", live_enabled=True)


class DashboardCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_separate_readonly_client_and_environment_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "live.json"
            path.write_text(json.dumps(asdict(LIVE)))
            store = DashboardStore(Path(folder) / "history.sqlite")
            store.update(empty_snapshot("live", "starting"))
            fake = NS(
                connect=AsyncMock(),
                account_view=AsyncMock(side_effect=ConnectionError("fixture disconnect")),
                close=Mock(),
                send_approved=Mock(),
            )
            with patch("paper_trader.dashboard.LiveBroker", return_value=fake) as live:
                await collect_account(store, "live", path)
                self.assertFalse(live.call_args.kwargs["writable"])
                self.assertEqual(live.call_args.args[0].client_id, LIVE.client_id + 1_000_000)
            self.assertEqual(store.snapshot()["mode"], "live")
            self.assertEqual(store.snapshot()["status"], "disconnected")
            fake.send_approved.assert_not_called()
            fake.close.assert_called_once()
            store.update(empty_snapshot("paper", "starting"))
            with patch("paper_trader.dashboard.PaperBroker") as paper:
                await collect_account(store, "paper", path)
                paper.assert_not_called()
            self.assertEqual(store.snapshot()["mode"], "paper")


class LiveConfigTests(unittest.TestCase):
    def test_live_requires_consistent_explicit_opt_in(self):
        LIVE.validate()
        replace(LIVE, port=7496).validate()
        for changes in [
            dict(live_enabled=False),
            dict(live_enabled="true"),
            dict(port=4002),
            dict(port=7497),
            dict(account="DU123"),
            dict(account=""),
            dict(mode="auto"),
            dict(host="example.com"),
            dict(client_id=2_147_483_648),
        ]:
            with self.subTest(changes=changes), self.assertRaises(SafetyError):
                replace(LIVE, **changes).validate()
        with self.assertRaises(SafetyError):
            Config(account="DU123", live_enabled=True).validate()

    def test_adapter_environment_and_exact_account_gates(self):
        journal = Mock()
        for cls, config in [(PaperBroker, LIVE), (LiveBroker, Config(account="DU123"))]:
            with self.assertRaises(SafetyError):
                cls(config, journal)
        broker = LiveBroker(LIVE, journal)
        broker.ib = NS(isConnected=lambda: True, managedAccounts=lambda: ["U123"])
        broker.guard()
        for accounts in [["DU123"], ["U999"], ["U123", "DU123"]]:
            broker.ib.managedAccounts = lambda accounts=accounts: accounts
            with self.assertRaises(SafetyError):
                broker.guard()
        broker.config = Config(account="DU123")
        with self.assertRaises(SafetyError):
            broker.guard()

    def test_cli_requires_selected_environment_and_session_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "live.json"
            path.write_text(json.dumps(asdict(LIVE)))
            args = NS(config=path, environment="live", command="trade", enable_live=False)
            with self.assertRaisesRegex(SafetyError, "enable-live"):
                load_config(args)
            args.enable_live = True
            self.assertEqual(load_config(args), LIVE)
            args.environment = "paper"
            with self.assertRaises(SafetyError):
                load_config(args)
            args.environment = "live"
            args.command = "check"
            with self.assertRaises(SafetyError):
                load_config(args)
            args.enable_live = False
            self.assertEqual(load_config(args), LIVE)

    def test_live_phrase_binds_account_order_price_and_mode(self):
        with self.assertRaises(ValueError):
            ConsoleApproval("unknown")
        approval = ConsoleApproval("live")
        terminal = patch("trading_approval.console.sys.stdin.isatty", return_value=True)
        terminal.start()
        self.addCleanup(terminal.stop)
        exact = f"APPROVE LIVE U123 {PROP.key} BUY 1 SPY LIMIT 500.00"
        with contextlib.redirect_stdout(io.StringIO()) as output:
            for answer in [
                f"APPROVE {PROP.key}",
                exact.replace("U123", "U999"),
                exact.replace("500.00", "501.00"),
                exact,
            ]:
                with patch("builtins.input", return_value=answer):
                    self.assertEqual(asyncio.run(approval.request(PROP, "U123")), answer == exact)
        self.assertIn("LIVE U123", output.getvalue())

    def test_live_refuses_noninteractive_approval(self):
        with (
            patch("trading_approval.console.sys.stdin.isatty", return_value=False),
            self.assertRaises(SafetyError),
        ):
            asyncio.run(ConsoleApproval("live").request(PROP, "U123"))

    def test_engine_live_proposal_keys_are_account_scoped(self):
        async def prepare():
            clock = SimulationClock()
            broker = SimulatedBroker(clock)
            await broker.connect()
            try:
                engine = TradingEngine(LIVE, broker, SmaStrategy(), Mock(), clock=clock)
                proposal = await engine.proposal("SPY")
                self.assertTrue(proposal.key.startswith("LIVE-U123-SPY-"))
                report = await engine.diagnose()
                self.assertEqual(report["connection"], "verified_live")
            finally:
                broker.close()

        asyncio.run(prepare())


class LiveExecutionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.journal = Journal(Path(self.folder.name) / "live.sqlite")
        self.addCleanup(self.journal.db.close)
        self.config = replace(LIVE, kill_file=str(Path(self.folder.name) / "STOP"))
        self.broker = FakeBroker()
        self.broker.config = self.config
        self.execution = Execution(self.config, self.broker, self.journal)
        self.clock = patch("trading_execution.service.datetime", FrozenDateTime)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.terminal = patch("trading_approval.console.sys.stdin.isatty", return_value=True)
        self.terminal.start()
        self.addCleanup(self.terminal.stop)
        self.phrase = f"APPROVE LIVE U123 {PROP.key} BUY 1 SPY LIMIT 500.00"

    def execute(self, answer, proposal=PROP):
        with (
            patch(
                "builtins.input",
                side_effect=answer if callable(answer) else None,
                return_value=answer,
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            return asyncio.run(self.execution.execute(proposal))

    def test_manual_live_order_and_duplicate_protection(self):
        self.assertEqual(self.execute(self.phrase), "Filled")
        self.assertEqual(len(self.broker.sent), 1)
        with self.assertRaises(SafetyError):
            self.execute(self.phrase)

    def test_decline_and_paper_phrase_never_submit(self):
        for answer in ["yes", f"APPROVE {PROP.key}", ""]:
            self.assertEqual(self.execute(answer), "DECLINED")
        self.assertEqual(self.broker.sent, [])

    def test_live_rejects_price_precision_hidden_by_approval_display(self):
        with self.assertRaisesRegex(SafetyError, "whole-cent"):
            self.execute(self.phrase, proposal=replace(PROP, limit=500.001))
        self.assertEqual(self.broker.sent, [])

    def test_live_forbids_injected_automatic_approval(self):
        with self.assertRaises(SafetyError):
            asyncio.run(self.execution.execute(PROP, approve=lambda _: self.phrase))
        self.execution.approval = Mock()
        with self.assertRaises(SafetyError):
            self.execute(self.phrase)
        self.assertEqual(self.broker.sent, [])

    def test_account_mismatch_before_or_during_approval(self):
        self.broker.config = replace(self.config, account="U999")
        with self.assertRaises(SafetyError):
            self.execute(self.phrase)
        self.broker.config = self.config

        def change(_):
            self.broker.config = replace(self.config, account="U999")
            return self.phrase

        with self.assertRaises(SafetyError):
            self.execute(change)
        self.assertEqual(self.broker.sent, [])

    def test_kill_switch_disconnect_and_expiry_after_approval(self):
        for kind in ["kill", "disconnect", "expiry"]:
            self.broker.fault = False
            Path(self.config.kill_file).unlink(missing_ok=True)

            def interrupt(_, kind=kind):
                if kind == "kill":
                    Path(self.config.kill_file).touch()
                elif kind == "disconnect":
                    self.broker.fault = True
                else:
                    self.execution.clock = NS(now=lambda: NOW.replace(minute=1))
                return self.phrase

            with self.subTest(kind=kind), self.assertRaises(SafetyError):
                self.execute(interrupt)
        self.assertEqual(self.broker.sent, [])

    def test_uncertain_send_is_reserved_and_blocks_restart(self):
        self.broker.fail_send = True
        with self.assertRaises(ConnectionError):
            self.execute(self.phrase)
        self.assertEqual(self.journal.unresolved(), [(PROP.key, "UNKNOWN")])
        other = Execution(self.config, self.broker, self.journal)
        with self.assertRaises(SafetyError):
            asyncio.run(other.execute(replace(PROP, key="another")))
