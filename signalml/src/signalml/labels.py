"""Forward returns on trading days from daily bars."""

from __future__ import annotations

import numpy as np
import pandas as pd


def forward_close_return(
    bars: pd.DataFrame,
    signal_dates: pd.Series,
    horizon_days: int,
) -> np.ndarray:
    """For each signal_date, return (close[t+h]/close[t]) - 1; NaN if missing.

    bars: trade_date, close sorted ascending.
    signal_dates: same length as output alignment target (index by position).
    """
    if bars.empty or horizon_days < 1:
        return np.full(len(signal_dates), np.nan)
    closes = bars["close"].astype(float).values
    # numpy datetime64 for searchsorted
    d64 = pd.to_datetime(bars["trade_date"]).values.astype("datetime64[ns]")
    out = np.empty(len(signal_dates), dtype=float)
    for i, sd in enumerate(signal_dates):
        if pd.isna(sd):
            out[i] = np.nan
            continue
        s = pd.Timestamp(sd).normalize().to_datetime64()
        j = np.searchsorted(d64, s, side="left")
        if j >= len(d64):
            out[i] = np.nan
            continue
        # use first bar on or after signal date
        if d64[j] != s:
            # if no exact match, still use on-or-after
            pass
        k = j + horizon_days
        if k >= len(closes) or j < 0:
            out[i] = np.nan
            continue
        c0, c1 = closes[j], closes[k]
        if c0 and c0 > 0 and np.isfinite(c0) and np.isfinite(c1):
            out[i] = (c1 / c0) - 1.0
        else:
            out[i] = np.nan
    return out


def attach_forward_returns(
    df: pd.DataFrame,
    bars_by_symbol: dict[str, pd.DataFrame],
    horizon_days: int,
    symbol_col: str = "symbol",
    date_col: str = "signal_date",
) -> pd.DataFrame:
    out = df.copy()
    rets = []
    for _, row in out.iterrows():
        sym = row.get(symbol_col)
        bars = bars_by_symbol.get(str(sym).strip()) or bars_by_symbol.get(normalize_sym(sym))
        if bars is None or bars.empty:
            rets.append(np.nan)
            continue
        r = forward_close_return(bars, pd.Series([row[date_col]]), horizon_days)
        rets.append(float(r[0]) if len(r) else np.nan)
    out["label_fwd_ret"] = rets
    return out


def normalize_sym(sym):
    from signalml.prices import normalize_symbol_6
    return normalize_symbol_6(str(sym))
