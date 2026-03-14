import altair as alt
import pandas as pd
import streamlit as st

# Configure the page to use wide layout
st.set_page_config(layout="wide")

# Define pages structure for top navigation
pages = {
    "Dashboard": [
        st.Page("views/dashboard_as.py", title="AS", icon="🇨🇳"),
        st.Page("views/dashboard_binance.py", title="Binance", icon="🪙"),
        st.Page("views/dashboard_em.py", title="EM", icon="🌍"),
    ],
    "Profit Patterns": [
        st.Page("views/review_hotspot.py", title="Hotspot", icon="🔥", default=True),
        st.Page("views/active_vol_then_nested_bc.py", title="active_vol_then_nested_bc", icon="📉"),
        st.Page("views/profit_pattern_cl3b_zsx.py", title="CL3B ZSX", icon="📈"),
    ],
    "Review": [
        st.Page("views/overview.py", title="Overview", icon="🏠"),
        st.Page("views/review_today.py", title="Today Review", icon="📋"),
        st.Page("views/review_em.py", title="EM Review", icon="📋"),
        st.Page("views/review_key.py", title="Key Review", icon="⭐"),
    ],
    "Performance": [
        st.Page("views/performance_nested_2bc.py", title="Nested 2bc", icon="🔍"),
        st.Page("views/performance_nested_2bc_em.py", title="Nested 2bc EM", icon="🔍"),
        st.Page("views/performance_pair_seg.py", title="Pair Seg", icon="📐"),
        st.Page("views/performance_cl3b_macd.py", title="CL3B MACD", icon="📈"),
        st.Page("views/performance_cmp_em.py", title="CMP EM", icon="📊"),
    ],
    "Signals": [
        st.Page("views/all_signals_by_symbol.py", title="All Signals by Symbol", icon="📊"),
        st.Page("views/sector_signals.py", title="Sector Signals", icon="🏢"),
        st.Page("views/search_signals.py", title="Search Signals", icon="🔍"),
    ],
}

# Run navigation with top position
pg = st.navigation(pages, position="top")


# Create a database connection using Streamlit's connection API
def _get_conn_str():
    """Get PostgreSQL connection string from secrets or environment."""
    import os
    try:
        return st.secrets["connections"]["quantdb"]["url"]
    except (KeyError, FileNotFoundError, Exception):
        pass
    return os.environ.get("POSTGRESQL_URL") or os.environ.get("DATABASE_URL")


@st.cache_resource
def get_connection():
    """Create a database connection using Streamlit's connection API."""
    import os
    import streamlit as st
    import psycopg

    conn_str = _get_conn_str()
    if not conn_str:
        st.error(
            "未配置数据库连接。请任选其一：\n"
            "1. 复制 `.streamlit/secrets.toml.example` 为 `.streamlit/secrets.toml` 并填入 `[connections.quantdb] url`\n"
            "2. 或设置环境变量 `POSTGRESQL_URL` 或 `DATABASE_URL`"
        )
        st.stop()

    try:
        from streamlit.connections import SQLConnection
        return st.connection('quantdb', type=SQLConnection, url=conn_str)
    except Exception:
        return psycopg.connect(conn_str)

# Import the centralized load_data function
from data import load_data


# --- Settings: parameterize time window in sidebar ---
from datetime import date, timedelta

with st.sidebar:
    st.markdown("### Settings")
    
    # Time window selection
    time_option = st.selectbox(
        "Time window",
        options=["10 days", "45 days (default)", "90 days", "Custom range"],
        index=1,
    )

    # Custom date range if needed
    if time_option == "Custom range":
        default_start = date.today() - timedelta(days=45)
        default_end = date.today()
        start_end = st.date_input("Custom date range", value=(default_start, default_end))
        if isinstance(start_end, tuple) and len(start_end) == 2:
            start_sel, end_sel = start_end
        else:
            start_sel = start_end
            end_sel = start_end

        if start_sel > end_sel:
            st.error("Start date cannot be after end date. Please reselect.")
            st.stop()

        start_str = start_sel.isoformat()
        end_str = end_sel.isoformat()
        df = load_data(time_window_days=None, start_date=start_str, end_date=end_str)
    else:
        days_map = {"10 days": 10, "45 days (default)": 45, "90 days": 90}
        days = days_map.get(time_option, 45)
        df = load_data(time_window_days=days)

# 确保 Performance 子页用到的信号在数据中（否则「Select signals」无对应选项）
PERFORMANCE_SIGNAL_PREFIXES = ["nested_2bc", "pair_seg", "cl3b_macd", "cmp_em"]
all_signal_names = set(df["signal_name"].dropna().unique())
for prefix in PERFORMANCE_SIGNAL_PREFIXES:
    if not any(str(s).startswith(prefix) for s in all_signal_names):
        if time_option == "Custom range":
            df_extra = load_data(time_window_days=None, start_date=start_str, end_date=end_str, signal_name_prefix=prefix)
        else:
            _days = days_map.get(time_option, 45)
            df_extra = load_data(time_window_days=_days, signal_name_prefix=prefix)
        if not df_extra.empty:
            df = pd.concat([df, df_extra]).drop_duplicates()

# Signals multiselect - shared across all pages
with st.sidebar:
    # Signals multiselect - shared across all pages
    signals_options = df["signal_name"].dropna().unique()

    # Default to all signals
    if 'selected_signals' not in st.session_state:
        st.session_state['selected_signals'] = list(signals_options)
    
    selected_signals = st.multiselect(
        "Signals",
        signals_options,
        st.session_state['selected_signals'],
        key='signals_multiselect'
    )
    # Update session state when selection changes
    st.session_state['selected_signals'] = selected_signals

# Guard: stop early with helpful messages if data is missing or columns absent
if df.empty:
    st.warning("No data loaded from database. Please check the connection and query.")
    st.stop()

required_cols = ["signal_name", "signal_date", "symbol"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"Missing required columns in data: {', '.join(missing)}")
    st.stop()

# Store df in session state for pages to access
st.session_state.df = df

# Run the selected page
pg.run()