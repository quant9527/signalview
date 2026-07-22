"""Sector hotspot review page (url_path=review_hotspot)."""
from __future__ import annotations

import pandas as pd

import streamlit as st

from data import (
    create_all_signals_columns,
    get_sector_constituents_from_db,
    load_data,
)
from utils import display_signals_multiview

SECTOR_EXCHANGES = ['ths']


def page_review_hotspot() -> None:
    """Sector hotspot tracker (url_path=review_hotspot)."""
    st.set_page_config(layout="wide", page_title="Sector Hotspot")
    st.header("🔥 板块热点")
    st.markdown("""
**模式特征：板块轮动中的领涨先锋**

- 🎯 **核心逻辑**：板块启动时，率先反弹的个股往往是后续行情的领涨龙头
- 📊 **识别特征**：板块指数企稳时，个股率先突破关键均线
- ⏰ **最佳时机**：板块整体调整末期，关注率先放量启动的个股
""")
    st.divider()

    df = load_data(45, signal_name_prefix='cmp', signal_not='SELL')

    if df.empty:
        st.warning("暂无数据")
        st.stop()

    if 'signal_date' in df.columns:
        df['signal_date'] = pd.to_datetime(df['signal_date'])
        min_date = df['signal_date'].min().date()
        max_date = df['signal_date'].max().date()

        unique_dates = sorted(df['signal_date'].dt.date.unique(), reverse=True)
        if len(unique_dates) >= 3:
            default_start = unique_dates[2]
        else:
            default_start = unique_dates[-1] if unique_dates else min_date

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

        st.info(f"📅 显示 {date_range[0]} 至 {date_range[1]} 的信号")

    st.divider()

    st.subheader("1️⃣ 板块反弹急先锋")
    st.caption(f"本段仅统计 **exchange ∈ {SECTOR_EXCHANGES}**（同花顺板块）的 cmp 系列信号。")

    ths_df = df[df["exchange"].isin(SECTOR_EXCHANGES)].copy()
    available_signals = sorted(ths_df["signal_name"].unique().tolist())

    st.markdown("**追踪信号：**")
    for sig in available_signals:
        st.text(f"• {sig}")

    pattern_df = ths_df[ths_df["signal_name"].isin(available_signals)].copy()

    if pattern_df.empty:
        st.warning("未找到符合当前模式的信号数据")
    else:
        symbol_signal_summary = pattern_df.groupby('symbol').agg({
            'signal_name': lambda x: list(x.unique()),
            'signal_date': ['min', 'max', 'count'],
            'symbol_name': 'first',
            'exchange': 'first',
        }).reset_index()

        symbol_signal_summary.columns = [
            'symbol', 'signals', 'first_signal', 'last_signal',
            'signal_count', 'symbol_name', 'exchange',
        ]
        symbol_signal_summary['signals_str'] = symbol_signal_summary['signals'].apply(
            lambda x: ', '.join(x)
        )
        symbol_signal_summary['signal_types'] = symbol_signal_summary['signals'].apply(len)

        symbol_signal_summary = symbol_signal_summary.sort_values(
            ['last_signal', 'signal_types', 'symbol'],
            ascending=[False, False, True],
        )

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 符合条件标的", len(symbol_signal_summary))
        with col2:
            st.metric("📈 总信号数", len(pattern_df))
        with col3:
            multi_signal = len(
                symbol_signal_summary[symbol_signal_summary['signal_types'] > 1]
            )
            st.metric("🎯 多信号共振", multi_signal)
        with col4:
            if 'last_signal' in symbol_signal_summary.columns:
                recent_count = len(
                    symbol_signal_summary[
                        symbol_signal_summary['last_signal']
                        >= pd.Timestamp.now() - pd.Timedelta(days=3)
                    ]
                )
                st.metric("🔥 近3日新增", recent_count)

        display_signals_multiview(pattern_df, height=400, show_stats=False)

    st.divider()

    st.subheader("2️⃣ 板块热点与成分股联动")

    sector_df = pattern_df[pattern_df['exchange'].isin(SECTOR_EXCHANGES)].copy()

    if sector_df.empty:
        st.info(f"未找到板块(exchange={SECTOR_EXCHANGES})相关信号")
    else:
        sector_df = sector_df.copy()
        sector_df['signal_date'] = pd.to_datetime(sector_df['signal_date'], utc=False)
        sector_latest = sector_df.groupby('symbol', as_index=False)['signal_date'].max()
        sector_latest = sector_latest.sort_values(
            ['signal_date', 'symbol'],
            ascending=[False, True],
        )
        sector_list = sector_latest['symbol'].tolist()

        st.write(f"发现 **{len(sector_list)}** 个板块有相关信号")

        for sector_symbol in sector_list:
            sector_signals = sector_df[sector_df['symbol'] == sector_symbol]

            if not sector_signals.empty:
                sector_name = (
                    sector_signals['symbol_name'].iloc[0]
                    if 'symbol_name' in sector_signals.columns else sector_symbol
                )
                signal_names = sector_signals['signal_name'].unique().tolist()
                first_ts = sector_signals['signal_date'].min()
                last_ts = sector_signals['signal_date'].max()
                first_str = first_ts.strftime('%Y-%m-%d') if pd.notna(first_ts) else '—'
                last_str = last_ts.strftime('%Y-%m-%d') if pd.notna(last_ts) else '—'
                time_range = f" | 首个 {first_str} → 最后 {last_str}"
                with st.expander(
                    f"📁 **{sector_symbol} - {sector_name}** "
                    f"({len(signal_names)}个信号){time_range}",
                    expanded=False,
                ):
                    st.write("**板块信号：**")
                    if 'signal_date' in sector_signals.columns:
                        df_latest = sector_signals.loc[
                            sector_signals.groupby("symbol")["signal_date"].idxmax()
                        ].copy()
                        df_with_all_signals = create_all_signals_columns(
                            df_latest, sector_signals, include_extra_info=True
                        )
                        display_cols = [
                            'display_symbol', 'symbol_name',
                            'all_signals', 'all_signals_count',
                        ]
                        available_cols = [
                            col for col in display_cols
                            if col in df_with_all_signals.columns
                        ]
                        st.dataframe(
                            df_with_all_signals[available_cols],
                            width='stretch',
                            hide_index=True,
                        )

                    constituent_codes = get_sector_constituents_from_db(
                        sector_symbol, 'ths'
                    )
                    if constituent_codes:
                        constituent_df = df[
                            df['symbol'].isin(constituent_codes)
                        ].copy()
                        if not constituent_df.empty:
                            st.write(
                                f"**🎯 成分股信号 "
                                f"({len(constituent_df['symbol'].unique())}"
                                f"/{len(constituent_codes)}):**"
                            )
                            display_signals_multiview(constituent_df, height=400)
                        else:
                            st.info("成分股中暂无信号")
                    else:
                        st.info(f"未找到 {sector_symbol} 的成分股数据")

    st.divider()