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
    "AS": [
        st.Page("views/today_opportunities.py", title="今日机会", icon="🎯", default=True),
        st.Page("views/review_index.py", title="大盘", icon="📈"),
        st.Page("views/review_hotspot.py", title="板块热点", icon="🔥"),
        st.Page("views/active_vol_then_nestedbc.py", title="active_vol_then_nestedbc", icon="📉"),
        st.Page("views/nested_bc.py", title="nested_bc", icon="📊"),
        st.Page("views/profit_pattern_cl3b_zsx.py", title="CL3B ZSX", icon="📈"),
        st.Page("views/main_then_yd.py", title="主→yd", icon="🔗"),
    ],
    "K线": [
        st.Page("views/kline.py", title="参数设置", icon="🕯️"),
        st.Page("views/kline_fullscreen.py", title="全屏图表", icon="🖥️"),
    ],
    "Review": [
        st.Page("views/overview.py", title="Overview", icon="🏠"),
        st.Page("views/review_today.py", title="Today Review", icon="📋"),
        st.Page("views/review_em.py", title="EM Review", icon="📋"),
        st.Page("views/review_key.py", title="Key Review", icon="⭐"),
    ],
    "Performance": [
        st.Page("views/performance.py", title="Performance", icon="📊"),
    ],
    "Signals": [
        st.Page("views/all_signals_by_symbol.py", title="All Signals by Symbol", icon="📊"),
        st.Page("views/sector_signals.py", title="Sector Signals", icon="🏢"),
        st.Page("views/search_signals.py", title="Search Signals", icon="🔍"),
    ],
    "Tools": [
        st.Page("views/instrument_groups.py", title="Instrument Groups", icon="📁"),
        st.Page("views/alert_rule_crud.py", title="Alert Rules", icon="🔔"),
    ],
    "ML": [
        st.Page("views/ml_scores.py", title="ML Scores", icon="🤖"),
    ],
}

# Run navigation with top position
pg = st.navigation(pages, position="top")

# Run the selected page
pg.run()