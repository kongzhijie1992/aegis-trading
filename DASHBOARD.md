# Aegis portfolio dashboard

The dashboard is part of trading-monitoring, with a small composition entry point
in the application. It is read-only and binds only to 127.0.0.1. No order creation,
cancellation, approval or account-changing HTTP route exists.

## Start a demo

```powershell
poetry install
poetry run paper-trader dashboard --source demo
```

Open http://127.0.0.1:8765. The banner explicitly labels the fictional demo account.
The sample historical curve is synthetic. It is never mixed with paper-account
data. Stop with Ctrl+C before switching sources on the same port.

## Show your IBKR paper account

Copy config.example.json to config.local.json and set the exact verified paper
account number. Keep the API port at 7497 (TWS) or 4002 (Gateway), enable socket
clients, and keep Read-Only API enabled in the paper session. Then:

```powershell
poetry run paper-trader dashboard --source ibkr --config config.local.json
```

You can instead pass the absolute path of your existing private config. Do not
commit that file. The dashboard client is constructed with writable=False and
the same exact paper-account/port checks as the rest of Aegis. It can display
stocks, options, shorts and non-USD holdings; this display path does not call or
weaken the trading-risk eligibility checks. The existing trading snapshot still
rejects unsupported assets. No extra market-data subscription is requested here.

## What it shows

- Net liquidation value, cash, broker daily P&L and unrealized/realized P&L.
- Account value history collected locally, scoped to account, mode and currency.
- Searchable positions, including option expiry/strike/right and native currency.
- Quantity, broker market price/value, broker average cost and position P&L.
- Open orders, quantities, filled amount, type and status.
- A read-only positions CSV export; missing values remain empty.
- Connection and snapshot timestamps, with stale/disconnected warnings.

Account collection runs every 15 seconds, browser refresh every 10 seconds. Missing
or unavailable broker values show a dash; there is no fabricated price fallback.
Broker marks may be delayed, frozen, or from the last session. Values are display
information, not execution quotes. Option average cost follows the broker's
contract convention and may differ from the per-unit quote convention.

Equity history begins when you start collecting. Account-value changes include
deposits/withdrawals and are **not** cash-flow-adjusted investment returns. There
is no invented return series, annualized return, Sharpe or historical drawdown.
For full historical performance, a later import of statements/cash flows is needed.
Daily P&L uses the broker's reset schedule, not an assumed UK midnight.

Position values/P&L retain each instrument's currency. Exposure is grouped by
currency, never summed across currencies without FX. Header totals are broker
base-account totals. Short positions stay negative in the table; exposure uses
absolute market value and is not delta-adjusted derivatives risk.

## Storage and failure behavior

Private SQLite history is in runtime/dashboard/demo or runtime/dashboard/ibkr.
It is ignored by Git and excluded from release archives. Restarting with the same
account preserves the recorded history; switching accounts or currencies selects
a separate series. Demo data uses separate storage and an explicit DEMO account.

If collection fails after startup, the last successful snapshot stays visible
with a stale/disconnected status. There is no automatic broker reconnect or order
retry. Restart deliberately after checking paper TWS. Authentication and connection
errors during startup stop the server. Keep this application local; internet
hosting needs a separate authentication/TLS/access-control design.

## Validation

```powershell
poetry run python scripts/quality.py
poetry run playwright install chromium
poetry run python scripts/check_dashboard_ui.py
```

Transport-fake tests cover the paper account view without real connections.
Dashboard tests cover persistence, account/mode/currency isolation, invalid numbers,
host rejection, read-only routes and stale-state preservation. Browser checks cover
chart rendering, search, CSV download, mobile layout and disconnect behavior.
Dashboard screenshots are fictional fixtures and may be uploaded as CI artifacts;
actual account screenshots/history must not be uploaded.
