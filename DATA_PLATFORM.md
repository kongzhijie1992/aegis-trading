# Local fundamentals and macro database

`trading-data` is an independently installable Python library. SQLite is the
local storage engine; no database server, brokerage connection or subscription
change is needed. The library has no trading or order-execution dependency.
The default database is `runtime/data/aegis.sqlite`, excluded from Git and releases.

## Start on Windows

Open PowerShell in the repository and run:

```powershell
poetry install
poetry run aegis-data init
poetry run aegis-data fetch-fred --series DGS10 --unit percent
poetry run aegis-data fetch-fred --series UNRATE --unit percent
poetry run aegis-data fetch-fred --series CPIAUCSL --unit index_1982_84_100
poetry run aegis-data fetch-fred --series GDP --unit billion_USD_SAAR
poetry run aegis-data fetch-fred --series FEDFUNDS --unit percent
poetry run aegis-data inventory
```

These commands import current FRED CSV snapshots. Historical observation dates
do **not** establish when those values became available. All current-snapshot
values are initially available from collection time, including old observations.
Units are explicit labels supplied by the caller; check them against the series
page before adding a series. No conversion or unit inference occurs.

For a separate, clearly synthetic fundamentals/macro example:

```powershell
poetry run aegis-data demo --db runtime/data/demo.sqlite
poetry run aegis-data inventory --db runtime/data/demo.sqlite
```

## Company fundamentals: SEC company facts

Use the company's numeric CIK, not a ticker guess. SEC downloads require an
identifying User-Agent containing your application/organization and public
contact email. Set `SEC_USER_AGENT` in your local PowerShell session to your real
contact string; do not commit it or paste credentials into this chat.

```powershell
poetry run aegis-data fetch-sec --cik 320193
```

This example requests Apple company facts. Entity IDs become `CIK0000320193`;
metrics keep their taxonomy, such as `us-gaap.Assets`. Each fact retains its unit,
period start/end and accession revision. The full original JSON is retained,
including form, fiscal-year/period and frame metadata. Those additional fields
are not yet separate query columns. Noncustom taxonomy and entity-wide SEC facts
are not a complete fundamentals product: custom tags, segment reconciliation,
ratios, quarterly-versus-YTD derivation, ticker history and delisted universes
remain future work. Never sum different durations or units blindly.

Already downloaded JSON can be imported without another network request:

```powershell
poetry run aegis-data import-sec --file C:\data\companyfacts.json
```

## Macro revision history: FRED/ALFRED

For historical vintages, set `FRED_API_KEY` locally, then use:

```powershell
poetry run aegis-data fetch-fred --series UNRATE --unit percent --vintages
```

The adapter requests the full real-time window with `output_type=1`. A truncated
response fails before ingestion; automatic pagination beyond 100,000 observations
is not implemented yet. API keys stay out of arguments, receipts and stored
metadata. Public CSV downloads need no API key but provide current values only.
Vintage JSON imports must carry the same full-window/output-type metadata:

```powershell
poetry run aegis-data import-fred --file C:\data\unrate-vintages.json --series UNRATE --unit percent --vintages
```

## Query what was known at a decision time

```python
from datetime import datetime, UTC
from trading_data import DataStore

store = DataStore("runtime/data/aegis.sqlite")
rows = store.as_of(
    source="fred-current",
    entity="US",
    metric="UNRATE",
    unit="percent",
    cutoff=datetime.now(UTC),
)
```

`knowledge="system"` is the default: both release availability and local ingestion
must precede the cutoff. It represents what this database actually knew then;
newly downloaded historical data cannot appear in past system snapshots.

`knowledge="source"` reconstructs using the provider's release-date evidence,
without the local ingestion constraint. SEC filed dates are conservatively usable
after the entire New York filing day; ALFRED vintage dates after the entire Chicago
day. These are date-end proxies, **not verified intraday publication timestamps**.
Do not claim strict intraday point-in-time accuracy from them. ALFRED validity-end
dates remain in raw JSON; queries return the latest eligible recorded vintage and
do not implement explicit withdrawal/expiry semantics.

