"""Public API tests use installed libraries, never compatibility imports."""

import unittest
from dataclasses import replace
from datetime import timedelta

from trading_contracts import SafetyError
from trading_marketdata import ValidatedMarketData
from trading_portfolio import PortfolioLedger, side_for_target
from trading_simulation import SimulatedBroker, SimulationClock
from trading_strategy import SmaStrategy


class LibraryTests(unittest.TestCase):
    def test_portfolio_rejects_overspend_and_short_without_mutation(self):
        portfolio = PortfolioLedger(100)
        for side, qty, price in [
            ("BUY", 1, 101),
            ("SELL", 1, 10),
            ("BUY", 0, 10),
            ("BUY", 1, float("nan")),
        ]:
            with self.subTest(side=side, qty=qty, price=price), self.assertRaises(SafetyError):
                portfolio.apply_fill("SPY", side, qty, price)
            self.assertEqual(portfolio.cash, 100)
            self.assertEqual(portfolio.positions, {})

    def test_portfolio_fill_cash_exposure_and_marks(self):
        portfolio = PortfolioLedger(1000)
        portfolio.apply_fill("SPY", "BUY", 1, 500)
        state = portfolio.snapshot({"SPY": 510})
        self.assertEqual(
            (state.positions, state.gross_usd, state.available_usd), ({"SPY": 1}, 510, 500)
        )
        with self.assertRaises(SafetyError):
            portfolio.snapshot({})
        portfolio.apply_fill("SPY", "SELL", 1, 510)
        self.assertEqual(portfolio.cash, 1010)

    def test_target_comparison(self):
        self.assertEqual(side_for_target(1, 0), "BUY")
        self.assertEqual(side_for_target(0, 1), "SELL")
        self.assertIsNone(side_for_target(1, 1))
        for target, holding in [(2, 0), (True, 0), (0, -1), (0, float("nan"))]:
            with self.assertRaises(SafetyError):
                side_for_target(target, holding)


class MarketDataLibraryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = SimulationClock()
        self.broker = SimulatedBroker(self.clock)
        await self.broker.connect()
        self.data = ValidatedMarketData(self.broker, self.clock)

    async def test_strategy_and_data_public_interfaces(self):
        self.assertEqual(SmaStrategy().target(await self.data.bars("SPY"), self.clock.now()), 1)
        self.assertTrue((await self.data.quote("QQQ")).live)

    async def test_bad_bars_and_quotes_fail_at_data_boundary(self):
        original = await self.broker.bars("SPY")

        async def backwards(symbol):
            return list(reversed(original))

        self.broker.bars = backwards
        with self.assertRaises(SafetyError):
            await self.data.bars("SPY")
        quote = await self.broker.quote("SPY")
        for bad in (
            replace(quote, bid=quote.ask + 1),
            replace(quote, ask=float("nan")),
            replace(quote, time=quote.time - timedelta(seconds=11)),
        ):

            async def bad_quote(symbol, bad=bad):
                return bad

            self.broker.quote = bad_quote
            with self.assertRaises(SafetyError):
                await self.data.quote("SPY")
