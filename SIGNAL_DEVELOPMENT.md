# Aegis signal development framework

This offline workflow lives in `trading-strategy` 0.2.0 and installs without IBKR.
It does not connect to a broker, fit an optimizer or submit an order. The existing
paper-trading defaults remain unchanged.

## Quick start

From the repository root:

```powershell
poetry install
poetry run aegis-signals list
poetry run aegis-signals demo --output runtime/signals/demo
```

The demo creates 234 fictional five-minute SPY closes across three regular-session
days and evaluates a fixed momentum model. It is a workflow example, not market
data or evidence of profitability.

For your own data, prepare one CSV per instrument. `time` is the bar **start**,
in timezone-aware ISO format. Closes must be positive and finite:

```csv
time,close
2026-01-05T14:30:00+00:00,500.10
2026-01-05T14:35:00+00:00,500.30
```

Those two rows describe the format only; a study needs sufficient warm-up,
forward labels and both chronological partitions. Store datasets under ignored
`runtime/signals/`. Record vendor, retrieval time, adjustments, sessions and known
gaps alongside the data. The reader does not infer calendars or corporate actions.

Create `runtime/signals/experiment.json`:

```json
{
  "symbol": "SPY",
  "model": "sma_trend",
  "data": "SPY-5m.csv",
  "parameters": {
    "lookback": 50,
    "fast": 20,
    "threshold": 0.001,
    "ttl_seconds": 30
  },
  "study": {
    "train_fraction": 0.7,
    "horizon": 3,
    "round_trip_bps": 10,
    "bar_minutes": 5
  }
}
```

Relative data paths resolve beside the experiment file:

```powershell
poetry run aegis-signals evaluate --config runtime/signals/experiment.json --output runtime/signals/runs
```

Round-trip basis points represent the combined entry/exit cost assumption, not
per-side costs. Fix the configuration before inspecting the held-out test set.
Unknown experiment or model parameters are rejected.

## Architecture and contracts

```text
CSV / market-data library
          ↓
MarketFrame(symbol, completed closes, as_of, bar_size)
          ↓
Reusable features → SignalModel.evaluate(frame)
          ↓
SignalRecord + shared validation
          ├── offline forward-return study → reproducible artifacts
          └── explicit SignalStrategy adapter → existing risk/approval pipeline
```

- `MarketFrame.completed(lookback)` excludes incomplete/future bars and rejects
  insufficient, stale, unordered, naive-timestamp or invalid data.
- `SignalModel` declares read-only name, version and lookback properties, plus
  `evaluate(frame) -> SignalRecord`. Evaluation supplies only the declared window.
- `SignalRecord` holds symbol, model/version, as-of time, completed-bar end, expiry,
  directional score, long/flat target, features and an explanation. Scores are
  bounded to [-1, 1]; they are not calibrated confidence or probabilities.
- `SignalRegistry` registers explicit trusted instances and rejects duplicate or
  unknown names. JSON configuration never loads arbitrary Python code.
- `SignalStrategy` is an optional adapter to the existing engine protocol. It
  shares output validation with research. It is never installed into trading
  automatically by a study or by a positive result.
- `trading_strategy.features` contains reusable pure calculations. The signal
  library has no broker or execution dependency.

The current engine Strategy interface returns an integer target. The adapter
validates signal TTL at decision time; it does not carry SignalRecord expiry
through to final execution. The engine's existing proposal/approval expiry is
independent. End-to-end signal-expiry propagation must be designed and tested
before relying on a custom TTL for paper execution. This framework is research-first.

| Built-in model | Feature | Long target when | Threshold units |
|---|---|---|---|
| sma_trend | fast mean / slow mean − 1 | feature > threshold | Fractional price spread |
| momentum | last close / first lookback close − 1 | feature > threshold | Fractional return |
| mean_reversion | (mean − last close) / population standard deviation | feature > threshold | Standard deviations |

Mean reversion returns zero on a constant window. N lookback closes span N−1
intervals for momentum. `fast` is used only by sma_trend. Scores use tanh of the
feature. Target 0 means flat, not short. Sizing and risk remain separate components.

## Development workflow for every new signal

