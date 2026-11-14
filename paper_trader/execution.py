"""Compatibility alias; implementation lives in trading-execution."""

import sys

from trading_execution import service as _implementation

sys.modules[__name__] = _implementation
