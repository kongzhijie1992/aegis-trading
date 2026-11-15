# Component development plan

Every component remains a separately versioned library. Work is sequenced by
dependency and acceptance evidence, rather than an arbitrary completion date.
The current code is a tested starter, not a production-ready trading platform.

| Order | Component | Next deliverable | Detailed plan |
|---|---|---|---|
| 1 | Contracts | Validated versioned messages and stable API | [Plan](plans/trading-contracts.md) |
| 2 | Market data | Reproducible local datasets and provider adapters | [Plan](plans/trading-marketdata.md) |
| 3 | Strategy | Strategy registry and deterministic research signals | [Plan](plans/trading-strategy.md) |
| 4 | Portfolio | Decimal ledger and idempotent fills | [Plan](plans/trading-portfolio.md) |
| 5 | Risk | Explainable decisions and complete position exposure | [Plan](plans/trading-risk.md) |
| 6 | Approval | Durable, expiring proposal-specific decisions | [Plan](plans/trading-approval.md) |
| 7 | Execution | Explicit order state machine and reconciliation | [Plan](plans/trading-execution.md) |
| 8 | Simulation | Historical event replay with realistic fill assumptions | [Plan](plans/trading-simulation.md) |
| 9 | Monitoring | Read-only operational reports and structured events | [Plan](plans/trading-monitoring.md) |
| 10 | IBKR | Fully typed adapter and controlled paper acceptance | [Plan](plans/trading-ibkr.md) |
| 11 | Engine | Typed composition and bounded scheduling | [Plan](plans/trading-engine.md) |
| 12 | Data | Local fundamentals/macro database and revision-safe ingestion | [Plan](plans/trading-data.md) |

Monitoring and simulated adapter tests are developed alongside each stage.
The numbered order describes dependencies, not twelve isolated waterfall projects.

For **each deliverable**: write an API/design note and failure cases; implement
one small change; add meaningful tests; run every applicable CI gate; perform
review 1 (correctness and trading safety); fix findings; perform review 2
(packaging, dependencies, security and operational failure); rerun affected gates.
Record evidence and unresolved limitations. Two self-reviews do not replace an
independent human review before merging critical execution changes.

Current gates and release rules are in [CONTRIBUTING.md](CONTRIBUTING.md).
Current review evidence is in [SELF_REVIEW.md](SELF_REVIEW.md). Plans describe
future work explicitly; a checked CI workflow is not evidence it has run remotely.

## Definition of done for a component milestone

- Its specified behavior and failure outcomes are demonstrated with tests.
- Public API, dependencies and version constraints are reviewed and documented.
- Formatter, linter, package boundaries and the applicable strict type checks pass.
- Combined statement/branch coverage is at least 90% for that library; risk and
  execution must reach 95%. A high percentage never replaces safety scenario tests.
- Built wheels install outside this source tree with declared dependencies only.
- Audit reports no known vulnerabilities; an unavailable audit service fails CI.
- No real broker session, password, account config or runtime history enters CI.
- Both reviews and relevant retests are recorded, with no unresolved release blockers.

## Scope constraints

No live-order capability, unattended approval, automatic liquidation, public
package publishing or external deployment is introduced by this plan. Existing
IBKR holdings/data restrictions remain effective. Historical backtest results
will be labeled research and require costs, data provenance, point-in-time
universes and out-of-sample validation before influencing paper-trading decisions.
