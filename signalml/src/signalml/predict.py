"""Load artifact and score a signal DataFrame."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from signalml.features import FeaturePipeline
from signalml.features_kline import attach_market_kline_features
from signalml.features_resonance import attach_resonance_features
from signalml.flight_kline import normalize_asindex_symbol
from signalml.prices import fetch_bars_map


def load_artifact(artifact_dir: str | Path) -> dict[str, Any]:
    artifact_dir = Path(artifact_dir)
    bundle = joblib.load(artifact_dir / "model.joblib")
    return bundle


def predict_scores(
    df: pd.DataFrame,
    artifact_dir: str | Path,
    context_df: pd.DataFrame | None = None,
) -> pd.Series:
    bundle = load_artifact(artifact_dir)
    pipe: FeaturePipeline = bundle["feature_pipeline"]
    model = bundle["model"]
    rc = bundle.get("resonance_config") or {}
    kc = bundle.get("kline_market_config") or {}
    idx = df.index
    work = df.reset_index(drop=True)
    if kc.get("enabled"):
        cache_raw = bundle.get("cache_dir")
        cache_dir = Path(cache_raw) if cache_raw else None
        sex = str(kc.get("stock_exchange") or "as").strip() or "as"
        hs300_sym = str(kc.get("hs300_symbol") or "sh000300").strip()
        hs300_key = normalize_asindex_symbol(hs300_sym)
        syms = work["symbol"].astype(str).unique().tolist()
        bars = fetch_bars_map(syms, cache_dir=cache_dir, exchange=sex)
        idx_map = fetch_bars_map([hs300_sym], cache_dir=cache_dir, exchange="asindex")
        hs300_bars = idx_map.get(hs300_key) if hs300_key else None
        work = attach_market_kline_features(work, bars, hs300_bars)
    if rc.get("enabled"):
        if context_df is None:
            raise ValueError(
                "该模型启用了共振特征：predict_scores 需要传入 context_df（与训练时相同时间窗内的全 exchange 信号表，"
                "需含 ths 与个股所在 exchange，以便复现共振统计）。"
            )
        work = attach_resonance_features(
            work,
            context_df if not context_df.empty else pd.DataFrame(),
            lookback_days=int(rc.get("lookback_days", 5)),
            stock_to_sectors=bundle.get("stock_to_sectors") or {},
            ths_signal_name_substr=rc.get("ths_signal_name_substr"),
            ths_position_filter=rc.get("ths_position_filter"),
        )
    X = pipe.transform(work)
    pred = model.predict(X)
    return pd.Series(pred, index=idx, name="pred_fwd_ret")
