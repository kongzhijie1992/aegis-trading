import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from trading_approval import ConsoleApproval
from trading_contracts import Bar, Config, Proposal, Quote, SafetyError, Snapshot
from trading_marketdata import ValidatedMarketData
from trading_monitoring import configure_logging
from trading_portfolio import PortfolioLedger
from trading_risk import StarterRisk, check, limit_price
from trading_simulation import SimulatedBroker, SimulationClock
from trading_strategy import SmaStrategy


class QualityBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_console_requires_exact_phrase(self):
        clock = SimulationClock()
        p = Proposal("fixture", "SPY", "BUY", 1, 500, clock.now())
        for response, expected in [("APPROVE fixture", True), ("yes", False)]:
            with patch("builtins.input", return_value=response):
                self.assertEqual(await ConsoleApproval().request(p, "DU000000"), expected)

    async def test_strategy_rejects_naive_bad_and_unordered_data(self):
        clock = SimulationClock()
        broker = SimulatedBroker(clock)
        await broker.connect()
        bars = await broker.bars("SPY")
        cases = [
            ([Bar(clock.now().replace(tzinfo=None), 500)], clock.now()),
            ([*bars[:-1], replace(bars[-1], close=float("nan"))], clock.now()),
            (list(reversed(bars)), clock.now()),
        ]
        for values, now in cases:
            with self.assertRaises(SafetyError):
                SmaStrategy().target(values, now)

        async def empty(_):
            return []

        broker.bars = empty
        with self.assertRaises(SafetyError):
            await ValidatedMarketData(broker, clock).bars("SPY")

        async def invalid(_):
            return [Bar(clock.now(), -1)]

        broker.bars = invalid
        with self.assertRaises(SafetyError):
            await ValidatedMarketData(broker, clock).bars("SPY")

    async def test_fixture_refuses_bad_orders_without_mutation(self):
        clock = SimulationClock()
        broker = SimulatedBroker(clock)
        await broker.connect()
        p = Proposal("fixture", "SPY", "BUY", 1, 499, clock.now())
        for invalid in (p, replace(p, side="SELL"), replace(p, quantity=2)):
            with self.assertRaises(SafetyError):
                await broker.send_approved(invalid)
        broker.positions["SPY"] = 1
        with self.assertRaises(SafetyError):
            await broker.send_approved(replace(p, side="SELL", limit=501))
        with self.assertRaises(SafetyError):
            await broker.bars("TSLA")
        self.assertEqual(broker.sent, [])

    async def test_risk_boundary_values_and_policy_wrapper(self):
        now = SimulationClock().now()
        cfg = Config(account="DU000000")
        p = Proposal("fixture", "SPY", "BUY", 1, 500, now)
        q = Quote(499.99, 500, now)
        state = Snapshot({}, 0, 10000, 0, 0)
        StarterRisk().validate(cfg, p, q, state, now, 0, False)
        for proposal, quote, config, s in [
            (replace(p, limit=-1), q, cfg, state),
            (p, q, replace(cfg, max_order_usd=400), state),
            (p, q, cfg, replace(state, open_orders=-1)),
            (replace(p, created=now.replace(tzinfo=None)), q, cfg, state),
        ]:
            with self.assertRaises(SafetyError):
                check(config, proposal, quote, s, now, 0, False)
        with self.assertRaises(SafetyError):
            limit_price(q, "HOLD")
        with self.assertRaises(SafetyError):
            PortfolioLedger(-1)

    async def test_logging_handlers_are_bounded(self):
        with tempfile.TemporaryDirectory() as folder, patch("logging.basicConfig") as configure:
            configure_logging(Path(folder) / "app.log")
            handlers = configure.call_args.kwargs["handlers"]
            self.assertEqual(handlers[0].maxBytes, 2_000_000)
            self.assertEqual(handlers[0].backupCount, 5)
            for handler in handlers:
                handler.close()
