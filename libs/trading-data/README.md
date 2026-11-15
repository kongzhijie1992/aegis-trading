# trading-data

Independent SQLite fundamentals/macro store. Public API: `DataStore`,
`Observation`, `DataError`; CLI: `aegis-data`. No broker dependencies.

Install this distribution with Python 3.12–3.14, then run:

```powershell
aegis-data init
aegis-data demo --db runtime/data/demo.sqlite
aegis-data inventory --db runtime/data/demo.sqlite
```

Values are exact decimal strings or null; revisions append history. As-of queries
default to information both available and ingested by the cutoff. SEC and ALFRED
date-only releases use documented conservative date-end proxies, not exact times.
Current FRED snapshots cannot reconstruct historical vintages. SQLite backups
use `aegis-data backup --output NEW_FILE`. See repository `DATA_PLATFORM.md` for
provider configuration, imports, limitations and examples.
