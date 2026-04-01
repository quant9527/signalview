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

from signalml.db import load_ths_stock_sector_pairs, pairs_to_stock_sectors
from signalml.features import FeaturePipeline
from signalml.features_kline import attach_market_kline_features
from signalml.features_resonance import attach_resonance_features
from signalml.labels import attach_forward_returns
from signalml.flight_kline import SYMBOL_CSI300, normalize_asindex_symbol
from signalml.prices import fetch_bars_map, normalize_symbol_6


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


def build_bars_map(
    symbols: list[str],
    cache_dir: Path | None,
    exchange: str = "as",
) -> dict[str, pd.DataFrame]:
    return fetch_bars_map(symbols, cache_dir=cache_dir, exchange=exchange)


def train_pipeline(
    df_all: pd.DataFrame,
    horizon_days: int,
    cache_dir: Path | None,
    test_ratio: float = 0.2,
    exchange_filter: str | None = "as",
    *,
    conn_url: str | None = None,
    use_resonance: bool = True,
    resonance_lookback_days: int = 5,
    use_ths_resonance: bool = True,
    ths_signal_name_substr: str | None = None,
    ths_position_filter: str | None = None,
    use_kline_market: bool = True,
) -> dict[str, Any]:
    d = df_all.copy()
    if exchange_filter and "exchange" in d.columns:
        d = d[d["exchange"].astype(str) == exchange_filter].copy()
    if d.empty:
        raise ValueError("No rows after exchange filter")
    syms = d["symbol"].astype(str).unique().tolist()
    ex = (exchange_filter or "as").strip() or "as"
    bars = build_bars_map(syms, cache_dir, exchange=ex)
    labeled = attach_forward_returns(d, bars, horizon_days=horizon_days)
    labeled = labeled.dropna(subset=["label_fwd_ret"])

    if use_kline_market:
        hs300_key = normalize_asindex_symbol(SYMBOL_CSI300)
        idx_map = fetch_bars_map(
            [SYMBOL_CSI300],
            cache_dir=cache_dir,
            exchange="asindex",
        )
        hs300_bars = idx_map.get(hs300_key) if hs300_key else None
        labeled = attach_market_kline_features(labeled, bars, hs300_bars)

    stock_to_sectors: dict[str, list[str]] = {}
    if use_resonance and use_ths_resonance and conn_url:
        pairs = load_ths_stock_sector_pairs(conn_url)
        stock_to_sectors = pairs_to_stock_sectors(pairs)
    if use_resonance:
        labeled = attach_resonance_features(
            labeled,
            df_all,
            lookback_days=resonance_lookback_days,
            stock_to_sectors=stock_to_sectors if use_ths_resonance else {},
            ths_signal_name_substr=ths_signal_name_substr if use_ths_resonance else None,
            ths_position_filter=ths_position_filter if use_ths_resonance else None,
        )
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
        "stock_to_sectors": stock_to_sectors,
        "resonance_config": {
            "enabled": use_resonance,
            "lookback_days": resonance_lookback_days,
            "use_ths": use_ths_resonance,
            "ths_signal_name_substr": ths_signal_name_substr,
            "ths_position_filter": ths_position_filter,
        },
        "kline_market_config": {
            "enabled": use_kline_market,
            "hs300_symbol": SYMBOL_CSI300,
            "stock_exchange": ex,
        },
        "cache_dir": str(cache_dir) if cache_dir is not None else None,
    }


def save_artifact(bundle: dict[str, Any], out_dir: str | Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, out_dir / "model.joblib")
    meta = {
        "horizon_days": bundle["horizon_days"],
        "exchange_filter": bundle["exchange_filter"],
        "metrics": bundle["metrics"],
        "resonance_config": bundle.get("resonance_config"),
        "kline_market_config": bundle.get("kline_market_config"),
        "cache_dir": bundle.get("cache_dir"),
    }
    (out_dir / "meta.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True), encoding="utf-8")
    return out_dir
