import pandas as pd
import streamlit as st
from data import create_all_signals_columns


st.header("Sector Multi/Signal Analysis")

df = st.session_state.df

# Sidebar for symbol input
st.sidebar.subheader("Symbol List Filter")
symbol_input = st.sidebar.text_area("Enter symbols (comma-separated)",
                                   help='Enter symbols to filter, e.g., "AAPL,GOOGL,MSFT"')

symbol_list = []
if symbol_input:
    # Split by comma and clean up whitespace
    symbol_list = [s.strip() for s in symbol_input.split(",") if s.strip()]

# Section 1: Signals for given symbol list
st.subheader("1. Signals for Given Symbol List")

if symbol_list:
    # Filter for signals with symbols in the provided list
    symbol_signals_df = df[df["symbol"].isin(symbol_list)].copy()
    
    if not symbol_signals_df.empty:
        st.write(f"**Signals for symbols: {', '.join(symbol_list)}**")
        st.dataframe(symbol_signals_df[["signal_name", "signal_date", "symbol", "freq"]], width="stretch")
        
        # Apply create_all_signals_columns function
        if "signal_date" in symbol_signals_df.columns:
            df_latest = symbol_signals_df.loc[symbol_signals_df.groupby("symbol")["signal_date"].idxmax()].copy()
            df_with_all_signals = create_all_signals_columns(df_latest, symbol_signals_df, include_extra_info=True)
            
            st.write("**Signals with aggregated data:**")
            display_cols = ["symbol", "signal_name", "signal_date", "all_signals", "all_signals_count"]
            available_cols = [col for col in display_cols if col in df_with_all_signals.columns]
            st.dataframe(df_with_all_signals[available_cols], width="stretch")
    else:
        st.info(f"No signals found for the given symbols: {', '.join(symbol_list)}")
else:
    st.info("Enter symbols in the sidebar to filter signals")

# Section 2: Exchange = 'em' or 'asindex' signals
st.subheader("2. Signals with Exchange = 'em' or 'asindex'")

# Filter for exchange = 'em' or 'asindex'
exchange_signals_df = df[
    (df["exchange"] == "em") | (df["exchange"] == "asindex")
].copy() if "exchange" in df.columns else pd.DataFrame()

if not exchange_signals_df.empty:
    st.write("**Exchange 'em' or 'asindex' Signals:**")
    st.dataframe(exchange_signals_df[["signal_name", "signal_date", "symbol", "freq", "exchange"]], width="stretch")
    
    # Apply create_all_signals_columns function
    if "signal_date" in exchange_signals_df.columns:
        df_latest = exchange_signals_df.loc[exchange_signals_df.groupby("symbol")["signal_date"].idxmax()].copy()
        df_with_all_signals = create_all_signals_columns(df_latest, exchange_signals_df, include_extra_info=True)
        
        st.write("**Exchange signals with aggregated data:**")
        display_cols = ["symbol", "signal_name", "signal_date", "all_signals", "all_signals_count", "exchange"]
        available_cols = [col for col in display_cols if col in df_with_all_signals.columns]
        st.dataframe(df_with_all_signals[available_cols], width="stretch")
else:
    st.info("No signals with exchange = 'em' or 'asindex' found.")

# Summary
st.subheader("Summary")
st.write(f"- Total signals in dataset: {len(df)}")
st.write(f"- Signals for given symbol list: {len(symbol_signals_df) if symbol_list and 'symbol_signals_df' in locals() else 0}")
st.write(f"- Exchange 'em' or 'asindex' signals: {len(exchange_signals_df)}")