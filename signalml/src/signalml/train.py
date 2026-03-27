"""Train LightGBM on labeled signals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from signalml.features import FeaturePipeline
from signalml.labels import attach_forward_returns
from signalml.prices import fetch_daily_bars, normalize_symbol_6


def time_based_split(df: pd.DataFrame, test_ratio: float = 0.2, date_col: str = "signal_date"):
    d = df.copy()
    d["_d"] = pd.to_datetime(d[date_col], errors="coerce")
    d = d.dropna(subset=["_d"]).sort_values("_d")
    n = len(d)
    if n < 10:
        raise ValueError(f"Need at least 10 rows for time split, got {n}")
    cut = int(n * (1.0 - test_ratio))
    cut = max(1, min(cut, n - 1))
    train, test = d.iloc[:cut], d.iloc[cut:]
    return train.drop(columns=["_d"]), test.drop(columns=["_d"])


def build_bars_map(symbols: list[str], cache_dir: Path | None) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        code = normalize_symbol_6(sym)
        bars = fetch_daily_bars(sym, cache_dir=cache_dir)
        if not bars.empty:
            out[code] = bars
    return out


def train_pipeline(
    df: pd.DataFrame,
    horizon_days: int,
    cache_dir: Path | None,
    test_ratio: float = 0.2,
    exchange_filter: str | None = "as",
) -> dict[str, Any]:
    d = df.copy()
    if exchange_filter and "exchange" in d.columns:
        d = d[d["exchange"].astype(str) == exchange_filter].copy()
    if d.empty:
        raise ValueError("No rows after exchange filter")
    syms = d["symbol"].astype(str).unique().tolist()
    bars = build_bars_map(syms, cache_dir)
    labeled = attach_forward_returns(d, bars, horizon_days=horizon_days)
    labeled = labeled.dropna(subset=["label_fwd_ret"])
    if len(labeled) < 50:
        raise ValueError(f"Too few labeled rows: {len(labeled)}")
    train_df, test_df = time_based_split(labeled, test_ratio=test_ratio)
    if len(train_df) < 20 or len(test_df) < 5:
        raise ValueError(
            f"Train/test too small after split: train={len(train_df)}, test={len(test_df)}"
        )
    pipe = FeaturePipeline().fit(train_df)
    X_tr, y_tr = pipe.transform(train_df), train_df["label_fwd_ret"].values
    X_te, y_te = pipe.transform(test_df), test_df["label_fwd_ret"].values
    model = HistGradientBoostingRegressor(
        max_iter=200,
        learning_rate=0.05,
        max_depth=8,
        random_state=42,
    )
    model.fit(X_tr, y_tr)
    pred_te = model.predict(X_te)
    metrics = {
        "mae_test": float(mean_absolute_error(y_te, pred_te)),
        "r2_test": float(r2_score(y_te, pred_te)),
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
    }
    return {
        "model": model,
        "feature_pipeline": pipe,
        "metrics": metrics,
        "horizon_days": horizon_days,
        "exchange_filter": exchange_filter,
    }


def save_artifact(bundle: dict[str, Any], out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_dir / "model.joblib")
    meta = {
        "horizon_days": bundle["horizon_days"],
        "exchange_filter": bundle["exchange_filter"],
        "metrics": bundle["metrics"],
    }
    (out_dir / "meta.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True), encoding="utf-8")
    return out_dir
