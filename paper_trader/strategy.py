"""Compatibility alias; implementation lives in trading-strategy."""

import sys

from trading_strategy import sma as _implementation

sys.modules[__name__] = _implementation
