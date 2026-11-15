import math
import re
from dataclasses import dataclass
from datetime import datetime


class SafetyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    mode: str = "paper"
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 71
    account: str = ""
    live_enabled: bool = False
    max_order_usd: float = 1500
    max_symbol_usd: float = 3000
    max_gross_usd: float = 5000
    max_daily_orders: int = 4
    max_daily_loss_usd: float = 100
    max_spread_bps: float = 20
    approval_seconds: int = 30
    kill_file: str = "runtime/STOP"

    def validate(self) -> None:
        if self.host != "127.0.0.1" or type(self.live_enabled) is not bool:
            raise SafetyError("Use localhost and an explicit boolean live opt-in")
        if self.mode == "paper":
            if self.port not in (7497, 4002) or self.live_enabled:
                raise SafetyError("Paper mode requires paper ports and live_enabled=false")
            pattern = r"DU(?:R)?\d+"
        elif self.mode == "live":
            if self.port not in (7496, 4001) or not self.live_enabled:
                raise SafetyError("Live mode requires live ports and live_enabled=true")
            pattern = r"U\d+"
        else:
            raise SafetyError("Unknown trading environment")
        if not re.fullmatch(pattern, self.account):
            raise SafetyError("Exact account format must match the configured environment")
        if type(self.client_id) is not int or not 0 < self.client_id <= 2_147_483_647:
            raise SafetyError("Use a positive signed 32-bit client ID")
        for field in (
            "max_order_usd",
            "max_symbol_usd",
            "max_gross_usd",
            "max_daily_orders",
            "max_daily_loss_usd",
            "max_spread_bps",
            "approval_seconds",
        ):
            value = getattr(self, field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (float, int))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise SafetyError(f"Invalid {field}")


@dataclass(frozen=True)
class Bar:
    time: datetime
    close: float


@dataclass(frozen=True)
class Quote:
    bid: float
    ask: float
    time: datetime
    live: bool = True


@dataclass(frozen=True)
class Proposal:
    key: str
    symbol: str
    side: str
    quantity: int
    limit: float
    created: datetime


@dataclass(frozen=True)
class Snapshot:
    positions: dict[str, float]
    gross_usd: float
    available_usd: float
    daily_pnl: float
    open_orders: int
