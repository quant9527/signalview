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

        # Include signal_name, signal_date, and freq in the all_signals column（按 signal_name+signal_date+freq 去重，避免重复行刷屏）
        def format_signals(group):
            key_cols = ["signal_name", "signal_date"]
            if "freq" in group.columns:
                key_cols.append("freq")
            group = group.drop_duplicates(subset=key_cols)
            rows = []
            for _, row in group.iterrows():
                # Format signal_date to be more readable
                signal_date = row["signal_date"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["signal_date"]) else str(row["signal_date"])
                signal_info = f"{row['signal_name']} | {signal_date}"
                if not include_extra_info and 'freq' in group.columns and pd.notna(row.get('freq')):
                    signal_info += f" | {row['freq']}"
                if include_extra_info and 'freq' in group.columns and pd.notna(row.get('freq')):
                    signal_info += f" | Freq: {row['freq']}"
                if include_extra_info and 'price' in group.columns and pd.notna(row.get('price')):
                    signal_info += f" | Price: {row['price']}"
                rows.append(signal_info)
            return "\n".join(rows)

        symbol_signals = df_sorted.groupby("symbol").apply(format_signals, include_groups=False).to_dict()
        # 去重后的条数作为 all_signals_count
        def count_unique_signals(group):
            key_cols = ["signal_name", "signal_date"]
            if "freq" in group.columns:
                key_cols.append("freq")
            return group.drop_duplicates(subset=key_cols).shape[0]
        symbol_signal_counts = df_sorted.groupby("symbol").apply(count_unique_signals, include_groups=False).to_dict()

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


def _get_latest_market_flight(symbols: list, exchange: str = "as", flight_url: str = "grpc://127.0.0.1:50001") -> pd.DataFrame:
    """
    通过 quant-lab Flight 服务拉取 K 线，取每只标的最近一根的 close 作为最新价。
    请求体与 flight_kline_client / quant-lab 一致。
    """
    from datetime import datetime, timedelta

    import flight_kline_client as fkc

    if not symbols:
        return pd.DataFrame(columns=["code", "price", "change_percent"])

    tags = fkc.build_kline_tags(list(symbols), exchange, "1d")
    if not tags:
        return pd.DataFrame(columns=["code", "price", "change_percent"])

    end_ts = int(datetime.now().timestamp() * 1000)
    start_ts = int((datetime.now() - timedelta(days=5)).timestamp() * 1000)
    kline_df = fkc.fetch_kline_dataframe(tags, start_ts, end_ts, flight_url=flight_url)

    if kline_df is None or kline_df.empty:
        return pd.DataFrame(columns=["code", "price", "change_percent"])

    close_col = "close" if "close" in kline_df.columns else "Close"
    if close_col not in kline_df.columns:
        return pd.DataFrame(columns=["code", "price", "change_percent"])

    # 取每个 (exchange, symbol) 最新一根的 close
    ts_col = "end_ts" if "end_ts" in kline_df.columns else "timestamp"
    if ts_col not in kline_df.columns and "datetime" in kline_df.columns:
        kline_df = kline_df.sort_values("datetime", ascending=True)
        latest = kline_df.groupby(["exchange", "symbol"], as_index=False).last()
    else:
        if ts_col in kline_df.columns:
            kline_df = kline_df.sort_values(ts_col, ascending=True)
        latest = kline_df.groupby(["exchange", "symbol"], as_index=False).last()

    latest = latest.rename(columns={"symbol": "code", close_col: "price"})
    if "code" not in latest.columns and "symbol" in latest.columns:
        latest["code"] = latest["symbol"]
    latest["price"] = pd.to_numeric(latest["price"], errors="coerce")

    # 涨跌幅：若有前收，则 (price - prev_close) / prev_close * 100
    change_pct = []
    for _, row in latest.iterrows():
        ex, sym = row.get("exchange", exchange), row.get("code", row.get("symbol", ""))
        sub = kline_df[(kline_df["exchange"] == ex) & (kline_df["symbol"] == sym)]
        if ts_col in sub.columns:
            sub = sub.sort_values(ts_col)
        if len(sub) >= 2:
            prev = sub[close_col].iloc[-2]
            curr = sub[close_col].iloc[-1]
            change_pct.append(100.0 * (curr - prev) / prev if prev and prev != 0 else None)
        else:
            change_pct.append(None)
    latest["change_percent"] = change_pct

    return latest[["code", "price", "change_percent"]].copy()


