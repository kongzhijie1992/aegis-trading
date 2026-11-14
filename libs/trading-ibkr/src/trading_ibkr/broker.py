"""Local TWS adapter; no live endpoint or automatic reconnect path."""

import asyncio
import math
from datetime import UTC, datetime
from pathlib import Path

from trading_contracts.models import Bar, Quote, SafetyError, Snapshot


class PaperBroker:
    def __init__(self, config, journal, writable=False):
        from ib_async import IB

        config.validate()
        self.config, self.journal, self.writable = config, journal, writable
        self.ib = IB()
        self.ib.RequestTimeout = 10
        self.fault = False
        self.ib.disconnectedEvent += self._disconnect
        self.ib.errorEvent += self._error
        self.contracts = {}

    def _disconnect(self):
        self.fault = True
        self.journal.event("disconnect", "All proposals invalid; manual restart required")

    def _error(self, req_id, code, message, contract=None):
        self.journal.event("broker_error", {"request": req_id, "code": code, "message": message})
        if code in (1100, 1101, 1102, 1300, 2103, 2105, 2110):
            self.fault = True

    def guard(self):
        self.config.validate()
        accounts = self.ib.managedAccounts()
        if self.fault or not self.ib.isConnected():
            raise SafetyError("Disconnected/degraded session: restart and reconcile in TWS")
        if accounts != [self.config.account]:
            raise SafetyError(
                "Require exactly the configured DU paper account; mixed sessions refused"
            )

    async def connect(self):
        await self.ib.connectAsync(
            self.config.host,
            self.config.port,
            clientId=self.config.client_id,
            timeout=8,
            readonly=not self.writable,
            account=self.config.account,
            raiseSyncErrors=True,
        )
        self.guard()
        self.ib.reqMarketDataType(1)
        self.journal.event("connected", {"port": self.config.port, "writable": self.writable})

    async def contract(self, symbol):
        from ib_async import Stock

        if symbol not in ("SPY", "QQQ"):
            raise SafetyError("Only SPY and QQQ allowed")
        if symbol not in self.contracts:
            result = await asyncio.wait_for(
                self.ib.qualifyContractsAsync(Stock(symbol, "SMART", "USD")), 10
            )
            if len(result) != 1:
                raise SafetyError("Contract qualification failed")
            self.contracts[symbol] = result[0]
        self.guard()
        return self.contracts[symbol]

    async def bars(self, symbol):
        contract = await self.contract(symbol)
        bars = await self.ib.reqHistoricalDataAsync(
            contract,
            endDateTime="",
            durationStr="3 D",
            barSizeSetting="5 mins",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=2,
            keepUpToDate=False,
            timeout=15,
        )
        self.guard()
        return [Bar(b.date, b.close) for b in bars]

    async def quote(self, symbol):
        contract = await self.contract(symbol)
        ticker = self.ib.reqMktData(contract, "", False, False)
        ready = asyncio.Event()
        received = {}

        def update(t):
            for tick in t.ticks:
                if tick.tickType in (1, 2) and math.isfinite(tick.price) and tick.price > 0:
                    received[tick.tickType] = datetime.now(UTC)
            if 1 in received and 2 in received:
                ready.set()

        ticker.updateEvent += update
        try:
            await asyncio.wait_for(ready.wait(), 10)
            self.guard()
            return Quote(ticker.bid, ticker.ask, min(received.values()), ticker.marketDataType == 1)
        finally:
            ticker.updateEvent -= update
            self.ib.cancelMktData(contract)

    async def snapshot(self):
        # Explicit fresh server requests, not cached positions/accountSummary().
        positions = await asyncio.wait_for(self.ib.reqPositionsAsync(), 10)
        self.ib.client.cancelPositions()
        # ib_async's reqAccountSummaryAsync returns no values and leaves a
        # subscription open. Collect this bounded request explicitly.
        summary_values = {}

        def account_value(value):
            summary_values[(value.account, value.tag, value.currency)] = value

        self.ib.accountSummaryEvent += account_value
        req_id = self.ib.client.getReqId()
        future = self.ib.wrapper.startReq(req_id)
        try:
            self.ib.client.reqAccountSummary(req_id, "All", "GrossPositionValue,AvailableFunds")
            await asyncio.wait_for(future, 10)
        finally:
            self.ib.client.cancelAccountSummary(req_id)
            self.ib.accountSummaryEvent -= account_value
        summary = list(summary_values.values())
        orders = await asyncio.wait_for(self.ib.reqAllOpenOrdersAsync(), 10)
        pnl = self.ib.reqPnL(self.config.account)
        try:
            for _ in range(100):
                if math.isfinite(pnl.dailyPnL):
                    break
                await asyncio.sleep(0.1)
            daily = pnl.dailyPnL
        finally:
            self.ib.cancelPnL(self.config.account)
        self.guard()

        def amount(tag):
            matches = [
                float(v.value)
                for v in summary
                if v.account == self.config.account and v.tag == tag and v.currency == "USD"
            ]
            if len(matches) != 1:
                raise SafetyError(f"Missing USD {tag}; starter requires a USD-base account")
            return matches[0]

        held = {}
        for p in positions:
            if p.account == self.config.account:
                if p.position and (
                    p.contract.secType != "STK" or p.contract.currency != "USD" or p.position < 0
                ):
                    raise SafetyError(
                        "Starter supports only long USD stock/ETF holdings; use a dedicated paper account"
                    )
                held[p.contract.symbol] = held.get(p.contract.symbol, 0) + float(p.position)
        return Snapshot(
            held,
            amount("GrossPositionValue"),
            amount("AvailableFunds"),
            daily,
            sum(not t.isDone() for t in orders),
        )

    async def account_view(self):
        """Read-only display of all assets; never relaxes snapshot() trading gates."""
        self.guard()
        # connectAsync synchronizes and subscribes to account updates once.
        # Re-subscribing to the same account need not produce another download-end
        # callback in TWS, so use a bounded heartbeat and the maintained stream.
        await asyncio.wait_for(self.ib.reqCurrentTimeAsync(), 10)
        values = self.ib.accountValues(self.config.account)
        portfolio = self.ib.portfolio(self.config.account)
        orders = await asyncio.wait_for(self.ib.reqAllOpenOrdersAsync(), 10)
        currency = next(
            (v.value for v in values if v.tag == "Currency" and v.currency == "BASE"), None
        )
        if not currency:
            currency = next((v.currency for v in values if v.tag == "NetLiquidation"), "BASE")

        def number(value):
            try:
                value = float(value)
                return value if math.isfinite(value) and abs(value) < 1e100 else None
            except (ValueError, TypeError):
                return None

        def amount(tag):
            return next(
                (
                    number(v.value)
                    for v in values
                    if v.tag == tag and v.currency in (currency, "BASE")
                ),
                None,
            )

        pnl = self.ib.reqPnL(self.config.account)
        try:
            for _ in range(50):
                if number(pnl.dailyPnL) is not None:
                    break
                await asyncio.sleep(0.1)
            daily = number(pnl.dailyPnL)
            unrealized = number(getattr(pnl, "unrealizedPnL", None))
            realized = number(getattr(pnl, "realizedPnL", None))
        finally:
            self.ib.cancelPnL(self.config.account)
        self.guard()
        positions = []
        for item in portfolio:
            if item.account != self.config.account or not item.position:
                continue
            contract = item.contract
            instrument = contract.secType
            if contract.secType == "OPT":
                instrument += (
                    f" {contract.lastTradeDateOrContractMonth} {contract.strike} {contract.right}"
                )
            positions.append(
                {
                    "symbol": contract.symbol,
                    "instrument": instrument,
                    "quantity": number(item.position),
                    "currency": contract.currency,
                    "market_price": number(item.marketPrice),
                    "market_value": number(item.marketValue),
                    "average_cost": number(item.averageCost),
                    "unrealized_pnl": number(item.unrealizedPNL),
                    "realized_pnl": number(item.realizedPNL),
                }
            )
        return {
            "mode": "paper",
            "status": "connected",
            "account": self.config.account,
            "currency": currency,
            "as_of": datetime.now(UTC).isoformat(),
            "net_liquidation": amount("NetLiquidation"),
            "cash": amount("TotalCashValue"),
            "daily_pnl": daily,
            "unrealized_pnl": unrealized if unrealized is not None else amount("UnrealizedPnL"),
            "realized_pnl": realized if realized is not None else amount("RealizedPnL"),
            "positions": positions,
            "orders": [
                {
                    "symbol": t.contract.symbol,
                    "side": t.order.action,
                    "quantity": number(t.order.totalQuantity),
                    "filled": number(t.orderStatus.filled),
                    "status": t.orderStatus.status,
                    "type": t.order.orderType,
                }
                for t in orders
                if not t.isDone() and t.order.account in ("", self.config.account)
            ],
            "notes": [
                "Broker marks can be delayed or from the last session. No trading permissions implied.",
                "Option average cost uses the broker contract convention; do not compare it directly with an option quote.",
            ],
        }

    async def send_approved(self, proposal):
        from ib_async import LimitOrder

        contract = await self.contract(proposal.symbol)
        self.guard()
        if (
            Path(self.config.kill_file).exists()
            or not 0
            <= (datetime.now(UTC) - proposal.created).total_seconds()
            <= self.config.approval_seconds
        ):
            raise SafetyError("Stopped or expired immediately before send")
        if not self.writable:
            raise SafetyError("Read-only session cannot send")
        order = LimitOrder(
            proposal.side,
            proposal.quantity,
            proposal.limit,
            account=self.config.account,
            tif="DAY",
            outsideRth=False,
            orderRef=proposal.key[:64],
            transmit=True,
        )
        trade = self.ib.placeOrder(contract, order)
        self.journal.event("send", {"key": proposal.key, "order_id": trade.order.orderId})

        def record(t):
            self.journal.status(proposal.key, t.orderStatus.status)
            self.journal.event(
                "order_status",
                {
                    "key": proposal.key,
                    "status": t.orderStatus.status,
                    "filled": t.orderStatus.filled,
                    "remaining": t.orderStatus.remaining,
                },
            )

        trade.statusEvent += record
        trade.fillEvent += lambda t, f: self.journal.event(
            "fill",
            {
                "key": proposal.key,
                "execution_id": f.execution.execId,
                "shares": str(f.execution.shares),
                "price": f.execution.price,
            },
        )
        record(trade)
        # Keep receiving statuses, including partial fills, but never resubmit.
        for _ in range(60):
            self.guard()
            if trade.isDone():
                break
            await asyncio.sleep(1)
        record(trade)
        return trade.orderStatus.status

    def close(self):
        self.ib.disconnect()
