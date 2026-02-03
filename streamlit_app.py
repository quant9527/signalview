import altair as alt
import pandas as pd
import streamlit as st
import hashlib

# Configure the page to use wide layout
st.set_page_config(layout="wide")

# Simple authentication system
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        # In a real app, you would verify the password against a database or other secure storage
        if st.session_state.get("password") == st.secrets["auth"]["password"]:  # Using secrets for password
            st.session_state["authenticated"] = True
        else:
            st.session_state["authenticated"] = False

    # Check if user is already authenticated in this session
    if st.session_state.get("authenticated"):
        return True

    if "authenticated" not in st.session_state:
        # First run, show the login form
        st.title("🔐 Login")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.write("*Please enter your password to access the application*")
        return False
    elif not st.session_state["authenticated"]:
        # Password incorrect, show the form again
        st.title("🔐 Login")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("Incorrect password")
        return False
    else:
        # Password correct
        return True

# Check if user is authenticated - stop here if not authenticated
if not check_password():
    st.stop()

# === Everything below only runs after successful authentication ===

# Define pages structure for top navigation
pages = {
    "Dashboard": [
        st.Page("views/dashboard_as.py", title="AS", icon="🇨🇳"),
        st.Page("views/dashboard_binance.py", title="Binance", icon="🪙"),
        st.Page("views/dashboard_em.py", title="EM", icon="🌍"),
    ],
    "Profit Patterns": [
        st.Page("views/review_hotspot.py", title="Hotspot", icon="🔥", default=True),
        st.Page("views/profit_pattern_volume_pullback.py", title="爆量回调见底", icon="📉"),
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
        st.Page("views/performance_cl3b_macd.py", title="CL3B MACD", icon="📈"),
        st.Page("views/performance_cmp_em.py", title="CMP EM", icon="📊"),
    ],
    "Signals": [
        st.Page("views/all_signals_by_symbol.py", title="All Signals by Symbol", icon="📊"),
        st.Page("views/sector_signals.py", title="Sector Signals", icon="🏢"),
        st.Page("views/search_signals.py", title="Search Signals", icon="🔍"),
    ],
}

# Run navigation with top position - only after authentication
pg = st.navigation(pages, position="top")


# Create a database connection using Streamlit's connection API
@st.cache_resource
def get_connection():
    """Create a database connection using Streamlit's connection API."""
    import streamlit as st
    import psycopg

    # For Streamlit's SQLConnection implementation, we can use the built-in SQLConnection
    # if available, otherwise we'll create a custom implementation
    try:
        # Try to use Streamlit's built-in SQLConnection if available
        from streamlit.connections import SQLConnection
        # Read connection string from secrets.toml
        conn_str = st.secrets["connections"]["postgresql"]["url"]
        return st.connection('postgresql', type=SQLConnection, url=conn_str)
    except:
        # Fallback: Create a custom connection approach
        # Since we can't use SQLConnection directly, we'll use a cached psycopg connection
        # Read connection details from secrets.toml
        conn_str = st.secrets["connections"]["postgresql"]["url"]
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