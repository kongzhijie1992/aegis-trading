# Independently installable Python libraries

The repository contains **12 separate Python distributions**, plus the small
`ibkr-paper-trader` composition application. Each library has its own
`pyproject.toml`, version, `src/` directory, README, dependencies and wheel.
They share one repository for convenient coordinated development; they do not
need separate Git repositories to be separately installable or versioned.

| Distribution | Python import | Responsibility |
|---|---|---|
| trading-data | trading_data | Local fundamental/macro ingestion, immutable revisions, as-of queries |
| trading-contracts | trading_contracts | Immutable data models, paper configuration, protocols |
| trading-marketdata | trading_marketdata | Provider-neutral access and data validation |
| trading-strategy | trading_strategy | Configurable SMA signals, no broker dependency |
| trading-portfolio | trading_portfolio | Cash/position ledger, fill accounting, target comparison |
| trading-risk | trading_risk | Price, exposure, session, loss and paper safety checks |
| trading-approval | trading_approval | Exact typed approval for one proposal |
| trading-execution | trading_execution | Rechecks, durable reservation, approved dispatch |
| trading-monitoring | trading_monitoring | SQLite audit/status journal and rotating logs |
| trading-simulation | trading_simulation | Deterministic offline fixture broker and clock |
| trading-ibkr | trading_ibkr | Explicit paper/live socket adapters; owns ib_async dependency |
| trading-engine | trading_engine | Composition and independent diagnostic checks |

The backtesting/simulation component currently supplies an execution simulator,
not a historical profitability backtester. Monitoring now supplies journal, logs and a read-only local portfolio dashboard;
see DASHBOARD.md. Market data supplies access and validation, not a
production historical-data warehouse. Those capabilities can be developed inside
their respective libraries without folding them back into the application.

## Dependency structure

```text
contracts ← marketdata, strategy, portfolio, risk, approval, ibkr
portfolio + contracts ← simulation
risk + approval + contracts ← execution
execution + marketdata + portfolio + risk + contracts ← engine
monitoring: standard-library-only audit/logging implementation
data: SQLite + provider adapters; tzdata for release-date proxies, no trading dependencies

composition app → selects libraries and wires them together
```

`ib_async` is only declared by trading-ibkr. `tzdata` is declared where Windows
timezone rules are used. There are no imports from a library back into
`paper_trader`, and no circular sibling dependencies. The offline simulation and
strategy libraries can be installed without the IBKR SDK. Protocols use structural
typing: supply your own provider, journal, clock, approval or additional risk veto.

## Development with Poetry

From the root `ibkr_paper` directory:

```powershell
poetry install
poetry run python -m unittest discover -s tests -v
poetry run paper-trader simulate
```

The root uses editable Poetry path dependencies, so editing one library updates
its behavior immediately. Existing config and the IBKR order journal remain in
the same locations. The `paper_trader.*` modules are compatibility aliases; the
implementation lives in the installed libraries, not duplicate source files.

## Import a library independently

```python
from trading_contracts import Config, Bar, Quote, Proposal, Snapshot
from trading_strategy import SmaStrategy
from trading_portfolio import PortfolioLedger

portfolio = PortfolioLedger(cash=10000)
portfolio.apply_fill("SPY", "BUY", quantity=1, price=500)
print(portfolio.snapshot({"SPY": 501}))
strategy = SmaStrategy(fast=20, slow=50)
```

Independent installation means installing a library with its declared dependencies;
it does not mean copying one directory without its dependencies.

## Build and install wheels

```powershell
python build_libraries.py
# Produces dist/wheels/<distribution>-<version>-py3-none-any.whl.

# In another Python 3.12+ virtual environment, install only signal research:
python -m pip install --no-index --find-links dist/wheels trading-strategy==0.2.0

# Or install the full application, including the local libraries:
python -m pip install --no-index --find-links dist/wheels ibkr-paper-trader==0.3.0
```

The full offline installation also needs third-party wheels (ib_async, its
dependencies, and tzdata) in the wheelhouse. The delivered wheel bundle includes
the resolved third-party wheels for this tested Windows/Python environment.
For other Python versions/platforms, obtain matching third-party wheels first.
The source project can instead use Poetry's normal dependency installation.

For an individual build, run `poetry build` in that library's folder. Its wheel
declares sibling package versions, without embedding absolute local paths.
Install sibling wheels from your private wheelhouse. These names are local;
nothing has been published to public PyPI. Don't run an unqualified public
package install expecting these exact libraries to exist there.

## Versioning and tests

Signal research brings trading-strategy to 0.2.0 and the application to 0.3.0;
other library versions remain at 0.1.0. A library can be
released independently by changing its version and updating affected sibling
constraints. Keep shared-contract changes compatible or coordinate version bumps.
This initial implementation pins sibling versions exactly to avoid silent drift.

The root `tests/` suite checks each public boundary and the cross-library pipeline.
Build validation also installs the built wheels in a clean environment, checks
package dependencies and runs the tests outside the source directory. No TWS
connection or brokerage submission is needed for these tests.

Paper/live separation, manual approval, journal keys and uncertain-order blocking
are preserved. Additional risk policies can add vetoes but cannot bypass base
checks. The existing mixed-portfolio and real-time-data blockers still prevent
the actual IBKR paper-order test; no live trading library is provided.
