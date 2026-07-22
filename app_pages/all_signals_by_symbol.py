"""All signals grouped by symbol page (url_path=all_signals_by_symbol)."""
from __future__ import annotations

import pandas as pd

import streamlit as st

from data import create_all_signals_columns
from utils import get_cached_data


def page_all_signals_by_symbol() -> None:
    """All signals grouped by symbol (url_path=all_signals_by_symbol)."""
    st.set_page_config(layout="wide", page_title="All Signals by Symbol")
    st.header("All Signals Grouped by Symbol")

    df = get_cached_data(45)

    # Apply shared signal selection filter if available
    if "selected_signals" in st.session_state and st.session_state["selected_signals"]:
        df = df[df["signal_name"].isin(st.session_state["selected_signals"])]

    required_cols = ["symbol", "signal_name", "signal_date"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        st.error(f"Missing required columns: {missing_cols}")
        st.stop()

    if "symbol" in df.columns and not df.empty:
        df_sorted = df.sort_values(["symbol", "signal_date"], ascending=[True, False])
        df_latest = df_sorted.loc[
            df_sorted.groupby("symbol")["signal_date"].idxmax()
        ].copy()
        df_latest = create_all_signals_columns(
            df_latest, df_sorted, include_extra_info=True
        )

        summary_df = df_latest[
            ['symbol', 'signal_name', 'signal_date', 'all_signals', 'all_signals_count']
        ].copy()
        summary_df = summary_df.rename(columns={
            'signal_name': 'latest_signal',
            'signal_date': 'latest_signal_date',
            'all_signals_count': 'total_signals',
        })
        summary_df = summary_df.sort_values("symbol", ascending=True)

        show_symbol_details = st.expander("Show/Hide Symbol Details", expanded=True)
        with show_symbol_details:
            all_symbols = sorted(summary_df["symbol"].astype(str).unique())
            selected_symbols = st.multiselect(
                "Select symbols to display (leave empty to show all)",
                options=all_symbols,
                default=[],
            )
            if selected_symbols:
                filtered_summary_df = summary_df[
                    summary_df["symbol"].isin(selected_symbols)
                ]
            else:
                filtered_summary_df = summary_df

        st.subheader(
            f"All Signals Grouped by Symbol ({len(filtered_summary_df)} symbols)"
        )
        if not filtered_summary_df.empty:
            display_cols = [
                "symbol", "latest_signal", "latest_signal_date", "total_signals"
            ]
            display_df = filtered_summary_df[display_cols].copy()
            display_df["latest_signal_date"] = pd.to_datetime(
                display_df["latest_signal_date"]
            ).dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(display_df, width="stretch", height=400)

            st.subheader("Detailed Signals by Symbol")
            for _, row in filtered_summary_df.iterrows():
                with st.expander(
                    f"Signals for {row['symbol']}", expanded=False
                ):
                    st.write(f"**Symbol:** {row['symbol']}")
                    st.write(f"**Total Signals:** {row['total_signals']}")
                    st.write(
                        f"**Latest Signal:** {row['latest_signal']} "
                        f"(Date: {row['latest_signal_date']})"
                    )
                    st.write("**All Signals (chronological order):**")
                    signals_list = (
                        row["all_signals"].split("\n") if row["all_signals"] else []
                    )
                    for signal in signals_list:
                        if signal.strip():
                            st.text(f"  • {signal}")
        else:
            st.info("No signals found for the selected criteria.")

        st.subheader("Summary Statistics")
        if not summary_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Symbols", len(summary_df))
            with col2:
                st.metric("Total Signals", len(df))
            with col3:
                avg_signals = (
                    summary_df["total_signals"].mean()
                    if "total_signals" in summary_df.columns else 0
                )
                st.metric("Avg. Signals per Symbol", f"{avg_signals:.1f}")
    else:
        st.warning("No symbols found in the data.")