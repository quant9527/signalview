import pandas as pd
import streamlit as st


# ============================================================================
# 周期排序（从大到小）
# ============================================================================
FREQ_ORDER = ['1M', '1w', '1d', '2h', '1h', '30m', '15m', '5m', '1m']

def sort_freqs(freqs: list[str]) -> list[str]:
    """
    按照标准周期顺序排序（从大到小）：1M > 1w > 1d > 2h > 1h > 30m > 15m > 5m > 1m
    未知周期排在最后
    """
    def get_order(freq):
        try:
            return FREQ_ORDER.index(freq)
        except ValueError:
            return len(FREQ_ORDER)  # 未知周期排在最后
    
    return sorted(freqs, key=get_order)


def normalize_signal_date_field(df, col: str = 'signal_date', tz: str = 'Asia/Shanghai'):
    """Normalize a date-like column to timezone `tz` (UTC+8) and return as tz-naive local datetimes.

    Handles numeric unix timestamps (seconds or milliseconds) and string date representations.
    The result will be timezone-local (Asia/Shanghai) and tz-naive datetimes.
    
    注意：
    - 数字类型（unix timestamp）假设是 UTC，会转换为目标时区
    - 字符串/datetime 如果有时区信息，会转换为目标时区
    - 字符串/datetime 如果没有时区信息，假设已经是目标时区，不做转换
    """
    if col not in df.columns:
        return df

    s = df[col]
    
    try:
        if pd.api.types.is_numeric_dtype(s):
            # 数字类型（unix timestamp）假设是 UTC
            if s.dropna().abs().gt(1e12).any():
                s_dt = pd.to_datetime(s, unit='ms', errors='coerce', utc=True)
            else:
                s_dt = pd.to_datetime(s, unit='s', errors='coerce', utc=True)
            # 转换为目标时区
            s_local = s_dt.dt.tz_convert(tz)
            s_local_str = s_local.dt.strftime("%Y-%m-%d %H:%M:%S")
            df[col] = pd.to_datetime(s_local_str, errors='coerce')
        else:
            # 非数字类型，先尝试解析
            s_dt = pd.to_datetime(s, errors='coerce')
            
            # 检查是否有时区信息
            if s_dt.dt.tz is not None:
                # 有时区信息，转换为目标时区
                s_local = s_dt.dt.tz_convert(tz)
                s_local_str = s_local.dt.strftime("%Y-%m-%d %H:%M:%S")
                df[col] = pd.to_datetime(s_local_str, errors='coerce')
            else:
                # 没有时区信息，假设已经是目标时区（东八区），直接使用
                df[col] = s_dt
    except Exception:
        # 兜底：直接解析，不做时区转换
        df[col] = pd.to_datetime(s, errors='coerce')

    return df