@st.cache_data(ttl=600, show_spinner=False)
def get_latest_market(source: str = "spot_em", symbols: list | None = None):
    """
    获取最新行情。source: "spot_em" | "spot" | "flight"。
    当 source=="flight" 时，symbols 必填，从 quant-lab Flight 服务拉取 A 股最新价。
    """
    import akshare as ak
    import pandas as pd
    import os

    def _find_column(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    if source == "flight":
        with st.spinner("Fetching latest prices from Flight (quant-lab)..."):
            flight_url = os.environ.get("FLIGHT_URL", "grpc://127.0.0.1:50001")
            return _get_latest_market_flight(symbols or [], exchange="as", flight_url=flight_url)

    # 多数据源依次尝试：东方财富(重试) -> 新浪 -> Flight(若传入 symbols)
    def _normalize_market_df(market_df):
        code_col = _find_column(market_df, ["代码", "symbol", "code"])
        price_col = _find_column(market_df, ["最新价", "现价", "price", "trade", "now"])
        change_col = _find_column(market_df, ["涨跌幅", "涨跌额", "涨跌%", "pct_chg", "change_percent", "changepercent", "change"])
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

    with st.spinner("Fetching latest market prices..."):
        import time
        last_err = None
        # 1) 东方财富
        for attempt in range(3):
            try:
                if attempt > 0:
                    time.sleep(2)
                market_df = ak.stock_zh_a_spot_em()
                if market_df is not None and not market_df.empty:
                    return _normalize_market_df(market_df)
            except Exception as e:
                last_err = e
                if attempt < 2:
                    continue
        # 2) 新浪 A 股实时行情（常返回 HTML 导致 JSONDecodeError，仅作 fallback）
        try:
            time.sleep(1)
            market_df = ak.stock_zh_a_spot()
            if market_df is not None and not market_df.empty:
                st.info("东方财富不可用，已改用新浪数据源。")
                return _normalize_market_df(market_df)
        except Exception as e:
            last_err = e
        # 3) Flight
        if symbols and len(symbols) > 0:
            flight_url = os.environ.get("FLIGHT_URL", "grpc://127.0.0.1:50001")
            fallback_df = _get_latest_market_flight(list(symbols), exchange="as", flight_url=flight_url)
            if not fallback_df.empty:
                st.info("东方财富/新浪均不可用，已自动改用 Flight 数据源。")
                return fallback_df
        st.error("获取 A 股行情失败，请稍后重试或切换为「最新价数据源 → Flight (quant-lab)」。")
        if last_err:
            st.exception(last_err)
    return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def _get_latest_market_em():
    """EM 板块（概念+行业）最新价，统一返回 code, price, change_percent。"""
    import akshare as ak
    concept_df = ak.stock_board_concept_name_em()
    industry_df = ak.stock_board_industry_name_em()
    concept_df = concept_df.rename(columns={"板块代码": "code", "板块名称": "name", "最新价": "price", "涨跌幅": "change_percent"})
    industry_df = industry_df.rename(columns={"板块代码": "code", "板块名称": "name", "最新价": "price", "涨跌幅": "change_percent"})
    return pd.concat([concept_df, industry_df], ignore_index=True)[["code", "price", "change_percent"]].copy()


@st.cache_data(ttl=600, show_spinner=False)
def _get_latest_market_ths():
    """同花顺板块最新价，统一返回 code, price, change_percent。"""
    import akshare as ak
    board_df = ak.stock_board_industry_summary_ths()
    return board_df.rename(columns={"代码": "code", "名称": "name", "最新价": "price", "涨跌幅": "change_percent"})[["code", "price", "change_percent"]].copy()


def get_latest_market_for_exchange(exchange: str, symbols: list | tuple | None = None, source_as: str = "spot_em") -> pd.DataFrame:
    """
    按 exchange 获取最新价，统一返回列：code, price, change_percent。
    供 Performance 等页复用。所有 exchange 均支持：主源失败时用 Flight (quant-lab) 兜底（需传入 symbols）。
    """
    symbols = list(symbols) if isinstance(symbols, tuple) else (symbols or [])
    if exchange == "as":
        return get_latest_market(source_as, symbols=tuple(symbols) if symbols else None)
    if exchange == "em":
        if source_as == "flight" and symbols:
            with st.spinner("Fetching latest prices from Flight (quant-lab)..."):
                return _get_latest_market_flight(symbols, exchange="em")
        with st.spinner("Fetching latest market prices..."):
            try:
                out = _get_latest_market_em()
                if out is not None and not out.empty:
                    return out
            except Exception:
                pass
            if symbols:
                st.info("东方财富板块不可用，已自动改用 Flight 数据源。")
                return _get_latest_market_flight(symbols, exchange="em")
        return pd.DataFrame(columns=["code", "price", "change_percent"])
    if exchange == "ths":
        if source_as == "flight" and symbols:
            with st.spinner("Fetching latest prices from Flight (quant-lab)..."):
                return _get_latest_market_flight(symbols, exchange="ths")
        with st.spinner("Fetching latest market prices..."):
            try:
                out = _get_latest_market_ths()
                if out is not None and not out.empty:
                    return out
            except Exception:
                pass
            if symbols:
                st.info("同花顺板块不可用，已自动改用 Flight 数据源。")
                return _get_latest_market_flight(symbols, exchange="ths")
        return pd.DataFrame(columns=["code", "price", "change_percent"])
    return pd.DataFrame(columns=["code", "price", "change_percent"])


def _print_sql(query: str, params: tuple | list | None = None):
    """执行前打印 SQL（便于调试）。"""
    if params:
        print("[SQL]", query.strip(), "| params:", params)
    else:
        print("[SQL]", query.strip())


@st.cache_data(ttl=600, show_spinner="正在连接数据库（Neon 冷启动可能需要 1-2 分钟）...")
def load_data(time_window_days: int = 30, start_date: str | None = None, end_date: str | None = None, signal_name_prefix: str | None = None):
    """Load signals from the database filtered by a time window. Optional signal_name_prefix filters by signal_name LIKE prefix%."""
    from utils import normalize_signal_date_field
    import psycopg
    
    conn_str = st.secrets["connections"]["quantdb"]["url"]
    
    try:
        with psycopg.connect(conn_str, connect_timeout=120) as conn:
            with conn.cursor() as cur:
                # 不查询 debug_info 字段，该字段数据量太大会导致传输极慢
                columns = "id, pick_id, pick_dt, symbol_id, exchange, symbol, freq, symbol_name, signal_date, signal_name, signal, reason, price, score, shares, version, created_at, updated_at, reverse, position"
                signal_filter = " AND signal_name LIKE %s" if signal_name_prefix else ""
                params: list = []
                if start_date and end_date:
                    query = f"""
                    SELECT {columns}
                    FROM signal
                    WHERE signal_date >= %s
                      AND signal_date < (%s::date + interval '1 day'){signal_filter}
                    ORDER BY signal_date DESC
                    """
                    params = [start_date, end_date]
                    if signal_name_prefix:
                        params.append(signal_name_prefix + "%")
                    _print_sql(query, params)
                    cur.execute(query, params)
                else:
                    ndays = int(time_window_days) if time_window_days is not None else 30
                    if signal_name_prefix:
                        query = f"""
                        SELECT {columns}
                        FROM signal
                        WHERE signal_date >= now() - interval '{ndays} days'
                          AND signal_name LIKE %s
                        ORDER BY signal_date DESC
                        """
                        _print_sql(query, (signal_name_prefix + "%",))
                        cur.execute(query, (signal_name_prefix + "%",))
                    else:
                        query = f"""
                        SELECT {columns}
                        FROM signal
                        WHERE signal_date >= now() - interval '{ndays} days'
                        ORDER BY signal_date DESC
                        """
                        _print_sql(query)
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
    conn_str = st.secrets["connections"]["quantdb"]["url"]
    try:
        import psycopg
        
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                sector_sql = """
                    SELECT DISTINCT stock_symbol
                    FROM sector_constituent
                    WHERE sector_symbol = %s
                      AND sector_exchange = %s
                      AND snapshot_date = (
                          SELECT MAX(snapshot_date)
                          FROM sector_constituent
                          WHERE sector_symbol = %s AND sector_exchange = %s
                      )
                """
                _print_sql(sector_sql, (sector_symbol, sector_exchange, sector_symbol, sector_exchange))
                cur.execute(sector_sql, (sector_symbol, sector_exchange, sector_symbol, sector_exchange))
                
                rows = cur.fetchall()
                return [row[0] for row in rows]
    except Exception as e:
        st.warning(f"Failed to fetch constituents from database for {sector_symbol}: {e}")
        return []