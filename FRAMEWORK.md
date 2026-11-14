# Paper trading framework

The implementations now live in separate installable libraries under `libs/`.
See [LIBRARIES.md](LIBRARIES.md) for the package map and independent installation.
Earlier `paper_trader.*` module names remain as compatibility aliases.

This project now exposes one trading engine with interchangeable components.
Both local IBKR paper trading and the offline fixture simulator use the same
strategy, risk validation, approval and durable execution pipeline.

```text
Broker.bars → Strategy.target → position comparison → immutable Proposal
                                                         ↓
                                             mandatory risk checks
                                                         ↓
                                            individual manual approval
                                                         ↓
                                      refresh quote + portfolio + risk
                                                         ↓
                                         durable UNKNOWN reservation
                                                         ↓
                                             Broker.send_approved
                                                         ↓
                                       status/fills → SQLite journal
```

## Run it

Run commands from the `ibkr_paper` folder after `poetry install`:

```powershell
# Full offline workflow, no TWS connection or account required:
poetry run paper-trader simulate

# Choose SMA lookbacks; defaults remain 20 and 50:
poetry run paper-trader simulate --fast 10 --slow 30

# Read-only diagnostic report against configured paper TWS:
poetry run paper-trader check

# One paper-account evaluation pass, with manual approval per order:
poetry run paper-trader trade

# Automated tests (offline; never connect to IBKR):
poetry run python -m unittest discover -s tests -v
```

`simulate` uses fixed synthetic SPY/QQQ prices, a virtual USD 10,000 balance,
and a controlled clock at 13 November 2026, 15:00 UTC. It labels itself OFFLINE
FIXTURE and never imports the IBKR adapter. The account label DU000000 is a
fixture, not your account. Type each exact approval phrase to simulate a fill,
or any other response to decline. There is no CLI auto-approval option.

Each CLI simulation starts a fresh portfolio and separate journal under
`runtime/simulation/session-<id>.sqlite`; it never reads/writes the IBKR order
intent journal. The simulation stop file is `runtime/simulation/STOP`.
Its clock stays fixed during interactive review; tests explicitly advance the
clock to exercise expiry. Simulator fills are immediate at the synthetic bid/ask
when a limit is executable. They do not model liquidity, fees, partial fills,
market impact or realistic performance. This is a workflow test, not a backtest.

`check` now records each portfolio, history/signal and quote check independently
in `runtime/diagnostics.json`. It exits with failure if any check fails, while
preserving all available diagnostic results. Reports may contain account details.
It never calls the send method. Connection/account verification must pass first.

## Extension points

`interfaces.py` defines `Broker`, `Clock`, `Strategy`, `Approval`, and `RiskPolicy`
protocols. `TradingEngine` takes these components through its constructor:

```pythonengine = TradingEngine(
    config,
    broker,
    SmaStrategy(fast=20, slow=50),
    journal,
    clock=clock,
    approval=approval,
    risk=additional_risk,
)

results = await engine.cycle()
```

Omit the optional components for the system clock, exact typed console approval
and mandatory starter risk checks. `StarterRisk` exposes those checks as a policy
object too. An additional risk policy can veto a submission; it cannot bypass the
mandatory checks. Keep adapters and approval providers trusted local code.

- **Broker / market data:** implement connect, guard, bars, quote, snapshot,
  send_approved and close. `PaperBroker` remains locked to localhost paper ports
  and the exact configured paper account; no live broker factory exists.
- **Strategy:** provide a name and `target(bars, now)` returning integer 0 or 1.
  The engine remains restricted to SPY/QQQ and one share per approved order.
  Alternate strategies must validate data quality; the built-in SMA checks
  completed bars, ordering, positivity and freshness.
- **Approval:** implement async `request(proposal, account)` returning a boolean.
  The shipped console provider requires the exact proposal identifier every time.
  The automated tests inject fixture approvals only with the fake/offline broker.
- **Clock:** implement timezone-aware `now()`. `SystemClock` is used for IBKR;
  `SimulationClock` provides deterministic tests without weakening real risk gates.
- **Risk:** implement `validate(...)` to raise `SafetyError` on an extra veto.
  Mandatory paper/session/price/exposure/holding/expiry/stop checks always run first.

The engine exposes `proposal(symbol)`, `cycle(symbols)` and `diagnose(symbols)`.
A proposal is data, not an order. Calling `proposal` alone never submits anything.
`cycle` is deliberately one pass; there is no scheduler or unattended order loop.

## Recovery and isolation

Existing IBKR order keys and the broker journal are preserved during this
refactor. Changing lookbacks does not bypass a consumed symbol/side/bar key.
Any pending/uncertain intent blocks further submissions. Reconcile it using the
procedure in README; never delete the broker journal to reset it.

The broker, console and SQLite components are meant to run in a single local
process. CLI locks prevent concurrent runs from this folder. This framework does
not provide distributed execution, a web UI, live trading, automatic liquidation,
multi-asset risk or a historical performance engine.

## Current IBKR account acceptance status

The previous read-only test connected successfully to the configured simulated
account and retrieved historical SPY/QQQ bars. Actual paper order testing remains
blocked by unsupported portfolio holdings and missing real-time API market-data
permissions. The framework preserves these gates. Keep TWS Read-Only API enabled
until those conditions are resolved and a specific paper-order test is reviewed.
