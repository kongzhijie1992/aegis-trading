"""Compatibility alias; implementation lives in trading-ibkr."""

import sys

from trading_ibkr import broker as _implementation

sys.modules[__name__] = _implementation
