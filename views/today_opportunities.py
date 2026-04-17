import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from data import get_sector_constituents_from_db, create_all_signals_columns
from signal_constants import CMP_SIGNAL_NAMES

# ============================================================================
# 🎯 Today Opportunities - 今日机会雷达
# 
# 核心设计：
# 1. 只关注今日新增信号，过滤历史噪音
# 2. 信号质量评分，优先展示高价值机会
# 3. 多维度共振检测（信号+板块+技术）
# 4. 一键决策辅助，降低认知负荷
# ============================================================================

st.header("🎯 今日机会雷达")

# 获取数据
df = st.session_state.df

if df.empty:
    st.warning("暂无数据")
    st.stop()

# 确保日期格式正确
df['signal_date'] = pd.to_datetime(df['signal_date'])

# ============================================================================
# 信号质量评分算法
# ============================================================================

def calculate_signal_score(row, all_signals_df, today, sector_data=None):
    """
    计算信号综合得分 (0-100分)
    
    评分维度：
    - 信号类型权重 (基础分 10-30分)
    - 时间新鲜度 (当天 +20分，1天内 +15分，2天内 +10分)
    - 多信号共振 (同股票多信号 +15-30分)
    - 板块热度 (板块内多信号 +10-20分)
    - 技术形态 (特定组合额外加分)
    """
    score = 0
    signal_date = pd.to_datetime(row['signal_date'])
    symbol = row['symbol']
    signal_name = row['signal_name']
    
    # 1. 信号类型基础分
    signal_weights = {
        'cmp_rebound_pioneer_ma5ma10': 30,  # 反弹先锋，高权重
        'cmp_rebound_pioneer_macd': 28,
        'cmp_zs_macd': 25,  # 中枢突破
        'cmp_zs_ma5ma10': 25,
        'cmp_xsx_ma5ma10': 20,  # 线上买
        'cmp_xsx_macd': 20,
        'cmp_break_ma5ma10': 22,  # 均线突破
        'cmp_break_macd': 22,
        'active_vol': 15,  # 放量
        'nested_2bc_ma5ma10_': 18,  # 二买
        'nested_2bc_macd_': 18,
        'cl3b_zsx': 20,  # 三买
    }
    
    # 匹配信号前缀获取权重
    base_score = 10
    for prefix, weight in signal_weights.items():
        if str(signal_name).startswith(prefix):
            base_score = weight
            break
    score += base_score
    
    # 2. 时间新鲜度加分
    days_diff = (today - signal_date).days
    if days_diff == 0:
        score += 20  # 当日信号
    elif days_diff == 1:
        score += 15
    elif days_diff == 2:
        score += 10
    else:
        score += max(0, 5 - days_diff)
    
    # 3. 多信号共振加分
    symbol_signals = all_signals_df[all_signals_df['symbol'] == symbol]
    unique_signals = symbol_signals['signal_name'].nunique()
    if unique_signals >= 3:
        score += 30  # 3+信号共振
    elif unique_signals == 2:
        score += 20  # 双信号共振
    elif unique_signals == 1:
        score += 10
    
    # 4. 信号频率加分（近期多次触发）
    recent_signals = symbol_signals[symbol_signals['signal_date'] >= today - timedelta(days=5)]
    if len(recent_signals) >= 3:
        score += 15  # 近期活跃
    elif len(recent_signals) == 2:
        score += 8
    
    # 5. 板块热度加分
    if sector_data and symbol in sector_data:
        sector_signals = sector_data[symbol]
        if sector_signals >= 5:
            score += 20  # 热门板块
        elif sector_signals >= 3:
            score += 15
        elif sector_signals >= 2:
            score += 10
    
    return min(100, score)  # 封顶100分


# ============================================================================
# 数据筛选与评分
# ============================================================================

# 获取今日日期（使用数据中最新日期作为"今日"）
latest_date = df['signal_date'].max().date()
today = pd.Timestamp(latest_date)

# 时间筛选选项
st.markdown(f"### 📅 分析日期：{latest_date}")

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    show_only_today = st.toggle("只看今日新增", value=True, help="只显示今天首次出现的信号")
with col2:
    min_score = st.slider("最低评分", min_value=0, max_value=100, value=40, step=5,
                         help="只显示高于此分数的机会")
