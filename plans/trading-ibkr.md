# trading-ibkr: Paper-only broker integration

## Current boundary

PaperBroker owns ib_async, exact account/port guard, bounded data requests and status callbacks.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Complete strict type annotations through a typed SDK facade and expand transport-fake timeout/cancellation tests.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Add explicit connection readiness and reconciliation before new proposals; classify pacing/entitlement failures without retrying orders.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Run a documented, manually approved paper acceptance scenario only after holdings and real-time entitlement blockers are resolved.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Wrong/live/mixed accounts, writable/read-only gates, callbacks, partial fills, request cleanup, farm faults, timeouts and unknown sends.

## Patterns and constraints

Paper port and account prefix are application safeguards, not cryptographic proof of broker mode. Never add a live factory or credentials to CI.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
