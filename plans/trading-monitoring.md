# trading-monitoring: Durable audit and operational visibility

## Current boundary

SQLite Journal, bounded rotating application logs, and a read-only local portfolio dashboard with snapshot history.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Define versioned structured events with correlation/proposal/order IDs, redaction and schema-migration tests.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Add read-only health, unresolved-order and risk-decision reports; test log retention and database backup/recovery.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Extend the implemented read-only dashboard with optional metrics and structured event drill-down, without introducing trading mutations into reporting.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Restart durability, concurrent event writes, disk-full behavior, corrupt/missing database, redaction and migration rollback.

## Patterns and constraints

Audit-write failure must block submissions. Do not upload runtime logs or credentials in CI artifacts.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
