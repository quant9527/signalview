"""
Performance 页同款：信号 × 行情合并表。可在任意 Streamlit 页调用，通过参数限定 signal / symbol 范围。
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

import pandas as pd
import streamlit as st

from constants import EXCHANGE_AS, EXCHANGE_BINANCE, EXCHANGE_EM, EXCHANGE_THS
from data import (
    calculate_performance_metrics,
    clear_a_share_latest_market_cache,
    create_all_signals_columns,
    get_latest_market_for_exchange,
    _get_latest_market_em,
    _get_latest_market_ths,
)


def filter_performance_rows(
    df: pd.DataFrame,
    *,
    signal_names: Collection[str] | None = None,
    signal_name_prefixes: Sequence[str] | None = None,
    symbols: Collection[str] | None = None,
    exchange: str | None = None,
) -> pd.DataFrame:
    """
    按条件筛选信号行（AND）。用于在调用展示函数前缩小 df_work。
    """
    if df.empty:
        return df.copy()
    out = df.copy()
    if exchange is not None and "exchange" in out.columns:
        out = out[out["exchange"].astype(str) == str(exchange)]
    if symbols is not None and len(symbols) > 0:
        sym_set = {str(x).strip() for x in symbols}
        out = out[out["symbol"].astype(str).str.strip().isin(sym_set)]
    if signal_names is not None and len(signal_names) > 0:
        sn = set(signal_names)
        out = out[out["signal_name"].isin(sn)]
    if signal_name_prefixes is not None and len(signal_name_prefixes) > 0:
        prefs = tuple(signal_name_prefixes)

        def _hit(x: object) -> bool:
            s = str(x)
            return any(s.startswith(p) for p in prefs)

        out = out[out["signal_name"].map(_hit)]
    return out


def normalize_symbol_series(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    s = s.str.replace(r"^[sS][hH]|^[sS][zZ]", "", regex=True)
    s = s.str.replace(r"\.[A-Za-z]+$", "", regex=True)
    s = s.str.replace(r"^\s+|\s+$", "", regex=True)
    return s.str.zfill(6)


def _performance_signal_mask(df: pd.DataFrame) -> pd.Series:
    if "freq" not in df.columns or "signal_name" not in df.columns:
        return pd.Series(True, index=df.index)
    return ~(
        (df["freq"].astype(str).str.endswith("m", na=False))
        | (df["signal_name"].astype(str).str.startswith("yd_", na=False))
    )


def _price_source_config(exchange: str) -> tuple[list[tuple[str, str]], str]:
    if exchange == EXCHANGE_AS:
        return [
            ("akshare (东方财富)", "spot_em"),
            ("Flight (quant-lab)", "flight"),
        ], "akshare 拉全市场；Flight 仅拉当前筛选出的标的（需 quant-lab 服务运行在 127.0.0.1:50001）"
    if exchange == EXCHANGE_EM:
        return [
            ("akshare (东方财富 概念/行业板块)", "spot_em"),
            ("Flight (quant-lab)", "flight"),
        ], "akshare 失败时自动用 Flight 兜底；也可直接选 Flight（需 quant-lab 服务）"
    if exchange == EXCHANGE_THS:
        return [
            ("akshare (同花顺板块)", "spot_em"),
            ("Flight (quant-lab)", "flight"),
        ], "akshare 失败时自动用 Flight 兜底；也可直接选 Flight（需 quant-lab 服务）"
    return [(f"当前 exchange={exchange}", "spot_em")], ""


def build_merged_performance(
    df_work: pd.DataFrame,
    df_full: pd.DataFrame,
    *,
    exchange: str,
    market_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    与 Performance 页一致：最新信号/标的、all_signals、行情合并、指标。
    不含 Streamlit；调用方负责拉取 market_df。
    """
    code_col, price_col, change_col = "code", "price", "change_percent"
    if code_col not in market_df.columns or price_col not in market_df.columns:
        return pd.DataFrame()

    df_filtered = df_work.copy()
    df_filtered = df_filtered.loc[_performance_signal_mask(df_filtered)].copy()

    if df_filtered.empty or "symbol" not in df_filtered.columns or "signal_date" not in df_filtered.columns:
        return pd.DataFrame()

    df_latest = df_filtered.loc[df_filtered.groupby("symbol")["signal_date"].idxmax()].copy()

    df_full_filtered = df_full.copy()
    df_full_filtered = df_full_filtered.loc[_performance_signal_mask(df_full_filtered)].copy()

    df_latest = create_all_signals_columns(df_latest, df_full_filtered)

    market_cols = [code_col, price_col]
    if change_col in market_df.columns:
        market_cols.append(change_col)
    market_df2 = market_df[market_cols].copy()
    market_df2 = market_df2.rename(columns={code_col: "symbol_market", price_col: "latest_price"})
    if change_col in market_df.columns:
        market_df2 = market_df2.rename(columns={change_col: "market_pct_change"})

    market_df2["symbol_market"] = normalize_symbol_series(market_df2["symbol_market"].copy())
    if exchange == EXCHANGE_AS:
        market_df2 = market_df2[
            market_df2["symbol_market"].str.match(r"^\d{6}$", na=False)
        ].copy()

    df_latest["symbol_normalized"] = normalize_symbol_series(df_latest["symbol"].copy())
    merged = pd.merge(
        df_latest,
        market_df2,
        left_on="symbol_normalized",
        right_on="symbol_market",
        how="left",
    )

    if not merged.empty and merged["latest_price"].isna().all():
        sample_signals = df_latest["symbol"].astype(str).head(10).tolist()
        sample_normalized = df_latest["symbol_normalized"].head(10).tolist()
        sample_market = market_df2["symbol_market"].head(10).tolist()
        st.warning(
            f"⚠️ 未匹配到最新价。\n\n"
            f"**Signal symbols (raw):** `{sample_signals}`\n\n"
            f"**归一化代码:** `{sample_normalized}`\n\n"
            f"**行情 code 样例:** `{sample_market}`\n\n"
            f"exchange=`{exchange}`。"
        )

    return calculate_performance_metrics(merged)


