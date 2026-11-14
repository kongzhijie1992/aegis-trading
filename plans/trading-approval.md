# trading-approval: Durable individual order review

## Current boundary

ConsoleApproval.request with exact proposal ID; async input keeps broker events flowing.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Bind decisions to a canonical immutable proposal hash including account, side, size, price, expiry and strategy version.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Persist approval/rejection/expiry records and invalidate decisions on changes or reconnection; add clock-injected timeout behavior.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Add an optional local review interface through the same provider port, with no bulk or default approval.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Wrong ID, changed price/quantity/account, rejection, expiry during review, disconnect, replayed token and input cancellation.

## Patterns and constraints

No unattended approvals in production adapters. Test approval fixtures must not be selectable by the trading CLI.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
