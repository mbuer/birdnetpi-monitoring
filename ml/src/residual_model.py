"""Retrospective residual RF comparison. No stored predictions are written."""

import argparse
from importlib.metadata import version
from pathlib import Path
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from timing import FEATURES, latest_completed_hour, prepare_hourly_frame


ACTIVITY_FEATURES = [
    "activity_index", "activity_lag_1h", "activity_lag_2h",
    "activity_lag_3h", "activity_lag_24h",
]
WEATHER_FEATURES = [
    "temperature_f", "humidity_pct", "wind_mph", "cloud_pct",
    "precipitation_in",
]
MODELS = [
    "Persistence", "Solar climatology", "RF full",
    "Residual RF", "Residual RF + weather",
]
MIN_BIN_ROWS = 3


def build_dataset(raw, cutoff):
    frame = prepare_hourly_frame(raw)
    frame = frame.loc[frame.index <= cutoff].copy()
    numeric = [column for column in dict.fromkeys(FEATURES + WEATHER_FEATURES)
               if not column.startswith("activity_lag_")]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame[numeric] = frame[numeric].replace([np.inf, -np.inf], np.nan)
    # Shifts precede filtering, so a missing hour remains a missing hour.
    for lag in (1, 2, 3, 24):
        frame[f"activity_lag_{lag}h"] = frame["activity_index"].shift(lag)
    frame["recent_complete"] = (
        frame["activity_index"].notna().rolling(25, min_periods=25).sum() == 25
    )
    frame["target_activity"] = frame["activity_index"].shift(-2)
    frame["target_hour"] = frame.index + pd.Timedelta(hours=2)
    # Outcome metadata is used only for retrospective subgroup diagnostics.
    frame["target_is_day"] = frame["is_day"].shift(-2)
    frame = frame.dropna(subset=FEATURES + WEATHER_FEATURES + ["target_activity"])
    frame["solar_bin"] = np.floor(frame["hours_from_sunrise"]).astype(int)
    return frame


def available_training(frame, feature_hour):
    return frame.loc[
        (frame.index < feature_hour) & (frame["target_hour"] <= feature_hour)
    ].copy()


def baseline_values(train, query, leave_one_out=False):
    """C's solar-bin -> clock-hour -> global mean fallback, fold-local.

    For training residuals, remove the row's own label from every candidate
    group. Other labels are allowed only because the outer issue-time filter
    has already established that their outcomes are available.
    """
    if train.empty:
        raise ValueError("Climatology requires historical labels.")
    if leave_one_out and not query.index.equals(train.index):
        raise ValueError("Leave-one-out queries must be the training frame.")
    own = query["target_activity"].to_numpy(float) if leave_one_out else 0.0
    removed = int(leave_one_out)
    denominator = len(train) - removed
    if denominator < 1:
        raise ValueError("Climatology requires another historical label.")
    result = np.full(len(query), train["target_activity"].sum(), dtype=float)
    result = (result - own) / denominator
    # Apply clock-hour fallback first; sufficiently populated solar bins win.
    for key in ("hour_of_day", "solar_bin"):
        stats = train.groupby(key)["target_activity"].agg(["sum", "count"])
        counts = query[key].map(stats["count"]).fillna(0).to_numpy(float) - removed
        sums = query[key].map(stats["sum"]).to_numpy(float) - own
        valid = counts >= MIN_BIN_ROWS
        result[valid] = sums[valid] / counts[valid]
    return result


def fit_fold(train, test, trees=300, jobs=1):
    if train["target_hour"].max() > test.index[0]:
        raise ValueError("Training includes unavailable target outcomes.")
    baseline = float(baseline_values(train, test)[0])
    residual = train["target_activity"].to_numpy(float) - baseline_values(
        train, train, leave_one_out=True
    )
    predictions = {
        "Persistence": float(test["activity_index"].iloc[0]),
        "Solar climatology": baseline,
    }
    fitted = {}
    raw_residuals = {}
    for name, features, labels in (
        ("RF full", FEATURES, train["target_activity"]),
        ("Residual RF", ACTIVITY_FEATURES, residual),
        ("Residual RF + weather", ACTIVITY_FEATURES + WEATHER_FEATURES, residual),
    ):
        model = RandomForestRegressor(
            n_estimators=trees, min_samples_leaf=3, random_state=42, n_jobs=jobs
        )
        model.fit(train[features].astype(float), labels)
        prediction = float(model.predict(test[features].astype(float))[0])
        if name != "RF full":
            raw_residuals[name] = prediction
            prediction += baseline
        predictions[name] = max(0.0, prediction)
        fitted[name] = (model, features)
    return predictions, raw_residuals, fitted


