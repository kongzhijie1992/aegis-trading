"""One-pass orchestration independent of any broker implementation."""

from datetime import UTC, datetime, timedelta

from trading_contracts.interfaces import Broker, Strategy
from trading_contracts.models import Proposal, SafetyError
from trading_execution.service import Execution
from trading_marketdata import ValidatedMarketData
from trading_portfolio import side_for_target
from trading_risk.policy import limit_price


class SystemClock:
    def now(self):
        return datetime.now(UTC)


class TradingEngine:
    def __init__(
        self,
        config,
        broker: Broker,
        strategy: Strategy,
        journal,
        *,
        clock=None,
        approval=None,
        risk=None,
        market_data=None,
    ):
        self.config, self.broker, self.strategy, self.journal = config, broker, strategy, journal
        self.clock = clock or SystemClock()
        self.market_data = ValidatedMarketData(market_data or broker, self.clock)
        self.execution = Execution(
            config, broker, journal, clock=self.clock, approval=approval, risk=risk
        )

    async def proposal(self, symbol):
        if symbol not in ("SPY", "QQQ"):
            raise SafetyError("Only SPY/QQQ enabled")
        bars = await self.market_data.bars(symbol)
        target = self.strategy.target(bars, self.clock.now())
        if type(target) is not int or target not in (0, 1):
            raise SafetyError("Strategy must return integer target 0 or 1")
        state = await self.broker.snapshot()
        held = state.positions.get(symbol, 0)
        side = side_for_target(target, held)
        if side is None:
            return None
        quote = await self.market_data.quote(symbol)
        now = self.clock.now()
        # Signal remains fresh even if an account/data request was slow.
        if self.strategy.target(bars, now) != target:
            raise SafetyError("Signal changed during preparation")
        last = max(b.time for b in bars if b.time + timedelta(minutes=5) <= now)
        # Retain legacy keys so existing consumed signals cannot be replayed.
        key = f"{symbol}-{side}-{last:%Y%m%dT%H%M}"
        return Proposal(key, symbol, side, 1, limit_price(quote, side), now)

    async def cycle(self, symbols=("SPY", "QQQ")):
        if self.journal.unresolved():
            raise SafetyError("Unresolved orders: reconcile before continuing")
        results = []
        for symbol in symbols:
            proposal = await self.proposal(symbol)
            if proposal is None:
                results.append({"symbol": symbol, "status": "HOLD"})
            elif self.journal.seen(proposal.key):
                results.append({"symbol": symbol, "status": "ALREADY_ATTEMPTED"})
            else:
                self.journal.event("proposal", proposal.__dict__)
                result = await self.execution.execute(proposal)
                results.append({"symbol": symbol, "key": proposal.key, "status": result})
                if self.journal.unresolved():
                    break
        return results

    async def diagnose(self, symbols=("SPY", "QQQ")):
        """Independent checks: portfolio restrictions do not hide data failures."""
        self.broker.guard()
        report = {
            "time": self.clock.now().isoformat(),
            "connection": "verified_paper",
            "read_only_diagnostics": True,
            "orders_submitted": 0,
            "checks": {},
        }

        async def capture(name, action):
            try:
                report["checks"][name] = {"ok": True, "result": await action()}
            except Exception as exc:
                report["checks"][name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

        await capture("account_risk", self.broker.snapshot)
        for symbol in symbols:

            async def history(s=symbol):
                bars = await self.market_data.bars(s)
                return {"bars": len(bars), "target": self.strategy.target(bars, self.clock.now())}

            await capture(symbol + "_history_signal", history)
            await capture(symbol + "_quote", lambda s=symbol: self.market_data.quote(s))
        report["ready"] = all(x["ok"] for x in report["checks"].values())
        return report
