"""同标的 / 多周期 / THS 板块 信号共振特征（仅使用 signal_date <= 当前行，避免标签泄漏）。"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _to_date64(series: pd.Series) -> np.ndarray:
    return pd.to_datetime(series, errors="coerce").dt.normalize().values.astype("datetime64[ns]")


def _build_context_by_symbol(ctx: pd.DataFrame) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """symbol -> (dates_ns sorted, signal_name, freq) for all context rows."""
    out: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    ctx = ctx.copy()
    if "signal_name" not in ctx.columns:
        ctx["signal_name"] = ""
    if "freq" not in ctx.columns:
        ctx["freq"] = ""
    need = ["symbol", "signal_date", "signal_name", "freq"]
    ctx = ctx[need].copy()
    ctx["_d"] = _to_date64(ctx["signal_date"])
    ctx = ctx.dropna(subset=["_d"])
    for sym, g in ctx.groupby("symbol", sort=False):
        g2 = g.sort_values("_d")
        out[str(sym)] = (
            g2["_d"].values.astype("datetime64[ns]"),
            g2["signal_name"].astype(str).values,
            g2["freq"].astype(str).values,
        )
    return out


def _build_ths_sector_dates(
    context_df: pd.DataFrame,
    ths_signal_name_substr: str | None,
    ths_position_filter: str | None = None,
) -> dict[str, np.ndarray]:
    """THS 板块/指数 symbol -> 升序 signal_date（仅 exchange==ths）。"""
    th = context_df[context_df["exchange"].astype(str) == "ths"].copy()
    if th.empty:
        return {}
    want_pos = (ths_position_filter or "").strip().lower()
    if want_pos and "position" in th.columns:
        pv = th["position"].astype(str).str.strip().str.lower()
        th = th[pv == want_pos]
    if ths_signal_name_substr:
        sub = ths_signal_name_substr.strip()
        if sub:
            th = th[th["signal_name"].astype(str).str.contains(sub, case=False, na=False)]
    if th.empty:
        return {}
    th["_d"] = _to_date64(th["signal_date"])
    th = th.dropna(subset=["_d"])
    out: dict[str, np.ndarray] = {}
    for sym, g in th.groupby("symbol", sort=False):
        arr = np.sort(g["_d"].values.astype("datetime64[ns]"))
        out[str(sym)] = arr
    return out


def _count_between(sorted_dates: np.ndarray, hi: np.datetime64, lo: np.datetime64) -> int:
    if sorted_dates.size == 0:
        return 0
    i = np.searchsorted(sorted_dates, lo, side="left")
    j = np.searchsorted(sorted_dates, hi, side="right")
    return int(j - i)


def attach_resonance_features(
    target_df: pd.DataFrame,
    context_df: pd.DataFrame,
    *,
    lookback_days: int,
    stock_to_sectors: dict[str, list[str]] | None,
    ths_signal_name_substr: str | None = None,
    ths_position_filter: str | None = None,
) -> pd.DataFrame:
    """
    对每个目标行 (symbol=S, signal_date=t)，在 [t-lookback_days, t] 内统计：
    - 同 S 的信号条数、distinct signal_name、distinct freq（多周期共振）
    - 与 S 关联的 THS 板块/指数 symbol 上，同期 THS 信号条数（板块-个股共振）

    仅统计 signal_date <= t 的行；窗口左端为日历日 lookback（与交易日 horizon 标签不同，属特征工程选择）。
    """
    td = target_df.reset_index(drop=True).copy()
    if td.empty:
        for c in _resonance_output_columns():
            td[c] = np.float64(0.0)
        return td

    ctx_by_sym = _build_context_by_symbol(context_df)
    ths_by_sec = _build_ths_sector_dates(
        context_df,
        ths_signal_name_substr,
        ths_position_filter=ths_position_filter,
    )
    stock_to_sectors = stock_to_sectors or {}
    L = np.timedelta64(int(lookback_days), "D")

    n = len(td)
    res_sym_n = np.zeros(n, dtype=np.float64)
    res_sym_n_name = np.zeros(n, dtype=np.float64)
    res_sym_n_freq = np.zeros(n, dtype=np.float64)
    res_sym_multi_freq = np.zeros(n, dtype=np.float64)
    res_ths_n = np.zeros(n, dtype=np.float64)
    res_ths_any = np.zeros(n, dtype=np.float64)
    res_ths_max = np.zeros(n, dtype=np.float64)

    sym_col = td["symbol"].astype(str)
    dt_col = _to_date64(td["signal_date"])

    for sym, grp_idx in td.groupby(sym_col, sort=False).indices.items():
        grp_idx = np.asarray(grp_idx, dtype=np.int64)
        order = np.argsort(dt_col[grp_idx])
        ordered = grp_idx[order]
        t_ord = dt_col[ordered]

        dates_ctx, names_ctx, freqs_ctx = ctx_by_sym.get(sym, (np.array([], "datetime64[ns]"), np.array([]), np.array([])))
        sectors = stock_to_sectors.get(sym, [])

        for k in range(len(ordered)):
            row_i = int(ordered[k])
            t = t_ord[k]
            if pd.isna(t):
                continue
            lo = t - L
            # 同 symbol：<= t 且在 [lo, t]
            i0 = np.searchsorted(dates_ctx, lo, side="left")
            i1 = np.searchsorted(dates_ctx, t, side="right")
            sl = slice(i0, i1)
            res_sym_n[row_i] = float(i1 - i0)
            if i1 > i0:
                un = len(np.unique(names_ctx[sl]))
                uf = len(np.unique(freqs_ctx[sl]))
                res_sym_n_name[row_i] = float(un)
                res_sym_n_freq[row_i] = float(uf)
                res_sym_multi_freq[row_i] = 1.0 if uf >= 2 else 0.0
            else:
                res_sym_n_name[row_i] = 0.0
                res_sym_n_freq[row_i] = 0.0
                res_sym_multi_freq[row_i] = 0.0

            total = 0
            best = 0
            for z in sectors:
                arr = ths_by_sec.get(str(z))
                if arr is None or arr.size == 0:
                    continue
                c = _count_between(arr, t, lo)
                total += c
                if c > best:
                    best = c
            res_ths_n[row_i] = float(total)
            res_ths_any[row_i] = 1.0 if total > 0 else 0.0
            res_ths_max[row_i] = float(best)

    td["res_sym_n_sig"] = res_sym_n
    td["res_sym_n_distinct_name"] = res_sym_n_name
    td["res_sym_n_distinct_freq"] = res_sym_n_freq
    td["res_sym_multi_freq"] = res_sym_multi_freq
    td["res_ths_sec_n_sig"] = res_ths_n
    td["res_ths_sec_any"] = res_ths_any
    td["res_ths_sec_max_sig"] = res_ths_max
    return td


def _resonance_output_columns() -> list[str]:
    return [
        "res_sym_n_sig",
        "res_sym_n_distinct_name",
        "res_sym_n_distinct_freq",
        "res_sym_multi_freq",
        "res_ths_sec_n_sig",
        "res_ths_sec_any",
        "res_ths_sec_max_sig",
    ]


def resonance_columns() -> list[str]:
    return _resonance_output_columns()
