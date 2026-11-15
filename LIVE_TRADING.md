# Paper and real accounts

The dashboard has **Paper** and **Real** account-view buttons. It starts on Paper
each time the page loads. Real views show a red REAL MONEY label; selecting one
does not submit an order, enable a writable API connection, start a strategy, or
stop/change a separate terminal trading session. Each snapshot request names its
environment. Switching clears the old positions, balances and history immediately;
late responses from the previous selection cannot replace the selected view.

The user explicitly authorized developing live execution on 15 November 2026.
This supersedes the original paper-only project scope. Paper remains the default;
the live capability has offline validation and is not a claim of production
readiness or an account-connected live-order acceptance test.

## Account setup

Keep the existing `config.local.json` for paper. Create a separate ignored file:

```powershell
Copy-Item config.live.example.json runtime/config.live.json
```

Edit that local file to contain the **exact** live account number; do not derive
it by removing letters from a paper account. This starter supports live `U` plus
digits accounts only. Leave passwords out of configuration. Review the monetary,
daily-loss, order-count and exposure limits for your account before use.

The live configuration requires `mode: live`, `live_enabled: true`, a live port
(Gateway 4001 or TWS 7496), and the exact live account. Paper requires paper ports
(4002/7497), a DU/DUR account and no live opt-in. Any mixed combination fails.
The adapter requires the managed-account list to contain exactly that one account;
additional/unexpected accounts are refused. Ports and names alone do not replace
this exact-account check.

Sign into the appropriate IBKR session yourself. For both account views to update
simultaneously, both authenticated sessions must be available at their respective
ports. One Gateway signed into paper does not also serve live data. Switching the
web view does not log Gateway in or change its trading mode. If a required session
was unavailable at dashboard start, check it and restart the dashboard deliberately;
collectors never reconnect automatically.

```powershell
poetry run paper-trader dashboard --source ibkr
```

The dashboard loads the optional `runtime/config.live.json` (override with
`--live-config PATH`). Missing live configuration displays an empty setup state;
failed live connections display their own error. It never falls back to paper
balances under a Real label. Both dashboard collectors use `writable=False`.
Dashboard clients use the configured client ID plus 1,000,000, keeping their
connections distinct from terminal trading sessions. Use small positive base
client IDs as in the examples; the derived ID must fit a signed 32-bit integer.
Leave Gateway's Read-Only API enabled when using portfolio views only.

## Trading with per-order approval

First run read-only diagnostics for the selected environment:

```powershell
poetry run paper-trader check --environment live
```

This checks data and account risk without placing an order. Current starter
restrictions remain: SPY/QQQ only, one whole share per proposal, regular-hours
window, fresh non-delayed quotes, limit orders, exposure/cash/loss/count limits,
no shorting or increasing an existing holding, no unresolved prior orders, and
rechecks after approval. Unsupported holdings can block the account risk snapshot;
the dashboard's broader display support does not relax execution restrictions.

A live session must be explicitly started from an interactive terminal:

```powershell
poetry run paper-trader trade --environment live --enable-live
```

This is a single strategy cycle, not an unattended trading service. Each eligible
proposal displays LIVE, the exact account, side, share count, symbol and limit
price, then requires the entire displayed phrase, for example:

```text
APPROVE LIVE U123 LIVE-U123-SPY-BUY-20261113T1455 BUY 1 SPY LIMIT 500.00
```

That example is illustrative, not an order instruction. Paper-style approval,
wrong account/price/key, blank input, piped input and injected automatic approvers
cannot authorize a live order. The proposal expires after the configured interval;
time, prices, risk, connection and account are rechecked after input. Decline by
entering anything other than the exact phrase, or stop with Ctrl+C. Gateway must
also permit API orders for a writable trading session; a read-only Gateway will
reject them. The application does not change that setting for you.

The browser deliberately has no order-entry or approval endpoint. The selector
chooses what you view; manual order approval happens in the selected terminal
session. Do not interpret selecting Real as approval to trade. No live orders
were submitted during implementation or automated tests.

## Separation and recovery

- Paper execution retains the existing `runtime/orders.sqlite` journal and lock,
  preserving consumed keys/unresolved orders. Paper dashboard history stays under
  `runtime/dashboard/ibkr`.
- Live execution journals and session locks live under `runtime/live/U…/` for the
  exact validated account; live proposal keys also include the account and LIVE.
  Live dashboard history is under `runtime/dashboard/live` and query-scoped by
  account, environment and currency.
- Creating `runtime/live/STOP` blocks the example live configuration's submissions;
  it does not cancel orders already at the broker. A STOP created while approval
  is pending is rechecked before dispatch.
- An uncertain submission is reserved before network dispatch and never retried.
  Reconcile broker executions and open orders before using the explicit journal
  reconciliation command, with the same environment/configuration arguments.
  Restarting or changing the dashboard selection cannot clear that reservation.
- Changing environments requires a new session and new approvals; there is no
  automatic promotion of paper approvals/orders to live. Configurations are frozen
  in memory; editing a file does not retarget an existing broker connection.

Human review of critical execution changes remains required before merge.
Hosting, multi-user authorization, encrypted secrets, disaster recovery, complete
exchange calendars and production operations are separate future milestones.

[Official IBKR API setup, ports and Read-Only behavior](https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/)
