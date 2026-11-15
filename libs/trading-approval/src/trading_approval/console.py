import asyncio
import sys

from trading_contracts.models import Proposal, SafetyError


class ConsoleApproval:
    """Every request requires the exact immutable proposal identifier."""

    def __init__(self, mode: str = "paper"):
        if mode not in ("paper", "live"):
            raise ValueError("Unknown approval environment")
        self.mode = mode

    async def request(self, proposal: Proposal, account: str) -> bool:
        if self.mode == "live" and not sys.stdin.isatty():
            raise SafetyError(
                "Live approval requires an interactive terminal; piped approval refused"
            )
        phrase = (
            f"APPROVE LIVE {account} {proposal.key} {proposal.side} {proposal.quantity} "
            f"{proposal.symbol} LIMIT {proposal.limit:.2f}"
            if self.mode == "live"
            else f"APPROVE {proposal.key}"
        )
        print(
            f"{self.mode.upper()} {account}: {proposal.side} {proposal.quantity} {proposal.symbol} "
            f"LMT ${proposal.limit:.2f}, DAY. Type exactly: {phrase}"
        )
        return await asyncio.to_thread(input, "> ") == phrase
