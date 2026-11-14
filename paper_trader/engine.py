"""Compatibility alias; implementation lives in trading-engine."""

import sys

from trading_engine import engine as _implementation

sys.modules[__name__] = _implementation
