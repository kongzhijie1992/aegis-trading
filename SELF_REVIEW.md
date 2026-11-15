# Two-pass self-review — 13 November 2026

Scope: component roadmaps, independent library boundaries, mandatory local gates,
CI candidate delivery and safety-preserving corrections. These are two explicit
reviews by the same author, not an independent external approval.

## Pass 1 — correctness, architecture and trading safety

Reviewed the proposal/approval/recheck/reservation/send path, account and port
checks, risk boundaries, data validation, simulator mutation and recovery tests.

Findings and corrections:

1. The IBKR adapter previously had approximately 31% statement/branch coverage.
   Added a fake TWS transport to test read-only connect, contract qualification,
   bid/ask callbacks and cleanup, fresh account snapshot construction, unsupported
   holdings, missing summary fields and paper limit/status/fill callbacks.
2. The simulator send method could accept a quantity other than one while applying
   a one-share fill. It now rejects such proposals before mutation; tests cover it.
3. Risk helpers silently accepted unknown side names in price rounding and did not
   explicitly reject naive timestamps/invalid counters. Added closed validation
   and regression cases without weakening any trading limit.
4. Automated tests lacked an explicit connection guard. Added socket and asyncio
   connection blocking. The first harness version also blocked Windows asyncio's
   internal socketpair; corrected it with a narrow synchronous stdlib exception,
   rather than allowing arbitrary localhost connections.
5. Style and package boundaries were descriptive only. Applied Ruff consistently,
   added exported APIs/typing markers, enforced declared dependency edges, and
   rejected cycles, reverse app imports and SDK imports outside trading-ibkr.

Pass 1 result: tests, coverage gates, dependency rules and applicable strict typing
pass. Existing paper-only checks, proposal keys and journal location are preserved.
No brokerage session or order is used by these automated checks.

## Pass 2 — packaging, security, CI behavior and completeness

Reviewed every component plan against its current API and future acceptance
criteria, then reviewed clean installations, release metadata and CI controls.

Findings and corrections:

1. Third-party wheel downloads could resolve newer transitive dependencies than
   Poetry's runtime lock. Replaced this with exact locked versions and mandatory
   hashes. Verification now rejects third-party wheels absent from the lock.
2. Old own-package wheels could survive a version bump, and the verifier hardcoded
   versions. The builder now removes only verified own-wheel paths in the output
   folder; the verifier derives expected names/versions from all source projects
   and rejects duplicates, stale/missing packages and local-path metadata.
3. Typed marker files were needed by installed consumers. All libraries now include
   py.typed, and built-wheel validation checks that the marker was packaged.
4. Wheel-installed tests previously lacked the explicit socket guard. They now run
   the same guarded runner after copying tests outside the source directory.
5. A prepared workflow could be mistaken for active CI. Documentation explicitly
   states there is no Git repository/remote here; branch protection and remote
   Linux/Python-version results remain unverified. CD produces candidates only.
6. Source export previously relied on ad hoc file lists. Added an allowlisted
   release packager, runtime/private-config rejection and SHA-256 manifest output.

Pass 2 result: all 41 tests passed both in the editable Windows/Python 3.12
workspace and from clean installed wheels. Minimal strategy installation excludes
IBKR and the application. pip check succeeds. Ruff, mypy in the stated five
libraries, workflow checks and all per-library coverage gates pass. The dependency
audit reports no known vulnerabilities. Runtime wheel hashes and all 12 own wheel
names/versions/metadata were verified. No unresolved blocker remains for this
local roadmap/tooling candidate.

## Limits retained after both reviews

- This does not certify production readiness or strategy profitability.
- Six async/integration libraries still need full strict-type migration; these
  are explicitly planned, not silently excluded from a claimed full type pass.
- GitHub Actions, branch protection, human reviews and remote matrix execution
  are not active. Only Windows/Python 3.12 was exercised locally.
- The ledger still uses floats; Decimal accounting and idempotent fill handling
  are milestones in the portfolio plan.
- Real IBKR paper-order acceptance remains blocked by unsupported account holdings
  and real-time market-data entitlements. Read-Only API should stay enabled.

Future changes must repeat both reviews and relevant retests; this document is
not a standing approval of future code or a substitute for human PR review.


## Dashboard review 1 — correctness and read-only behavior (14 November)

