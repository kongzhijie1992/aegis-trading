"""Deterministic offline fixture broker. No network or IBKR imports."""

from datetime import UTC, datetime, timedelta

from trading_contracts.models import Bar, Quote, SafetyError
from trading_portfolio import PortfolioLedger


class SimulationClock:
    def __init__(self):
        self.time = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)

    def now(self):
        return self.time

    def advance(self, seconds):
        self.time += timedelta(seconds=seconds)


class SimulatedBroker:
    def __init__(self, clock, *, cash=10000):
        self.clock = clock
        self.ledger = PortfolioLedger(cash)
        self.sent = []
        self.connected = False
        self.trend = 1

    @property
    def positions(self):
        return self.ledger.positions

    @property
    def cash(self):
        return self.ledger.cash

    async def connect(self):
        self.connected = True

    def guard(self):
        if not self.connected:
            raise SafetyError("Offline fixture broker disconnected")

    def base(self, symbol):
        if symbol not in ("SPY", "QQQ"):
            raise SafetyError("Unsupported fixture symbol")
        return 500 if symbol == "SPY" else 400

    async def bars(self, symbol):
        self.guard()
        base = self.base(symbol)
        return [
            Bar(
                self.clock.now() - timedelta(minutes=5 * (60 - i)),
                base + self.trend * (i - 59) * 0.1,
            )
            for i in range(60)
        ]

    async def quote(self, symbol):
        self.guard()
        base = self.base(symbol)
        # live=True models a fresh admissible quote only inside this fixture.
        return Quote(base - 0.01, base, self.clock.now(), live=True)

    async def snapshot(self):
        self.guard()
        return self.ledger.snapshot({s: self.base(s) for s in self.positions})

    async def send_approved(self, proposal):
        self.guard()
        if type(proposal.quantity) is not int or proposal.quantity != 1:
            raise SafetyError("Fixture requires exactly one share")
        quote = await self.quote(proposal.symbol)
        if proposal.side == "BUY":
            if proposal.limit < quote.ask or self.cash < quote.ask:
                raise SafetyError("Fixture limit not executable or insufficient cash")
            self.ledger.apply_fill(proposal.symbol, "BUY", 1, quote.ask)
        elif proposal.side == "SELL" and self.positions.get(proposal.symbol, 0) >= 1:
            if proposal.limit > quote.bid:
                raise SafetyError("Fixture sell limit not executable")
            self.ledger.apply_fill(proposal.symbol, "SELL", 1, quote.bid)
        else:
            raise SafetyError("Fixture refuses short selling")
        self.sent.append(proposal)
        return "Filled"

    def close(self):
        self.connected = False
