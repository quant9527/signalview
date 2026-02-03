import pandas as pd
import streamlit as st


def create_all_signals_columns(display_df, full_df, include_extra_info=False):
    """
    Create all_signals and all_signals_count columns for a dataframe.

    Args:
        display_df: Dataframe with records to display (e.g., latest records per symbol)
        full_df: Full dataframe containing all signals to be aggregated
        include_extra_info: Whether to include additional info like freq and price

    Returns:
        tuple: (updated_display_df with all_signals and all_signals_count columns)
    """
    if not full_df.empty and "signal_name" in full_df.columns and "signal_date" in full_df.columns:
        # Sort the full dataframe by symbol and signal_date for chronological display
        df_sorted = full_df.sort_values(["symbol", "signal_date"], ascending=[True, False])

        # Include signal_name, signal_date, and freq in the all_signals column
        def format_signals(group):
            rows = []
            for _, row in group.iterrows():
                # Format signal_date to be more readable
                signal_date = row["signal_date"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["signal_date"]) else str(row["signal_date"])
                signal_info = f"{row['signal_name']} | {signal_date}"
                if not include_extra_info and 'freq' in df_sorted.columns and pd.notna(row['freq']):
                    # This is the basic format for performance.py - just add freq without label
                    signal_info += f" | {row['freq']}"
                if include_extra_info and 'freq' in df_sorted.columns and pd.notna(row['freq']):
                    signal_info += f" | Freq: {row['freq']}"
                if include_extra_info and 'price' in df_sorted.columns and pd.notna(row['price']):
                    signal_info += f" | Price: {row['price']}"
                rows.append(signal_info)
            return "\n".join(rows)

        symbol_signals = df_sorted.groupby("symbol").apply(format_signals, include_groups=False).to_dict()
        # Create a dictionary for signal counts as well
        symbol_signal_counts = df_sorted.groupby("symbol")["signal_name"].count().to_dict()

        # Add the all_signals column to display_df
        display_df["all_signals"] = display_df["symbol"].map(symbol_signals).apply(lambda x: x if x is not None else "")
        # Add the all_signals_count column
        display_df["all_signals_count"] = display_df["symbol"].map(symbol_signal_counts).apply(lambda x: int(x) if pd.notna(x) else 0)
    else:
        display_df["all_signals"] = ""  # Create empty column if data is missing
        display_df["all_signals_count"] = 0  # Create empty count column if data is missing

    return display_df


def calculate_performance_metrics(merged_df):
    """
    Calculate performance metrics including percentage changes and derived columns.

    Args:
        merged_df: DataFrame with signal data merged with market data

    Returns:
        DataFrame with added performance metrics columns
    """
    # Ensure numeric columns are properly converted
    merged_df["latest_price"] = pd.to_numeric(merged_df["latest_price"], errors="coerce")
    merged_df["signal_price"] = pd.to_numeric(merged_df["price"], errors="coerce")

    # Process market percentage change column if it exists
    if "market_pct_change" in merged_df.columns:
        merged_df["market_pct_change"] = (
            merged_df["market_pct_change"].astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", "", regex=False)
        )
        merged_df["market_pct_change"] = pd.to_numeric(merged_df["market_pct_change"], errors="coerce")
    else:
        merged_df["market_pct_change"] = pd.NA

    # Calculate percentage change between latest price and signal price
    merged_df["pct_change"] = ((merged_df["latest_price"] - merged_df["signal_price"]) / merged_df["signal_price"]) * 100

    # Round market_pct_change if it exists
    if "market_pct_change" in merged_df.columns:
        merged_df["market_pct_change"] = merged_df["market_pct_change"].round(2)

    # Round pct_change
    merged_df["pct_change"] = merged_df["pct_change"].round(2)

    # Format percentage change with arrows and circles
    def _fmt_pct(x):
        try:
            x = float(x)
        except Exception:
            return ""
        if pd.isna(x):
            return ""
        arrow = "▲" if x > 0 else ("▼" if x < 0 else "—")
        circle = "🟢" if x > 0 else ("🔴" if x < 0 else "⚪️")
        # Show the actual value with sign, not absolute value
        return f"{arrow} {x:+.2f}% {circle}"

    merged_df["Change vs signal(%)"] = merged_df["pct_change"].apply(_fmt_pct)

    return merged_df


