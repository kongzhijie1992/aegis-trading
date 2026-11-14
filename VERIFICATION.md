# Verification â€” 13 November 2026



## Completed



- Inspected the accessible Investing project: existing research projects were

  present, but no IBKR trading project was found. Created this separate folder;

  synced `sources/` material was not changed.

- Installed the Poetry environment on Windows with Python 3.12.10,

  `ib_async` 2.1.0 and the resolved versions in `poetry.lock`.

- Passed 16 automated tests, including multiple failure cases per risk test:

  account/port rejection, read-only adapter rejection, connection fault latching,

  final kill-file check, typed approval, declines, expiry, post-approval risk

  changes, uncertain sends persisted across a second journal connection,

  duplicate prevention, SMA behavior and incomplete-bar exclusion.

- Ran the synthetic paper demo successfully. The order-execution tests use an

  in-memory fake broker; no test sends an order to IBKR.

- Compiled all application modules and checked Poetry metadata/lock consistency.

- Probed `127.0.0.1:7497` and `127.0.0.1:4002`; neither was reachable. See

  `connection-check.json` for the timestamp and raw socket results.



**No account-connected paper order or live order was submitted.** A real paper

account acceptance test remains pending a signed-in paper TWS/Gateway session

and the exact DU account configuration. No credentials are embedded.



## Account-connected acceptance steps



1. Follow `README.md`; verify the paper banner and exact DU account in TWS/Gateway.

2. With Read-Only API enabled, run `poetry run paper-trader check`. Confirm fresh

   account data, live quotes and completed-bar signals for SPY and QQQ.

3. Enable writes only in that paper session. Run `poetry run paper-trader trade`.

   If a proposal appears, first decline it; verify no order appears in TWS.

4. Run again. Review one one-share limit proposal and type its exact approval.

   Check account, instrument, side, price, DAY validity and order reference in TWS.

   A fill is not guaranteed. Compare statuses/fills with the local journal.

5. If it remains open, cancel it in paper TWS; verify any partial fills and

   manually reconcile its final journal state if needed.

6. Restart: the consumed signal key must be skipped, and unresolved orders must

   block submissions. Preserve the journal throughout this test.



Disconnect and uncertain-send behavior was tested with a fake broker. Do not

disconnect during an actual submission merely to induce uncertainty; use the

automated tests. The design never retries uncertain orders automatically.



This starter is an execution/safety demonstration, not evidence that the strategy

is profitable or a production trading platform.



## Local TWS setup update



TWS was installed and its signed-in window explicitly showed Simulated Trading. Its account uses the DUR prefix. The format gate was corrected to accept DU/DUR followed by digits, while keeping exact configured account matching and all live-port rejections. All 16 tests passed after this change, including added malformed-prefix cases. A private local config was created and excluded from the archive. API settings showed socket port 7497 and Read-Only API enabled, but Enable ActiveX and Socket Clients was unchecked. The read-only account connection remains pending the user enabling that local API setting.



## Successful read-only account connection — 13 November 2026



Connected to local paper TWS on port 7497, client 71, server version 178. Exact configured paper account match passed. Fresh positions were retrieved; the trading snapshot correctly refused a GBP ETF holding and a short option. No holdings were changed and no orders were submitted. Independent market-data diagnostics retrieved 234 five-minute regular-session historical bars for each of SPY and QQQ. The latest bar started 12 November at 20:55 UTC. At the test time (13 November, about 11:55 UTC), these bars were correctly rejected as stale for trading. Real-time SPY and QQQ requests received IBKR error 354 (market data not subscribed; delayed data available); the quote gate timed out without using delayed prices. The private diagnostic report is in runtime/connection-report.json. Real paper order acceptance remains blocked by unsupported existing holdings and unavailable real-time API data. Keep Read-Only API enabled.



## Framework extension verification — 13 November 2026



Added broker/strategy/clock/approval/risk interfaces and a shared TradingEngine used by the IBKR CLI and deterministic offline simulator. Added parameterized SMA windows, separate simulation journals, mandatory base risk plus optional extra vetoes, and independent diagnostics. All 26 automated tests passed, Poetry strict validation passed, and modules compiled. CLI simulation smoke tests covered two declines (unchanged virtual cash/positions) and two exact fixture approvals (one SPY and one QQQ synthetic fill; virtual cash USD 9,100). These CLI smoke tests used synthetic data without importing or connecting the IBKR adapter. No new brokerage orders were submitted. Existing account connection/data restrictions remain unresolved.



## Independent library packaging verification — 13 November 2026



Split the implementation into 11 Python distributions with src layouts, individual pyproject.toml files, README files, exact sibling version dependencies and separate wheels. Root application version is 0.2.0; libraries start at 0.1.0. The original module paths now alias library implementations so existing imports, journal keys and test patch targets remain compatible. Added portfolio fill accounting and provider-neutral data validation. All 31 tests passed in the editable Poetry environment. Built 12 own wheels (11 libraries plus app); inspected their metadata for local file dependencies. In a clean virtual environment installed only trading-strategy plus trading-contracts and verified that neither ib_async nor paper_trader was installed. In a second clean environment installed all wheels offline, passed pip check, confirmed imports came from installed wheel locations rather than the project, and passed all 31 tests outside the source tree. Bundled the resolved third-party Windows/Python 3.12 wheels separately for offline installation. No broker connection or order submission was performed during this packaging change.


## Component plans and CI gates — 13 November 2026

Added one three-milestone plan for each of 11 libraries, engineering/architecture rules, pinned GitHub Actions candidate workflow and explicit remote activation limits. Local quality gates include lock check, Ruff, strict mypy for five core libraries, dependency graph rules, workflow security invariants, guarded tests, and at least 90% statement/branch coverage for every library (95% required for risk/execution). All 41 tests passed; risk and execution reached 100%, adapter 94.19%, engine 90%. pip-audit reported no known vulnerabilities. Rebuilt wheels passed hash/version/metadata/typing-marker verification and clean installed tests. Two separate self-review passes and their fixes are recorded in SELF_REVIEW.md. Remote CI was not run because no Git repository/remote is configured.
