import pandas as pd
import streamlit as st
from data import (
    create_all_signals_columns,
    calculate_performance_metrics,
    get_latest_market_for_exchange,
    get_latest_market,
    _get_latest_market_em,
    _get_latest_market_ths,
)
from constants import EXCHANGE_AS, EXCHANGE_EM, EXCHANGE_THS, EXCHANGE_BINANCE, EXCHANGE_OPTIONS


st.header("Signal Performance vs Current Prices — Ranking")

df_full = st.session_state.df.copy()

# Get main signal from session state (set by parent page)
main_signal = st.session_state.get("main_signal", "")

# Get all available signals
all_signals = df_full['signal_name'].dropna().unique()

# Default signals based on main_signal prefix
if main_signal:
    default_signals = [s for s in all_signals if s.startswith(main_signal)]
else:
    default_signals = []

# Multi-select for all signals
selected_signals = st.multiselect(
    "Select signals",
    options=all_signals,
    default=default_signals,
)

# Filter data based on selected signals from multiselect
if selected_signals:
    df = df_full[df_full['signal_name'].isin(selected_signals)].copy()
else:
    st.warning("Please select at least one signal")
    st.stop()

default_exchange = st.session_state.get("exchange", EXCHANGE_AS)
default_index = EXCHANGE_OPTIONS.index(default_exchange) if default_exchange in EXCHANGE_OPTIONS else 0

exchange_option = st.selectbox(
    "Exchange",
    options=EXCHANGE_OPTIONS,
    index=default_index,
    help="Select exchange/market type",
)

# Filter by exchange if the column exists
if 'exchange' in df.columns:
    df = df[df['exchange'] == exchange_option].copy()

# Display signal and symbol counts after both selections
total_signals = len(selected_signals)
total_symbols = df['symbol'].nunique()
total_records = len(df)
st.info(f"📊 Selected signals: {total_signals} | Unique symbols: {total_symbols} | Total records: {total_records}")

if exchange_option == EXCHANGE_BINANCE:
    st.warning("Binance exchange not yet implemented")
    st.stop()

# 最新价数据源：所有 exchange 都提供选择（参考 performance_nested_2bc 等）
symbols_for_latest = None
source_as = "spot_em"
if exchange_option == EXCHANGE_AS:
    price_sources = [
        ("akshare (东方财富)", "spot_em"),
        ("Flight (quant-lab)", "flight"),
    ]
    help_text = "akshare 拉全市场；Flight 仅拉当前筛选出的标的（需 quant-lab 服务运行在 127.0.0.1:50001）"
elif exchange_option == EXCHANGE_EM:
    price_sources = [
        ("akshare (东方财富 概念/行业板块)", "spot_em"),
        ("Flight (quant-lab)", "flight"),
    ]
    help_text = "akshare 失败时自动用 Flight 兜底；也可直接选 Flight（需 quant-lab 服务）"
elif exchange_option == EXCHANGE_THS:
    price_sources = [
        ("akshare (同花顺板块)", "spot_em"),
        ("Flight (quant-lab)", "flight"),
    ]
    help_text = "akshare 失败时自动用 Flight 兜底；也可直接选 Flight（需 quant-lab 服务）"
else:
    price_sources = [(f"当前 exchange={exchange_option}", "spot_em")]
    help_text = ""

source_labels = [p[0] for p in price_sources]
price_source_label = st.selectbox(
    "最新价数据源",
    options=source_labels,
    index=0,
    help=help_text,
)
source_as = price_sources[source_labels.index(price_source_label)][1]
# 所有 exchange 都传 symbols，供 Flight 兜底使用
symbols_for_latest = df["symbol"].astype(str).str.strip().str.replace(r"\.[A-Za-z]+$", "", regex=True).str.zfill(6).unique().tolist()

if st.button("Refresh latest prices"):
    get_latest_market.clear()
    _get_latest_market_em.clear()
    _get_latest_market_ths.clear()
    st.rerun()

market_df = get_latest_market_for_exchange(exchange_option, symbols=symbols_for_latest, source_as=source_as)
if market_df.empty:
    st.info("Failed to fetch latest market data. Try again later or check network/akshare")
    st.stop()

# Use standardized column names
code_col = "code"
price_col = "price"
change_col = "change_percent"

if code_col not in market_df.columns or price_col not in market_df.columns:
    st.error("Market data format not supported: required columns not found after normalization")
    st.warning(f"Available columns: {', '.join(market_df.columns.tolist())}")
    st.stop()

# Filter out records where freq ends with "m" and signal_name starts with "yd_"
df_filtered = df.copy()
if "freq" in df_filtered.columns and "signal_name" in df_filtered.columns:
    mask = ~((df_filtered["freq"].astype(str).str.endswith("m", na=False)) |
             (df_filtered["signal_name"].astype(str).str.startswith("yd_", na=False)))
    df_filtered = df_filtered[mask]