def format_performance_display_dataframe(
    merged: pd.DataFrame,
    *,
    extra_columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """列选择、中文表头、顺序（与 Performance 页一致），可追加 extra_columns（保持原列名）。"""
    if merged.empty:
        return merged
    base_cols = [
        "symbol",
        "symbol_name",
        "market_pct_change",
        "pct_change",
        "signal_date",
        "signal_name",
        "all_signals",
        "all_signals_count",
        "signal_price",
        "latest_price",
    ]
    extras = list(extra_columns) if extra_columns else []
    cols = [c for c in base_cols if c in merged.columns]
    for c in extras:
        if c in merged.columns and c not in cols:
            cols.append(c)

    display_show = merged[cols].copy()
    rename_map = {
        "market_pct_change": "当日涨幅(%)",
        "pct_change": "相对信号价(%)",
        "signal_price": "信号价",
        "latest_price": "最新价",
        "all_signals": "All Signals (by date)",
        "all_signals_count": "All Signals Count",
    }
    rename_map = {k: v for k, v in rename_map.items() if k in display_show.columns}
    display_show = display_show.rename(columns=rename_map)

    desired_front = [
        "symbol",
        "symbol_name",
        "当日涨幅(%)",
        "相对信号价(%)",
    ]
    if "All Signals (by date)" in display_show.columns:
        desired_front.append("All Signals (by date)")
    if "All Signals Count" in display_show.columns:
        desired_front.append("All Signals Count")
    for c in extras:
        if c in display_show.columns and c not in desired_front:
            desired_front.append(c)

    desired_front = [c for c in desired_front if c in display_show.columns]
    other_cols = [c for c in display_show.columns if c not in desired_front]
    return display_show[desired_front + other_cols]


def render_performance_signal_table(
    df_work: pd.DataFrame,
    df_full: pd.DataFrame,
    *,
    exchange: str,
    key_prefix: str = "perf_tbl",
    heading: str | None = None,
    caption: str | None = None,
    show_summary_info: bool = True,
    show_price_source: bool = True,
    price_source_label: str = "最新价数据源",
    show_refresh: bool = True,
    refresh_label: str = "刷新行情",
    show_na_toggle: bool = True,
    na_checkbox_label: str = "包含无最新价的记录",
    show_date_sort: bool = True,
    date_sort_label: str = "按信号日期排序",
    signal_date_sort_options: Sequence[tuple[str, bool]] | None = None,
    sort_by: str = "signal_date",
    sort_ascending: bool = False,
    row_limit: int | None = None,
    extra_display_columns: Sequence[str] | None = None,
    stop_on_empty_work: bool = False,
    stop_on_empty_market: bool = True,
) -> bool:
    """
    在当前位置渲染 Performance 同款表格。

    - df_work: 已限定 signal/symbol 的工作集（可由 filter_performance_rows 得到）。
    - df_full: 生成 all_signals 用的全集，一般为 st.session_state.df。
    - stop_on_empty_market: True 时行情失败会 st.stop()（Performance 主流程）；False 时仅 warning 并返回 False。
    """
    if heading:
        st.markdown(heading)
    if caption:
        st.caption(caption)

    if df_work.empty:
        st.warning("当前条件下无信号数据。")
        if stop_on_empty_work:
            st.stop()
        return False

    if exchange == EXCHANGE_BINANCE:
        st.warning("Binance 行情尚未支持。")
        if stop_on_empty_work:
            st.stop()
        return False

    if show_summary_info:
        ns = df_work["signal_name"].nunique() if "signal_name" in df_work.columns else 0
        nu = df_work["symbol"].nunique() if "symbol" in df_work.columns else 0
        st.info(f"📊 信号种类: {ns} | 标的数: {nu} | 记录数: {len(df_work)}")

    price_sources, help_text = _price_source_config(exchange)
    source_labels = [p[0] for p in price_sources]
    source_as = price_sources[0][1]

    if show_price_source:
        _psel = st.selectbox(
            price_source_label,
            options=source_labels,
            index=0,
            key=f"{key_prefix}_price_src",
            help=help_text or None,
        )
        source_as = price_sources[source_labels.index(_psel)][1]

    symbols_for_latest = (
        df_work["symbol"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.[A-Za-z]+$", "", regex=True)
        .str.zfill(6)
        .unique()
        .tolist()
    )

    if show_refresh:
        if st.button(refresh_label, key=f"{key_prefix}_refresh"):
            clear_a_share_latest_market_cache()
            _get_latest_market_em.clear()
            _get_latest_market_ths.clear()
            st.rerun()

    with st.spinner("拉取最新行情…"):
        market_df = get_latest_market_for_exchange(
            exchange, symbols=symbols_for_latest, source_as=source_as
        )

    if market_df.empty:
        st.warning("未能获取行情，请稍后重试或检查网络 / 数据源。")
        if stop_on_empty_market:
            st.stop()
        return False

    if "code" not in market_df.columns or "price" not in market_df.columns:
        st.error("行情列不符合预期（需 code, price）。")
        st.caption(", ".join(market_df.columns.tolist()))
        if stop_on_empty_market:
            st.stop()
        return False

    merged = build_merged_performance(
        df_work, df_full, exchange=exchange, market_df=market_df
    )
    if merged.empty:
        st.warning("合并后无可用行（检查 symbol / signal_date）。")
        if stop_on_empty_market:
            st.stop()
        return False

    show_na = True
    if show_na_toggle:
        show_na = st.checkbox(
            na_checkbox_label,
            value=True,
            key=f"{key_prefix}_show_na",
        )

    display_df = merged.copy()
    if not show_na:
        display_df = display_df[
            display_df["latest_price"].notna() & display_df["signal_price"].notna()
        ]

    asc = sort_ascending
    if show_date_sort and sort_by == "signal_date" and "signal_date" in display_df.columns:
        _opts = list(
            signal_date_sort_options
            or (("降序（新→旧）", False), ("升序（旧→新）", True))
        )
        _labels = [o[0] for o in _opts]
        _picked = st.selectbox(
            date_sort_label,
            options=_labels,
            index=0,
            key=f"{key_prefix}_date_order",
        )
        asc = next(o[1] for o in _opts if o[0] == _picked)

    _sort_col = sort_by if sort_by in display_df.columns else (
        "signal_date" if "signal_date" in display_df.columns else None
    )
    if _sort_col is not None:
        display_df = display_df.sort_values(
            _sort_col,
            ascending=asc,
            na_position="last",
        )

    if row_limit is not None and row_limit > 0:
        display_df = display_df.head(int(row_limit))

    display_show = format_performance_display_dataframe(
        display_df,
        extra_columns=extra_display_columns,
    )
    st.dataframe(display_show, width="stretch", hide_index=True)
    return True
