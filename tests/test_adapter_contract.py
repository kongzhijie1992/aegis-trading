"""Exercise real adapter callbacks against an in-process fake TWS transport."""

import asyncio
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

from trading_contracts import Config, Proposal, SafetyError
from trading_ibkr import LiveBroker, PaperBroker
from trading_monitoring import Journal


class Event:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self

    def __isub__(self, handler):
        self.handlers.remove(handler)
        return self

    def emit(self, *args):
        for handler in list(self.handlers):
            handler(*args)


class AdapterContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.tmp.name) / "journal.sqlite")
        self.config = Config(account="DU123", kill_file=str(Path(self.tmp.name) / "STOP"))
        self.broker = PaperBroker(self.config, self.journal)
        self.positions = []
        self.summary = [("GrossPositionValue", "0"), ("AvailableFunds", "10000")]
        self.future = None
        self.ib = NS(
            managedAccounts=lambda: ["DU123"],
            isConnected=lambda: True,
            connectAsync=AsyncMock(),
            reqMarketDataType=Mock(),
            disconnect=Mock(),
            qualifyContractsAsync=AsyncMock(side_effect=lambda c: [c]),
            reqHistoricalDataAsync=AsyncMock(return_value=[NS(date=datetime.now(UTC), close=500)]),
            accountSummaryEvent=Event(),
            reqPositionsAsync=AsyncMock(side_effect=lambda: self.positions),
            reqAllOpenOrdersAsync=AsyncMock(return_value=[]),
            reqPnL=Mock(return_value=NS(dailyPnL=0)),
            cancelPnL=Mock(),
            cancelMktData=Mock(),
        )

        def start(_):
            self.future = asyncio.get_running_loop().create_future()
            return self.future

        def summary(*_):
            for tag, value in self.summary:
                self.ib.accountSummaryEvent.emit(
                    NS(account="DU123", tag=tag, value=value, currency="USD")
                )
            self.future.set_result(None)

        self.ib.wrapper = NS(startReq=start)
        self.ib.client = NS(
            getReqId=lambda: 1,
            cancelPositions=Mock(),
            reqAccountSummary=summary,
            cancelAccountSummary=Mock(),
        )
        self.broker.ib = self.ib

    async def asyncTearDown(self):
        self.journal.db.close()
        self.tmp.cleanup()

    async def test_readonly_connect_qualification_history_and_close(self):
        await self.broker.connect()
        self.assertTrue(self.ib.connectAsync.call_args.kwargs["readonly"])
        await self.broker.contract("SPY")
        await self.broker.contract("SPY")
        self.assertEqual(self.ib.qualifyContractsAsync.call_count, 1)
        self.assertEqual((await self.broker.bars("SPY"))[0].close, 500)
        with self.assertRaises(SafetyError):
            await self.broker.contract("TSLA")
        self.ib.qualifyContractsAsync.return_value = []
        self.ib.qualifyContractsAsync.side_effect = None
        with self.assertRaises(SafetyError):
            await self.broker.contract("QQQ")
        self.broker.close()
        self.ib.disconnect.assert_called_once()

    async def test_quote_uses_both_fresh_bid_and_ask_and_cancels(self):
        ticker = NS(
            updateEvent=Event(),
            bid=499.99,
            ask=500,
            marketDataType=1,
            ticks=[NS(tickType=1, price=499.99), NS(tickType=2, price=500)],
        )

        def subscribe(*_):
            asyncio.get_running_loop().call_soon(ticker.updateEvent.emit, ticker)
            return ticker

        self.ib.reqMktData = subscribe
        quote = await self.broker.quote("SPY")
        self.assertTrue(quote.live)
        self.assertEqual((quote.bid, quote.ask), (499.99, 500))
        self.ib.cancelMktData.assert_called_once()
        self.assertEqual(ticker.updateEvent.handlers, [])

    async def test_snapshot_fresh_account_data_and_cleanup(self):
        self.positions = [
            NS(
                account="DU123",
                position=1,
                contract=NS(symbol="SPY", secType="STK", currency="USD"),
            )
        ]
        state = await self.broker.snapshot()
        self.assertEqual(state.positions, {"SPY": 1})
        self.assertEqual(state.available_usd, 10000)
        self.ib.cancelPnL.assert_called_once_with("DU123")
        self.ib.client.cancelAccountSummary.assert_called_once_with(1)
        self.assertEqual(self.ib.accountSummaryEvent.handlers, [])

    async def test_snapshot_refuses_unsupported_assets_and_missing_summary(self):
        self.positions = [
            NS(
                account="DU123",
                position=1,
                contract=NS(symbol="GSPX", secType="STK", currency="GBP"),
            )
        ]
        with self.assertRaises(SafetyError):
            await self.broker.snapshot()
        self.positions = []
        self.summary = []
        with self.assertRaises(SafetyError):
            await self.broker.snapshot()

    async def test_paper_limit_order_status_fill_callbacks(self):
        self.broker.writable = True
        proposal = Proposal("adapter-test", "SPY", "BUY", 1, 500, datetime.now(UTC))
        self.journal.reserve(proposal, "2026-11-13")
        trade = NS(
            order=NS(orderId=123),
            orderStatus=NS(status="Filled", filled=1, remaining=0),
            statusEvent=Event(),
            fillEvent=Event(),
            isDone=lambda: True,
        )
        self.ib.placeOrder = Mock(return_value=trade)
        self.assertEqual(await self.broker.send_approved(proposal), "Filled")
        order = self.ib.placeOrder.call_args.args[1]
        self.assertEqual((order.account, order.orderType, order.tif), ("DU123", "LMT", "DAY"))
        self.assertFalse(order.outsideRth)
        trade.statusEvent.emit(trade)
        trade.fillEvent.emit(trade, NS(execution=NS(execId="fixture", shares=1, price=500)))
        self.assertEqual(self.journal.unresolved(), [])

    async def test_live_adapter_uses_live_port_and_exact_account_with_fake_transport(self):
        config = replace(self.config, mode="live", live_enabled=True, port=4001, account="U123")
        broker = LiveBroker(config, self.journal)
        broker.ib = self.ib
        self.ib.managedAccounts = lambda: ["U123"]
        await broker.connect()
        self.assertEqual(self.ib.connectAsync.call_args.args, ("127.0.0.1", 4001))
        self.assertTrue(self.ib.connectAsync.call_args.kwargs["readonly"])
        proposal = Proposal("LIVE-U123-fake", "SPY", "BUY", 1, 500, datetime.now(UTC))
        with self.assertRaises(SafetyError):
            await broker.send_approved(proposal)
        broker.writable = True
        self.journal.reserve(proposal, "2026-11-13")
        trade = NS(
            order=NS(orderId=456),
            orderStatus=NS(status="Filled", filled=1, remaining=0),
            statusEvent=Event(),
            fillEvent=Event(),
            isDone=lambda: True,
        )
        self.ib.placeOrder = Mock(return_value=trade)
        self.assertEqual(await broker.send_approved(proposal), "Filled")
        order = self.ib.placeOrder.call_args.args[1]
        self.assertEqual((order.account, order.orderType, order.tif), ("U123", "LMT", "DAY"))
        self.assertFalse(order.outsideRth)

    async def test_readonly_account_view_displays_mixed_assets_without_relaxing_risk(self):
        self.ib.reqAccountUpdatesAsync = AsyncMock()
        self.ib.reqCurrentTimeAsync = AsyncMock(return_value=datetime.now(UTC))
        self.ib.reqPnL.return_value = NS(dailyPnL=0, unrealizedPnL=12, realizedPnL=3)
        self.ib.accountValues = lambda _: [
            NS(tag="Currency", currency="BASE", value="USD"),
            NS(tag="NetLiquidation", currency="USD", value="10000"),
            NS(tag="TotalCashValue", currency="USD", value="bad"),
        ]
        stock = NS(symbol="GSPX", secType="STK", currency="GBP")
        option = NS(
            symbol="NVDA",
            secType="OPT",
            currency="USD",
            lastTradeDateOrContractMonth="20261120",
            strike=180,
            right="C",
        )
        self.ib.portfolio = lambda _: [
            NS(
                account="DU123",
                contract=c,
                position=q,
                marketPrice=10,
                marketValue=q * 10,
                averageCost=11,
                unrealizedPNL=-1,
                realizedPNL=0,
            )
            for c, q in [(stock, 1), (option, -1), (stock, 0)]
        ]
        trade = NS(
            contract=stock,
            order=NS(account="DU123", action="BUY", totalQuantity=1, orderType="LMT"),
            orderStatus=NS(filled=0, status="Submitted"),
            isDone=lambda: False,
        )
        self.ib.reqAllOpenOrdersAsync = AsyncMock(return_value=[trade])
        result = await self.broker.account_view()
        self.assertEqual(len(result["positions"]), 2)
        self.assertEqual(result["positions"][1]["quantity"], -1)
        self.assertEqual(result["net_liquidation"], 10000)
        self.assertIsNone(result["cash"])
        self.assertEqual(len(result["orders"]), 1)
        self.assertFalse(self.broker.writable)
        self.assertEqual(result["unrealized_pnl"], 12)
        self.assertEqual(result["realized_pnl"], 3)
        self.ib.reqPnL.return_value = NS(dailyPnL=0)
        self.ib.accountValues = lambda _: [NS(tag="NetLiquidation", currency="GBP", value="1e300")]
        fallback = await self.broker.account_view(heartbeat_seconds=15)
        self.assertEqual(fallback["currency"], "GBP")
        self.assertIsNone(fallback["net_liquidation"])
        self.assertEqual(self.ib.reqCurrentTimeAsync.await_count, 1)
        self.broker._last_dashboard_heartbeat -= 16
        await self.broker.account_view(heartbeat_seconds=15)
        self.assertEqual(self.ib.reqCurrentTimeAsync.await_count, 2)
        self.ib.reqAccountUpdatesAsync.assert_not_awaited()

    async def test_account_view_stops_on_failed_heartbeat(self):
        self.ib.reqCurrentTimeAsync = AsyncMock(side_effect=TimeoutError("heartbeat"))
        with self.assertRaises(TimeoutError):
            await self.broker.account_view()
