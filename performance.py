import pandas as pd
import streamlit as st
from data import create_all_signals_columns, calculate_performance_metrics, get_latest_market
from constants import EXCHANGE_AS, EXCHANGE_EM, EXCHANGE_THS, EXCHANGE_BINANCE, EXCHANGE_OPTIONS


def _find_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


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

if exchange_option == EXCHANGE_EM:
    import akshare as ak
    if st.button("Refresh latest prices"):
        st.cache_data.clear()
        st.rerun()
    
    @st.cache_data(ttl=600)
    def get_em_board_data():
        concept_df = ak.stock_board_concept_name_em()
        industry_df = ak.stock_board_industry_name_em()
        concept_df = concept_df.rename(columns={"板块代码": "code", "板块名称": "name", "最新价": "price", "涨跌幅": "change_percent"})
        industry_df = industry_df.rename(columns={"板块代码": "code", "板块名称": "name", "最新价": "price", "涨跌幅": "change_percent"})
        return pd.concat([concept_df, industry_df], ignore_index=True)
    
    with st.spinner("Fetching latest market prices..."):
        market_df = get_em_board_data()
elif exchange_option == EXCHANGE_THS:
    import akshare as ak
    if st.button("Refresh latest prices"):
        st.cache_data.clear()
        st.rerun()
    
    @st.cache_data(ttl=600)
    def get_ths_board_data():
        board_df = ak.stock_board_industry_summary_ths()
        return board_df.rename(columns={"代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_percent"})
    
    with st.spinner("Fetching latest market prices..."):
        market_df = get_ths_board_data()
elif exchange_option == EXCHANGE_BINANCE:
    st.warning("Binance exchange not yet implemented")
    st.stop()
else:
    source_param = "spot_em"
    if st.button("Refresh latest prices"):
        get_latest_market.clear()
        st.rerun()
    market_df = get_latest_market(source_param)
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

market_df2["symbol_market"] = market_df2["symbol_market"].astype(str).str.zfill(6)
df_latest["symbol"] = df_latest["symbol"].astype(str).str.zfill(6)

merged = pd.merge(df_latest, market_df2, left_on="symbol", right_on="symbol_market", how="left")

# Debug: check merge results
if merged["latest_price"].isna().all():
    st.warning(f"⚠️ No price matches found. Sample symbols from signals: {df_latest['symbol'].head(5).tolist()} | Sample codes from market: {market_df2['symbol_market'].head(5).tolist()}")
    st.info(f"Exchange: {exchange_option} | Signal symbols are stock codes, but exchange may use different code format (e.g., board codes for EM/THS)")
    
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
    rename_map["market_pct_change"] = "Market change (%)"
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

csv = display_df[cols_available].to_csv(index=False)
st.download_button("Export CSV", csv, file_name="signal_performance_vs_current.csv")