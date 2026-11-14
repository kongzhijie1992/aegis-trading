import asyncio

from trading_contracts.models import Proposal


class ConsoleApproval:
    """Every request requires the exact immutable proposal identifier."""

    async def request(self, proposal: Proposal, account: str) -> bool:
        phrase = f"APPROVE {proposal.key}"
        print(
            f"PAPER {account}: {proposal.side} {proposal.quantity} {proposal.symbol} "
            f"LMT ${proposal.limit:.2f}, DAY. Type exactly: {phrase}"
        )
        return await asyncio.to_thread(input, "> ") == phrase
