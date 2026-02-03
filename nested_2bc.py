import altair as alt
import pandas as pd
import streamlit as st
from data import create_all_signals_columns, calculate_performance_metrics


st.header("Nested 2bc Signals")

df = st.session_state.df

# Section 1: Large frequency signals with nested_2bc name pattern and symbol ending with _1b
st.subheader("1. nested_2bc_1b")

# Filter for signal names that start with 'nested_2bc' AND symbol ends with '_1b'
nested_2bc_1b_df = df[
    (df['signal_name'].str.startswith('nested_2bc', na=False)) &
    (df['signal_name'].str.endswith('_1b', na=False))
].copy()

if nested_2bc_1b_df.empty:
    st.warning("No 'nested_2bc' signals with symbol ending '_1b' found in the data.")
else:
    # Define large frequency categories
    large_freqs = ['1h', '2h', '1d', '1w', '1M']

    # Filter for large frequency signals
    large_freq_1b_df = nested_2bc_1b_df[nested_2bc_1b_df['freq'].isin(large_freqs)] if 'freq' in nested_2bc_1b_df.columns else pd.DataFrame()

    if not large_freq_1b_df.empty:
        st.write("**Large Frequency Signals (1h, 2h, 1d, 1w, 1M) with symbol ending _1b:**")
        st.dataframe(large_freq_1b_df[['signal_name', 'signal_date', 'symbol', 'freq']], width='stretch')

        # Apply create_all_signals_columns and calculate_performance_metrics

        # Group by symbol to get latest record for each symbol
        if 'signal_date' in large_freq_1b_df.columns:
            df_latest = large_freq_1b_df.loc[large_freq_1b_df.groupby("symbol")["signal_date"].idxmax()].copy()

            # Apply the reusable functions
            df_with_all_signals = create_all_signals_columns(df_latest, large_freq_1b_df)

            # Only apply performance metrics if price data exists
            if 'price' in df_with_all_signals.columns:
                df_with_metrics = calculate_performance_metrics(df_with_all_signals)
                st.write("**Signals with aggregated data and performance metrics:**")
                display_cols = ['symbol', 'signal_name', 'signal_date', 'all_signals', 'all_signals_count', 'pct_change', 'Change vs signal(%)']
                available_cols = [col for col in display_cols if col in df_with_metrics.columns]
                st.dataframe(df_with_metrics[available_cols], width='stretch')
            else:
                st.write("**Signals with aggregated data:**")
                display_cols = ['symbol', 'signal_name', 'signal_date', 'all_signals', 'all_signals_count']
                available_cols = [col for col in display_cols if col in df_with_all_signals.columns]
                st.dataframe(df_with_all_signals[available_cols], width='stretch')
    else:
        st.info("No large frequency signals (1h, 2h, 1d, 1w, 1M) with symbol ending '_1b' found for nested_2bc.")

# Section 2: Exchange = 'em' signals
st.subheader("2. nested_2bc Signals with Exchange = 'em'")

# Filter for signal names that start with 'nested_2bc'
nested_2bc_df = df[df['signal_name'].str.startswith('nested_2bc', na=False)].copy()

# Filter for exchange = 'em'
em_signals_df = nested_2bc_df[nested_2bc_df['exchange'] == 'em'] if 'exchange' in nested_2bc_df.columns else pd.DataFrame()

if not em_signals_df.empty:
    st.write("**Exchange 'em' Signals:**")
    st.dataframe(em_signals_df[['signal_name', 'signal_date', 'symbol', 'freq', 'exchange']], width='stretch')

    # Chart for exchange 'em' signals over time
    chart_df = em_signals_df.copy()
    chart_df['signal_date'] = pd.to_datetime(chart_df['signal_date'])
    chart = (
        alt.Chart(chart_df)
        .mark_circle(size=60)
        .encode(
            x=alt.X('signal_date:T', title='Date', axis=alt.Axis(format="%Y-%m-%d %H:%M:%S")),
            y=alt.Y('signal_name:N', title='Signal Name'),
            color=alt.Color('freq:N', title='Frequency'),
            tooltip=[
                alt.Tooltip('signal_date:T', title='Date', format="%Y-%m-%d %H:%M:%S"),
                'signal_name:N',
                'symbol:N',
                'freq:N',
                'exchange:N'
            ]
        )
        .properties(height=400)
    )
    st.altair_chart(chart, width='stretch')
else:
    st.info("No signals with exchange = 'em' found for nested_2bc.")

# Additional summary
st.subheader("Summary")
st.write(f"- Total nested_2bc signals: {len(nested_2bc_df)}")
st.write(f"- Nested_2bc signals with symbol ending '_1b': {len(nested_2bc_1b_df)}")
st.write(f"- Large frequency nested_2bc signals with symbol ending '_1b': {len(large_freq_1b_df) if 'large_freq_1b_df' in locals() else 0}")
st.write(f"- Exchange 'em' signals: {len(em_signals_df)}")