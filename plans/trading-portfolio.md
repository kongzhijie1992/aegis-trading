# trading-portfolio: Accurate positions and cash accounting

## Current boundary

PortfolioLedger.apply_fill/snapshot and side_for_target; currently long-only float accounting.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Migrate cash, cost basis and fills to Decimal with explicit currency rounding; add immutable fill IDs and idempotent application.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Separate cash, settled cash, realized/unrealized P&L and reservations; add persistence/replay and ledger-to-broker reconciliation.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Add FX-aware valuation and instrument-specific exposure only after separate design and risk approval; keep unsupported assets blocked meanwhile.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Duplicate/partial fills, fees, overspend, short rejection, rounding, restart replay, missing marks and accounting conservation invariants.

## Patterns and constraints

Do not replace authoritative broker holdings with virtual positions. Never net derivatives into equity share counts.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
