import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from trading_contracts import Bar, SafetyError
from trading_strategy import CloseSignal, MarketFrame, SignalRegistry, SignalStrategy, make_model
from trading_strategy.cli import demo_data, main
from trading_strategy.features import mean_reversion, momentum, trend
from trading_strategy.research import StudyConfig, evaluate, load_bars, save_study, summarize


def prices(count=100):
    start = datetime(2026, 1, 5, 14, 30, tzinfo=UTC)
    return tuple(Bar(start + timedelta(minutes=5 * i), 100 + i) for i in range(count))


class SignalTests(unittest.TestCase):
    def test_features_and_directional_models(self):
        bars = prices()
        frame = MarketFrame("SPY", bars, bars[-1].time + timedelta(minutes=5))
        for name, target in [("sma_trend", 1), ("momentum", 1), ("mean_reversion", 0)]:
            result = make_model(name, {}).evaluate(frame)
            self.assertEqual(result.target, target)
            self.assertEqual(result.bar_end, frame.as_of)
            self.assertTrue(-1 <= result.score <= 1)
            self.assertTrue(result.features)
        falling = tuple(replace(b, close=300 - b.close) for b in bars)
        self.assertEqual(
            CloseSignal(kind="mean_reversion").evaluate(replace(frame, bars=falling)).target, 1
        )
        self.assertEqual(mean_reversion([100, 100]), (0, 100, 0))
        self.assertGreater(momentum([100, 101]), 0)
        self.assertGreater(trend([100, 101, 102], 1)[0], 0)

    def test_future_and_incomplete_bars_do_not_change_signal(self):
        bars = prices()
        now = bars[-1].time + timedelta(minutes=5)
        model = CloseSignal()
        expected = model.evaluate(MarketFrame("SPY", bars, now))
        extra = (Bar(now, 1e99), Bar(now + timedelta(minutes=5), 0.001))
        actual = model.evaluate(MarketFrame("SPY", bars + extra, now))
        self.assertEqual(expected, actual)
        self.assertTrue(actual.valid_at(now))
        self.assertFalse(actual.valid_at(actual.expires_at))
        self.assertFalse(actual.valid_at(now - timedelta(seconds=1)))
        with self.assertRaises(SafetyError):
            actual.valid_at(now.replace(tzinfo=None))

    def test_frame_quality_and_parameter_rejections(self):
        bars = prices()
        now = bars[-1].time + timedelta(minutes=5)
        frame = MarketFrame("SPY", bars, now)
        cases = [
            replace(frame, symbol="../data"),
            replace(frame, as_of=now.replace(tzinfo=None)),
            replace(frame, bar_size=timedelta(0)),
            replace(frame, bars=bars[:3]),
            replace(frame, bars=tuple(reversed(bars))),
            replace(frame, as_of=now + timedelta(minutes=6)),
            replace(frame, bars=bars[:-1] + (replace(bars[-1], close=-1),)),
        ]
        for item in cases:
            with self.assertRaises(SafetyError):
                CloseSignal().evaluate(item)
        for kwargs in (
            {"kind": "unknown"},
            {"lookback": 1},
            {"fast": 0},
            {"fast": 50},
            {"ttl_seconds": 0},
            {"threshold": float("nan")},
            {"threshold": True},
        ):
            with self.assertRaises(SafetyError):
                CloseSignal(**kwargs)
        for values in ([], [1, float("inf")], [0, 1]):
            with self.assertRaises(SafetyError):
                momentum(values)
        with self.assertRaises(SafetyError):
            momentum([1e-320, 1e99])
        with self.assertRaises(SafetyError):
            trend([1, 2], 2)

    def test_registry_factory_and_explicit_strategy_adapter(self):
        model = make_model("momentum", {"lookback": 3})
        registry = SignalRegistry()
        registry.register(model)
        self.assertIs(registry.get("momentum"), model)
        self.assertEqual(registry.names(), ("momentum",))
        with self.assertRaises(SafetyError):
            registry.register(model)
        with self.assertRaises(SafetyError):
            registry.get("unknown")
        for name, params in [
            ("unknown", {}),
            ("momentum", {"mystery": 1}),
            ("momentum", {"lookback": True}),
            ("momentum", {"threshold": "1"}),
        ]:
            with self.assertRaises(SafetyError):
                make_model(name, params)
        bars = prices()
        self.assertEqual(
            SignalStrategy(model, "SPY").target(list(bars), bars[-1].time + timedelta(minutes=5)), 1
        )


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.model = CloseSignal(kind="momentum", lookback=5)

    def tearDown(self):
        self.tmp.cleanup()

    def test_alignment_purging_costs_and_no_future_features(self):
        bars = prices(100)
        config = StudyConfig(horizon=3, round_trip_bps=10)
        rows = evaluate(self.model, "SPY", bars, config)
        for row in rows:
            signal_index = (
                int((datetime.fromisoformat(row.as_of) - bars[0].time).total_seconds() / 300) - 1
            )
            if row.split == "train":
                self.assertLess(
                    datetime.fromisoformat(row.exit_time), bars[70].time + timedelta(minutes=5)
                )
            else:
                self.assertGreaterEqual(signal_index, 70)
            self.assertEqual(
                datetime.fromisoformat(row.entry_time),
                bars[signal_index + 1].time + timedelta(minutes=5),
            )
            expected = bars[signal_index + 4].close / bars[signal_index + 1].close - 1
            self.assertAlmostEqual(row.forward_return, expected)
            self.assertAlmostEqual(row.net_opportunity_return, expected - 0.001)
        changed = bars[:70] + tuple(replace(b, close=b.close * 5) for b in bars[70:])
        after = evaluate(self.model, "SPY", changed, config)
        self.assertEqual(
            tuple(r for r in rows if r.split == "train"),
            tuple(r for r in after if r.split == "train"),
        )
        self.assertEqual(rows, evaluate(self.model, "SPY", bars, config))

    def test_gap_checks_and_empty_partition_rejection(self):
        bars = prices()
        gapped = bars[:30] + tuple(replace(b, time=b.time + timedelta(hours=1)) for b in bars[30:])
        rows = evaluate(self.model, "SPY", gapped, StudyConfig())
        self.assertLess(len(rows), len(evaluate(self.model, "SPY", bars, StudyConfig())))
        with self.assertRaises(SafetyError):
            evaluate(self.model, "SPY", bars[:6], StudyConfig())
        with self.assertRaises(SafetyError):
            evaluate(self.model, "SPY", bars, StudyConfig(train_fraction=0.99))
        for kwargs in (
            {"train_fraction": 0},
            {"horizon": 0},
            {"bar_minutes": 0},
            {"round_trip_bps": -1},
            {"round_trip_bps": True},
        ):
            with self.assertRaises(SafetyError):
                StudyConfig(**kwargs).validate()
        self.assertIsNone(summarize(())["active_hit_rate"])

    def test_invalid_custom_model_is_never_accepted(self):
        base = self.model
        for change in (
            {"target": 2},
            {"score": float("nan")},
            {"symbol": "QQQ"},
            {"features": (("bad", float("inf")),)},
        ):

            class Invalid:
                name = base.name
                version = base.version
                lookback = base.lookback

                def evaluate(self, frame, change=change):
                    return replace(base.evaluate(frame), **change)

            with self.assertRaises(SafetyError):
                evaluate(Invalid(), "SPY", prices(), StudyConfig())

        class InvalidTarget:
            name = base.name
            version = base.version
            lookback = base.lookback

            def evaluate(self, frame):
                return replace(base.evaluate(frame), target=True)

        with self.assertRaises(SafetyError):
            SignalStrategy(InvalidTarget(), "SPY").target(
                list(prices()), prices()[-1].time + timedelta(minutes=5)
            )

    def test_csv_validation_and_reproducible_outputs(self):
        dataset = self.root / "data.csv"
        demo_data(dataset)
        bars = load_bars(dataset)
        self.assertEqual(len(bars), 234)
        config = StudyConfig()
        rows = evaluate(self.model, "SPY", bars, config)
        with self.assertRaises(SafetyError):
            save_study(self.root / "runs", dataset, self.model, config, (), {})
        folder = save_study(self.root / "runs", dataset, self.model, config, rows, {"lookback": 5})
        self.assertEqual(
            folder,
            save_study(self.root / "runs", dataset, self.model, config, rows, {"lookback": 5}),
        )
        report = json.loads((folder / "report.json").read_text())
        with self.assertRaises(SafetyError):
            save_study(
                self.root / "runs",
                dataset,
                self.model,
                config,
                rows,
                {},
                expected_dataset_hash="changed",
            )
        self.assertEqual(report["symbol"], "SPY")
        self.assertTrue((folder / "observations.csv").exists())
        other = evaluate(self.model, "QQQ", bars, config)
        self.assertNotEqual(
            folder,
            save_study(self.root / "runs", dataset, self.model, config, other, {"lookback": 5}),
        )
        for bad in (
            "date,close\nx,1\n",
            "time,close\n2026-01-05T00:00:00,1\n",
            "time,close\n2026-01-05T00:00:00+00:00,-1\n",
            "time,close\n2026-01-05T00:00:00+00:00,1\n2026-01-05T00:00:00+00:00,2\n",
        ):
            dataset.write_text(bad)
            with self.assertRaises(SafetyError):
                load_bars(dataset)

    def test_cli_demo_config_list_and_errors(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            main(["list"])
            main(["demo", "--output", str(self.root / "demo")])
            config = self.root / "experiment.json"
            dataset = self.root / "data.csv"
            demo_data(dataset)
            values = {
                "symbol": "SPY",
                "model": "mean_reversion",
                "data": "data.csv",
                "parameters": {"lookback": 5},
                "study": {},
            }
            config.write_text(json.dumps(values))
            main(["evaluate", "--config", str(config), "--output", str(self.root / "runs")])
            with self.assertRaises(SystemExit):
                main(["evaluate"])
            for content in ({"unknown": 1}, {"symbol": None}):
                config.write_text(json.dumps(content))
                with self.assertRaises(SafetyError):
                    main(["evaluate", "--config", str(config)])
