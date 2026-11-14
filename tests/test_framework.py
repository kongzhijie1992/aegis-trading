import tempfile
import unittest
from pathlib import Path

from paper_trader.core import Config, SafetyError
from paper_trader.engine import TradingEngine
from paper_trader.journal import Journal
from paper_trader.simulator import SimulatedBroker, SimulationClock
from paper_trader.strategy import SmaStrategy


class TestApproval:
    """Test fixture only; never wired to the CLI or IBKR broker."""

    def __init__(self, accept=True, before=None):
        self.accept, self.before, self.requests = accept, before, []

    async def request(self, proposal, account):
        self.requests.append(proposal)
        if self.before:
            self.before()
        return self.accept


class FrameworkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = Config(account="DU000000", kill_file=str(Path(self.temp.name) / "STOP"))
        self.clock = SimulationClock()
        self.broker = SimulatedBroker(self.clock)
        self.journal = Journal(Path(self.temp.name) / "sim.sqlite")
        self.approval = TestApproval()
        self.engine = TradingEngine(
            self.config,
            self.broker,
            SmaStrategy(),
            self.journal,
            clock=self.clock,
            approval=self.approval,
        )
        await self.broker.connect()

    async def asyncTearDown(self):
        self.broker.close()
        self.journal.db.close()
        self.temp.cleanup()

    async def test_full_two_symbol_cycle_and_cash(self):
        results = await self.engine.cycle()
        self.assertEqual([r["status"] for r in results], ["Filled", "Filled"])
        self.assertEqual(len(self.approval.requests), 2)
        self.assertEqual(self.broker.positions, {"SPY": 1, "QQQ": 1})
        self.assertEqual(self.broker.cash, 9100)
        self.assertEqual(self.journal.count("2026-11-13"), 2)
        self.assertEqual([r["status"] for r in await self.engine.cycle()], ["HOLD", "HOLD"])

    async def test_decline_does_not_change_portfolio(self):
        self.approval.accept = False
        result = await self.engine.cycle(("SPY",))
        self.assertEqual(result[0]["status"], "DECLINED")
        self.assertEqual(self.broker.sent, [])
        self.assertEqual(self.broker.cash, 10000)

    async def test_entry_and_exit_use_same_pipeline(self):
        await self.engine.cycle(("SPY",))
        self.clock.advance(300)
        self.broker.trend = -1
        result = await self.engine.cycle(("SPY",))
        self.assertEqual(result[0]["status"], "Filled")
        self.assertEqual(self.broker.positions["SPY"], 0)
        self.assertAlmostEqual(self.broker.cash, 9999.99)

    async def test_disconnect_during_manual_review(self):
        self.approval.before = self.broker.close
        with self.assertRaises(SafetyError):
            await self.engine.cycle(("SPY",))
        self.assertEqual(self.broker.sent, [])

    async def test_expired_approval_with_controlled_clock(self):
        self.approval.before = lambda: self.clock.advance(31)
        with self.assertRaises(SafetyError):
            await self.engine.cycle(("SPY",))
        self.assertEqual(self.broker.sent, [])

    async def test_duplicate_signal_survives_new_engine(self):
        await self.engine.cycle(("SPY",))
        # Simulate an external flattening: consumed key remains consumed.
        self.broker.positions.clear()
        other = TradingEngine(
            self.config,
            self.broker,
            SmaStrategy(),
            self.journal,
            clock=self.clock,
            approval=self.approval,
        )
        result = await other.cycle(("SPY",))
        self.assertEqual(result[0]["status"], "ALREADY_ATTEMPTED")
        self.assertEqual(len(self.broker.sent), 1)

    async def test_diagnostics_collect_independent_failures_without_orders(self):
        async def failed_snapshot():
            raise SafetyError("unsupported portfolio")

        self.broker.snapshot = failed_snapshot
        report = await self.engine.diagnose()
        self.assertFalse(report["ready"])
        self.assertFalse(report["checks"]["account_risk"]["ok"])
        self.assertTrue(report["checks"]["SPY_quote"]["ok"])
        self.assertTrue(report["checks"]["QQQ_history_signal"]["ok"])
        self.assertEqual(self.broker.sent, [])
        self.assertEqual(self.approval.requests, [])

    async def test_custom_strategy_and_risk_extensions(self):
        class Flat:
            name = "flat"

            def target(self, bars, now):
                return 0

        engine = TradingEngine(self.config, self.broker, Flat(), self.journal, clock=self.clock)
        self.assertEqual((await engine.cycle(("SPY",)))[0]["status"], "HOLD")

        class BlockAll:
            def validate(self, *args):
                raise SafetyError("custom risk veto")

        engine = TradingEngine(
            self.config,
            self.broker,
            SmaStrategy(),
            self.journal,
            clock=self.clock,
            approval=self.approval,
            risk=BlockAll(),
        )
        with self.assertRaises(SafetyError):
            await engine.cycle(("SPY",))
        self.assertEqual(self.broker.sent, [])

    async def test_invalid_windows_and_targets(self):
        for strategy in (SmaStrategy(50, 20), SmaStrategy(0, 50)):
            with self.assertRaises(SafetyError):
                strategy.target(await self.broker.bars("SPY"), self.clock.now())

        class Invalid:
            name = "invalid"

            def target(self, bars, now):
                return -1

        engine = TradingEngine(self.config, self.broker, Invalid(), self.journal, clock=self.clock)
        with self.assertRaises(SafetyError):
            await engine.cycle(("SPY",))

    async def test_risk_extension_cannot_bypass_mandatory_gate(self):
        class AllowAll:
            def validate(self, *args):
                pass

        Path(self.config.kill_file).touch()
        engine = TradingEngine(
            self.config,
            self.broker,
            SmaStrategy(),
            self.journal,
            clock=self.clock,
            approval=self.approval,
            risk=AllowAll(),
        )
        with self.assertRaises(SafetyError):
            await engine.cycle(("SPY",))
        self.assertEqual(self.broker.sent, [])