# ============================================================================
# Compact 模式显示函数
# ============================================================================
def display_signals_compact(
    df: pd.DataFrame,
    group_by_cols: list[str] = ['exchange', 'symbol', 'signal_name'],
    include_freq: bool = True,
    height: int = 600,
    title: str = None,
) -> None:
    """
    以 Compact 模式显示信号数据
    
    Args:
        df: 信号数据 DataFrame
        group_by_cols: 分组依据的列
        include_freq: 是否在 signal_info 中包含 freq
        height: dataframe 显示高度
        title: 可选的标题，显示在数据表上方
    """
    if df.empty:
        st.info("暂无数据")
        return
    
    # 填充空值
    df_filled = df.copy()
    df_filled['exchange'] = df_filled['exchange'].replace('', pd.NA).fillna('(No Exchange)')
    df_filled['symbol'] = df_filled['symbol'].replace('', pd.NA).fillna('(No Symbol)')
    if 'signal_name' in group_by_cols:
        df_filled['signal_name'] = df_filled['signal_name'].replace('', pd.NA).fillna('(No Signal)')
    
    # 创建组合显示字段：exchange:symbol-symbol_name (如 as:000001-平安银行)
    if 'symbol' in df_filled.columns and 'symbol_name' in df_filled.columns:
        df_filled['_display_symbol'] = df_filled.apply(
            lambda row: f"{row['exchange']}:{row['symbol']}-{row['symbol_name']}" 
                if pd.notna(row['symbol_name']) and row['symbol_name'] 
                else f"{row['exchange']}:{row['symbol']}", 
            axis=1
        )
    
    # 构建 signal_info 内容
    # 如果 signal_name 不在分组列中，需要在每行显示 signal_name
    include_signal_name = 'signal_name' not in group_by_cols
    
    def build_signal_info(group):
        lines = []
        for _, row in group.iterrows():
            dt = row.get('signal_date')
            date_str = dt.strftime('%Y-%m-%d %H:%M:%S') if pd.notna(dt) else 'N/A'
            parts = [date_str]
            # 如果 signal_name 不在分组列中，显示 signal_name
            if include_signal_name and 'signal_name' in group.columns:
                parts.append(f"{row['signal_name'] if pd.notna(row.get('signal_name')) else 'N/A'}")
            if include_freq and 'freq' in group.columns:
                parts.append(f"Freq: {row['freq'] if pd.notna(row.get('freq')) else 'N/A'}")
            if 'price' in group.columns:
                parts.append(f"Price: {row['price'] if pd.notna(row.get('price')) else 'N/A'}")
            if 'score' in group.columns:
                parts.append(f"Score: {row['score'] if pd.notna(row.get('score')) else 'N/A'}")
            lines.append(' | '.join(parts))
        return '\n'.join(lines)
    
    # 分组聚合
    df_sorted = df_filled.sort_values('signal_date', ascending=False)
    
    # 使用 agg 替代 apply，更稳定
    grouped_df = df_sorted.groupby(group_by_cols, as_index=False).agg(
        symbol_name=('symbol_name', 'first'),
        count=('symbol', 'size'),
        _latest_date=('signal_date', 'max'),
    )
    
    # 单独计算 signal_info（需要访问多列）
    signal_info_dict = {}
    for keys, group in df_sorted.groupby(group_by_cols):
        key = keys if isinstance(keys, tuple) else (keys,)
        signal_info_dict[key] = build_signal_info(group)
    
    # 将 signal_info 合并到 grouped_df
    grouped_df['signal_info'] = grouped_df.apply(
        lambda row: signal_info_dict.get(tuple(row[col] for col in group_by_cols), ''),
        axis=1
    )
    
    # 按最新信号时间降序排序
    grouped_df = grouped_df.sort_values('_latest_date', ascending=False)
    
    # 检查是否为空
    if grouped_df.empty:
        st.warning("分组后数据为空")
        return
    
    # 确定显示列
    if '_display_symbol' in df_filled.columns:
        # 合并 _display_symbol
        merge_cols = group_by_cols + ['_display_symbol']
        grouped_df = grouped_df.merge(
            df_filled[merge_cols].drop_duplicates(),
            on=group_by_cols,
            how='left'
        )
        # 构建列顺序：用 _display_symbol 替换 exchange+symbol（已合并）
        column_order = ['_display_symbol']
        for col in group_by_cols:
            if col not in ['exchange', 'symbol']:  # 跳过已合并的列
                column_order.append(col)
        column_order.extend(['count', 'signal_info'])
    else:
        column_order = group_by_cols + ['symbol_name', 'count', 'signal_info']
    
    available_cols = [c for c in column_order if c in grouped_df.columns]
    
    # 显示标题
    if title:
        st.write(title)
    
    st.dataframe(
        grouped_df[available_cols],
        height=height,
        width='stretch',
        hide_index=True
    )


# ============================================================================
# 多视图模式显示函数
# ============================================================================
def display_signals_multiview(
    df: pd.DataFrame,
    height: int = 500,
    show_stats: bool = True,
    freq_col: str = 'freq',
) -> None:
    """
    以多视图模式显示信号数据（Symbol优先 + 信号优先 + 按周期分别显示）
    
    Args:
        df: 信号数据 DataFrame
        height: dataframe 显示高度
        show_stats: 是否显示统计信息
        freq_col: 周期列名
    """
    if df.empty:
        st.info("暂无数据")
        return
    
    # 显示统计信息
    if show_stats:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📊 标的数量", df['symbol'].nunique())
        with col2:
            st.metric("📈 信号总数", len(df))
    
    # 获取可用周期
    available_freqs = []
    if freq_col in df.columns:
        available_freqs = sort_freqs(df[freq_col].dropna().unique().tolist())
    
    # 构建 tabs：Symbol优先 + 信号优先 + 各周期
    tab_names = ["📊 Symbol优先", "📋 信号优先"] + [f"⏱️ {freq}" for freq in available_freqs]
    tabs = st.tabs(tab_names)
    
    # Symbol优先：以 symbol 为单位分组
    with tabs[0]:
        display_signals_compact(
            df,
            group_by_cols=['exchange', 'symbol'],
            include_freq=True,
            height=height,
        )
    
    # 信号优先：按 signal_name 分组
    with tabs[1]:
        display_signals_compact(
            df,
            group_by_cols=['exchange', 'symbol', 'signal_name'],
            include_freq=True,
            height=height,
        )
    
    # 按周期分别显示
    for i, freq in enumerate(available_freqs):
        with tabs[i + 2]:
            freq_df = df[df[freq_col] == freq].copy()
            if freq_df.empty:
                st.info(f"暂无 {freq} 周期的信号")
            else:
                st.write(f"**{freq} 周期信号数：{len(freq_df)}，涉及 {freq_df['symbol'].nunique()} 个标的**")
                display_signals_compact(
                    freq_df,
                    group_by_cols=['exchange', 'symbol', 'signal_name'],
                    include_freq=False,
                    height=height,
                )
