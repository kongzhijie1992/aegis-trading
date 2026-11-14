import asyncio
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from paper_trader.core import Bar, Config, Proposal, Quote, SafetyError, Snapshot
from paper_trader.execution import Execution
from paper_trader.journal import Journal
from paper_trader.risk import check
from paper_trader.strategy import signal

NOW = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
CFG = Config(account="DU123456")
PROP = Proposal("SPY-BUY-20261113T1455", "SPY", "BUY", 1, 500, NOW)
QUOTE = Quote(499.99, 500, NOW)
STATE = Snapshot({}, 0, 10000, 0, 0)


class RiskTests(unittest.TestCase):
    def check(self, p=PROP, q=QUOTE, s=STATE, now=NOW, n=0, killed=False, cfg=CFG):
        check(cfg, p, q, s, now, n, killed)

    def test_valid_order(self):
        self.check()
        replace(CFG, account="DUR239069").validate()

    def test_live_and_misconfigured_sessions(self):
        for changes in (
            {"mode": "live"},
            {"port": 7496},
            {"port": 4001},
            {"port": 9999},
            {"host": "10.0.0.1"},
            {"account": "U123456"},
            {"account": "UR239069"},
            {"account": "DUR"},
            {"account": "DUR239069oops"},
            {"account": ""},
            {"max_daily_loss_usd": float("nan")},
            {"client_id": 0},
        ):
            with self.subTest(changes=changes), self.assertRaises(SafetyError):
                replace(CFG, **changes).validate()

    def test_risk_failures(self):
        cases = [
            dict(q=replace(QUOTE, live=False)),
            dict(q=replace(QUOTE, time=NOW - timedelta(seconds=11))),
            dict(q=replace(QUOTE, ask=float("nan"))),
            dict(q=replace(QUOTE, bid=490)),
            dict(s=replace(STATE, available_usd=100)),
            dict(s=replace(STATE, gross_usd=4900)),
            dict(s=replace(STATE, positions={"SPY": 1})),
            dict(s=replace(STATE, positions={"SPY": -1})),
            dict(s=replace(STATE, open_orders=1)),
            dict(s=replace(STATE, daily_pnl=-100)),
            dict(s=replace(STATE, daily_pnl=float("nan"))),
            dict(killed=True),
            dict(n=4),
            dict(p=replace(PROP, side="SELL")),
            dict(p=replace(PROP, quantity=2)),
            dict(p=replace(PROP, symbol="TSLA")),
            dict(p=replace(PROP, limit=510)),
            dict(p=replace(PROP, created=NOW - timedelta(seconds=31))),
            dict(now=NOW.replace(hour=22)),
            dict(now=NOW + timedelta(days=1)),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(SafetyError):
                self.check(**case)

    def test_exit_owned_share(self):
        self.check(p=replace(PROP, side="SELL"), s=replace(STATE, positions={"SPY": 1}))

    def test_strategy_completed_bars_only(self):
        bars = [Bar(NOW - timedelta(minutes=5 * (60 - i)), 400 + i) for i in range(60)]
        self.assertEqual(signal(bars, NOW), 1)
        self.assertEqual(signal(bars + [Bar(NOW, 0.01)], NOW), 1)
        self.assertEqual(signal([replace(b, close=1000 - b.close) for b in bars], NOW), 0)
        with self.assertRaises(SafetyError):
            signal(bars[:20], NOW)
        with self.assertRaises(SafetyError):
            signal(bars, NOW + timedelta(hours=1))


class FakeBroker:
    def __init__(self):
        self.sent = []
        self.fault = False
        self.state = STATE
        self.fail_send = False

    def guard(self):
        if self.fault:
            raise SafetyError("disconnect")

    async def quote(self, symbol):
        self.guard()
        return QUOTE

    async def snapshot(self):
        self.guard()
        return self.state

    async def send_approved(self, proposal):
        self.guard()
        self.sent.append(proposal)
        if self.fail_send:
            raise ConnectionError("uncertain socket write")
        return "Filled"


class FrozenDateTime:
    @staticmethod
    def now(tz=None):
        return NOW


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.tmp.name) / "journal.sqlite")
        self.broker = FakeBroker()
        self.config = replace(CFG, kill_file=str(Path(self.tmp.name) / "STOP"))
        self.engine = Execution(self.config, self.broker, self.journal)
        self.clock = patch("paper_trader.execution.datetime", FrozenDateTime)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.journal.db.close()
        self.tmp.cleanup()

    def run_order(self, approve):
        return asyncio.run(self.engine.execute(PROP, approve))

    def test_decline_sends_nothing(self):
        self.assertEqual(self.run_order(lambda _: "yes"), "DECLINED")
        self.assertEqual(self.broker.sent, [])
        self.assertFalse(self.journal.seen(PROP.key))

    def test_exact_approval_and_duplicate_prevention(self):
        self.assertEqual(self.run_order(lambda _: "APPROVE " + PROP.key), "Filled")
        self.assertEqual(self.broker.sent, [PROP])
        with self.assertRaises(SafetyError):
            self.run_order(lambda _: "APPROVE " + PROP.key)

    def test_disconnect_while_approving(self):
        def approve(_):
            self.broker.fault = True
            return "APPROVE " + PROP.key

        with self.assertRaises(SafetyError):
            self.run_order(approve)
        self.assertEqual(self.broker.sent, [])

    def test_risk_rechecked_after_approval(self):
        def approve(_):
            self.broker.state = replace(STATE, open_orders=1)
            return "APPROVE " + PROP.key

        with self.assertRaises(SafetyError):
            self.run_order(approve)
        self.assertEqual(self.broker.sent, [])

    def test_kill_switch_during_approval(self):
        def approve(_):
            Path(self.config.kill_file).touch()
            return "APPROVE " + PROP.key

        with self.assertRaises(SafetyError):
            self.run_order(approve)
        self.assertEqual(self.broker.sent, [])

    def test_expired_approval(self):
        def approve(_):
            class Later:
                @staticmethod
                def now(tz=None):
                    return NOW + timedelta(seconds=31)

            self.later = patch("paper_trader.execution.datetime", Later)
            self.later.start()
            return "APPROVE " + PROP.key

        try:
            with self.assertRaises(SafetyError):
                self.run_order(approve)
        finally:
            self.later.stop()
        self.assertEqual(self.broker.sent, [])

    def test_uncertain_send_persists_and_blocks_restart(self):
        self.broker.fail_send = True
        with self.assertRaises(ConnectionError):
            self.run_order(lambda _: "APPROVE " + PROP.key)
        other = Journal(Path(self.tmp.name) / "journal.sqlite")
        try:
            self.assertEqual(other.unresolved(), [(PROP.key, "UNKNOWN")])
            self.assertEqual(other.count("2026-11-13"), 1)
        finally:
            other.db.close()
        with self.assertRaises(SafetyError):
            asyncio.run(
                self.engine.execute(replace(PROP, key="different"), lambda _: "APPROVE different")
            )
        self.assertEqual(len(self.broker.sent), 1)


if __name__ == "__main__":
    unittest.main()
