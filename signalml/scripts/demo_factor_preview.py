#!/usr/bin/env python3
"""
可复现的小样本：打印「信号 + K 线市场因子 + 共振因子」及 FeaturePipeline 变换后的矩阵。

在 signalml 包目录下执行：
  uv run python scripts/demo_factor_preview.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from signalml.features import FeaturePipeline
from signalml.features_kline import attach_market_kline_features, kline_market_feature_columns
from signalml.features_resonance import attach_resonance_features, resonance_columns


def main() -> None:
    td = pd.date_range("2024-06-03", periods=5, freq="B")
    stock = pd.DataFrame(
        {
            "trade_date": td,
            "close": [100.0, 102.0, 101.0, 105.0, 104.0],
            "ma5ma10_sc": [0.0, 1.0, 0.0, 0.5, 1.0],
            "ma5ma10_jc": [1.0, 0.0, 0.0, 0.0, 0.0],
        }
    )
    hs300 = pd.DataFrame({"trade_date": td, "close": [3500.0, 3510.0, 3495.0, 3520.0, 3510.0]})

    sig = pd.DataFrame(
        {
            "symbol": ["600519", "600519", "000001"],
            "signal_date": [td[1], td[3], td[2]],
            "exchange": ["as", "as", "as"],
            "freq": ["1d", "1h", "1d"],
            "signal_name": ["k_buy", "k_buy", "breakout"],
            "score": [12.5, 8.0, np.nan],
        }
    )

    bars = {"600519": stock, "000001": stock.assign(close=stock["close"] * 0.98)}

    sig_k = attach_market_kline_features(sig, bars, hs300)

    ctx = pd.DataFrame(
        {
            "symbol": ["600519", "600519", "600519", "600519", "sec_ai", "sec_ai", "600519"],
            "signal_date": [td[0], td[1], td[1], td[2], td[1], td[2], td[4]],
            "exchange": ["as", "as", "as", "as", "ths", "ths", "as"],
            "signal_name": ["a", "b", "c", "d", "ths1", "ths2", "e"],
            "freq": ["1d", "1d", "1h", "1d", "1d", "1d", "1m"],
            "position": ["long"] * 7,
        }
    )
    sectors = {"600519": ["sec_ai"], "000001": []}
    sig_r = attach_resonance_features(sig_k, ctx, lookback_days=5, stock_to_sectors=sectors)

    kcols = kline_market_feature_columns()
    rcols = resonance_columns()
    meta = ["symbol", "signal_date", "score", "exchange", "freq", "signal_name"]
    show = meta + [c for c in kcols + rcols if c in sig_r.columns]

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)

    print("—— 示例：3 条信号 + K线市场因子 + 共振因子（数值保留 4 位）——\n")
    out = sig_r[show].copy()
    for c in kcols + rcols:
        if c in out.columns:
            out[c] = out[c].round(4)
    if "score" in out.columns:
        out["score"] = out["score"].round(2)
    print(out.to_string(index=False))

    pipe = FeaturePipeline().fit(sig_r)
    X = pipe.transform(sig_r)
    fn = pipe.feature_names()
    print("\n—— 同一批数据经 FeaturePipeline 后的矩阵（Ordinal 编码 + 数值列）——\n")
    mat = pd.DataFrame(X, columns=fn).round(4)
    print(mat.to_string(index=False))


if __name__ == "__main__":
    main()
