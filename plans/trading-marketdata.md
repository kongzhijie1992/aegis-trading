# trading-marketdata: Reproducible market data

## Current boundary

MarketData protocol and ValidatedMarketData wrapper; provider is injected.

The current starter is implemented; the milestones below are planned work, not completed features.

## Milestone 1 — strengthen the boundary

Define bar-end semantics, exchange sessions and data-quality metadata; add CSV/Parquet dataset reader with provenance and explicit adjustment flags.

Acceptance: publish a reviewed API/design note; demonstrate the boundary and malformed-input failures in tests; preserve current behavior or document a versioned migration.

## Milestone 2 — add the main capability

Add a local durable store with deduplication, gap detection, request pacing and bounded retries for read-only requests.

Acceptance: deterministic integration fixtures demonstrate normal, failed and interrupted paths without contacting a broker. Dependencies must pass the AST boundary checker.

## Milestone 3 — operational readiness

Add provider contract tests and delayed/live classifications; keep order paths unable to consume delayed quotes silently.

Acceptance: install the candidate wheel outside the source tree, demonstrate recovery/compatibility, document residual limits, and complete both reviews before release.

## Required scenario tests

Missing bars, duplicates, corporate-action adjustments, early closes, DST, stale quotes, provider timeouts and reproducible dataset hashes.

## Patterns and constraints

Data licenses and entitlement failures must be surfaced. Do not infer fresh prices from cached timestamps.

Use the ports/adapters, constructor injection, explicit errors and style rules in [CONTRIBUTING.md](../CONTRIBUTING.md). Add typed public APIs; migrate remaining untyped code rather than hiding errors with Any or ignore rules.

## Delivery gate

Run the complete quality and installed-wheel suites. The library must meet at least 90% combined statement/branch coverage, pass the applicable strict type checks, and have no unresolved correctness/safety review finding. Review dependency constraints and semantic versioning before releasing only the affected distribution and its compatible dependents. Never publish private data or introduce live trading.
