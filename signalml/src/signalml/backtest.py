"""Simple backtest metrics on predicted scores."""

from __future__ import annotations

import numpy as np
import pandas as pd


def daily_portfolio_simple(
    df: pd.DataFrame,
    score_col: str,
    label_col: str,
    date_col: str = "signal_date",
    top_frac: float = 0.2,
) -> dict:
    """Per calendar day, long equal-weight top fraction by score; return summary stats."""
    if df.empty or score_col not in df.columns or label_col not in df.columns:
        return {"mean_label_top": float("nan"), "mean_label_all": float("nan"), "n_days": 0}
    d = df[[date_col, score_col, label_col]].copy()
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce").dt.normalize()
    d = d.dropna(subset=[date_col, label_col])
    tops = []
    alls = []
    for _, g in d.groupby(date_col):
        g = g.dropna(subset=[score_col])
        if len(g) < 2:
            continue
        k = max(1, int(len(g) * top_frac))
        top = g.nlargest(k, score_col)
        tops.append(top[label_col].mean())
        alls.append(g[label_col].mean())
    if not tops:
        return {"mean_label_top": float("nan"), "mean_label_all": float("nan"), "n_days": 0}
    return {
        "mean_label_top": float(np.nanmean(tops)),
        "mean_label_all": float(np.nanmean(alls)),
        "n_days": len(tops),
    }
