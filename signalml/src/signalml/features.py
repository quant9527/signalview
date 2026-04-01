"""Minimal tabular features for signal rows."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OrdinalEncoder

from signalml.features_kline import kline_market_feature_columns
from signalml.features_resonance import resonance_columns


def _coerce_score(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


@dataclass
class FeaturePipeline:
    """Fits on train DataFrame; transforms same columns for inference."""

    categorical: list[str] = field(default_factory=lambda: ["signal_name", "exchange", "freq"])
    encoder: ColumnTransformer | None = None
    score_median: float = 0.0

    def fit(self, df: pd.DataFrame) -> FeaturePipeline:
        sub = df.copy()
        sub["score_num"] = _coerce_score(sub.get("score", pd.Series(0, index=sub.index)))
        self.score_median = float(sub["score_num"].median()) if sub["score_num"].notna().any() else 0.0
        sub["score_num"] = sub["score_num"].fillna(self.score_median)
        if "signal_date" in sub.columns:
            sd = pd.to_datetime(sub["signal_date"], errors="coerce")
            sub["dow"] = sd.dt.dayofweek.fillna(0).astype(int)
            sub["month"] = sd.dt.month.fillna(1).astype(int)
        else:
            sub["dow"] = 0
            sub["month"] = 1
        cat_cols = [c for c in self.categorical if c in sub.columns]
        for c in cat_cols:
            sub[c] = sub[c].fillna("").astype(str)
        self.encoder = ColumnTransformer(
            [
                (
                    "cat",
                    OrdinalEncoder(
                        handle_unknown="use_encoded_value",
                        unknown_value=-1,
                        dtype=np.int64,
                    ),
                    cat_cols,
                ),
            ],
            remainder="drop",
            verbose_feature_names_out=False,
        )
        self.encoder.fit(sub[cat_cols])
        self._cat_cols = cat_cols
        self.resonance_cols = [c for c in resonance_columns() if c in sub.columns]
        kline_all = kline_market_feature_columns()
        self.kline_market_cols = [c for c in kline_all if c in sub.columns]
        self._num_cols = ["score_num", "dow", "month"] + self.resonance_cols + self.kline_market_cols
        return self

    def _resonance_cols_safe(self) -> list[str]:
        return getattr(self, "resonance_cols", [])

    def _kline_market_cols_safe(self) -> list[str]:
        return getattr(self, "kline_market_cols", [])

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        sub = df.copy()
        sub["score_num"] = _coerce_score(sub.get("score", pd.Series(0, index=sub.index))).fillna(self.score_median)
        if "signal_date" in sub.columns:
            sd = pd.to_datetime(sub["signal_date"], errors="coerce")
            sub["dow"] = sd.dt.dayofweek.fillna(0).astype(int)
            sub["month"] = sd.dt.month.fillna(1).astype(int)
        else:
            sub["dow"] = 0
            sub["month"] = 1
        cat_cols = self._cat_cols
        for c in cat_cols:
            sub[c] = sub[c].fillna("").astype(str) if c in sub.columns else ""
        for c in self._resonance_cols_safe():
            if c not in sub.columns:
                sub[c] = 0.0
            sub[c] = pd.to_numeric(sub[c], errors="coerce").fillna(0.0)
        for c in self._kline_market_cols_safe():
            if c not in sub.columns:
                sub[c] = 0.0
            sub[c] = pd.to_numeric(sub[c], errors="coerce").fillna(0.0)
        X_cat = self.encoder.transform(sub[cat_cols])
        X_num = sub[self._num_cols].values.astype(np.float64)
        return np.hstack([X_cat, X_num])

    def feature_names(self) -> list[str]:
        names = list(self.encoder.get_feature_names_out())
        return names + list(self._num_cols)
