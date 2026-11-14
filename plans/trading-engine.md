# trading-engine: Composition and bounded orchestration

## Current boundary

TradingEngine.proposal/cycle/diagnose; accepts injected broker, data, strategy, clock and approval.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Complete strict typing and a typed composition configuration; validate dependencies and deterministic startup/shutdown before scheduling.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Add an explicitly bounded paper-only evaluation scheduler, backpressure and cancellation; each order still requires separate approval.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Add persisted run metadata and recovery coordination, keeping policy decisions in their owning libraries.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Independent diagnostics, no-signal holds, duplicates, unresolved order stops, signal freshness during preparation and graceful shutdown.

## Patterns and constraints

No broker-specific SDK logic, automatic approval or hidden live path. The engine must not weaken component safety policies.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
