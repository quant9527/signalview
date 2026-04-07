"""主信号先于 YD：同一标的在时间窗口内先出现主类信号、后出现 YD 类信号。"""

import bisect
import pandas as pd
import streamlit as st

from signal_constants import CL3B_ZSX_PREFIX


def _match_signal(series: pd.Series, pattern: str, mode: str) -> pd.Series:
    pattern = (pattern or "").strip()
    if not pattern:
        return pd.Series(False, index=series.index)
    if mode == "包含":
        return series.astype(str).str.contains(pattern, regex=False, na=False)
    return series.astype(str).str.startswith(pattern, na=False)


def _group_cols(df: pd.DataFrame) -> list[str]:
    cols = ["symbol"]
    if "exchange" in df.columns:
        cols.append("exchange")
    return cols


def build_main_then_yd_table(
    df: pd.DataFrame,
    main_pattern: str,
    yd_pattern: str,
    match_mode: str,
) -> pd.DataFrame:
    """每个分组取「最早的一次 YD，且该 YD 之前存在至少一次主信号」对应的锚点对。"""
    main_pattern = (main_pattern or "").strip()
    yd_pattern = (yd_pattern or "").strip()
    if not main_pattern or not yd_pattern:
        return pd.DataFrame()

    work = df.copy()
    work["signal_date"] = pd.to_datetime(work["signal_date"])

    main_m = _match_signal(work["signal_name"], main_pattern, match_mode)
    yd_m = _match_signal(work["signal_name"], yd_pattern, match_mode)

    keys = _group_cols(work)
    out_rows: list[dict] = []

    for _key, g in work.groupby(keys, sort=False):
        g_main = g[main_m.loc[g.index]]
        g_yd = g[yd_m.loc[g.index]]
        if g_main.empty or g_yd.empty:
            continue

        main_sorted = sorted(g_main["signal_date"].dropna().tolist())
        if not main_sorted:
            continue

        yd_unique_ts = sorted(g_yd["signal_date"].dropna().unique())
        paired_yd_ts = None
        paired_main_ts = None
        for yd_ts in yd_unique_ts:
            i = bisect.bisect_left(main_sorted, yd_ts)
            if i > 0 and main_sorted[i - 1] < yd_ts:
                paired_yd_ts = yd_ts
                paired_main_ts = main_sorted[i - 1]
                break

        if paired_yd_ts is None or paired_main_ts is None:
            continue

        main_row = g_main[g_main["signal_date"] == paired_main_ts].iloc[-1]
        yd_row = g_yd[g_yd["signal_date"] == paired_yd_ts].iloc[-1]

        row = {
            "symbol": main_row["symbol"],
            "主时间": paired_main_ts,
            "主信号名": main_row["signal_name"],
            "yd时间": paired_yd_ts,
            "yd信号名": yd_row["signal_name"],
            "间隔(秒)": (paired_yd_ts - paired_main_ts).total_seconds(),
        }
        if "exchange" in keys:
            row["exchange"] = main_row.get("exchange", "")
        if "freq" in g.columns:
            row["主周期"] = main_row.get("freq", "")
            row["yd周期"] = yd_row.get("freq", "")
        out_rows.append(row)

    if not out_rows:
        return pd.DataFrame()

    res = pd.DataFrame(out_rows)
    sort_cols = ["yd时间", "symbol"]
    if "exchange" in res.columns:
        sort_cols = ["yd时间", "exchange", "symbol"]
    return res.sort_values(sort_cols, ascending=[False, True, True]).reset_index(drop=True)


st.header("📌 主 → yd")
st.markdown(
    """
在同一时间窗口内，筛选 **同一标的** 上 **先出现主信号、后出现 yd 信号** 的情形（按 `signal_date` 比较；主信号时间须 **严格早于** yd 时间）。

默认名称范围与现有 AS 常用系列一致，可在下方改为前缀或任意子串（「包含」模式）。
"""
)

df = st.session_state.df
if df.empty:
    st.warning("暂无数据")
    st.stop()

if "signal_date" not in df.columns:
    st.error("数据中缺少 signal_date")
    st.stop()

df = df.copy()
df["signal_date"] = pd.to_datetime(df["signal_date"])
min_date = df["signal_date"].min().date()
max_date = df["signal_date"].max().date()
unique_dates = sorted(df["signal_date"].dt.date.unique(), reverse=True)
default_start = unique_dates[min(4, len(unique_dates) - 1)] if unique_dates else min_date

date_range = st.slider(
    "选择信号日期范围",
    min_value=min_date,
    max_value=max_date,
    value=(default_start, max_date),
    format="YYYY-MM-DD",
)
df = df[
    (df["signal_date"].dt.date >= date_range[0]) & (df["signal_date"].dt.date <= date_range[1])
].copy()
_dates_in_win = df["signal_date"].dt.date.nunique() if not df.empty else 0
st.info(f"📅 {date_range[0]} 至 {date_range[1]}（窗口内 {_dates_in_win} 个有信号的日历日）")

st.subheader("信号名称范围")
c1, c2, c3 = st.columns([2, 2, 1])
with c1:
    main_default = CL3B_ZSX_PREFIX
    main_pattern = st.text_input("主信号（名称前缀或子串）", value=main_default)
with c2:
    yd_default = "cmp_xsx"
    yd_pattern = st.text_input("yd（名称前缀或子串）", value=yd_default)
with c3:
    match_mode = st.radio("匹配方式", ("前缀", "包含"), horizontal=True)

if not main_pattern.strip() or not yd_pattern.strip():
    st.warning("请填写主信号与 yd 的名称范围。")
    st.stop()

result = build_main_then_yd_table(df, main_pattern, yd_pattern, match_mode)

st.subheader("结果")
if result.empty:
    st.warning("当前条件下没有「先主后 yd」的标的，或侧栏未包含相关信号。")
else:
    st.metric("标的数", result["symbol"].nunique())
    display_df = result.copy()
    if "间隔(秒)" in display_df.columns:
        display_df["间隔"] = pd.to_timedelta(display_df["间隔(秒)"], unit="s")
        display_df = display_df.drop(columns=["间隔(秒)"])
    st.dataframe(display_df, width="stretch", height=480)
