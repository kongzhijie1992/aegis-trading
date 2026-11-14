# trading-contracts: Shared models and schema compatibility

## Current boundary

Config, Bar, Quote, Proposal, Snapshot; Clock/Broker/Strategy/Approval/RiskPolicy protocols.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Add validated identifiers, explicit currency/asset types and schema versions; reject naive timestamps and invalid counters at message construction.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Introduce serializable order/fill/reconciliation messages with backward-compatible readers and golden round-trip fixtures.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Freeze a documented public API and add compatibility tests against previous released contract wheels.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Malformed IDs, nonfinite prices, timezone transitions, schema upgrades and immutable message behavior.

## Patterns and constraints

Avoid making this package a collection of business logic. Breaking contracts require coordinated major versions.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
