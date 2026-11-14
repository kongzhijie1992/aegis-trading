"""Compatibility alias; implementation lives in trading-contracts."""

import sys

from trading_contracts import models as _implementation

sys.modules[__name__] = _implementation