Added monitoring-owned snapshot/history/HTTP presentation and a separate read-only
account_view in the IBKR adapter. Checked that all broker holdings can be displayed
without calling or weakening snapshot() trading eligibility. Missing numeric fields
remain null; nonfinite sentinels are discarded. Header totals use broker base currency;
position values stay in native currency, and exposure is grouped per currency. NAV
history is scoped to account/mode/currency and explicitly is not investment return.
Found that sqlite3 context managers commit but do not close connections on Windows;
changed all dashboard database uses to explicit closing plus transaction contexts.
Added regression tests for persistence, stale preservation, host checks and callback
views. No submit/cancel/approve HTTP route exists; the collector sets writable=False.

## Dashboard review 2 — presentation, packaging and failure states (14 November)

Inspected desktop and mobile screenshots and tested real browser rendering/search,
chart, CSV download and stale refresh. Fixed a connected badge that could contradict
an aged snapshot warning. CSV escaping preserves numeric negative holdings while
neutralizing formula-leading strings. Replaced browser string-evaluation polling
with locator assertions rather than weakening CSP. Verified release source packaging
includes HTML, and installed-wheel tests read the actual packaged dashboard asset.
The HTML has no external scripts, fonts or analytics. Loopback host checking, no-store,
CSP and frame denial are tested. Demo and actual account histories use separate files.
All 45 guarded tests, per-library coverage gates, current typing/style checks and the
dependency audit pass. Browser interactions pass at 1440px and 390px. No actual account
snapshot was collected because paper TWS was not listening; live-account support and
hosted access remain outside scope. The prior bootstrap GitHub matrix passed.


Dashboard presentation follow-up: mobile screenshot inspection found a crowded
chart header and wrapping wordmark. Added wrapping gaps and a stable wordmark,
then repeated responsive browser checks. HTML/CSS/JS source now uses a pinned,
lockfile-installed Prettier tool; the mandatory quality runner enforces it and
CI audits its development dependencies. npm audit reports zero vulnerabilities.
The Python runtime still needs no Node server or external frontend assets.


## Paper-account acceptance follow-up — 14 November 2026

Review 1 (refresh correctness): a real read-only paper session exposed a timeout
when account_view re-requested the account subscription already initialized by
ib_async.connectAsync. Changed refreshes to use a bounded broker heartbeat and
the maintained account stream. Startup now raises synchronization errors rather
than presenting a partially synchronized account. Regression tests verify two
refreshes never re-subscribe and a failed heartbeat stops collection.

Review 2 (valuation and privacy): real broker account-update tags did not include
the header realized/unrealized totals. These now use the same base-currency PnL
subscription as daily PnL, with the account tags as a missing-value fallback. Tests
cover both sources. Verified actual paper data loads and refreshes, including all
three nonzero positions, base-account currency, cash and PnL. No account numbers,
balances, holdings snapshots, private config or history were added to tracked
files. The local read-only service uses a separate client ID; no orders were sent.
All 46 guarded tests and local quality/coverage gates passed after the correction.


## Signal framework review 1 — decision and label integrity (14 November)

Reviewed every frame/model/label boundary. Consolidated custom-output validation
so research and the explicit Strategy adapter reject wrong symbols/model IDs,
invalid/expired timestamps, nonfinite features/scores and invalid long/flat targets
through the same function. Verified completed-bar and future-data invariance.
Training labels reaching the test period are purged; next-completed-close entry
and horizon exit are checked against known prices, with round-trip cost subtraction.
Gapped forward intervals are excluded. Reports explicitly describe overlapping
opportunities, not portfolio P&L. No fitting or execution path was introduced.
Found and fixed a run-ID collision risk for identical prices labelled with different
symbols by including symbol and generated observations in provenance. Added tests
for those IDs and for corrupted custom outputs. All 55 guarded tests pass.

## Signal framework review 2 — reproducibility, scaling and packaging (14 November)

Changed evaluator inputs from growing historical prefixes to declared lookback
windows, avoiding quadratic prefix scans while still excluding future data. Added
Python/library versions and a CLI dataset-before/after hash check, with a regression
case that rejects changed input. Verified a minimal installed strategy wheel can
run the research CLI without IBKR or the application; full installed-wheel tests
also pass. Bumped trading-strategy to 0.2.0 and the composition app to 0.3.0 and
updated the lock and dependent constraints; existing trading defaults are unchanged.
The model is a directional feature, not calibrated confidence; costs, overlap and
holdout-reuse limitations are explicit. The adapter checks TTL at decision time,
but the existing integer-target engine does not propagate SignalRecord expiry to
submission; this is documented as a future integration requirement rather than
claiming end-to-end expiry enforcement. Both reviews found no remaining blocker
for the offline research scope. No account data or research outputs are committed.

