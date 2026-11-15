# Aegis Trading

Fundamental and macro database: [DATA_PLATFORM.md](DATA_PLATFORM.md). Inspect local
data with `poetry run aegis-data inventory`; ingestion and backups are separate
from the broker and order-approval process.

Signal development: [SIGNAL_DEVELOPMENT.md](SIGNAL_DEVELOPMENT.md). Try the offline
workflow with `poetry run aegis-signals demo --output runtime/signals/demo`.

Portfolio dashboard: [DASHBOARD.md](DASHBOARD.md). Run
`poetry run paper-trader dashboard --source demo` for a local preview, or
`--source ibkr --config config.local.json` for the read-only paper account.

A modular Python trading platform, starting with manually approved IBKR paper
trading. Research, market data, portfolio accounting, risk and execution are
independent libraries in one repository. Live trading and hosted deployment are
future milestones; current execution remains paper-only.

Development roadmap: [COMPONENT_PLANS.md](COMPONENT_PLANS.md).
Mandatory engineering gates: [CONTRIBUTING.md](CONTRIBUTING.md).
Two-pass review record: [SELF_REVIEW.md](SELF_REVIEW.md).



The components are now **12 independently installable Python libraries** under

`libs/`, each with its own project metadata and wheel. Start with

[LIBRARIES.md](LIBRARIES.md) for imports, dependencies, builds and installation.

The root package is the composition app; legacy module paths remain compatible.



See [FRAMEWORK.md](FRAMEWORK.md) for the reusable engine, extension interfaces,

full offline simulator and independent diagnostic checks.



```powershell

poetry run paper-trader simulate

```



Semi-automated research starter. **No live mode exists.** Every submitted order

requires its own exact typed approval. The default `check` command is read-only.

The demo is synthetic, not an account-connected paper trade or a backtest.



## Quick start



Open PowerShell in this project folder:



```powershell

poetry config virtualenvs.in-project true --local

poetry install

poetry run python -m unittest discover -s tests -v

poetry run paper-trader demo

Copy-Item config.example.json config.local.json

notepad config.local.json

```



Requires Python 3.12–3.14 and Poetry 2.x. Set `account` to your exact **paper DU/DUR

account number**, not your username. Never store an IBKR password here. The

example account is deliberately invalid. `config.local.json` is ignored by git.

Use a dedicated, USD-base paper account with only long USD stock/ETF holdings.

Other account types, non-USD holdings, shorts and derivatives fail closed.



## Configure TWS or IB Gateway on Windows



1. Install current stable TWS or IB Gateway from IBKR. Select **Paper Trading**

   when signing in. Verify the simulated/paper banner and DU account in the app.

2. In TWS, open **File → Global Configuration → API → Settings**. In Gateway,

   open its API settings. Enable **ActiveX and Socket Clients** where shown.

3. Set the paper socket port to **7497 for TWS** or **4002 for Gateway**, matching

   `config.local.json`. This program refuses every other port, including the

   live defaults 7496/4001. Leave localhost-only access enabled; do not expose

   the port to the network. Accept the local connection prompt if shown.

4. Initially leave **Read-Only API** enabled. Use client ID 71 exclusively for

   this program. Turn off other API clients during testing; concurrent manual

   trading can change account state between a snapshot and an order.

5. Enable paper market-data sharing/subscriptions as appropriate in IBKR. The

   program requires fresh **live** bid/ask data, even in the paper account. It

   refuses delayed or frozen quotes and will not guess missing prices or P&L.

6. Keep TWS/Gateway running and logged in. No password automation is included.



Run during a US regular trading session, after 09:35 and before 15:55 New York:



```powershell

poetry run paper-trader check

```



This verifies the exact account, fresh positions/risk data, live quotes and

completed five-minute historical bars for SPY and QQQ. It cannot submit orders.

Outside session hours stale bars/quotes can cause it to fail, as intended.



After a successful check, verify the paper banner again and disable **Read-Only

API in the paper session only**, then run:



```powershell

poetry run paper-trader trade

```



The program evaluates SPY then QQQ once and exits. There is no unattended loop.

If there is no change needed, it prints `hold`. A proposal prints the account,

symbol, side, quantity, exact limit, DAY validity, and a unique approval phrase.

Type that complete phrase to approve **that order only**; any other input declines.

Approval expires after 30 seconds by default. Risk, account and connection checks

run again after approval. Changing prices can require a new proposal/run.



Orders are one-share, SMART-routed USD stock/ETF **DAY limit orders**, restricted

to regular hours. A limit order can remain unfilled. The app observes statuses

for up to 60 seconds, then exits; inspect any remaining order in TWS. It never

assumes a submitted order filled and never resends a timed-out order.



## Strategy and limits



The strategy compares the 20-bar and 50-bar simple moving averages of completed

five-minute regular-hours TRADES bars. Fast > slow gives a one-share long target;

otherwise target is zero. This is a regime signal, not necessarily a new crossover.

