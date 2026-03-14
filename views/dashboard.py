"""
Dashboard 公共逻辑：按 exchange 筛选并展示信号。
供 dashboard_as / dashboard_em / dashboard_binance 调用。
"""
import pandas as pd
import streamlit as st
from utils import display_signals_multiview


def render_dashboard(exchange: str) -> None:
    """
    按指定 exchange 筛选 session_state.df 并多视图展示信号。

    Args:
        exchange: 交易所/数据源标识，如 "as" | "em" | "binance"
    """
    title_map = {"as": "🇨🇳 AS", "em": "🌍 EM", "binance": "🪙 Binance"}
    title = title_map.get(exchange.lower(), exchange)

    st.header(f"Dashboard — {title}")
    st.divider()

    df = st.session_state.df
    if df.empty:
        st.warning("暂无数据")
        return

    if "exchange" not in df.columns:
        st.info("当前数据无 exchange 列，显示全部信号")
    else:
        df = df[df["exchange"] == exchange].copy()
        if df.empty:
            st.warning(f"未找到 exchange={exchange} 的数据")
            return
        st.info(f"已筛选 Exchange: **{exchange}**（共 {len(df)} 条信号，{df['symbol'].nunique()} 个标的）")

    st.divider()
    st.subheader("信号 — 多视图")
    display_signals_multiview(df, height=500, show_stats=True)
