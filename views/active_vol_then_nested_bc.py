import pandas as pd
import streamlit as st
from utils import display_signals_multiview


# ============================================================================
# active_vol_then_nested_bc
# 
# 模式说明：
# 筛选5m和15m出现 active_vol_then_nested_bc 信号的标的，等待回调见底机会
# ============================================================================

st.header("💰 active_vol_then_nested_bc")
st.markdown("""
**模式特征：5分钟/15分钟级别放量信号 → 回调缩量 → 底部确认**

- 🎯 **核心逻辑**：小周期放量突破后的回调是绝佳买点
- 📊 **筛选条件**：5m 或 15m 出现 active_vol_then_nested_bc 信号
- ⏰ **最佳时机**：放量后缩量回调，出现底部确认信号时介入
""")

st.divider()

# 获取数据
df = st.session_state.df

if df.empty:
    st.warning("暂无数据")
    st.stop()

# ============================================================================
# 配置区域（紧凑显示）
# ============================================================================
TARGET_SIGNAL_PREFIX = 'nested_2bc'   # 实际筛选用
DISPLAY_SIGNAL_NAME = 'active_vol_then_nested_bc'  # 页内展示用
TARGET_FREQS = ['5m', '15m']

# 紧凑显示配置信息
with st.expander(f"📋 信号配置 | 信号: {DISPLAY_SIGNAL_NAME}* | 周期: {', '.join(TARGET_FREQS)}", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**目标信号（{DISPLAY_SIGNAL_NAME} 系列）**")
    with col2:
        st.markdown(f"**目标周期**: {', '.join(TARGET_FREQS)}")

# ============================================================================
# 时间范围筛选
# ============================================================================
if 'signal_date' in df.columns:
    df['signal_date'] = pd.to_datetime(df['signal_date'])
    min_date = df['signal_date'].min().date()
    max_date = df['signal_date'].max().date()
    
    # 获取最近5个有效日期作为默认起始日期
    unique_dates = sorted(df['signal_date'].dt.date.unique(), reverse=True)
    default_start = unique_dates[min(4, len(unique_dates) - 1)] if unique_dates else min_date
    
    date_range = st.slider(
        "选择信号日期范围",
        min_value=min_date,
        max_value=max_date,
        value=(default_start, max_date),
        format="YYYY-MM-DD"
    )
    
    df = df[(df['signal_date'].dt.date >= date_range[0]) & 
            (df['signal_date'].dt.date <= date_range[1])].copy()
    
    st.info(f"📅 显示 {date_range[0]} 至 {date_range[1]} 的信号（共 {len(unique_dates)} 个有效日期）")

st.divider()

# ============================================================================
# 筛选 5m 和 15m 的 nested_2bc 系列信号（页内文案称 active_vol_then_nested_bc）
# ============================================================================
st.subheader("1️⃣ 目标标的（5m/15m active_vol_then_nested_bc 系列）")

# freq 统一转小写再匹配，避免 5M/5m 等导致漏数
freq_lower = df['freq'].astype(str).str.strip().str.lower() if 'freq' in df.columns else pd.Series(dtype=str)
target_freqs_lower = [f.strip().lower() for f in TARGET_FREQS]

# 筛选条件：signal_name 以 TARGET_SIGNAL_PREFIX 开头 且 freq 为 5m 或 15m（不区分大小写）
filtered_df = df[
    (df['signal_name'].str.startswith(TARGET_SIGNAL_PREFIX, na=False)) & 
    (freq_lower.isin(target_freqs_lower))
].copy()

# 若库里有大量目标信号但几乎没有 5m/15m，提示可能原因
target_all_count = (df['signal_name'].str.startswith(TARGET_SIGNAL_PREFIX, na=False)).sum()
if target_all_count > 0 and filtered_df.empty and 'freq' in df.columns:
    sample_freqs = df.loc[df['signal_name'].str.startswith(TARGET_SIGNAL_PREFIX, na=False), 'freq'].dropna().unique().tolist()[:10]
    st.info(f"💡 本页只显示 **5m / 15m** 的 active_vol_then_nested_bc。库中共 {target_all_count} 条，但周期多为：{sample_freqs}，故当前筛选结果为 0。可放宽侧栏时间范围或确认数据源是否产出 5m/15m。")

if filtered_df.empty:
    st.warning(f"未找到 {DISPLAY_SIGNAL_NAME}* 信号（周期：{', '.join(TARGET_FREQS)}）。侧栏时间范围内若有该信号但多为其他周期，此处会为空。")
    st.stop()

# 显示实际匹配到的信号类型
matched_signals = filtered_df['signal_name'].unique().tolist()
with st.expander(f"📌 匹配到 {len(matched_signals)} 种信号类型", expanded=False):
    for sig in sorted(matched_signals):
        count = len(filtered_df[filtered_df['signal_name'] == sig])
        st.text(f"• {sig} ({count}条)")

# 显示统计信息
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📊 符合条件标的", filtered_df['symbol'].nunique())
with col2:
    st.metric("📈 信号总数", len(filtered_df))
with col3:
    freq_5m_count = (filtered_df['freq'].astype(str).str.lower() == '5m').sum()
    st.metric("⏱️ 5m信号数", freq_5m_count)
with col4:
    freq_15m_count = (filtered_df['freq'].astype(str).str.lower() == '15m').sum()
    st.metric("⏱️ 15m信号数", freq_15m_count)

st.divider()

# ============================================================================
# 多视图模式显示
# ============================================================================
st.subheader("2️⃣ 信号——多视图")

display_signals_multiview(filtered_df, height=600, show_stats=False)

st.divider()

# ============================================================================
# 信号时序分析
# ============================================================================
st.subheader("3️⃣ 信号时序分析")

if not filtered_df.empty and 'signal_date' in filtered_df.columns:
    # 按日期和周期统计
    daily_signals = filtered_df.groupby([
        filtered_df['signal_date'].dt.date, 
        'freq'
    ]).size().reset_index(name='count')
    daily_signals.columns = ['date', 'freq', 'count']
    
    # 透视表显示
    pivot_df = daily_signals.pivot(index='date', columns='freq', values='count').fillna(0)
    pivot_df = pivot_df.sort_index(ascending=False)
    
    st.write("**每日信号分布（按周期）：**")
    st.dataframe(pivot_df, width='stretch', height=300)
    
    # 趋势图（柱状）
    st.write("**信号趋势：**")
    st.bar_chart(pivot_df)

