# trading-simulation: Event-driven historical replay

## Current boundary

Deterministic fixture broker and SimulationClock; same engine/approval/risk pipeline as paper.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Define a timestamp-ordered event feed and reproducible run configuration; keep the existing synthetic fixture for fast workflow tests.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Add configurable spreads, commissions, latency, limit crossing and partial fills; prohibit current-bar fills using future high/low information.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Add out-of-sample/walk-forward reports, benchmark and cost sensitivity, dataset provenance and run hashes.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

No look-ahead, deterministic replay, fees/P&L conservation, stale data, delayed fills, out-of-order events and restart reproducibility.

## Patterns and constraints

The current simulator is not a historical backtester. Paper fills and simulated results must never be presented as live returns.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
