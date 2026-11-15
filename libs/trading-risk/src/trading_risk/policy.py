import math
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from zoneinfo import ZoneInfo

from trading_contracts.models import Config, Proposal, Quote, SafetyError, Snapshot


class StarterRisk:
    def validate(
        self,
        config: Config,
        proposal: Proposal,
        quote: Quote,
        state: Snapshot,
        now: datetime,
        daily_count: int,
        killed: bool,
    ) -> None:
        check(config, proposal, quote, state, now, daily_count, killed)


def limit_price(quote: Quote, side: str) -> float:
    if side not in ("BUY", "SELL"):
        raise SafetyError("Unsupported order side")
    # Round buy down / sell up to avoid crossing the reviewed price.
    return float(
        Decimal(str(quote.ask if side == "BUY" else quote.bid)).quantize(
            Decimal("0.01"), rounding=ROUND_FLOOR if side == "BUY" else ROUND_CEILING
        )
    )


def check(
    config: Config,
    proposal: Proposal,
    quote: Quote,
    state: Snapshot,
    now: datetime,
    daily_count: int,
    killed: bool,
) -> None:
    config.validate()
    if any(t.tzinfo is None for t in (now, proposal.created, quote.time)):
        raise SafetyError("Timezone-aware risk timestamps required")
    if (
        type(daily_count) is not int
        or daily_count < 0
        or type(state.open_orders) is not int
        or state.open_orders < 0
        or state.gross_usd < 0
    ):
        raise SafetyError("Invalid account risk counters or gross exposure")
    if killed:
        raise SafetyError("STOP file is present")
    ny = now.astimezone(ZoneInfo("America/New_York"))
    # Conservative weekday window; holidays/early closes also fail on missing fresh quotes.
    if ny.weekday() >= 5 or not ((9, 35) <= (ny.hour, ny.minute) < (15, 55)):
        raise SafetyError("Outside conservative regular-hours window")
    if proposal.symbol not in ("SPY", "QQQ") or proposal.side not in ("BUY", "SELL"):
        raise SafetyError("Unsupported instrument or side")
    if type(proposal.quantity) is not int or proposal.quantity != 1:
        raise SafetyError("Starter strategy allows exactly one share per order")
    if not math.isfinite(proposal.limit) or proposal.limit <= 0:
        raise SafetyError("Invalid limit price")
    if config.mode == "live" and Decimal(str(proposal.limit)) != Decimal(
        str(proposal.limit)
    ).quantize(Decimal("0.01")):
        raise SafetyError("Live limit prices must match the displayed whole-cent approval price")
    if not timedelta(0) <= now - proposal.created <= timedelta(seconds=config.approval_seconds):
        raise SafetyError("Proposal expired; generate a new proposal")
    if not quote.live or not timedelta(0) <= now - quote.time <= timedelta(seconds=10):
        raise SafetyError("Fresh live quote required; delayed/frozen quotes refused")
    if not all(math.isfinite(x) and x > 0 for x in (quote.bid, quote.ask)) or quote.bid > quote.ask:
        raise SafetyError("Invalid bid/ask")
    if (quote.ask - quote.bid) / quote.bid * 10000 > config.max_spread_bps:
        raise SafetyError("Spread too wide")
    if abs(proposal.limit / (quote.ask if proposal.side == "BUY" else quote.bid) - 1) > 0.002:
        raise SafetyError("Price moved; approval must be renewed")
    if not all(
        math.isfinite(x) and abs(x) < 1e100
        for x in (state.gross_usd, state.available_usd, state.daily_pnl, *state.positions.values())
    ):
        raise SafetyError("Missing or nonfinite account risk data")
    if (
        state.open_orders
        or daily_count >= config.max_daily_orders
        or state.daily_pnl <= -config.max_daily_loss_usd
    ):
        raise SafetyError("Open orders, daily order cap or daily loss limit blocks trading")
    holding = state.positions.get(proposal.symbol, 0)
    if (
        holding < 0
        or (proposal.side == "BUY" and holding != 0)
        or (proposal.side == "SELL" and holding < 1)
    ):
        raise SafetyError("No shorting, adding to holdings, or selling unowned shares")
    value = proposal.quantity * proposal.limit
    if value > config.max_order_usd:
        raise SafetyError("Order notional exceeds limit")
    if proposal.side == "BUY" and (
        value > state.available_usd
        or (holding + 1) * proposal.limit > config.max_symbol_usd
        or state.gross_usd + value > config.max_gross_usd
    ):
        raise SafetyError("Buying power or exposure limit exceeded")
