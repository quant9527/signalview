import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Add custom CSS to handle long option names
st.markdown("""
<style>
    /* Increase width and handle long text in select boxes */
    div[data-baseweb="select"] > div {
        min-width: 300px !important;
    }
    
    /* Handle long text in multiselect dropdown */
    div[data-baseweb="select"] div[class*="multiValue"] {
        max-width: none !important;
    }
    
    /* Ensure full text visibility */
    div[data-baseweb="select"] div[class*="option"] {
        white-space: normal !important;
        word-break: break-all !important;
    }
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Dashboard", layout="wide")

# Page title
st.title("📊 Signal Dashboard")

# Get data from session state
if 'df' not in st.session_state:
    st.warning("No data available. Please load data first.")
    st.stop()

df = st.session_state.df

# Get current dashboard type from session state FIRST
dashboard_type = st.session_state.get('dashboard_type', 'as')

# First row: Dashboard type and Signal Names selection (side by side)

    available_signals = df["signal_name"].dropna().unique().tolist()

    # Final fallback
    if not selected_signals and default_signals:
        selected_signals = default_signals.copy()
        st.info(f"Using defaults: {', '.join(default_signals)}")


# Use first selected signal for display purposes
signal_name = selected_signals[0] if selected_signals else (available_signals[0] if available_signals else "Unknown")

# Third row: Time range selection
st.subheader("Select Time Range")
time_range = st.selectbox(
    "Time Range",
    options=["Last 7 days", "Last 30 days", "Last 90 days", "Custom"],
    index=1,
    key="time_range",
    label_visibility="collapsed"
)

# Filter data based on time range
if time_range == "Last 7 days":
    days = 7
elif time_range == "Last 30 days":
    days = 30
elif time_range == "Last 90 days":
    days = 90
else:
    # Custom date range
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
    with col_end:
        end_date = st.date_input("End Date", value=datetime.now())
    days = None

# Filter data
filtered_df = df.copy()

# Filter by dashboard type (exchange)
if dashboard_type == "as":
    filtered_df = filtered_df[filtered_df["exchange"] == "as"] if "exchange" in filtered_df.columns else filtered_df
elif dashboard_type == "binance":
    filtered_df = filtered_df[filtered_df["exchange"] == "binance"] if "exchange" in filtered_df.columns else filtered_df
elif dashboard_type == "em":
    filtered_df = filtered_df[filtered_df["exchange"] == "em"] if "exchange" in filtered_df.columns else filtered_df

# Filter by selected signal names (multiselect)
if selected_signals:
    filtered_df = filtered_df[filtered_df["signal_name"].isin(selected_signals)]
else:
    # If no signals selected, show all (or handle as needed)
    filtered_df = filtered_df.head(0)  # Show empty if no selection

# Filter by time range
if days:
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_df = filtered_df[pd.to_datetime(filtered_df["signal_date"]) >= cutoff_date]
else:
    # Use custom date range
    filtered_df = filtered_df[
        (pd.to_datetime(filtered_df["signal_date"]).dt.date >= start_date) &
        (pd.to_datetime(filtered_df["signal_date"]).dt.date <= end_date)
    ]

# Display filter summary
selected_signals_display = ", ".join(selected_signals) if selected_signals else "None"
st.subheader(f"📋 {dashboard_type.upper()} - Multiple Signals Data")
st.info(f"Filters: Type={dashboard_type}, Signals=[{selected_signals_display}], Time Range={time_range}")

# Display data statistics
stat_col1, stat_col2, stat_col3 = st.columns(3)

with stat_col1:
    st.metric("Total Signals", len(filtered_df))

with stat_col2:
    unique_symbols = filtered_df["symbol"].nunique() if "symbol" in filtered_df.columns else 0
    st.metric("Unique Symbols", unique_symbols)

with stat_col3:
    date_range = f"{filtered_df['signal_date'].min()[:10]} to {filtered_df['signal_date'].max()[:10]}" if "signal_date" in filtered_df.columns and len(filtered_df) > 0 else "N/A"
    st.metric("Date Range", date_range)

# Display signal data table
if not filtered_df.empty:
    st.dataframe(
        filtered_df,
        height=600,
        width='stretch'
    )
    
    # Export functionality
    csv = filtered_df.to_csv(index=False)
    st.download_button(
        label="📥 Export CSV",
        data=csv,
        file_name=f"dashboard_{dashboard_type}_{signal_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
else:
    st.warning("No signal data found matching the criteria")