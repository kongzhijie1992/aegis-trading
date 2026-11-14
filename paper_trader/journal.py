"""Compatibility alias; implementation lives in trading-monitoring."""

import sys

from trading_monitoring import journal as _implementation

sys.modules[__name__] = _implementation