1. **Write a research card.** State a falsifiable economic mechanism, instrument
   universe, timeframe, information available at decision time, expected horizon,
   benchmark, cost assumptions and failure conditions before testing.
2. **Implement pure features.** Declare the lookback and missing-input policy.
   Validate data; never read account state or observations after the decision.
3. **Implement SignalModel.** Return an immutable record with finite features,
   an explicit version, correct timestamps and a meaningful explanation.
4. **Register explicitly.** Call `registry.register(MyModel(...))` in research
   code. The shipped JSON factory only constructs the three built-ins; exposing
   your own model there requires a reviewed factory extension.
5. **Test invariants.** Changing future data must not change earlier signals.
   Include warm-up, constants, gaps, stale data, thresholds and invalid outputs.
6. **Evaluate chronologically.** Choose parameters using training data, freeze
   them, then inspect the untouched test partition. Repeated selection on test
   results turns that partition into training; acquire another holdout afterward.
7. **Stress the result.** Vary costs, dates, regimes, symbols and small parameter
   choices. Compare flat/long baselines and preserve failed experiments. Do not
   hide multiple-testing exposure by reporting only the best configuration.
8. **Review twice.** First check data/label alignment and signal correctness;
   then reproducibility, costs, dependencies, packaging and operational failure.
9. **Propose paper integration separately.** Any adapter still passes mandatory
   paper account, risk, expiry and individual approval gates. Research results
   never authorize submission or turn on an execution loop.

Example use of the registry:

```python
from trading_strategy import CloseSignal, SignalRegistry

registry = SignalRegistry()
model = CloseSignal(kind="momentum", lookback=20, threshold=0.002)
registry.register(model)
# Implement SignalModel and construct SignalRecord for a custom model.
# Version custom code separately; built-in source hashes do not include it.
```

## Evaluation semantics and limits

At completed decision bar i, the model gets only observations through i. Entry
is conservatively measured at the **next completed bar's close (i+1)**. Exit is
the close at i+1+horizon. Future closes are used only for return labels. This
close-only assumption is not an order-fill model. A horizon of 3 with five-minute
bars means a 15-minute hold following one completed-bar entry delay.

Training observations whose labels reach the chronological test boundary are
purged. Test features may use earlier training-period prices because those would
have been available then. Labels crossing an overnight/missing-bar/time gap are
excluded; feature lookback can span earlier sessions. There is no calendar or
automatic adjustment pipeline.

Reports show counts, active counts, unconditional mean forward return, mean net
return among active opportunities and active net-positive hit rate. Flat targets
have zero opportunity return. Samples can overlap: **do not compound their
returns or interpret them as portfolio P&L**. There is no automatic deployment
flag, annualization, Sharpe, drawdown, capacity estimate or significance claim.
Realistic fills, walk-forward fitting, multiple-test correction and portfolio
backtesting remain separate work in the planned simulation component.

## Saved artifacts

Each content-derived run folder contains:

- `report.json`: symbol, model/version, parameters, settings, Python/library
  versions, dataset hash, built-in source hash, observation hash and split summaries.
- `observations.csv`: symbol/time, train/test assignment, score, target, label
  entry/exit times, forward/net opportunity returns, features, reason and expiry.
  Expiry describes operational validity; it is distinct from the label horizon.

The CLI compares the dataset hash before evaluation and export, rejecting a
changed file. The export API also accepts `expected_dataset_hash` for this check.
Run IDs include symbol and generated records, avoiding collisions when identical
closes are studied under different symbols. Built-in source hashes cover signals,
features and evaluation; custom code must have its own explicit version. Exact
floating-point results are reproducible within the same environment; equality
across different Python/platform versions is not assumed.

All output stays under ignored local runtime directories. No signal research
artifacts or account data are automatically uploaded.

## Quality and package gates

```powershell
npm ci --ignore-scripts
poetry run python scripts/quality.py
```

The full signal library is strict-mypy checked. Tests cover future-bar invariance,
shared output validation, purged partitions, label alignment, costs, invalid data,
gaps, reproducible artifacts and CLI behavior. Its wheel must remain independently
installable without IBKR or the application. Automated research cannot send orders.