def metrics(actual, predicted):
    error = np.asarray(predicted, float) - np.asarray(actual, float)
    absolute = np.abs(error)
    return (absolute.mean(), np.sqrt(np.mean(error ** 2)),
            np.median(absolute), np.percentile(absolute, 90))


def print_table(label, rows):
    print(f"\n{label} ({len(rows)} hours)")
    if rows.empty:
        print("  No matched hours.")
        return
    print(f"{'Model':<24} {'MAE':>9} {'RMSE':>9} {'Median AE':>10} {'P90 AE':>9}")
    for name in MODELS:
        values = metrics(rows["actual"], rows[name])
        print(f"{name:<24} " + " ".join(f"{value:>9.3f}" for value in values))


def print_results(rows, fitted):
    print_table("Overall", rows)
    for day, label in ((1, "Target day"), (0, "Target night")):
        print_table(label, rows.loc[rows["target_is_day"] == day])
    unknown_day = rows["target_is_day"].isna().sum()
    print(f"\nTarget day/night unavailable: {unknown_day}")
    # Retain input-hour grouping for comparison with B/C's historical tables.
    for day, label in ((1, "Input day (B/C convention)"), (0, "Input night (B/C convention)")):
        print_table(label, rows.loc[rows["input_is_day"] == day])
    for label, mask in (
        ("Activity 0", rows["actual"] == 0),
        ("Activity 1-5", (rows["actual"] > 0) & (rows["actual"] <= 5)),
        ("Activity 6-15", (rows["actual"] > 5) & (rows["actual"] <= 15)),
        ("Activity 16+", rows["actual"] > 15),
    ):
        print_table(label, rows.loc[mask])
    print("\nHead-to-head: first wins / second wins / ties")
    for left, right in (
        ("Residual RF", "Solar climatology"),
        ("Residual RF", "RF full"),
        ("Residual RF + weather", "Residual RF"),
        ("Residual RF + weather", "RF full"),
    ):
        a = np.abs(rows[left] - rows["actual"])
        b = np.abs(rows[right] - rows["actual"])
        ties = np.isclose(a, b, rtol=0, atol=1e-9)
        print(f"  {left} vs {right}: {(~ties & (a < b)).sum()} / "
              f"{(~ties & (b < a)).sum()} / {ties.sum()}")
    actual_residual = rows["actual"] - rows["Solar climatology"]
    print("\nActual residual distribution (outcome minus fold-local baseline)")
    print(actual_residual.describe(percentiles=[0.1, 0.5, 0.9]).to_string())
    print("\nResidual MAE: raw model output / effective output after activity clipping")
    print(f"  Zero correction: {np.abs(actual_residual).mean():.3f}")
    for name in MODELS[3:]:
        raw_mae = np.abs(rows[f"raw {name}"] - actual_residual).mean()
        effective_mae = np.abs(rows[name] - rows["actual"]).mean()
        print(f"  {name}: {raw_mae:.3f} / {effective_mae:.3f}")
    # A fixed activity-index threshold, not selected from the evaluation data.
    for label, mask in (
        ("Unusually active (residual >= +5)", actual_residual >= 5),
        ("Unusually quiet (residual <= -5)", actual_residual <= -5),
    ):
        print_table(label, rows.loc[mask])
    print("\nFinal fold feature importance. Diagnostic only; not causality.")
    for name, (model, features) in fitted.items():
        print(name)
        values = pd.Series(model.feature_importances_, index=features).sort_values(ascending=False)
        for feature, value in values.items():
            print(f"  {feature:<24} {value:.4f}")
    print("\nDecision: NO PRODUCTION CHANGE")
    print("Retrospective evidence only. Stored forward forecasts were not read or written.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", help="Latest completed outcome hour, local wall-clock time")
    parser.add_argument("--min-training-rows", type=int, default=192)
    parser.add_argument("--trees", type=int, default=300)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--max-forecasts", type=int, help="Smoke test only; not the full experiment")
    parser.add_argument("--output", type=Path, required=True, help="New CSV outside the Git checkout")
    args = parser.parse_args()
    if args.min_training_rows < 4 or args.trees < 1 or args.jobs == 0:
        parser.error("Invalid training size, tree count, or job count.")
    if args.max_forecasts is not None and args.max_forecasts < 1:
        parser.error("--max-forecasts must be positive.")
    repo = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    if output.is_relative_to(repo) or output.exists() or not output.parent.is_dir():
        parser.error("Output must be a new CSV in an existing directory outside the checkout.")
    latest = latest_completed_hour()
    cutoff = pd.Timestamp(args.cutoff) if args.cutoff else latest
    if cutoff.tzinfo is not None or cutoff != cutoff.floor("h") or cutoff > latest:
        parser.error("Cutoff must be a completed local wall-clock hour without a timezone suffix.")
    # Lazy import keeps synthetic tests independent of PostgreSQL dependencies.
    from data import load_hourly_data
    raw = load_hourly_data()
    frame = build_dataset(raw, cutoff)
    print("BirdNET residual-model retrospective experiment", flush=True)
    print("Prediction horizon: completed hour T -> target T+2")
    print(f"Raw hourly rows: {len(raw)}; matched usable rows: {len(frame)}")
    print(f"Completed outcome cutoff: {cutoff}")
    print(f"Matched input window: {frame.index.min()} -> {frame.index.max()}")
    print(f"Training minimum: {args.min_training_rows}; trees: {args.trees}; jobs: {args.jobs}")
    print("Training residuals: fold-local leave-one-out climatology.")
    print("Input weather only; chronology does not reconstruct historical ingestion snapshots.")
    print("Pre-health observations retain legacy provenance; precipitation units retain historical uncertainty.")
    for name in ("numpy", "pandas", "scikit-learn", "psycopg"):
        print(f"  {name}=={version(name)}")
    if args.max_forecasts or args.trees != 300 or args.min_training_rows != 192:
        print("NONSTANDARD / SMOKE RUN: do not compare directly with the full default experiment.")
    started = time.monotonic()
    rows = []
    skipped_recent = skipped_training = 0
    fitted = {}
    # Exclusive creation avoids overwriting an earlier run. Flush each row so
    # an interrupted run retains completed forecasts, explicitly as partial.
    with output.open("x", encoding="utf-8", newline="") as handle:
        for pos in range(len(frame)):
            test = frame.iloc[[pos]]
            hour = test.index[0]
            train = available_training(frame, hour)
            if len(train) < args.min_training_rows:
                skipped_training += 1
                continue
            if not bool(test["recent_complete"].iloc[0]):
                skipped_recent += 1
                continue
            predictions, corrections, fitted = fit_fold(train, test, args.trees, args.jobs)
            row = {
                "feature_hour": hour, "target_hour": test["target_hour"].iloc[0],
                "training_rows": len(train), "latest_training_target": train["target_hour"].max(),
                "actual": float(test["target_activity"].iloc[0]),
                "input_is_day": int(test["is_day"].iloc[0]),
                "target_is_day": test["target_is_day"].iloc[0],
                **predictions, **{f"raw {name}": value for name, value in corrections.items()},
            }
            pd.DataFrame([row]).to_csv(handle, index=False, header=not rows)
            handle.flush()
            rows.append(row)
            if len(rows) % 25 == 0 or len(rows) == 1:
                print(f"  {len(rows):4} forecasts ({(time.monotonic() - started) / 60:.1f} min)", flush=True)
            if args.max_forecasts and len(rows) >= args.max_forecasts:
                break
    if not rows:
        raise RuntimeError("No forecasts produced; review dataset and training history.")
    print(f"\nCompleted {len(rows)} forecasts in {(time.monotonic() - started) / 60:.1f} minutes.")
    print(f"Skipped: {skipped_training} insufficient training; {skipped_recent} recent-history gaps.")
    result = pd.DataFrame(rows)
    print(f"Scored target window: {result['target_hour'].min()} -> {result['target_hour'].max()}")
    print_results(result, fitted)
    print(f"\nForecast CSV: {output}")


if __name__ == "__main__":
    main()
