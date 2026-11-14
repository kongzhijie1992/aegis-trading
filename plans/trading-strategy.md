# trading-strategy: Broker-independent signal research

## Current boundary

SmaStrategy.target and signal over completed bars; configurable fast/slow windows.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Define a strategy configuration/version ID, warm-up requirements and timestamped signal object; retain the current SMA as a reference strategy.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Add a small explicit registry and parameter validation; separate research features from deployable signals and document look-ahead constraints.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Add walk-forward research hooks, benchmark comparisons and persisted experiment configurations through the simulator interface.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Future-bar exclusion, warm-up boundaries, nonfinite inputs, deterministic results, parameter changes and point-in-time feature availability.

## Patterns and constraints

No direct broker, portfolio mutation or execution imports. A positive backtest does not authorize deployment.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.

Signal research update: SignalModel/SignalRecord, registry, features, shared validation and purged offline studies are now implemented in version 0.2.0. Walk-forward fitting, statistical inference and portfolio backtesting remain planned. See SIGNAL_DEVELOPMENT.md.