@st.cache_data(ttl=600, show_spinner=False)
def get_latest_market(source: str = "spot_em"):
    import akshare as ak
    import pandas as pd
    
    def _find_column(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None
    
    sources = ["spot_em", "spot"] if source == "spot_em" else ["spot", "spot_em"]
    
    with st.spinner("Fetching latest market prices..."):
        for src in sources:
            try:
                if src == "spot_em":
                    market_df = ak.stock_zh_a_spot_em()
                    # Normalize column names for spot_em
                    code_col = _find_column(market_df, ["代码", "symbol", "code"])
                    price_col = _find_column(market_df, ["最新价", "现价", "price", "now"])
                    change_col = _find_column(market_df, ["涨跌幅", "涨跌额", "涨跌%", "pct_chg", "change_percent", "change"])
                else:
                    market_df = ak.stock_zh_a_spot()
                    # Normalize column names for spot
                    code_col = _find_column(market_df, ["code", "代码", "symbol"])
                    price_col = _find_column(market_df, ["trade", "最新价", "现价", "price", "now"])
                    change_col = _find_column(market_df, ["changepercent", "涨跌幅", "涨跌额", "涨跌%", "pct_chg", "change_percent", "change"])
                
                # Rename columns to standard names
                rename_map = {}
                if code_col:
                    rename_map[code_col] = "code"
                if price_col:
                    rename_map[price_col] = "price"
                if change_col:
                    rename_map[change_col] = "change_percent"
                
                if rename_map:
                    market_df = market_df.rename(columns=rename_map)
                
                return market_df
            except Exception as e:
                if src == sources[-1]:
                    st.error(f"Failed to fetch market data from all sources.")
                    st.exception(e)
                else:
                    continue
    
    return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner="正在连接数据库（Neon 冷启动可能需要 1-2 分钟）...")
def load_data(time_window_days: int = 30, start_date: str | None = None, end_date: str | None = None):
    """Load signals from the database filtered by a time window."""
    from utils import normalize_signal_date_field
    import psycopg
    
    conn_str = st.secrets["connections"]["postgresql"]["url"]
    
    try:
        with psycopg.connect(conn_str, connect_timeout=120) as conn:
            with conn.cursor() as cur:
                # 不查询 debug_info 字段，该字段数据量太大会导致传输极慢
                columns = "id, pick_id, pick_dt, symbol_id, exchange, symbol, freq, symbol_name, signal_date, signal_name, signal, reason, price, score, shares, version, created_at, updated_at, reverse"
                if start_date and end_date:
                    query = f"""
                    SELECT {columns}
                    FROM signal
                    WHERE signal_date >= %s
                      AND signal_date < (%s::date + interval '1 day')
                    ORDER BY signal_date DESC
                    """
                    cur.execute(query, (start_date, end_date))
                else:
                    ndays = int(time_window_days) if time_window_days is not None else 30
                    query = f"""
                    SELECT {columns}
                    FROM signal
                    WHERE signal_date >= now() - interval '{ndays} days'
                    ORDER BY signal_date DESC
                    """
                    cur.execute(query)

                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]
                df = pd.DataFrame(rows, columns=colnames)
                df = normalize_signal_date_field(df, 'signal_date', 'Asia/Shanghai')
                
                # 处理 reverse 列：新增 display_symbol 列，如果 reverse 为 True 则显示为 "symbol:reverse"
                df['display_symbol'] = df.apply(
                    lambda row: f"{row['symbol']}:reverse" if row.get('reverse') else row['symbol'],
                    axis=1
                )
                
                return df
    except Exception as e:
        import sys
        st.error(f"Failed to load data from database: {e} (python: {sys.executable})")
        st.exception(e)
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_sector_constituents_from_db(sector_symbol: str, sector_exchange: str = 'em'):
    """Get constituent stocks for a given sector from the database.
    
    Args:
        sector_symbol: The sector symbol (e.g., 'BK0480')
        sector_exchange: The sector exchange (default: 'em')
    
    Returns:
        List of stock symbols that are constituents of the sector
    """
    conn_str = st.secrets["connections"]["postgresql"]["url"]
    try:
        import psycopg
        
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT stock_symbol 
                    FROM sector_constituent 
                    WHERE sector_symbol = %s 
                      AND sector_exchange = %s
                      AND snapshot_date = (
                          SELECT MAX(snapshot_date) 
                          FROM sector_constituent 
                          WHERE sector_symbol = %s AND sector_exchange = %s
                      )
                """, (sector_symbol, sector_exchange, sector_symbol, sector_exchange))
                
                rows = cur.fetchall()
                return [row[0] for row in rows]
    except Exception as e:
        st.warning(f"Failed to fetch constituents from database for {sector_symbol}: {e}")
        return []