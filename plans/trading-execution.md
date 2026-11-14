# trading-execution: Explicit order lifecycle and reconciliation

## Current boundary

Execution.execute performs approval, fresh checks and durable reservation before dispatch.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Specify a state machine for proposed/approved/reserved/submitted/partial/terminal/unknown and reject illegal transitions.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Add bounded status reconciliation using broker order/execution IDs; preserve at-most-once intent semantics and classify unknown sends.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Add explicit user-approved cancel/replace flows with atomic reservations; no automatic resend after ambiguous failures.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Crash before/after network send, duplicate keys, partial fills, rejection, cancellation races, reconnect and persistent unresolved states.

## Patterns and constraints

No exactly-once guarantee across network failures. UNKNOWN always blocks until reconciled; do not delete history to recover.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 95% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
