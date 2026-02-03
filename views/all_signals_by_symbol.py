import pandas as pd
import streamlit as st
from data import create_all_signals_columns


st.header("All Signals Grouped by Symbol")

df = st.session_state.df

# Apply shared signal selection filter if available
if "selected_signals" in st.session_state and st.session_state["selected_signals"]:
    df = df[df["signal_name"].isin(st.session_state["selected_signals"])]

# Ensure required columns exist
required_cols = ["symbol", "signal_name", "signal_date"]
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    st.error(f"Missing required columns: {missing_cols}")
    st.stop()

# Group signals by symbol
if "symbol" in df.columns and not df.empty:
    # Sort the dataframe by symbol and signal_date for consistent display
    df_sorted = df.sort_values(["symbol", "signal_date"], ascending=[True, False])

    # Get the latest record for each symbol
    df_latest = df_sorted.loc[df_sorted.groupby("symbol")["signal_date"].idxmax()].copy()

    # Create all_signals and all_signals_count columns using the reusable function
    df_latest = create_all_signals_columns(df_latest, df_sorted, include_extra_info=True)

    # Create a summary dataframe with the required information
    summary_df = df_latest[['symbol', 'signal_name', 'signal_date', 'all_signals', 'all_signals_count']].copy()
    summary_df = summary_df.rename(columns={
        'signal_name': 'latest_signal',
        'signal_date': 'latest_signal_date',
        'all_signals_count': 'total_signals'
    })

    # Sort by symbol
    summary_df = summary_df.sort_values("symbol", ascending=True)
    
    # Display options
    show_symbol_details = st.expander("Show/Hide Symbol Details", expanded=True)
    
    with show_symbol_details:
        # Allow user to select specific symbols to display
        all_symbols = sorted(summary_df["symbol"].astype(str).unique())
        selected_symbols = st.multiselect(
            "Select symbols to display (leave empty to show all)",
            options=all_symbols,
            default=[]
        )
        
        if selected_symbols:
            filtered_summary_df = summary_df[summary_df["symbol"].isin(selected_symbols)]
        else:
            filtered_summary_df = summary_df
    
    # Display grouped signals
    st.subheader(f"All Signals Grouped by Symbol ({len(filtered_summary_df)} symbols)")
    
    if not filtered_summary_df.empty:
        # Display as dataframe with expandable all_signals column
        display_cols = ["symbol", "latest_signal", "latest_signal_date", "total_signals"]
        display_df = filtered_summary_df[display_cols].copy()
        
        # Format the date column
        display_df["latest_signal_date"] = pd.to_datetime(display_df["latest_signal_date"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Show the summary table
        st.dataframe(display_df, width="stretch", height=400)
        
        # Show detailed signals for each symbol
        st.subheader("Detailed Signals by Symbol")
        for _, row in filtered_summary_df.iterrows():
            with st.expander(f"Signals for {row['symbol']}", expanded=False):
                st.write(f"**Symbol:** {row['symbol']}")
                st.write(f"**Total Signals:** {row['total_signals']}")
                st.write(f"**Latest Signal:** {row['latest_signal']} (Date: {row['latest_signal_date']})")
                st.write("**All Signals (chronological order):**")
                # Format the signals nicely
                signals_list = row["all_signals"].split("\n") if row["all_signals"] else []
                for signal in signals_list:
                    if signal.strip():
                        st.text(f"  • {signal}")
    else:
        st.info("No signals found for the selected criteria.")
    
    # Additional statistics
    st.subheader("Summary Statistics")
    if not summary_df.empty:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Symbols", len(summary_df))
        with col2:
            st.metric("Total Signals", len(df))
        with col3:
            avg_signals = summary_df["total_signals"].mean() if "total_signals" in summary_df.columns else 0
            st.metric("Avg. Signals per Symbol", f"{avg_signals:.1f}")
    
    # Export option
    csv = summary_df.to_csv(index=False)
    st.download_button(
        "Export All Signals by Symbol (CSV)", 
        csv, 
        file_name="all_signals_by_symbol.csv"
    )
else:
    st.warning("No symbols found in the data.")