# Get the latest record for each symbol from the filtered data
df_latest = df_filtered.loc[df_filtered.groupby("symbol")["signal_date"].idxmax()].copy()

# Create a column with all signals for each symbol, ordered by date (descending)
# Use df_full for collecting all signals, not just the main signal
df_full_filtered = df_full.copy()
if "freq" in df_full_filtered.columns and "signal_name" in df_full_filtered.columns:
    mask = ~((df_full_filtered["freq"].astype(str).str.endswith("m", na=False)) |
             (df_full_filtered["signal_name"].astype(str).str.startswith("yd_", na=False)))
    df_full_filtered = df_full_filtered[mask]

df_latest = create_all_signals_columns(df_latest, df_full_filtered)

# Prepare market data columns
market_cols = [code_col, price_col]
if change_col in market_df.columns:
    market_cols.append(change_col)
market_df2 = market_df[market_cols].copy()
market_df2 = market_df2.rename(columns={code_col: "symbol_market", price_col: "latest_price"})
if change_col in market_df.columns:
    market_df2 = market_df2.rename(columns={change_col: "market_pct_change"})

# 统一为可比较的代码格式：去掉 sh/sz 前缀、.SH/.SZ 后缀，再补零到 6 位（东方财富/新浪/Flight 一致）
def _normalize_symbol(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    # 新浪等：去掉 sh/sz 前缀（不区分大小写）
    s = s.str.replace(r"^[sS][hH]|^[sS][zZ]", "", regex=True)
    # 去掉 .SH / .SZ / .BJ 等后缀
    s = s.str.replace(r"\.[A-Za-z]+$", "", regex=True)
    s = s.str.replace(r"^\s+|\s+$", "", regex=True)
    return s.str.zfill(6)

market_df2["symbol_market"] = _normalize_symbol(market_df2["symbol_market"].copy())
# A 股(as)时只保留沪市/深市 6 位代码，排除北交所 bj 等前缀
if exchange_option == EXCHANGE_AS:
    market_df2 = market_df2[market_df2["symbol_market"].str.match(r"^\d{6}$", na=False)].copy()

df_latest["symbol_normalized"] = _normalize_symbol(df_latest["symbol"].copy())

merged = pd.merge(df_latest, market_df2, left_on="symbol_normalized", right_on="symbol_market", how="left")

# Debug: 无匹配时给出可操作的排查信息
if merged["latest_price"].isna().all():
    sample_signals = df_latest["symbol"].astype(str).head(10).tolist()
    sample_normalized = df_latest["symbol_normalized"].head(10).tolist()
    sample_market = market_df2["symbol_market"].head(10).tolist()
    st.warning(
        f"⚠️ No price matches found.\n\n"
        f"**Signal symbols (raw):** `{sample_signals}`\n\n"
        f"**Signal symbols (normalized to 6-digit):** `{sample_normalized}`\n\n"
        f"**Market codes (sample):** `{sample_market}`\n\n"
        f"Exchange: `{exchange_option}`. For A-share (as), market data is 6-digit stock codes; "
        f"if your DB stores symbols with suffix (e.g. 600519.SH), they are now normalized. "
        f"If still no match, check that symbols are A-share codes and exchange is 'as'."
    )
    
# Calculate performance metrics using the reusable function
merged = calculate_performance_metrics(merged)

show_na = st.checkbox("Include records without latest price", value=True)
sort_order = st.selectbox("Sort by signal date order", options=["Descending", "Ascending"], index=0)
ascending = True if sort_order == "Ascending" else False

display_df = merged.copy()
if not show_na:
    display_df = display_df[display_df["latest_price"].notna() & display_df["signal_price"].notna()]

display_df = display_df.sort_values("signal_date", ascending=ascending)

cols = ["symbol", "symbol_name", "pct_change", "market_pct_change", "signal_date", "signal_name", "all_signals", "all_signals_count", "signal_price", "latest_price"]
cols_available = [c for c in cols if c in display_df.columns]

display_show = display_df[cols_available].copy()

rename_map = {}
if "market_pct_change" in display_show.columns:
    rename_map["market_pct_change"] = "当日涨幅 (%)"
if "all_signals" in display_show.columns:
    rename_map["all_signals"] = "All Signals (by date)"
if "all_signals_count" in display_show.columns:
    rename_map["all_signals_count"] = "All Signals Count"

display_show = display_show.rename(columns=rename_map)

desired_front = ["symbol","symbol_name","pct_change"]
if "all_signals" in display_show.columns:
    desired_front.append("all_signals")
if "all_signals_count" in display_show.columns:
    desired_front.append("all_signals_count")
other_cols = [c for c in display_show.columns if c not in desired_front]
display_show = display_show[desired_front + other_cols]

st.dataframe(display_show, width="stretch")