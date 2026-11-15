"""Data provenance, revisions and failure atomicity, without network access."""

import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from trading_data import DataError, DataStore, Observation
from trading_data.cli import entrypoint, main
from trading_data.client import PublicDataClient
from trading_data.models import number, timestamp
from trading_data.providers import (
    fred_current_csv,
    fred_vintages,
    mapping,
    records_csv,
    sec_facts,
    sequence,
    text,
)

T0 = datetime(2025, 2, 1, tzinfo=UTC)
T1 = T0 + timedelta(days=1)
T2 = T1 + timedelta(days=1)


def observation(**kwargs):
    return replace(
        Observation("test", "US", "GDP", "USD", "2024-12-31", T0, "v1", "1.20"), **kwargs
    )


def sec_payload():
    return json.dumps(
        {
            "cik": 320193,
            "facts": {
                "us-gaap": {
                    "Revenue": {
                        "units": {
                            "USD": [
                                {
                                    "end": "2024-12-31",
                                    "start": "2024-01-01",
                                    "filed": "2025-01-31",
                                    "accn": "a1",
                                    "val": 10000000000001,
                                }
                            ]
                        }
                    }
                }
            },
        }
    ).encode()


def fred_payload():
    return json.dumps(
        {
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "output_type": 1,
            "count": 2,
            "observations": [
                {
                    "date": "2024-12-01",
                    "realtime_start": "2025-01-01",
                    "realtime_end": "2025-02-01",
                    "value": "3.10",
                },
                {
                    "date": "2024-12-01",
                    "realtime_start": "2025-02-02",
                    "realtime_end": "9999-12-31",
                    "value": ".",
                },
            ],
        }
    ).encode()


class DataTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)
        self.store = DataStore(self.path / "data.sqlite")

    def query(self, at=T2, **kwargs):
        return self.store.as_of(
            source="test", entity="US", metric="GDP", unit="USD", cutoff=at, **kwargs
        )

    def test_exact_values_and_validation(self):
        for value, expected in [
            ("100000000000000000000.0001", "100000000000000000000.0001"),
            (Decimal("1.20"), "1.2"),
            (1.5, "1.5"),
            (0, "0"),
            ("-0.00", "0"),
            (None, None),
            (".", None),
            ("", None),
        ]:
            self.assertEqual(number(value), expected)
        for value in [True, {}, "abc", "NaN", "Infinity", "1e999"]:
            with self.assertRaises(DataError):
                number(value)
        with self.assertRaises(DataError):
            timestamp(datetime(2025, 1, 1))
        for row in [
            observation(unit=""),
            observation(period_start="2025-01-01"),
            observation(available_at=datetime(2025, 1, 1)),
        ]:
            with self.assertRaises(DataError):
                row.validate()

    def test_first_seen_vs_source_history_and_revision(self):
        rows = [observation(), observation(revision="v2", value="2.2", available_at=T1)]
        result = self.store.ingest("test", "gdp", b"raw", rows, T2)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(self.query(T1), [])
        self.assertEqual(self.query(T0, knowledge="source")[0]["value"], "1.2")
        self.assertEqual(self.query(T2)[0]["value"], "2.2")
        self.assertEqual(self.query(T0 - timedelta(seconds=1), knowledge="source"), [])
        self.assertEqual(self.store.inventory()[0]["revisions"], 2)
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT body FROM payloads").fetchone()[0], b"raw")

    def test_replay_correction_and_reversion(self):
        initial = self.store.ingest("test", "gdp", b"a", [observation()], T0)
        replay = self.store.ingest("test", "gdp", b"a", [observation()], T0)
        self.assertTrue(replay["replayed"])
        self.assertEqual(initial["batch_id"], replay["batch_id"])
        self.assertEqual(self.store.ingest("test", "gdp", b"a", [observation()], T1)["inserted"], 0)
        self.store.ingest("test", "gdp", b"b", [observation(value="2")], T1)
        self.assertEqual(self.query(T0, knowledge="source")[0]["value"], "1.2")
        self.assertEqual(self.query(T1)[0]["value"], "2")
        self.assertEqual(self.query(T1)[0]["basis"], "same_revision_correction_first_seen")
        self.store.ingest("test", "gdp", b"a", [observation()], T2)
        self.assertEqual(self.query(T2)[0]["value"], "1.2")
        self.assertEqual(self.store.inventory()[0]["revisions"], 3)

    def test_atomic_rollback_and_ambiguous_batch(self):
        self.store.ingest("test", "gdp", b"a", [observation()], T2)
        with self.assertRaises(DataError):
            self.store.ingest(
                "test", "gdp", b"b", [observation(metric="CPI"), observation(value="2")], T1
            )
        self.assertEqual(len(self.store.inventory()), 1)
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM batches").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM payloads").fetchone()[0], 1)
        for rows in [[observation(), observation(value="3")], [observation(source="other")]]:
            with self.assertRaises(DataError):
                self.store.ingest("test", "gdp", b"b", rows, T2)
        with self.assertRaises(DataError):
            self.store.ingest("", "gdp", b"", [], T0)
        with self.assertRaises(DataError):
            self.query(knowledge="invalid")

    def test_old_revision_correction_does_not_replace_newer_release(self):
        self.store.ingest("test", "gdp", b"first", [observation()], T0)
        self.store.ingest(
            "test", "gdp", b"next", [observation(revision="v2", value="5", available_at=T1)], T1
        )
        self.store.ingest("test", "gdp", b"old-fix", [observation(value="2")], T2)
        self.assertEqual(self.query(T2)[0]["value"], "5")
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 3)

    def test_schema_migration_and_unsafe_legacy_correction_refusal(self):
        legacy = self.path / "legacy.sqlite"
        with contextlib.closing(sqlite3.connect(legacy)) as db:
            db.executescript(
                "CREATE TABLE observations(id INTEGER PRIMARY KEY,source TEXT,entity TEXT,metric TEXT,unit TEXT,period_start TEXT,period_end TEXT,revision TEXT,value TEXT,available_at TEXT,ingested_at TEXT,basis TEXT,event_key TEXT,batch_id TEXT); PRAGMA user_version=1;"
            )
        migrated = DataStore(legacy)
        with migrated.connection() as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 2)
        unsafe = self.path / "unsafe.sqlite"
        with contextlib.closing(sqlite3.connect(unsafe)) as db:
            db.executescript(
                "CREATE TABLE observations(basis TEXT); INSERT INTO observations VALUES('same_revision_correction_first_seen'); PRAGMA user_version=1;"
            )
        with self.assertRaisesRegex(DataError, "reimport"):
            DataStore(unsafe)

    def test_units_periods_missing_and_sql_parameters(self):
        self.store.ingest(
            "test",
            "gdp",
            b"a",
            [
                observation(value=None),
                observation(period_start="2024-01-01", value="7"),
                observation(unit="EUR", value="99"),
            ],
            T0,
        )
        self.assertEqual({r["value"] for r in self.query()}, {None, "7"})
        self.assertEqual(
            self.store.as_of(
                source="test' OR 1=1 --", entity="US", metric="GDP", unit="USD", cutoff=T2
            ),
            [],
        )

    def test_backup_reopen_and_unknown_schema(self):
        self.store.ingest("test", "gdp", b"a", [observation()], T0)
        backup = self.path / "backup" / "data.sqlite"
        self.store.backup(backup)
        self.assertEqual(DataStore(backup).inventory(), self.store.inventory())
        for target in [backup, self.store.path]:
            with self.assertRaises(DataError):
                self.store.backup(target)
        with contextlib.closing(sqlite3.connect(backup)) as db:
            db.execute("PRAGMA user_version=99")
        with self.assertRaises(DataError):
            DataStore(backup)

    def test_provider_normalization(self):
        sec = sec_facts(sec_payload())[0]
        sec.validate()
        self.assertEqual(sec.entity, "CIK0000320193")
        self.assertEqual(sec.available_at, datetime(2025, 2, 1, 5, tzinfo=UTC))
        self.assertEqual(sec.value, "10000000000001")
        self.assertEqual(sec.period_start, "2024-01-01")
        vintages = fred_vintages(fred_payload(), "GDP", "USD")
        self.assertEqual(vintages[0].value, "3.1")
        self.assertIsNone(vintages[1].value)
        self.assertEqual(vintages[0].available_at, datetime(2025, 1, 2, 6, tzinfo=UTC))
        current = fred_current_csv(
            b"observation_date,DGS10\n2020-01-01,1.20\n2020-01-02,.\n", "DGS10", "percent", T2
        )
        self.assertEqual(current[0].available_at, T2)
        self.assertIsNone(current[1].value)
        self.assertEqual(
            fred_current_csv(b"DATE,GDP\n2020-01-01,4\n", "GDP", "USD", T0)[0].value, "4"
        )

    def test_provider_rejects_invalid_structures(self):
        for function, arg in [
            (mapping, []),
            (mapping, {1: 2}),
            (sequence, {}),
            (text, None),
            (text, ""),
        ]:
            with self.assertRaises(DataError):
                function(arg)
        for raw in [
            b'{"cik":"bad","facts":{}}',
            sec_payload().replace(b'"val": 10000000000001', b'"wrong": 1'),
        ]:
            with self.assertRaises(DataError):
                sec_facts(raw)
        with self.assertRaises(DataError):
            fred_vintages(b"{}", "GDP", "USD")
        with self.assertRaises(DataError):
            fred_current_csv(b"DATE,OTHER\n2020-01-01,1\n", "GDP", "USD", T0)
        with self.assertRaises(DataError):
            records_csv(b"wrong\n1\n", "test")

    def test_canonical_csv(self):
        payload = b"entity,metric,unit,period_end,available_at,revision,value,period_start,basis\nUS,GDP,USD,2024-12-31,2025-02-01T00:00:00Z,v1,1.20,,\n"
        row = records_csv(payload, "test")[0]
        self.assertEqual(row.value, "1.2")
        self.assertEqual(row.basis, "imported_availability")
        self.store.ingest("test", "csv", payload, [row], T0)
        self.assertEqual(self.query(T0)[0]["value"], "1.2")
        with self.assertRaisesRegex(DataError, "canonical"):
            observation(period_end="20241231").validate()

    def test_entrypoint_sanitized_failure(self):
        with (
            patch("sys.argv", ["aegis-data", "inventory", "--db", str(self.store.path)]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            entrypoint()
        with (
            patch("trading_data.cli.main", side_effect=DataError("Provider connection failed")),
            contextlib.redirect_stderr(io.StringIO()) as output,
            self.assertRaises(SystemExit) as caught,
        ):
            entrypoint()
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("Provider connection failed", output.getvalue())

    def command(self, *args):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main([*args, "--db", str(self.store.path)])
        return output.getvalue()

    def test_cli_database_demo_queries_backup(self):
        self.assertIn("ready", self.command("init"))
        self.assertIn("SYNTHETIC", self.command("demo"))
        self.assertIn("revenue", self.command("inventory"))
        self.assertIn(
            "1000000",
            self.command(
                "asof",
                "--source",
                "demo",
                "--entity",
                "DEMO-CO",
                "--metric",
                "revenue",
                "--unit",
                "USD",
                "--at",
                "2099-01-01T00:00:00Z",
            ),
        )
        self.command("backup", "--output", str(self.path / "copy.sqlite"))

    def test_cli_imports_and_fetches(self):
        file = self.path / "input"
        file.write_bytes(sec_payload())
        self.command("import-sec", "--file", str(file))
        file.write_bytes(fred_payload())
        self.command(
            "import-fred", "--file", str(file), "--vintages", "--series", "GDP", "--unit", "USD"
        )
        file.write_bytes(b"DATE,GDP\n2020-01-01,3\n")
        self.command("import-fred", "--file", str(file), "--series", "GDP", "--unit", "USD")
        file.write_bytes(
            b"entity,metric,unit,period_end,available_at,revision,value\nUS,CPI,index,2020-01-01,2020-02-01T00:00:00Z,v1,2\n"
        )
        self.command("import-csv", "--file", str(file), "--source", "test")
        with (
            patch.object(PublicDataClient, "sec", return_value=sec_payload()),
            patch.object(PublicDataClient, "fred", return_value=b"DATE,GDP\n2020-01-01,3\n"),
        ):
            self.command("fetch-sec", "--cik", "320193")
            self.command("fetch-fred", "--series", "GDP", "--unit", "USD")

    def test_cli_missing_required_inputs(self):
        for args in [
            ("backup",),
            ("asof",),
            ("import-sec",),
            ("fetch-sec",),
            ("fetch-fred",),
            ("import-fred", "--file", str(self.store.path)),
        ]:
            with (
                self.subTest(args=args),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                self.command(*args)
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(DataError):
            self.command("fetch-fred", "--series", "GDP", "--unit", "USD", "--vintages")


class ClientTests(unittest.TestCase):
    def test_fetches_and_credentials(self):
        client = PublicDataClient()
        with patch.object(client, "read", return_value=fred_payload()) as read:
            client.fred("GDP")
            self.assertIn("graph.csv", read.call_args.args[0])
            client.fred("GDP", "a" * 32)
            self.assertIn("realtime_start=1776", read.call_args.args[0])
            client.sec("320193", "Aegis contact@example.com")
            self.assertIn("CIK0000320193.json", read.call_args.args[0])
        for function, args in [
            (client.sec, ("bad", "a@b")),
            (client.sec, ("123", "missing")),
            (client.sec, ("123", "a@b\r\nx")),
            (client.fred, ("a/b",)),
            (client.fred, ("GDP", "bad")),
        ]:
            with self.assertRaises(DataError):
                function(*args)
        with (
            patch.object(client, "read", return_value=b'{"count":3,"observations":[]}'),
            self.assertRaises(DataError),
        ):
            client.fred("GDP", "a" * 32)

    @patch("trading_data.client.time.sleep")
    @patch("trading_data.client.urlopen")
    def test_network_bounds_retry_and_secret_redaction(self, open_url, sleep):
        client = PublicDataClient()
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"ok"
        retry = HTTPError("https://secret", 429, "secret", {}, None)
        open_url.side_effect = [retry, response]
        self.assertEqual(client.read("https://example.com"), b"ok")
        self.assertEqual(open_url.call_count, 2)
        self.assertEqual(open_url.call_args.kwargs["timeout"], 30)
        for error in [
            HTTPError("secret", 403, "secret", {}, None),
            URLError("secret"),
            TimeoutError("secret"),
        ]:
            open_url.side_effect = error
            with self.assertRaises(DataError) as caught:
                client.read("https://example.com?api_key=secret")
            self.assertNotIn("secret", str(caught.exception))
        open_url.side_effect = retry
        with self.assertRaises(DataError):
            client.read("https://example.com")
        response.__enter__.return_value.read.return_value = b"x" * (64 * 1024 * 1024 + 1)
        open_url.side_effect = None
        open_url.return_value = response
        with self.assertRaisesRegex(DataError, "64 MiB"):
            client.read("https://example.com")
