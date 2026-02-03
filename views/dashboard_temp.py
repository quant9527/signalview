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

# Get current dashboard type from session state
dashboard_type = st.session_state.get('dashboard_type', 'as')

# Two columns layout
col1, col2 = st.columns(2)

with col1:
    st.subheader("Exchange & Time Controls")
    
    # Exchange selection
    st.markdown("**Select Exchange Type:**")
    ex_col1, ex_col2, ex_col3 = st.columns(3)
    with ex_col1:
        if st.button("AS", use_container_width=True, type="primary" if dashboard_type == 'as' else "secondary"):
            st.session_state['dashboard_type'] = 'as'
            st.rerun()

    with ex_col2:
        if st.button("BINANCE", use_container_width=True, type="primary" if dashboard_type == 'binance' else "secondary"):
            st.session_state['dashboard_type'] = 'binance'
            st.rerun()

    with ex_col3:
        if st.button("EM", use_container_width=True, type="primary" if dashboard_type == 'em' else "secondary"):
            st.session_state['dashboard_type'] = 'em'
            st.rerun()

    # Time Range selection (in the same column as exchange)
    st.markdown("**Select Time Range:**")
    time_range = st.selectbox(
        "Time Range",
        options=["Last 7 days", "Last 30 days", "Last 90 days", "Custom"],
        index=1,
        key="time_range",
        label_visibility="collapsed"
    )

with col2:
    st.subheader("Signal Selection")
    
    # Auto-set default signals based on dashboard type
    available_signals = df["signal_name"].dropna().unique().tolist()

    if dashboard_type == "em":
        default_signals = ["cmp_rebound"] if "cmp_rebound" in available_signals else []
    elif dashboard_type == "binance":
        # Binance specific signals
        binance_signals = ["nested_2bc_ma5ma10_2b", "nested_2bc_ma5ma10_1b"]
        default_signals = [sig for sig in binance_signals if sig in available_signals]
    else:
        # Default for AS and others
        default_signals = ["nested_2bc"] if "nested_2bc" in available_signals else []

    # Initialize session state for signal selections
    if 'selected_signals_cache' not in st.session_state:
        st.session_state.selected_signals_cache = {}

    # Use dashboard type as key to cache selections
    cache_key = f"signals_{dashboard_type}"

    # Set defaults if cache is empty or dashboard type changed
    if cache_key not in st.session_state.selected_signals_cache or not st.session_state.selected_signals_cache[cache_key]:
        st.session_state.selected_signals_cache[cache_key] = default_signals.copy()

    # Simple checkbox selection
    st.markdown("**Available Signals:**")
    current_selections = []

    # Display checkboxes for each signal
    for signal in available_signals:
        # Check if this signal should be selected by default
        is_default = signal in st.session_state.selected_signals_cache[cache_key]
        
        # Create checkbox with unique key per dashboard type
        checkbox_key = f"signal_checkbox_{dashboard_type}_{signal}"
        if st.checkbox(signal, value=is_default, key=checkbox_key):
            current_selections.append(signal)

    # Update cache with current selections
    st.session_state.selected_signals_cache[cache_key] = current_selections.copy()

    # Use selections from cache if current selection is empty
    selected_signals = current_selections if current_selections else st.session_state.selected_signals_cache[cache_key]

    # Final fallback
    if not selected_signals and default_signals:
        selected_signals = default_signals.copy()
        st.info(f"Using defaults: {', '.join(default_signals)}")

# Use first selected signal for display purposes
signal_name = selected_signals[0] if selected_signals else (available_signals[0] if available_signals else "Unknown")

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

# Display filter summary in a cleaner format
st.subheader(f"📋 {dashboard_type.upper()} Dashboard Results")

# Create a more organized filter display
filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    st.metric("📊 Exchange", dashboard_type.upper())

with filter_col2:
    signals_text = ", ".join(selected_signals) if selected_signals else "None Selected"
    st.metric("📈 Signals", f"{len(selected_signals)} selected")

with filter_col3:
    st.metric("⏰ Time Range", time_range)

# Show detailed signal list in expandable section
if selected_signals:
    with st.expander("🔍 Selected Signals Details", expanded=False):
        for i, signal in enumerate(selected_signals, 1):
            st.write(f"{i}. {signal}")
else:
    st.info("No signals selected - showing all available signals")


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

# Display data table with view mode selection
st.subheader("📋 Signal Data")

# Add view mode selection
view_mode = st.radio(
    "View mode",
    options=["Compact", "Detail"],
    index=0,
    horizontal=True
)

if not filtered_df.empty:
    if view_mode == "Detail":
        # Detail view - show all available columns
        display_columns = [
            'symbol', 'symbol_name', 'symbol_id', 'exchange', 'signal_name',
            'signal_date', 'freq', 'price', 'score', 'reason'
        ]
        
        # Only include columns that exist in the dataframe
        available_columns = [col for col in display_columns if col in filtered_df.columns]
        
        # Sort by signal date (most recent first)
        filtered_df_sorted = filtered_df.sort_values('signal_date', ascending=False)
        
        # Create a combined symbol display for better readability
        if 'symbol' in filtered_df_sorted.columns and 'symbol_name' in filtered_df_sorted.columns:
            filtered_df_sorted['_display_symbol'] = filtered_df_sorted.apply(
                lambda row: f"{row['symbol']} - {row['symbol_name']}", axis=1
            )
            
            # Prepare display columns
            display_cols = []
            for col in available_columns:
                if col == 'symbol':
                    display_cols.append('_display_symbol')
                elif col != 'symbol_name':  # Skip symbol_name since it's in the combined column
                    display_cols.append(col)
            display_df = filtered_df_sorted[display_cols]
        else:
            display_df = filtered_df_sorted[available_columns]
        
        # Display the dataframe
        st.dataframe(
            display_df,
            height=600,
            width='stretch'
        )
        
    else:
        # Compact view - grouped by symbol and signal_name
        # Fill NaN and empty strings to avoid groupby dropping them
        filtered_df_filled = filtered_df.copy()
        filtered_df_filled['exchange'] = filtered_df_filled['exchange'].replace('', pd.NA).fillna('(No Exchange)')
        filtered_df_filled['symbol'] = filtered_df_filled['symbol'].replace('', pd.NA).fillna('(No Symbol)')
        filtered_df_filled['signal_name'] = filtered_df_filled['signal_name'].replace('', pd.NA).fillna('(No Signal)')
        
        grouped_df = filtered_df_filled.sort_values('signal_date', ascending=False).groupby(['exchange', 'symbol', 'signal_name'], as_index=False).apply(
            lambda group: pd.Series({
                'symbol_name': group['symbol_name'].iloc[0] if 'symbol_name' in group.columns else '''',
    )
else:
    st.warning("No signal data found matching the criteria")