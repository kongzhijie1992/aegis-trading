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