with col3:
    # 快速筛选按钮
    quick_filter = st.segmented_control("快速筛选", 
        options=["全部", "高分(70+)", "共振", "反弹先锋", "放量突破"],
        default="全部")

# 根据快速筛选调整参数
if quick_filter == "高分(70+)":
    min_score = max(min_score, 70)
    show_only_today = False
elif quick_filter == "共振":
    show_only_today = False
elif quick_filter == "反弹先锋":
    show_only_today = True
elif quick_filter == "放量突破":
    show_only_today = True

# 筛选数据时间范围
if show_only_today:
    # 只看今日信号
    filtered_df = df[df['signal_date'].dt.date == latest_date].copy()
else:
    # 看近3天信号
    filtered_df = df[df['signal_date'] >= today - timedelta(days=3)].copy()

if filtered_df.empty:
    st.warning(f"📭 {'今日' if show_only_today else '近3日'}暂无信号数据")
    st.stop()

# 计算板块热度
sector_df = filtered_df[filtered_df['exchange'] == 'ths']
sector_signal_counts = sector_df.groupby('symbol').size().to_dict() if not sector_df.empty else {}

# 计算每个信号的得分
st.markdown("### 🔍 正在分析信号质量...")

scored_data = []
for idx, row in filtered_df.iterrows():
    score = calculate_signal_score(row, filtered_df, today, sector_signal_counts)
    scored_data.append({
        **row.to_dict(),
        'score': score,
        'score_level': '🔥' if score >= 80 else '⚡' if score >= 60 else '📊' if score >= 40 else '💤'
    })

scored_df = pd.DataFrame(scored_data)

# 按评分排序
scored_df = scored_df.sort_values(['score', 'signal_date'], ascending=[False, False])

# 过滤低分信号
scored_df = scored_df[scored_df['score'] >= min_score]

if scored_df.empty:
    st.warning(f"📭 没有评分高于 {min_score} 分的信号")
    st.stop()

# ============================================================================
# 核心指标展示
# ============================================================================

st.divider()
st.markdown("### 📊 核心指标")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    total_signals = len(scored_df)
    st.metric("总信号数", total_signals)

with col2:
    today_signals = len(scored_df[scored_df['signal_date'].dt.date == latest_date])
    st.metric("今日新增", today_signals, delta=f"+{today_signals}" if today_signals > 0 else None)

with col3:
    high_score = len(scored_df[scored_df['score'] >= 70])
    st.metric("高分机会(70+)", high_score)

with col4:
    # 多信号共振数
    multi_signal_symbols = scored_df.groupby('symbol').filter(lambda x: len(x) >= 2)['symbol'].nunique()
    st.metric("共振标的", multi_signal_symbols)

with col5:
    # 平均得分
    avg_score = int(scored_df['score'].mean())
    st.metric("平均评分", f"{avg_score}分")

st.divider()

# ============================================================================
# 高质量机会展示 (Top 10)
# ============================================================================

st.markdown("### 🎯 今日Top机会 (按评分排序)")

# 准备展示数据
display_df = scored_df.head(20).copy()

# 分组展示
symbol_groups = display_df.groupby('symbol')

