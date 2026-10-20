"""每日看点：A 股 bc_xd4 各周期每日标的数曲线（url_path=daily_bc_xd4）。"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from constants import EXCHANGE_AS
from signal_constants import BC_XD4_PREFIX
from utils import get_cached_data, sort_freqs


# 曲线页默认回看窗口。比单日筛选页更长，方便看趋势。
_LOOKBACK_DAYS = 180
_DEFAULT_WINDOW_DAYS = 60


def daily_symbol_counts_by_freq(
    df: pd.DataFrame,
    start: date,
    end: date,
) -> pd.DataFrame:
    """按日、按周期统计去重 symbol 数。

    仅保留 ``exchange == as`` 且 ``signal_name`` 以 ``bc_xd4`` 开头的行。
    返回宽表：索引为 ``YYYY-MM-DD``，每列一个周期，缺失日填 0。
    列顺序按周期从大到小排列。
    """
    full_index = pd.date_range(
        start=pd.Timestamp(start),
        end=pd.Timestamp(end),
        freq="D",
    ).strftime("%Y-%m-%d")
    empty = pd.DataFrame(index=full_index)
    empty.index.name = "date"

    required = {"signal_date", "symbol", "freq", "exchange", "signal_name"}
    if df.empty or not required.issubset(df.columns):
        return empty

    work = df.loc[
        (df["exchange"].astype(str).str.strip() == EXCHANGE_AS)
        & df["signal_name"].astype(str).str.startswith(BC_XD4_PREFIX)
    ].copy()
    if work.empty:
        return empty

    work["signal_date"] = pd.to_datetime(work["signal_date"])
    if work["signal_date"].dt.tz is not None:
        work["signal_date"] = (
            work["signal_date"].dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
        )
    work["symbol"] = work["symbol"].astype(str).str.strip()
    work["freq"] = work["freq"].astype(str).str.strip()
    work = work[
        (work["signal_date"].dt.date >= start)
        & (work["signal_date"].dt.date <= end)
        & work["symbol"].ne("")
        & work["freq"].ne("")
    ]
    if work.empty:
        return empty

    daily = (
        work.assign(_date=work["signal_date"].dt.normalize())
        .groupby(["_date", "freq"], dropna=False)["symbol"]
        .nunique()
        .reset_index(name="symbol_count")
    )
    pivot = daily.pivot(index="_date", columns="freq", values="symbol_count")
    ordered = sort_freqs([str(col) for col in pivot.columns])
    pivot = pivot.reindex(columns=ordered)
    pivot = pivot.reindex(pd.to_datetime(full_index)).fillna(0).astype(int)
    pivot.index = pivot.index.strftime("%Y-%m-%d")
    pivot.index.name = "date"
    pivot.columns.name = None
    return pivot


def page_daily_bc_xd4() -> None:
    """A 股 bc_xd4 每日标的数曲线页。"""
    st.set_page_config(layout="wide", page_title="每日看点 · bc_xd4")
    st.header("AS bc_xd4 每日标的数")
    st.caption(
        "仅 `exchange = as`，`signal_name` 以 `bc_xd4` 开头。"
        "每个周期一条曲线，纵轴是当日去重后的 symbol 数量。"
    )

    today = date.today()
    load_start = today - timedelta(days=_LOOKBACK_DAYS)
    df = get_cached_data(
        start_date=load_start.isoformat(),
        end_date=today.isoformat(),
        signal_name_prefix=BC_XD4_PREFIX,
    )

    if df.empty or "signal_date" not in df.columns:
        st.info("最近 180 天没有 bc_xd4 信号。")
        return

    df = df.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    data_max = df["signal_date"].dt.date.max()
    window_end = min(data_max, today)
    window_start = max(load_start, window_end - timedelta(days=_LOOKBACK_DAYS))
    default_start = max(window_start, window_end - timedelta(days=_DEFAULT_WINDOW_DAYS))

    date_range = st.slider(
        "日期范围",
        min_value=window_start,
        max_value=window_end,
        value=(default_start, window_end),
        format="YYYY-MM-DD",
        key="daily_bc_xd4_range",
    )

    chart = daily_symbol_counts_by_freq(df, date_range[0], date_range[1])
    freqs = [str(col) for col in chart.columns]
    if not freqs:
        st.info("该日期范围内没有 A 股 bc_xd4 信号。")
        return

    selected = st.pills(
        "周期",
        freqs,
        selection_mode="multi",
        default=freqs,
        key=f"daily_bc_xd4_freqs_{'_'.join(freqs)}",
    )
    chosen = [freq for freq in freqs if freq in (selected or [])]
    if not chosen:
        st.info("至少选择一个周期。")
        return

    shown = chart[chosen]
    latest = shown.iloc[-1]
    previous = shown.iloc[-2] if len(shown) > 1 else None
    with st.container(horizontal=True):
        for freq in chosen:
            delta = None if previous is None else int(latest[freq] - previous[freq])
            st.metric(
                freq,
                int(latest[freq]),
                delta,
                border=True,
                chart_data=shown[freq].tolist(),
                chart_type="line",
                delta_description="较前一日",
            )

    st.line_chart(
        shown,
        x_label="日期",
        y_label="symbol 数量",
        height=420,
    )
