# Engineering and CI/CD rules

## Architecture and style

- Use a ports-and-adapters design with constructor injection. Contracts are the
  dependency root; concrete broker SDK types stay inside trading-ibkr. The engine
  composes components; it does not duplicate strategy, ledger or risk logic.
- Keep signal/risk calculations pure where possible. Use immutable proposal and
  quote messages; isolate side effects in adapters, approval, journal and execution.
- Use explicit state transitions and at-most-once intent reservation. Never retry
  an ambiguous submission. Reconciliation is a separate operation, not a retry.
- Python 3.12–3.14, src layouts, explicit imports and exported public APIs. No
  sys.path hacks, application imports from libraries, or circular dependencies.
- Ruff format is authoritative: four spaces, double quotes, 100-column target.
  Ruff E4/E7/E9/F/I/B/UP rules are mandatory; no blanket noqa or ignored failures.
- New or changed public APIs require type annotations and documented failure
  semantics. Strict mypy is currently enforced for contracts, marketdata,
  strategy, portfolio and risk (11 source files). The other six async/integration
  libraries are not yet fully type-checked; their plans require incremental
  migration without Any-only stubs or blanket ignore flags.
- Time is timezone-aware UTC at boundaries. New monetary accounting uses Decimal
  and currency-specific rounding; the existing float ledger migration is planned,
  not claimed complete. Never silently infer FX rates or ignore derivatives.
- Every wait is bounded. Cancellation and resource cleanup use finally blocks.
  Inject clocks and fake transports in tests; no sleeping to simulate market time.
- Errors fail closed on submission paths. Operational logging must never include
  passwords, tokens, or full raw account responses. Sanitized fixtures only.

## Local gates

```powershell
poetry install
poetry run python scripts/quality.py
poetry run pip-audit --skip-editable --format json --output audit.json
python build_libraries.py
poetry run python scripts/download_wheels.py
python verify_wheels.py
```

The quality runner is fail-fast: lock/metadata validation, lint, format check,
strict typing in the stated packages, AST dependency rules, workflow invariants,
network-blocked tests, coverage reports and per-library thresholds. Coverage
includes branches and all eleven libraries; nothing is omitted to pass a gate.
Risk/execution require 95%, every other library 90%. The CLI and build scripts are
linted but are not included in the library coverage denominator.

Automated tests block socket connects, including local broker ports. A narrow
exception allows only the synchronous standard-library socketpair operation
required by Windows asyncio. CI uses fake TWS transports and synthetic data.
The dependency audit is separate because it intentionally contacts the advisory
service. Private editable sibling packages are excluded from public-PyPI lookup,
not from tests or package-boundary checks.

## Pull requests and two-pass review

One behavioral change per PR where practical. Include the concrete trigger,
before/after behavior, affected libraries, test evidence, migration implications
and residual risks. Review 1 checks boundary values, approval expiry, paper gates,
exposure, idempotency, partial fills, disconnects and crashes. Review 2 checks
dependency declarations, lock drift, clean wheel installation, private-data
exclusion, workflow permissions, package compatibility and recovery instructions.
Fix findings and repeat affected checks. Preserve original order keys and journals.

Before merge, require a human reviewer, resolved conversations, current branches
and the aggregate `required` CI job. Require two human approvals for changes to
risk, approval, execution or the IBKR adapter once a repository/team is configured.
Self-review cannot approve its own PR. Do not enable an administrator bypass.

## CI and delivery

`.github/workflows/ci.yml` runs on PRs, main pushes, version tags and manual
dispatch. It checks Python 3.12/3.13/3.14 on Linux and Windows, then builds wheels
and runs installed tests in clean environments. All jobs have timeouts, action
references are pinned to full SHAs, permissions are read-only, checkout does not
persist credentials, and failing/unknown audit results block success.

The `required` job runs even when an earlier job fails and checks every result;
no continue-on-error or ignored matrix failure is allowed. Artifact delivery
contains only built wheels and designated quality reports, not local runtime data.
CI never receives broker credentials or connects to TWS. This follows the relevant
[GitHub workflow security guidance](https://docs.github.com/en/actions/reference/security/secure-use)
and [Ruff configuration reference](https://docs.astral.sh/ruff/configuration/).

CD currently means a verified **release candidate artifact**, not deployment or
publishing to PyPI. Version bumps need an API/compatibility review, changelog and
updated dependent constraints. Prefer private package hosting later; add a
protected environment and explicit release approval before enabling publication.
Rollback installs a prior compatible wheel set and preserves the order database.

## Activation status

The project is now located at the root of the cloned `aegis-trading` Git repository,
with `origin` pointing to `kongzhijie1992/aegis-trading` on GitHub. The workflow is
in the correct `.github/workflows/` location. Its first remote execution, branch
protection and reviewer rules are still pending; having a remote does not prove
those controls are active. Push the reviewed bootstrap change, then require the
complete matrix and aggregate `required` check before treating CI as active.
Only Windows/Python 3.12 has been verified locally so far.