```powershell
poetry run aegis-data asof --source fred-vintage --entity US --metric UNRATE --unit percent --at 2025-01-15T16:00:00Z --knowledge source
```

The returned `value` is an exact decimal string or null. Convert strings to
`Decimal` for calculations. `source_available_at` preserves the original release
proxy; `available_at` also guards corrections discovered later. Corrections to an
older revision cannot displace a newer release just because they were collected
later. Each distinct start/end period remains separate. SQL values are bound
parameters. Callers must explicitly choose entity, source, metric and unit.

Integrating a macro/fundamental feature into a signal should inject this store at
the feature-building boundary and query **each signal's decision timestamp**.
The current bar-only signal examples do not consume database features yet.
Do not read today's inventory and join its latest values onto historical bars.

## Other providers through a canonical CSV

Required header:

```csv
entity,metric,unit,period_end,available_at,revision,value
```

Optional columns: `period_start`, `basis`. Dates use `YYYY-MM-DD`; availability
must include an explicit timezone. Missing values use an empty field or `.`.
The caller is responsible for truthful availability evidence and licensing.

```powershell
poetry run aegis-data import-csv --file C:\data\fundamentals.csv --source my-provider
```

## Storage and operations

| Table | Purpose |
|---|---|
| `payloads` | SHA-256 addressed original response bytes, without request credentials |
| `batches` | Durable receipt: source, dataset, raw hash, collection time, inserted count |
| `observations` | Immutable values, units, periods, revisions and availability evidence |

Each ingestion is one transaction. Invalid rows, mixed sources, ambiguous values
within one revision, or an out-of-order correction roll back the entire batch.
Identical rows are not duplicated; same-revision changes and later reversions
append history. Empty provider datasets produce an auditable zero-row receipt.
Receipts are printed as JSON. Network failures print a sanitized error and return
a nonzero exit code; no partial payload or successful receipt is committed.
HTTP 429 and selected 5xx responses get at most three attempts. Reads are paced,
have a 30-second socket timeout and a 64 MiB response limit. Connection failures
leave the existing database intact. No unattended scheduler is installed.

SQLite uses WAL, foreign keys, full synchronization and a 10-second busy timeout.
Use one ingestion writer on a local disk; this is not a shared/network-drive or
multi-host service. No encryption-at-rest is provided. Back up using the online
backup command, rather than copying an active `.sqlite` file without its WAL:

```powershell
poetry run aegis-data backup --output runtime/backups/data-2026-11-15.sqlite
poetry run aegis-data inventory --db runtime/backups/data-2026-11-15.sqlite
```

Backup requires a new destination and never overwrites an existing file. Schema
version 2 is enforced; unknown versions fail closed. The prototype version-1
schema can migrate when it contains no same-revision corrections; otherwise
reimport original payloads into a new database, because original release ordering
cannot safely be recovered from that prototype. Never downgrade a database in
place. Retain backups and source payloads before future schema upgrades.

The wheel installs without the IBKR SDK or the composition application. CI checks
typing, dependencies, format, offline tests and at least 90% combined statement/
branch coverage for this library, including clean installed-wheel tests.

## Next milestones

1. Versioned dataset/metric catalog, provider unit/frequency validation and release calendars.
2. Resumable pagination, scheduled ingestion, freshness reports and failed-run logging.
3. Fundamental period normalization and timestamp-safe signal feature joins.
4. Dataset exports/manifests and broader provider adapters, with explicit entitlements.
5. PostgreSQL adapter, migrations, access control and hosted backups when multiple
   workers or hosted deployment justify a database server. Keep provider and query
   contracts separate from that storage choice.

## Official references

- [SEC EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC automated access/User-Agent guidance](https://www.sec.gov/about/webmaster-frequently-asked-questions)
- [FRED observations and output types](https://fred.stlouisfed.org/docs/api/fred/series_observations.html)
- [FRED real-time periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html)
- [FRED API keys](https://fred.stlouisfed.org/docs/api/api_key.html)
