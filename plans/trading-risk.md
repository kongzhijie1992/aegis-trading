# trading-risk: Explainable mandatory risk controls

## Current boundary

check, limit_price and StarterRisk; optional policies only add vetoes.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Return structured allow/deny reasons with named rules while preserving fail-closed behavior; centralize session calendars and configuration validation.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Add full-account exposure and pending-order reservations from typed portfolio snapshots, plus broker-defined daily-P&L reset metadata.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Add bounded sizing policies and stress scenarios only after dedicated tests; unsupported instrument/currency handling must remain explicit.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Exact limit boundaries, negative/nonfinite inputs, expiry, holidays/early closes, daily loss, total exposure and concurrent pending intents.

## Patterns and constraints

Risk extensions cannot override mandatory checks. Loss cutoff is not a stop order or automatic liquidation.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 95% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
