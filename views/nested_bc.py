import pandas as pd
import streamlit as st
from constants import EXCHANGE_AS
from performance_table import render_performance_signal_table
from signal_constants import NESTED_2BC_LONG_FREQS, NESTED_2BC_PREFIX
from utils import display_signals_multiview

# ============================================================================
# nested_2bc（1w / 1d）
# ============================================================================

st.header("📊 nested_2bc（周线 / 日线）")
st.markdown(f"""
**说明**：展示 `signal_name` 以 `{NESTED_2BC_PREFIX}` 开头的信号，且 **freq** 为 **1w** 或 **1d**（不区分大小写）。
""")

st.divider()

df = st.session_state.df

if df.empty:
    st.warning("暂无数据")
    st.stop()

TARGET_FREQS = list(NESTED_2BC_LONG_FREQS)

with st.expander(
    f"📋 信号配置 | 前缀: `{NESTED_2BC_PREFIX}`* | 周期: {', '.join(TARGET_FREQS)}",
    expanded=False,
):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**信号前缀**: `{NESTED_2BC_PREFIX}`")
    with c2:
        st.markdown(f"**目标周期**: {', '.join(TARGET_FREQS)}")

if "signal_date" in df.columns:
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    min_date = df["signal_date"].min().date()
    max_date = df["signal_date"].max().date()
    unique_dates = sorted(df["signal_date"].dt.date.unique(), reverse=True)
    default_start = unique_dates[min(4, len(unique_dates) - 1)] if unique_dates else min_date

    date_range = st.slider(
        "选择信号日期范围",
        min_value=min_date,
        max_value=max_date,
        value=(default_start, max_date),
        format="YYYY-MM-DD",
    )

    df = df[
        (df["signal_date"].dt.date >= date_range[0])
        & (df["signal_date"].dt.date <= date_range[1])
    ].copy()

    st.info(
        f"📅 显示 {date_range[0]} 至 {date_range[1]} 的信号（共 {len(unique_dates)} 个有效日期）"
    )

st.divider()

st.subheader(f"1️⃣ 目标标的（{', '.join(TARGET_FREQS)} · nested_2bc*）")

freq_lower = (
    df["freq"].astype(str).str.strip().str.lower()
    if "freq" in df.columns
    else pd.Series(dtype=str)
)
target_freqs_lower = [f.strip().lower() for f in TARGET_FREQS]

filtered_df = df[
    (df["signal_name"].str.startswith(NESTED_2BC_PREFIX, na=False))
    & (freq_lower.isin(target_freqs_lower))
].copy()

prefix_mask = df["signal_name"].str.startswith(NESTED_2BC_PREFIX, na=False)
target_all_count = int(prefix_mask.sum())
if target_all_count > 0 and filtered_df.empty and "freq" in df.columns:
    sample_freqs = (
        df.loc[prefix_mask, "freq"].dropna().unique().tolist()[:12]
    )
    st.info(
        f"💡 本页只显示 **{' / '.join(TARGET_FREQS)}** 的 nested_2bc。库中该前缀共 {target_all_count} 条，"
        f"当前时间范围内 freq 样例：{sample_freqs}。若无 1w/1d，此处为空。"
    )

if filtered_df.empty:
    st.warning(
        f"未找到 `{NESTED_2BC_PREFIX}`* 且周期为 {', '.join(TARGET_FREQS)} 的信号。"
    )
    st.stop()

matched_signals = filtered_df["signal_name"].unique().tolist()
with st.expander(f"📌 匹配到 {len(matched_signals)} 种 signal_name", expanded=False):
    for sig in sorted(matched_signals):
        count = len(filtered_df[filtered_df["signal_name"] == sig])
        st.text(f"• {sig} ({count}条)")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("符合条件标的", filtered_df["symbol"].nunique())
with col2:
    st.metric("信号总数", len(filtered_df))
with col3:
    n_1w = (filtered_df["freq"].astype(str).str.strip().str.lower() == "1w").sum()
    st.metric("1w 条数", int(n_1w))
with col4:
    n_1d = (filtered_df["freq"].astype(str).str.strip().str.lower() == "1d").sum()
    st.metric("1d 条数", int(n_1d))

st.divider()

st.subheader("2️⃣ 当日涨幅排名（A 股）")
st.caption(
    "仅 **exchange = as** 的标的；按 **当日涨跌幅** 降序，便于挑出信号出现后盘面仍偏强的一批。"
    " **相对信号价** 为最新价相对信号记录中 `price` 的涨跌幅，供参考。"
)

if "exchange" in filtered_df.columns:
    as_df = filtered_df[filtered_df["exchange"] == EXCHANGE_AS].copy()
else:
    as_df = filtered_df.copy()
    st.warning("数据中无 `exchange` 列，行情合并按全部标的尝试匹配 A 股代码。")

if as_df.empty:
    st.info("当前筛选下无 A 股（as）标的，跳过当日涨幅排名。")
else:
    top_n = st.number_input(
        "显示前 N 名",
        min_value=10,
        max_value=500,
        value=80,
        step=10,
        key="nested_bc_top_n",
    )
    render_performance_signal_table(
        as_df,
        st.session_state.df,
        exchange=EXCHANGE_AS,
        key_prefix="nested_bc_rank",
        show_summary_info=False,
        sort_by="market_pct_change",
        sort_ascending=False,
        show_date_sort=False,
        show_na_toggle=False,
        row_limit=int(top_n),
        extra_display_columns=("freq",),
        stop_on_empty_market=False,
    )

st.divider()

st.subheader("3️⃣ 信号——多视图")
display_signals_multiview(filtered_df, height=600, show_stats=False)

st.divider()

st.subheader("4️⃣ 信号时序分析")

if not filtered_df.empty and "signal_date" in filtered_df.columns:
    daily_signals = (
        filtered_df.groupby(
            [filtered_df["signal_date"].dt.date, "freq"]
        )
        .size()
        .reset_index(name="count")
    )
    daily_signals.columns = ["date", "freq", "count"]
    pivot_df = daily_signals.pivot(
        index="date", columns="freq", values="count"
    ).fillna(0)
    pivot_df = pivot_df.sort_index(ascending=False)

    st.write("**每日信号分布（按周期）：**")
    st.dataframe(pivot_df, width="stretch", height=300)
    st.write("**信号趋势：**")
    st.bar_chart(pivot_df)
