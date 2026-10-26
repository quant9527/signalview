"""每日看点：A 股 bc_xd4 各周期每日标的数曲线（url_path=daily_bc_xd4）。"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from constants import EXCHANGE_AS
from signal_constants import BC_XD4_PREFIX
from utils import get_cached_data, sort_freqs


# 取数起点足够早，覆盖库里全部 bc_xd4；图表默认只画最近半年。
_ALL_START = date(2000, 1, 1)
_DEFAULT_MONTHS = 6
_RANGE_KEY = "daily_bc_xd4_range"


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


def display_window(
    data_min: date,
    data_max: date,
    today: date,
) -> tuple[date, date, tuple[date, date]]:
    """滑块覆盖全部历史，默认选中最近半年。

    返回 ``(最早日, 最晚日, (默认起点, 默认终点))``。
    历史不足半年时，默认起点退回最早日，即全部。
    """
    window_end = min(data_max, today)
    window_start = min(data_min, window_end)
    default_start = (
        pd.Timestamp(window_end) - pd.DateOffset(months=_DEFAULT_MONTHS)
    ).date()
    if default_start < window_start:
        default_start = window_start
    return window_start, window_end, (default_start, window_end)


def _clamp_range(
    raw: object,
    window_start: date,
    window_end: date,
    default_range: tuple[date, date],
) -> tuple[date, date]:
    """把已保存的滑块值收进当前数据边界。"""
    if not isinstance(raw, tuple) or len(raw) != 2:
        return default_range
    start, end = raw
    if not isinstance(start, date) or not isinstance(end, date):
        return default_range
    start = min(max(start, window_start), window_end)
    end = min(max(end, window_start), window_end)
    if start > end:
        return default_range
    return start, end


def page_daily_bc_xd4() -> None:
    """A 股 bc_xd4 每日标的数曲线页。"""
    st.set_page_config(layout="wide", page_title="每日看点 · bc_xd4")
    st.header("AS bc_xd4 每日标的数")
    st.caption(
        "仅 `exchange = as`，`signal_name` 以 `bc_xd4` 开头。"
        "每个周期一条曲线，纵轴是当日去重后的 symbol 数量。"
        "默认显示最近半年，下方滑块拖到最早日期即全部历史。"
    )

    today = date.today()
    df = get_cached_data(
        start_date=_ALL_START.isoformat(),
        end_date=today.isoformat(),
        signal_name_prefix=BC_XD4_PREFIX,
    )

    if df.empty or "signal_date" not in df.columns:
        st.info("没有 bc_xd4 信号。")
        return

    df = df.copy()
    df["signal_date"] = pd.to_datetime(df["signal_date"])
    as_dates = df.loc[
        (df["exchange"].astype(str).str.strip() == EXCHANGE_AS)
        & df["signal_name"].astype(str).str.startswith(BC_XD4_PREFIX),
        "signal_date",
    ].dropna()
    if as_dates.empty:
        st.info("没有 A 股 bc_xd4 信号。")
        return

    window_start, window_end, default_range = display_window(
        as_dates.min().date(),
        as_dates.max().date(),
        today,
    )
    if _RANGE_KEY not in st.session_state:
        st.session_state[_RANGE_KEY] = default_range
    else:
        st.session_state[_RANGE_KEY] = _clamp_range(
            st.session_state[_RANGE_KEY],
            window_start,
            window_end,
            default_range,
        )
    date_range = st.session_state[_RANGE_KEY]

    chart = daily_symbol_counts_by_freq(df, date_range[0], date_range[1])
    freqs = [str(col) for col in chart.columns]
    if not freqs:
        st.info("该日期范围内没有 A 股 bc_xd4 信号。")
    else:
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
        else:
            shown = chart[chosen]
            latest = shown.iloc[-1]
            previous = shown.iloc[-2] if len(shown) > 1 else None
            with st.container(horizontal=True):
                for freq in chosen:
                    delta = (
                        None if previous is None else int(latest[freq] - previous[freq])
                    )
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

    st.slider(
        "日期范围",
        min_value=window_start,
        max_value=window_end,
        format="YYYY-MM-DD",
        key=_RANGE_KEY,
        help="默认最近半年。左端拖到最早日期即全部历史。",
    )
