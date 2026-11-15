# trading-ibkr

Explicit paper/live IBKR socket adapters. `PaperBroker` rejects live configurations;
`LiveBroker` requires a validated live opt-in, live port and exact live account.
Dashboard connections are read-only. Trading callers must use the mandatory
execution/approval pipeline; `send_approved` is an internal dispatch boundary for
already approved proposals. See repository `LIVE_TRADING.md` for setup and limits.

Import from `trading_ibkr`. This library has its own version and wheel. Install with sibling dependencies from the framework wheelhouse; these packages are local and have not been published to PyPI.
