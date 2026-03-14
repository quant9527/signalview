import pandas as pd
import streamlit as st
from utils import display_signals_multiview

# ============================================================================
# 📈 大盘 - 指数信号
# ============================================================================

st.header("📈 大盘")
st.markdown("""
**主要宽基指数信号**

- 上证指数、沪深300、深证成指、创业板指等指数的多周期信号
- 多视图：Symbol 优先 / 信号优先 / 按周期分 tab
""")

st.divider()

# 获取数据
df = st.session_state.df

if df.empty:
    st.warning("暂无数据")
    st.stop()

# 指数代码列表
INDEX_SYMBOLS = [
    'sh000001',  # 上证指数
    'sh000300',  # 沪深300
    'sz399001',  # 深证成指
    'sz399006',  # 创业板指
]

# ============================================================================
# 指数信号 (Index Signals) - 多视图模式
# ============================================================================
st.subheader("📈 指数信号 (Index Signals)")

# 筛选指数数据
index_df = df[df['symbol'].isin(INDEX_SYMBOLS)].copy()

if index_df.empty:
    st.info(f"未找到指数信号 ({', '.join(INDEX_SYMBOLS)})")
else:
    display_signals_multiview(index_df, height=400)