## Local data review 1 — release ordering and ingestion integrity (15 November)

Reviewed exact decimal normalization, date/timestamp validation, period/unit
separation, raw payload retention and transactional ingestion. Fixed ambiguous
same-revision values within one batch and made batch identity include normalized
rows. A late correction to an older release previously could outrank a newer
release: preserved source release ordering separately from correction availability
and added a regression case. Verified reversion history, duplicate imports,
rollback after a partially processed batch, missing values, parameterized queries
and system-versus-source cutoffs. Current-only downloads remain unavailable to
past system queries. SEC/FRED date-only availability is explicitly a conservative
proxy; no strict intraday point-in-time claim is made.

## Local data review 2 — operations, isolation and delivery (15 November)

Reviewed provider credentials, retries, response bounds, database upgrades,
backup/restore and installed packages. Corrected the FRED CSV URL against a real
download. Collection timestamps are captured after the complete response arrives.
Schema changes run transactionally; ambiguous prototype corrections cannot migrate
silently. Added sanitized nonzero CLI failures and ignored local databases/env
files. The data wheel installs without the IBKR SDK/application; coverage discovery
now checks every library dynamically. Both source and installed suites pass all
72 tests, strict mypy covers 21 files, trading-data combined statement/branch
coverage is 99.15%, and dependency audits report no known vulnerabilities. Two
reviews found no unresolved blocker for this local ingestion scope. API vintage
pagination, automated scheduling, complete fundamental normalization and signal
feature joins remain planned. No brokerage configuration or execution code changed.

## One-second refresh review 1 — collection cadence (15 November)

Changed the collector to a one-second target measured from collection start.
Slow collections remain sequential; failure still stops collection and preserves
stale data. Broker price/account publication cadence is unchanged.

## One-second refresh review 2 — display and recovery (15 November)

Browser reads run every second, skip overlapping reads and time out after five
seconds. Reviewed cleanup in finally so failures do not prevent future refreshes.
All 72 offline tests and local quality gates pass; existing browser interaction
checks pass. Runtime-only paper configuration remains private and read-only.
Live acceptance caught repeated-heartbeat timeouts at the faster cadence. Kept
heartbeats 15 seconds apart while collecting snapshots every second, added a
regression case for heartbeat reuse/expiry and clearer timeout diagnostics, and
reran all local gates successfully. Verified 22 distinct connected paper snapshots
over approximately 24 seconds, including a subsequent heartbeat boundary.

## Paper/Real review 1 — authorization and execution boundaries (15 November)

The user explicitly authorized live execution with manual approval for each order,
superseding the initial paper-only requirement. Kept paper defaults and separate
PaperBroker/LiveBroker adapters; mode, localhost port, opt-in and exact managed
account must agree. Live sessions require an explicit CLI flag, interactive
terminal and a phrase binding LIVE/account/key/side/quantity/symbol/price. Injected
approvers and paper approvals cannot authorize live orders. Recheck broker/config
identity and mandatory risk after input; expiry, disconnect and STOP still block
submission. Found that off-cent custom prices could be rounded in the approval
prompt; rejected those live proposals and added a regression case. Uncertain
sends remain reserved and cannot be retried. Live account keys, journals and locks
are separate, preserving the existing paper journal. All order tests use fakes.

## Paper/Real review 2 — presentation, isolation and packaging (15 November)

Reviewed environment-specific snapshot routing, missing configuration, failed
connections, rapid selection and history isolation. Selecting Real clears paper
values immediately; late responses cannot replace the selected environment.
Cleared chart date labels as well as values. Missing Real configuration has an
explicit empty state and never falls back to paper data. The browser has no order
submission or approval route; selecting a view cannot start/stop a terminal trading
session. Both collectors remain read-only. Found potential dashboard/trader client
ID collisions and allocated distinct bounded IDs, with a collector regression test.
Bumped changed libraries and updated dependent versions/lock; checked independent
and full wheel installs. All 88 guarded tests, browser checks, strict typing/style,
per-library coverage gates and dependency audit pass. Risk, approval and execution
have 100% combined coverage. These reviews do not replace required human review
before merging critical execution changes. Live account configuration/login and
live-order acceptance are not verified; no live orders were submitted.
