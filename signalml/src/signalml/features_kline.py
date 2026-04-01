"""K 线截面特征：相对沪深300 日涨跌幅 + Flight 原生 ma5ma10_sc / ma5ma10_jc 等。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from signalml.prices import normalize_symbol_6

# 训练/预测统一输出的特征列名（缺失则填 0）
RAW_KLINE_SIGNALS = ("ma5ma10_sc", "ma5ma10_jc")


def kline_market_feature_columns() -> list[str]:
    cols = [
        "feat_stock_day_pct",
        "feat_hs300_day_pct",
        "feat_hs300_excess_day_pct",
    ]
    cols += [f"feat_{n}" for n in RAW_KLINE_SIGNALS]
    return cols


def _add_day_pct(bars: pd.DataFrame) -> pd.DataFrame:
    b = bars.sort_values("trade_date").copy()
    c = b["close"].astype(float)
    b["_day_pct"] = (c / c.shift(1) - 1.0) * 100.0
    return b


def _stock_long_table(bars_by_code: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for code, raw in bars_by_code.items():
        if raw is None or raw.empty or "trade_date" not in raw.columns:
            continue
        b = _add_day_pct(raw)
        b = b.copy()
        b["_sym6"] = str(code)
        b["_sigd"] = pd.to_datetime(b["trade_date"], errors="coerce").dt.normalize()
        use_cols = ["_sym6", "_sigd", "_day_pct"]
        for name in RAW_KLINE_SIGNALS:
            if name in b.columns:
                use_cols.append(name)
        parts.append(b[use_cols].dropna(subset=["_sigd"]))
    if not parts:
        return pd.DataFrame(columns=["_sym6", "_sigd", "_day_pct"])
    return pd.concat(parts, ignore_index=True).sort_values(["_sym6", "_sigd"])


def attach_market_kline_features(
    df: pd.DataFrame,
    bars_by_code: dict[str, pd.DataFrame],
    hs300_bars: pd.DataFrame | None,
    *,
    symbol_col: str = "symbol",
    date_col: str = "signal_date",
) -> pd.DataFrame:
    """
    在 signal_date 当日（按交易日 merge_asof backward）对齐：
    - 个股日涨跌幅 vs 沪深300 日涨跌幅 -> feat_hs300_excess_day_pct
    - K 线表中的 ma5ma10_sc / ma5ma10_jc -> feat_*
    """
    out = df.reset_index(drop=True).copy()
    out["_orig_idx"] = np.arange(len(out), dtype=np.int64)
    out["_sym6"] = out[symbol_col].map(normalize_symbol_6)
    out["_sigd"] = pd.to_datetime(out[date_col], errors="coerce").dt.normalize()

    sl = _stock_long_table(bars_by_code)
    if sl.empty:
        for c in kline_market_feature_columns():
            out[c] = 0.0
        out = out.sort_values("_orig_idx").drop(columns=["_sym6", "_sigd", "_orig_idx"], errors="ignore")
        return out.reset_index(drop=True)

    merge_cols = ["_sym6", "_sigd", "_day_pct"] + [n for n in RAW_KLINE_SIGNALS if n in sl.columns]
    sl = sl[merge_cols].sort_values(["_sym6", "_sigd"])
    sl_r = sl.rename(columns={"_day_pct": "_stock_day_pct"})
    right_keep = ["_sigd", "_stock_day_pct"] + [n for n in RAW_KLINE_SIGNALS if n in sl_r.columns]
    chunks: list[pd.DataFrame] = []
    # 按标的分别 merge_asof：多标的交错时全局 _sigd 非单调，pandas 会报错
    for sym, left_g in out.groupby("_sym6", sort=False):
        left_g = left_g.sort_values("_sigd")
        sub = sl_r.loc[sl_r["_sym6"] == sym, right_keep].sort_values("_sigd")
        if sub.empty:
            mg = left_g.copy()
            mg["_stock_day_pct"] = np.nan
            for n in RAW_KLINE_SIGNALS:
                if n in sl.columns:
                    mg[n] = np.nan
        else:
            mg = pd.merge_asof(left_g, sub, on="_sigd", direction="backward")
        chunks.append(mg)
    m = pd.concat(chunks, ignore_index=True)

    if hs300_bars is not None and not hs300_bars.empty and "trade_date" in hs300_bars.columns:
        hi = _add_day_pct(hs300_bars)
        hi["_sigd"] = pd.to_datetime(hi["trade_date"], errors="coerce").dt.normalize()
        idx = (
            hi[["_sigd", "_day_pct"]]
            .rename(columns={"_day_pct": "_idx_day_pct"})
            .dropna(subset=["_sigd"])
            .sort_values("_sigd")
            .drop_duplicates("_sigd", keep="last")
        )
        m = m.merge(idx, on="_sigd", how="left")
    else:
        m["_idx_day_pct"] = np.nan

    m["feat_stock_day_pct"] = pd.to_numeric(m["_stock_day_pct"], errors="coerce").fillna(0.0)
    m["feat_hs300_day_pct"] = pd.to_numeric(m["_idx_day_pct"], errors="coerce").fillna(0.0)
    m["feat_hs300_excess_day_pct"] = m["feat_stock_day_pct"] - m["feat_hs300_day_pct"]

    for name in RAW_KLINE_SIGNALS:
        feat = f"feat_{name}"
        if name in m.columns:
            m[feat] = pd.to_numeric(m[name], errors="coerce").fillna(0.0)
        else:
            m[feat] = 0.0

    m = m.drop(
        columns=[
            c
            for c in ["_sym6", "_sigd", "_stock_day_pct", "_idx_day_pct"] + list(RAW_KLINE_SIGNALS)
            if c in m.columns
        ],
        errors="ignore",
    )
    m = m.sort_values("_orig_idx").drop(columns=["_orig_idx"], errors="ignore")
    return m.reset_index(drop=True)
