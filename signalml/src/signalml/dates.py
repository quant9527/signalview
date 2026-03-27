"""Normalize signal_date like signalview utils (no streamlit)."""

import pandas as pd


def normalize_signal_date_field(df: pd.DataFrame, col: str = "signal_date", tz: str = "Asia/Shanghai") -> pd.DataFrame:
    if col not in df.columns:
        return df
    s = df[col]
    try:
        if pd.api.types.is_numeric_dtype(s):
            if s.dropna().abs().gt(1e12).any():
                s_dt = pd.to_datetime(s, unit="ms", errors="coerce", utc=True)
            else:
                s_dt = pd.to_datetime(s, unit="s", errors="coerce", utc=True)
            s_local = s_dt.dt.tz_convert(tz)
            s_local_str = s_local.dt.strftime("%Y-%m-%d %H:%M:%S")
            df[col] = pd.to_datetime(s_local_str, errors="coerce")
        else:
            s_dt = pd.to_datetime(s, errors="coerce")
            if s_dt.dt.tz is not None:
                s_local = s_dt.dt.tz_convert(tz)
                s_local_str = s_local.dt.strftime("%Y-%m-%d %H:%M:%S")
                df[col] = pd.to_datetime(s_local_str, errors="coerce")
            else:
                df[col] = s_dt
    except Exception:
        df[col] = pd.to_datetime(s, errors="coerce")
    return df
