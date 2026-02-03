import pandas as pd
import streamlit as st
from data import create_all_signals_columns


def render_nested_2bc(df: pd.DataFrame):
    st.header("Daily Buy Signals")

    # Find all available dates with signals
    if "signal_date" not in df.columns or df["signal_date"].dropna().empty:
        st.warning("No signal dates available in the data.")
        return

    # Get all unique dates and find the latest
    all_dates = sorted(df["signal_date"].dt.date.unique(), reverse=True)

    # Date selector - defaults to the latest available date
    selected_date = st.selectbox(
        "Select Date",
        options=all_dates,
        format_func=lambda x: x.strftime("%Y-%m-%d"),
        index=0  # Default to the first (latest) date
    )

    selected_date_str = selected_date.strftime("%Y-%m-%d")

    st.subheader(f"Daily Buy Signals for {selected_date_str}")

    # First, find records in df that have main signals to get df1
    # Identify main strategy signals (signal_name starts with "nested_2bc" and freq is 1h, 2h, 1d, or 1w)
    # Handle NaN values properly
    signal_name_mask = df["signal_name"].str.startswith("nested_2bc", na=False)
    freq_mask = df["freq"].isin(["1h", "2h", "1d", "1w"])
    main_strategy_mask = signal_name_mask & freq_mask

    # Get df1 with all main strategy signals within 10 days before the selected date (inclusive)
    date_range_start = pd.to_datetime(selected_date) - pd.Timedelta(days=10)
    df1 = df[
        (df["signal_date"].dt.date >= date_range_start.date()) &
        (df["signal_date"].dt.date <= selected_date) &
        main_strategy_mask
    ].copy()

    if df1.empty:
        st.info(f"No main strategy signals (nested_2bc with freq 1h/2h/1d/1w) found in the date range {date_range_start.date()} to {selected_date_str}")
        return

    # Get the latest main strategy signal date for each symbol in the date range
    df1_latest = df1.loc[df1.groupby("symbol")["signal_date"].idxmax()].copy()
    main_strategy_symbols = df1_latest["symbol"].unique()
    main_strategy_dates = df1_latest.set_index("symbol")["signal_date"]

    # Now filter for signals on the selected date for symbols that had main signals
    selected_date_signals = df[
        (df["signal_date"].dt.date == selected_date) &
        (df["symbol"].isin(main_strategy_symbols))
    ].copy()

    # Add the main strategy signal date to the selected date signals
    selected_date_signals = selected_date_signals.copy()
    selected_date_signals["main_strategy_signal_date"] = selected_date_signals["symbol"].map(main_strategy_dates)

    if selected_date_signals.empty:
        st.info(f"No signals found for the selected date ({selected_date_str}) for symbols with main strategy signals in the date range")
        return

    st.write(f"Found **{len(selected_date_signals)}** signals on {selected_date_str} for **{len(main_strategy_symbols)}** symbols that had main strategy signals in the date range {date_range_start.date()} to {selected_date_str}")

    # Get the main strategy record for each symbol on this date (in case multiple signals exist per symbol)
    if "symbol" in selected_date_signals.columns:
        # Identify main strategy signals among the selected date signals
        signal_name_mask = selected_date_signals["signal_name"].str.startswith("nested_2bc", na=False)
        freq_mask = selected_date_signals["freq"].isin(["1h", "2h", "1d", "1w"])
        main_strategy_mask = signal_name_mask & freq_mask

        # Prioritize main strategy signals - if a symbol has both main and non-main signals,
        # prefer the main strategy signal; if multiple main signals exist, get the latest
        selected_date_signals_with_main_flag = selected_date_signals.copy()
        selected_date_signals_with_main_flag['is_main_strategy'] = main_strategy_mask

        # Sort by symbol and then by is_main_strategy (descending) and signal_date (descending)
        # to prioritize main strategy signals and then the latest ones
        df_sorted = selected_date_signals_with_main_flag.sort_values(
            ["symbol", "is_main_strategy", "signal_date"],
            ascending=[True, False, False]
        )

        # Get the first record for each symbol (which will be the main strategy if it exists, latest otherwise)
        df_latest_per_symbol = df_sorted.groupby("symbol").first().reset_index()

        # Remove the temporary column used for sorting
        df_latest_per_symbol = df_latest_per_symbol.drop('is_main_strategy', axis=1)

        # Use the create_all_signals_columns method from data.py to group signals by symbol
        df_with_signals = create_all_signals_columns(df_latest_per_symbol, df, include_extra_info=True)

        # Prepare display columns - prioritize the most important information
        display_columns = [
            'symbol', 'symbol_name', 'signal_name', 'freq', 'price', 'score',
            'reason', 'all_signals', 'all_signals_count', 'exchange', 'main_strategy_signal_date'
        ]

        # Only include columns that exist in the dataframe
        available_columns = [col for col in display_columns if col in df_with_signals.columns]

        # Sort by score if available (descending), otherwise by signal name
        if "score" in df_with_signals.columns:
            df_display = df_with_signals.sort_values("score", ascending=False)
        else:
            df_display = df_with_signals.sort_values("signal_name")

        # Display results in a dataframe format
        st.subheader(f"Signals Grouped by Symbol ({selected_date_str}) - Main Strategy Symbols Only")

        # Display the grouped results as a dataframe
        st.dataframe(
            df_display[available_columns],
            height=600,
            width="stretch"
        )

    else:
        # If no symbol column, just display the signals as a dataframe
        st.dataframe(selected_date_signals, width='stretch')