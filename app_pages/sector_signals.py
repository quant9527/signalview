"""Sector multi/signal analysis page (url_path=sector_signals)."""
from __future__ import annotations

import pandas as pd

import streamlit as st

from data import create_all_signals_columns
from utils import get_cached_data


def page_sector_signals() -> None:
    """Sector multi/signal analysis (url_path=sector_signals)."""
    st.set_page_config(layout="wide", page_title="Sector Signals")
    st.header("Sector Multi/Signal Analysis")

    df = get_cached_data(45)

    st.sidebar.subheader("Symbol List Filter")
    symbol_input = st.sidebar.text_area(
        "Enter symbols (comma-separated)",
        help='Enter symbols to filter, e.g., "AAPL,GOOGL,MSFT"',
    )

    symbol_list: list[str] = []
    if symbol_input:
        symbol_list = [s.strip() for s in symbol_input.split(",") if s.strip()]

    st.subheader("1. Signals for Given Symbol List")
    symbol_signals_df = (
        df[df["symbol"].isin(symbol_list)].copy() if symbol_list else pd.DataFrame()
    )

    if symbol_list:
        if not symbol_signals_df.empty:
            st.write(f"**Signals for symbols: {', '.join(symbol_list)}**")
            st.dataframe(
                symbol_signals_df[["signal_name", "signal_date", "symbol", "freq"]],
                width="stretch",
            )
            if "signal_date" in symbol_signals_df.columns:
                df_latest = symbol_signals_df.loc[
                    symbol_signals_df.groupby("symbol")["signal_date"].idxmax()
                ].copy()
                df_with_all_signals = create_all_signals_columns(
                    df_latest, symbol_signals_df, include_extra_info=True
                )
                st.write("**Signals with aggregated data:**")
                display_cols = [
                    "symbol", "signal_name", "signal_date",
                    "all_signals", "all_signals_count",
                ]
                available_cols = [
                    col for col in display_cols if col in df_with_all_signals.columns
                ]
                st.dataframe(
                    df_with_all_signals[available_cols], width="stretch"
                )
        else:
            st.info(f"No signals found for the given symbols: {', '.join(symbol_list)}")
    else:
        st.info("Enter symbols in the sidebar to filter signals")

    st.subheader("2. Signals with Exchange = 'em' or 'asindex'")
    exchange_signals_df = (
        df[(df["exchange"] == "em") | (df["exchange"] == "asindex")].copy()
        if "exchange" in df.columns else pd.DataFrame()
    )

    if not exchange_signals_df.empty:
        st.write("**Exchange 'em' or 'asindex' Signals:**")
        st.dataframe(
            exchange_signals_df[
                ["signal_name", "signal_date", "symbol", "freq", "exchange"]
            ],
            width="stretch",
        )
        if "signal_date" in exchange_signals_df.columns:
            df_latest = exchange_signals_df.loc[
                exchange_signals_df.groupby("symbol")["signal_date"].idxmax()
            ].copy()
            df_with_all_signals = create_all_signals_columns(
                df_latest, exchange_signals_df, include_extra_info=True
            )
            st.write("**Exchange signals with aggregated data:**")
            display_cols = [
                "symbol", "signal_name", "signal_date",
                "all_signals", "all_signals_count", "exchange",
            ]
            available_cols = [
                col for col in display_cols if col in df_with_all_signals.columns
            ]
            st.dataframe(
                df_with_all_signals[available_cols], width="stretch"
            )
    else:
        st.info("No signals with exchange = 'em' or 'asindex' found.")

    st.subheader("Summary")
    st.write(f"- Total signals in dataset: {len(df)}")
    st.write(
        f"- Signals for given symbol list: "
        f"{len(symbol_signals_df) if symbol_list else 0}"
    )
    st.write(f"- Exchange 'em' or 'asindex' signals: {len(exchange_signals_df)}")