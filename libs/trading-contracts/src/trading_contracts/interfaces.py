"""Extension points shared by the IBKR and offline adapters."""

from datetime import datetime
from typing import Protocol

from .models import Bar, Config, Proposal, Quote, Snapshot


class Clock(Protocol):
    def now(self) -> datetime: ...


class Broker(Protocol):
    async def connect(self) -> None: ...
    def guard(self) -> None: ...
    async def bars(self, symbol: str) -> list[Bar]: ...
    async def quote(self, symbol: str) -> Quote: ...
    async def snapshot(self) -> Snapshot: ...
    async def send_approved(self, proposal: Proposal) -> str: ...
    def close(self) -> None: ...


class Strategy(Protocol):
    name: str

    def target(self, bars: list[Bar], now: datetime) -> int: ...


class Approval(Protocol):
    async def request(self, proposal: Proposal, account: str) -> bool: ...


class RiskPolicy(Protocol):
    def validate(
        self,
        config: Config,
        proposal: Proposal,
        quote: Quote,
        state: Snapshot,
        now: datetime,
        daily_count: int,
        killed: bool,
    ) -> None: ...
