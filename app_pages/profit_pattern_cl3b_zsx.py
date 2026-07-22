"""CL3B ZSX signal tracker page (url_path=profit_pattern_cl3b_zsx)."""
from __future__ import annotations

import pandas as pd

import streamlit as st

from signal_constants import CL3B_ZSX_PREFIX
from utils import display_signals_multiview, get_cached_data


def page_profit_pattern_cl3b_zsx() -> None:
    """CL3B ZSX profit-pattern page (url_path=profit_pattern_cl3b_zsx)."""
    st.set_page_config(layout="wide", page_title="CL3B ZSX")
    st.header("📈 盈利模式: CL3B ZSX 信号")
    st.markdown("""
**模式特征：CL3B ZSX 系列信号追踪**

- 🎯 **核心逻辑**：跟踪 cl3b_zsx 信号出现的标的
- 📊 **筛选条件**：signal_name 以 cl3b_zsx 开头
- ⏰ **关注重点**：信号出现后的走势跟踪
""")

    target_signal_prefix = CL3B_ZSX_PREFIX
    st.divider()

    df_full = get_cached_data(45)
    df = df_full[
        df_full["signal_name"].str.startswith(target_signal_prefix, na=False)
    ].copy()

    if df.empty:
        st.warning("暂无数据")
        st.stop()

    all_matching_signals = (
        df[df["signal_name"].str.startswith(target_signal_prefix, na=False)]
        ["signal_name"].unique().tolist()
    )
    available_freqs_all = (
        df[df["signal_name"].str.startswith(target_signal_prefix, na=False)]
        ["freq"].unique().tolist()
        if "freq" in df.columns else []
    )

    with st.expander(
        f"📋 信号配置 | 信号: {', '.join(sorted(all_matching_signals)) or 'N/A'}"
        f" | 周期: {', '.join(sorted(available_freqs_all)) or 'N/A'}",
        expanded=False,
    ):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**目标信号（{target_signal_prefix} 系列）**")
            st.text(
                ", ".join(sorted(all_matching_signals)) if all_matching_signals
                else "暂无匹配信号"
            )
        with col2:
            st.markdown("**可用周期**")
            st.text(", ".join(sorted(available_freqs_all)) if available_freqs_all else "N/A")

    if 'signal_date' in df.columns:
        df['signal_date'] = pd.to_datetime(df['signal_date'])
        min_date = df['signal_date'].min().date()
        max_date = df['signal_date'].max().date()

        unique_dates = sorted(df['signal_date'].dt.date.unique(), reverse=True)
        default_start = (
            unique_dates[min(4, len(unique_dates) - 1)] if unique_dates else min_date
        )

        date_range = st.slider(
            "选择信号日期范围",
            min_value=min_date,
            max_value=max_date,
            value=(default_start, max_date),
            format="YYYY-MM-DD",
        )

        df = df[
            (df['signal_date'].dt.date >= date_range[0])
            & (df['signal_date'].dt.date <= date_range[1])
        ].copy()

        st.info(
            f"📅 显示 {date_range[0]} 至 {date_range[1]} 的信号"
            f"（共 {len(unique_dates)} 个有效日期）"
        )

    st.divider()

    st.subheader(f"1️⃣ {target_signal_prefix} 系列信号标的")

    filtered_df = df[
        df['signal_name'].str.startswith(target_signal_prefix, na=False)
    ].copy()

    if filtered_df.empty:
        st.warning(f"未找到 {target_signal_prefix}* 信号")
        st.stop()

    matched_signals = filtered_df['signal_name'].unique().tolist()
    with st.expander(
        f"📌 匹配到 {len(matched_signals)} 种信号类型", expanded=False,
    ):
        for sig in sorted(matched_signals):
            count = len(filtered_df[filtered_df['signal_name'] == sig])
            st.text(f"• {sig} ({count}条)")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 符合条件标的", filtered_df['symbol'].nunique())
    with col2:
        st.metric("📈 信号总数", len(filtered_df))
    with col3:
        if 'freq' in filtered_df.columns:
            freq_counts = filtered_df['freq'].value_counts()
            if len(freq_counts) > 0:
                top_freq = freq_counts.index[0]
                st.metric("🔝 最多信号周期", f"{top_freq} ({freq_counts.iloc[0]})")
            else:
                st.metric("🔝 最多信号周期", "N/A")

    st.divider()
    st.subheader("2️⃣ 信号——多视图")
    display_signals_multiview(filtered_df, height=600, show_stats=False)

    st.divider()
    st.subheader("3️⃣ 信号时序分析")

    if not filtered_df.empty and 'signal_date' in filtered_df.columns:
        if 'freq' in filtered_df.columns:
            daily_signals = filtered_df.groupby([
                filtered_df['signal_date'].dt.date,
                'freq',
            ]).size().reset_index(name='count')
            daily_signals.columns = ['date', 'freq', 'count']
            pivot_df = daily_signals.pivot(
                index='date', columns='freq', values='count',
            ).fillna(0)
            pivot_df = pivot_df.sort_index(ascending=False)
            st.write("**每日信号分布（按周期）：**")
            st.dataframe(pivot_df, width='stretch', height=300)
            st.write("**信号趋势：**")
            st.bar_chart(pivot_df)
        else:
            daily_signals = filtered_df.groupby(
                filtered_df['signal_date'].dt.date,
            ).size().reset_index(name='count')
            daily_signals.columns = ['date', 'count']
            daily_signals = (
                daily_signals.set_index('date').sort_index(ascending=False)
            )
            st.write("**每日信号分布：**")
            st.dataframe(daily_signals, width='stretch', height=300)
            st.write("**信号趋势：**")
            st.bar_chart(daily_signals)