for symbol, group in list(symbol_groups)[:10]:  # 只展示前10个标的
    row = group.iloc[0]
    symbol_name = row.get('symbol_name', symbol)
    exchange = row.get('exchange', '')
    score = int(row['score'])
    
    # 确定优先级标签
    if score >= 80:
        priority = "🚨 URGENT"
        border_color = "#ff4b4b"
    elif score >= 60:
        priority = "⚡ HIGH"
        border_color = "#ffa726"
    else:
        priority = "📊 NORMAL"
        border_color = "#66bb6a"
    
    # 收集该股票的所有信号
    all_signals = group['signal_name'].tolist()
    signal_badges = ' '.join([f"`{s}`" for s in all_signals[:3]])
    if len(all_signals) > 3:
        signal_badges += f" +{len(all_signals)-3} more"
    
    # 最新信号日期
    latest_signal = group['signal_date'].max().strftime('%m-%d %H:%M') if len(group) > 0 else ''
    
    # 显示卡片
    with st.container():
        st.markdown(f"""
        <div style="border-left: 4px solid {border_color}; padding-left: 10px; margin: 10px 0;">
            <h4>{priority} | {symbol} {symbol_name} <span style="color:{border_color};font-size:1.2em">{score}分</span></h4>
            <p><strong>信号:</strong> {signal_badges}</p>
            <p><small>交易所: {exchange} | 最新: {latest_signal}</small></p>
        </div>
        """, unsafe_allow_html=True)
        
        # 详细信息展开
        with st.expander(f"查看 {symbol} 详情", expanded=False):
            detail_cols = ['signal_date', 'signal_name', 'exchange', 'score']
            detail_df = group[detail_cols].copy()
            detail_df['signal_date'] = detail_df['signal_date'].dt.strftime('%Y-%m-%d %H:%M')
            detail_df['score'] = detail_df['score'].astype(int)
            st.dataframe(detail_df, hide_index=True, use_container_width=True)
            
            # 如果是板块，显示成分股
            if exchange == 'ths':
                constituents = get_sector_constituents_from_db(symbol, 'ths')
                if constituents:
                    st.markdown(f"**成分股 ({len(constituents)}只):**")
                    # 检查成分股是否有信号
                    constituent_signals = df[
                        (df['symbol'].isin(constituents)) & 
                        (df['signal_date'] >= today - timedelta(days=3))
                    ]
                    if not constituent_signals.empty:
                        st.dataframe(
                            constituent_signals[['symbol', 'symbol_name', 'signal_name', 'signal_date']].head(10),
                            hide_index=True
                        )
                    else:
                        st.info("成分股近3日暂无信号")

st.divider()

# ============================================================================
# 板块热度排行
# ============================================================================

st.markdown("### 🔥 板块热度排行")

if sector_df.empty:
    st.info("暂无板块信号")
else:
    # 统计板块热度
    sector_stats = sector_df.groupby('symbol').agg({
        'signal_name': 'count',
        'symbol_name': 'first',
        'signal_date': 'max'
    }).reset_index()
    sector_stats.columns = ['symbol', 'signal_count', 'name', 'latest_signal']
    sector_stats = sector_stats.sort_values('signal_count', ascending=False).head(10)
    
    # 可视化
    chart_data = sector_stats.copy()
    chart_data['display'] = chart_data['symbol'] + ' ' + chart_data['name']
    
    import altair as alt
    
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('signal_count:Q', title='信号数量'),
        y=alt.Y('display:N', title='板块', sort='-x'),
        color=alt.Color('signal_count:Q', scale=alt.Scale(scheme='oranges'), title='热度'),
        tooltip=['symbol', 'name', 'signal_count', 'latest_signal']
    ).properties(height=300)
    
    st.altair_chart(chart, use_container_width=True)

st.divider()

# ============================================================================
# 信号类型分布
# ============================================================================

st.markdown("### 📈 信号类型分布")

signal_dist = scored_df['signal_name'].value_counts().head(15)

# 使用柱状图展示
dist_df = signal_dist.reset_index()
dist_df.columns = ['signal_name', 'count']

dist_chart = alt.Chart(dist_df).mark_bar().encode(
    x=alt.X('count:Q', title='出现次数'),
    y=alt.Y('signal_name:N', title='信号类型', sort='-x'),
    color=alt.Color('count:Q', scale=alt.Scale(scheme='blues'), title='次数'),
    tooltip=['signal_name', 'count']
).properties(height=400)

st.altair_chart(dist_chart, use_container_width=True)

# ============================================================================
# 完整数据下载
# ============================================================================

st.divider()
with st.expander("📥 下载完整数据", expanded=False):
    download_df = scored_df[['symbol', 'symbol_name', 'signal_name', 'signal_date', 'score', 'exchange']].copy()
    download_df['signal_date'] = download_df['signal_date'].dt.strftime('%Y-%m-%d')
    download_df['score'] = download_df['score'].astype(int)
    
    csv = download_df.to_csv(index=False)
    st.download_button(
        label="下载CSV",
        data=csv,
        file_name=f"today_opportunities_{latest_date}.csv",
        mime="text/csv"
    )
    
    st.dataframe(download_df, hide_index=True, use_container_width=True, height=400)
