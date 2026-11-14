import asyncio
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from trading_approval.console import ConsoleApproval
from trading_contracts.models import SafetyError
from trading_risk.policy import check


class Execution:
    def __init__(self, config, broker, journal, *, clock=None, approval=None, risk=None):
        self.config, self.broker, self.journal = config, broker, journal
        self.clock, self.approval, self.risk = clock, approval or ConsoleApproval(), risk

    def now(self):
        return self.clock.now() if self.clock else datetime.now(UTC)

    async def execute(self, proposal, approve=None):
        if self.journal.seen(proposal.key) or self.journal.unresolved():
            raise SafetyError("Duplicate or unresolved prior order: reconcile before continuing")
        quote = await self.broker.quote(proposal.symbol)
        state = await self.broker.snapshot()
        self._check(proposal, quote, state)
        if approve is None:
            accepted = await self.approval.request(proposal, self.config.account)
        else:
            # Explicit injected approval reader for deterministic tests.
            accepted = await asyncio.to_thread(approve, "> ") == f"APPROVE {proposal.key}"
        if not accepted:
            self.journal.event("declined", proposal.key)
            return "DECLINED"
        self.journal.event("approved", proposal.__dict__)
        quote = await self.broker.quote(proposal.symbol)
        state = await self.broker.snapshot()
        self.broker.guard()
        self._check(proposal, quote, state)
        day = self.now().astimezone(ZoneInfo("America/New_York")).date().isoformat()
        # Commit BEFORE network send; crashes/timeouts consume the intent permanently.
        self.journal.reserve(proposal, day)
        try:
            result = await self.broker.send_approved(proposal)
            self.journal.status(proposal.key, result)
            return result
        except BaseException:
            self.journal.event("uncertain_send", proposal.key)
            raise

    def _check(self, proposal, quote, state):
        now = self.now()
        day = now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
        context = (
            self.config,
            proposal,
            quote,
            state,
            now,
            self.journal.count(day),
            Path(self.config.kill_file).exists(),
        )
        # Extensions may add restrictions, never replace the mandatory gates.
        check(*context)
        if self.risk:
            self.risk.validate(*context)
