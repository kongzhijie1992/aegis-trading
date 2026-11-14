"""Long-only virtual cash ledger and target-to-order comparison."""

import math
from collections.abc import Mapping

from trading_contracts import SafetyError, Snapshot


def side_for_target(target: int, holding: float) -> str | None:
    if type(target) is not int or target not in (0, 1):
        raise SafetyError("Target must be integer 0 or 1")
    if not math.isfinite(holding) or holding < 0:
        raise SafetyError("Long-only holdings required")
    if target == 1 and holding == 0:
        return "BUY"
    if target == 0 and holding >= 1:
        return "SELL"
    return None


class PortfolioLedger:
    def __init__(self, cash: float = 10000) -> None:
        if not math.isfinite(cash) or cash < 0:
            raise SafetyError("Invalid initial cash")
        self.cash = cash
        self.positions: dict[str, float] = {}

    def apply_fill(self, symbol: str, side: str, quantity: int, price: float) -> None:
        if type(quantity) is not int or quantity <= 0 or not math.isfinite(price) or price <= 0:
            raise SafetyError("Invalid fill")
        holding = self.positions.get(symbol, 0)
        value = quantity * price
        if side == "BUY" and value <= self.cash:
            self.positions[symbol] = holding + quantity
            self.cash -= value
        elif side == "SELL" and quantity <= holding:
            self.positions[symbol] = holding - quantity
            self.cash += value
        else:
            raise SafetyError("Fill would overspend cash or short a position")

    def snapshot(self, marks: Mapping[str, float]) -> Snapshot:
        if any(
            s not in marks or not math.isfinite(marks[s]) or marks[s] <= 0 for s in self.positions
        ):
            raise SafetyError("A valid mark is required for each holding")
        gross = sum(marks[s] * q for s, q in self.positions.items())
        return Snapshot(dict(self.positions), gross, self.cash, 0, 0)
