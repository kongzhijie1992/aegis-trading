"""Compatibility alias; implementation lives in trading-approval."""

import sys

from trading_approval import console as _implementation

sys.modules[__name__] = _implementation
