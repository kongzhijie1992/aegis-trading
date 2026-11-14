"""Compatibility alias; implementation lives in trading-simulation."""

import sys

from trading_simulation import broker as _implementation

sys.modules[__name__] = _implementation
