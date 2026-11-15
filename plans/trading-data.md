# trading-data development plan

## Responsibility and boundary

Own local fundamental/macro ingestion, original payload retention, revision
history, explicit units and availability-aware queries. Independently installable;
no broker SDK, trading, approval or execution imports. Providers normalize immutable
observations; the store owns transactions; the CLI composes the two.

## First milestone

SQLite schema, raw payload hashes, receipts, revision-aware SEC/FRED adapters,
canonical CSV, as-of system/source queries and online backups. Preserve decimal
values exactly. Reject malformed/mixed batches and ambiguous same-revision values.
Never backdate current snapshots to observation dates. Date-only release evidence
uses conservative documented proxies. Keep synthetic examples in a separate DB.

Acceptance: offline cases demonstrate revision ordering, corrections and reversion,
no future-data leakage, idempotence, exact precision, rollback, schema refusal,
backup reopen and network error redaction. All strict style/type/boundary gates,
90% per-library statement/branch coverage, clean independent wheel installation
and supported Windows/Linux Python matrix must pass. Two reviews are recorded.

## Follow-up milestones

1. Catalog and quality reports: units, frequency, seasonality, staleness, expected
   coverage and corporate identity mappings. Acceptance: wrong units/frequencies
   fail validation and missing periods appear explicitly in reports.
2. Production ingestion: pagination, checkpoints, release schedules, failed-run
   journal, retry budgets and provider quotas. Acceptance: interrupted downloads
   resume without duplication and incomplete pages cannot be marked complete.
3. Research integration: timestamp-safe fundamental/macro feature joins, explicit
   YTD/quarter transformations, real vintage datasets and provenance manifests.
   Acceptance: changing future observations cannot change earlier features.
4. Hosting: PostgreSQL adapter/migrations only when multiple writers or hosted
   workloads require it. Add access controls, encrypted backups and restore drills.

## Limitations

No exact historical intraday publication timestamps, full security master,
quarterly fundamentals normalization, scheduler or automatic signal integration
is claimed. API credentials/contact configuration and provider access remain local.
See [DATA_PLATFORM.md](../DATA_PLATFORM.md) for runnable commands and failure rules.
