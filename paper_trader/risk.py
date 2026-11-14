"""Compatibility alias; implementation lives in trading-risk."""

import sys

from trading_risk import policy as _implementation

sys.modules[__name__] = _implementation
