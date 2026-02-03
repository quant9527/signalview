import pandas as pd
import streamlit as st

st.title("Signal Overview")

df = st.session_state.df

if df.empty:
    st.warning("No data loaded.")
    st.stop()

required_cols = ["signal_name", "signal_date", "symbol"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"Missing required columns: {', '.join(missing)}")
    st.stop()

df['signal_date'] = pd.to_datetime(df['signal_date'])

st.subheader("Signal Count Trends (Last 5 Days)")

unique_dates = sorted(df['signal_date'].dt.date.unique(), reverse=True)
last_5_dates = unique_dates[:5] if len(unique_dates) >= 5 else unique_dates

if not last_5_dates:
    st.warning("No signal dates available")
    st.stop()

df_recent = df[df['signal_date'].dt.date.isin(last_5_dates)].copy()

signal_date_counts = df_recent.groupby(['signal_name', df_recent['signal_date'].dt.date]).size().reset_index(name='count')
signal_date_counts.columns = ['signal_name', 'signal_date', 'count']

pivot_table = signal_date_counts.pivot(index='signal_name', columns='signal_date', values='count').fillna(0).astype(int)

pivot_table = pivot_table[sorted(pivot_table.columns, reverse=True)]

date_cols = [col for col in pivot_table.columns if isinstance(col, pd.Timestamp) or isinstance(col, type(pivot_table.columns[0]))]

for i in range(len(date_cols) - 1):
    current_date = date_cols[i]
    previous_date = date_cols[i + 1]
    
    def calc_change(row):
        current = row[current_date]
        previous = row[previous_date]
        if previous == 0:
            if current == 0:
                return f"{int(current)}"
            else:
                return f"{int(current)} (+100%)"
        change_pct = ((current - previous) / previous) * 100
        return f"{int(current)} ({change_pct:+.1f}%)"
    
    pivot_table[current_date] = pivot_table.apply(calc_change, axis=1)

last_date = date_cols[-1]
pivot_table[last_date] = pivot_table[last_date].astype(int).astype(str)

pivot_table['Total'] = pivot_table[[col for col in date_cols]].apply(lambda row: sum([int(str(v).split()[0]) for v in row]), axis=1)

pivot_table = pivot_table.sort_values('Total', ascending=False)

st.dataframe(pivot_table, width='stretch')

st.write(f"**Total signals in selected time window:** {len(df)}")
st.write(f"**Unique symbols:** {df['symbol'].nunique()}")
st.write(f"**Signal types:** {df['signal_name'].nunique()}")