An incomplete last bar is excluded. Insufficient, stale, invalid or unordered data

blocks a proposal. A flat account may therefore get an immediate buy proposal

when started in an existing bullish regime. Existing positions above one share

are not increased; bearish exits reduce them by one share per approved run.



Defaults: $1,500 maximum order, $3,000 maximum symbol exposure, $5,000 maximum

gross account position value, four attempted orders per New York date, $100

account daily-loss cutoff, 20-basis-point maximum spread, 10-second quote age,

and a 0.2% maximum drift from the approved price. Daily P&L is IBKR's account

daily P&L, whose reset schedule is broker-defined. Failed/uncertain sends count

toward the order cap. These are conservative starter values, not a sizing model.



Any open account order blocks new submissions. Risk gates also apply to exits;

if the loss cutoff blocks an exit, manage the paper position manually in TWS.

The loss cutoff **does not place a stop-loss or automatically liquidate holdings**.

This demonstration is not validated for profitability. Fees, slippage, paper-fill

limitations, exchange calendars and production execution require further research.

The time gate is weekday/time based, not an exchange holiday calendar; closed

markets also fail on missing fresh data. It excludes the first and last five minutes.



## Stop, disconnect and recover



```powershell

New-Item runtime\STOP -ItemType File -Force

poetry run paper-trader journal

```



`STOP` blocks new orders, including after approval. It does **not cancel existing

orders**. Cancel those manually in paper TWS; there is no global-cancel feature.

Ctrl+C exits the program, also without cancelling already submitted orders.



Connection loss, farm-disconnect messages and reconnection events latch a fault.

There is no automatic reconnect/resubmission. Restart only after checking paper

TWS open orders **and executions**, including possible partial fills. Pending,

inactive or uncertain journal entries block further trading across restarts.



The SQLite journal records an `UNKNOWN` intent durably **before** sending an

order. An uncertain send remains blocked even if the process crashes. Its unique

key prevents replaying the same symbol/side/bar signal. Preserve this journal:

deleting it removes duplicate prevention and the daily attempt count.



After manually verifying an order's final disposition in paper TWS, record it:



```powershell

poetry run paper-trader reconcile --key SPY-BUY-20261113T1455 --status Filled

```



Use the actual journal key and verified terminal status (`Filled`, `Cancelled`,

or `Rejected`). A partially filled order must have its remaining quantity

cancelled/otherwise resolved in TWS before marking it `Cancelled`. This command

records your attestation; it does not query the broker or cancel anything. The

original key stays consumed and still counts toward its original day's limit.



`runtime/session.lock` prevents concurrent local runs from this folder. After a

crash, first ensure no process is running and reconcile TWS, then remove that

specific stale lock. After resolving the reason for a stop, remove `runtime/STOP`.

Always run from this project folder so all runs share the same journal and lock.



Logs: `runtime/app.log` rotates; `runtime/orders.sqlite` stores proposals, approvals

through send records, broker errors, order statuses, fills and reconciliation.

Logs may contain account/order details; keep them private. SQLite can be inspected

with standard SQLite tools. Do not edit it to bypass safety gates.



## Components



- `core.py`: immutable configuration, bars, quotes, proposals and snapshots.

- `market_data.py`: replaceable provider interface; `broker.py` implements TWS data.

- `strategy.py`: pure 20/50 signal, independent of IBKR.

- `risk.py`: pure validation of prices, exposure, session, loss and position rules.

- `execution.py`: manual approval, final checks, durable reservation and dispatch.

- `broker.py`: pinned `ib_async` 2.1.0 socket adapter, account gate and event handling.

- `journal.py`: SQLite audit trail and persistent duplicate/uncertainty protection.

- `cli.py`: read-only check, one-pass trade, demo and manual reconciliation.



`ib_async` is a third-party maintained TWS protocol implementation; it does not

require installing `ibapi`. It is not an IBKR-supported library. The dependency

lock file pins the resolved environment; review updates before upgrading.

Port numbers alone do not prove paper mode: the exact DU/DUR-account match and refusal

of mixed-account sessions are additional safeguards. This is application-level

protection, not a sandbox for arbitrarily modified code or a misconfigured broker.



## References



- [IBKR Windows API installation](https://www.interactivebrokers.com/docs/tws-api/doc/install-the-tws-api-on-windows)

- [IBKR TWS API configuration](https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/)

- [IBKR paper connection and default port](https://www.interactivebrokers.com/support/faq/content/29950139)

- [IBKR connectivity message codes](https://interactivebrokers.github.io/tws-api/message_codes.html)

- [ib_async source and usage](https://github.com/ib-api-reloaded/ib_async)



## Verification in this workspace



See `VERIFICATION.md` for the checks actually performed and the remaining

account-connected acceptance steps. No live orders are permitted or tested.



Local setup update: a signed-in TWS window confirmed a DUR-format account in Simulated Trading. The account format gate now accepts DU or DUR followed by digits; exact broker-account matching remains mandatory.

