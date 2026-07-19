"""
K 线图表页：Kline.html 风格渲染（深色面板、固定 tooltip、箭头 BUY/SELL 信号、联动）。

- 仅从 URL query params 读取参数（不使用 st.session_state）
- `symbol=exchange:symbol:freq[:reverse]`，逗号分隔多个；`start` / `end` 全局日期
- 按 (freq, reverse) 分组分别调用 Flight，再按 symbol 提取
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from urllib.parse import urlencode

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as st_html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import data
import flight_kline_client as fkc
import views.kline_charts as kc
from symbol_picker import SymbolToken, parse_symbol_tokens

SYMBOL_CHART_HEIGHT = 600


def _qp_str(key: str) -> str:
    return str(st.query_params.get(key, "") or "").strip()


def _qp_bool(key: str) -> bool:
    return str(st.query_params.get(key, "") or "").strip() in ("1", "true", "yes")


def _parse_iso_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _back_href(entries: list[SymbolToken], start_d: date, end_d: date, all_signals: bool) -> str:
    params = {
        "symbol": ",".join(e.token for e in entries),
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "all_signals": "1" if all_signals else "0",
    }
    return f"kline?{urlencode(params)}"


@st.cache_data(ttl=600, show_spinner=False)
def _build_symbol_name_map(
    exchanges_symbols: tuple[tuple[str, str], ...],
) -> dict[tuple[str, str], str]:
    """按 exchange 查询 instrument 表，构建 (exchange, symbol) -> name 映射。"""
    result: dict[tuple[str, str], str] = {}
    exchanges = {ex for ex, _ in exchanges_symbols}
    for ex in exchanges:
        df = data.get_instruments_by_exchange(ex)
        if df.empty:
            continue
        for _, row in df.iterrows():
            sym = str(row.get("symbol", "")).strip()
            name = str(row.get("name", "")).strip()
            if sym and name:
                result[(ex, sym)] = name
    return result


def _chart_title(token: SymbolToken, name_map: dict[tuple[str, str], str]) -> str:
    """图表标题：优先显示 symbol 名称，保留 token 作为副信息。"""
    name = name_map.get((token.exchange, token.symbol))
    if name:
        return f"{name} · {token.token}"
    return token.token


def _group_entries(entries: list[SymbolToken]) -> dict[tuple[str, bool], list[SymbolToken]]:
    groups: dict[tuple[str, bool], list[SymbolToken]] = {}
    for e in entries:
        groups.setdefault((e.freq, e.reverse), []).append(e)
    return groups


def _fetch_groups(
    groups: dict[tuple[str, bool], list[SymbolToken]],
    start_ms: int,
    end_ms: int,
    flight_url: str,
) -> dict[tuple[str, bool], pd.DataFrame]:
    """按 (freq, reverse) 分组拉取 Flight K 线。"""
    frames: dict[tuple[str, bool], pd.DataFrame] = {}
    for (freq, reverse), group in groups.items():
        tags: list[str] = []
        for e in group:
            tags.extend(fkc.build_kline_tags([e.symbol], e.exchange, freq))
        if not tags:
            continue
        raw = fkc.fetch_kline_dataframe(
            tags,
            start_ms,
            end_ms,
            flight_url=flight_url or None,
            kline_reverse=reverse,
        )
        if raw is not None and not raw.empty:
            frames[(freq, reverse)] = raw
    return frames


def _entry_sym_key(e: SymbolToken) -> str | None:
    tags = fkc.build_kline_tags([e.symbol], e.exchange, e.freq)
    return kc.symbol_key_from_tags(tags)


def _build_charts(
    entries: list[SymbolToken],
    frames: dict[tuple[str, bool], pd.DataFrame],
    start_d: date,
    end_d: date,
    all_signals: bool = False,
) -> tuple[list[dict], dict[str, dict], dict[str, int]]:
    """构建对比图 + 各标的图；返回 (chart_configs, metas, bar_counts)。"""
    sym_data: dict[str, tuple[pd.DataFrame, dict]] = {}
    for e in entries:
        frame = frames.get((e.freq, e.reverse))
        sk = _entry_sym_key(e)
        if frame is None or sk is None:
            continue
        parsed = kc.extract_symbol_data(frame, sk, exchange=e.exchange)
        if parsed is not None:
            sym_data[e.token] = parsed

    if not sym_data:
        return [], {}, {}

    name_map = _build_symbol_name_map(tuple((e.exchange, e.symbol) for e in entries))

    charts: list[dict] = []
    metas: dict[str, dict] = {}

    for e in entries:
        if e.token not in sym_data:
            continue
        prep, meta = sym_data[e.token]
        labels = kc.date_labels(prep["_x"], freq=e.freq)
        ohlc = kc.to_echarts_ohlc(prep)
        vol = kc.to_echarts_volume(prep)
        ma_lines = kc.to_echarts_ma(prep, meta["ma_cols"])
        macd = kc.to_echarts_macd(prep, meta["macd"])
        has_vol = meta["has_volume"] and prep["volume"].notna().any()

        signal_freq = None if all_signals else e.freq
        signals_df = data.get_kline_signals(e.exchange, e.symbol, start_d, end_d, freq=signal_freq)
        signals = kc.map_signals_to_bars(prep, signals_df, chart_freq=signal_freq)

        cid = f"ch_{len(metas)}"
        charts.append({
            "id": cid,
            "height": SYMBOL_CHART_HEIGHT,
            "option": kc.build_symbol_candle_option(
                title=_chart_title(e, name_map),
                labels=labels,
                ohlc=ohlc,
                volume=vol,
                ma_lines=ma_lines,
                macd=macd,
                has_volume=has_vol,
                signals=signals or None,
            ),
        })
        metas[cid] = kc.build_chart_meta(labels, ohlc, ma_lines, signals)

    bar_counts = {tok: len(prep) for tok, (prep, _) in sym_data.items()}
    return charts, metas, bar_counts


def main() -> None:
    st.markdown(
        "<style>div.block-container{padding-top:1rem;padding-bottom:0.5rem;}</style>",
        unsafe_allow_html=True,
    )

    default_end = date.today()
    default_start = default_end - timedelta(days=365)

    entries = parse_symbol_tokens(_qp_str("symbol"))
    if not entries:
        st.info("URL 中无 `symbol` 参数，请先到「参数设置」页选择标的。")
        st.stop()

    start_d = _parse_iso_date(_qp_str("start")) or default_start
    end_d = _parse_iso_date(_qp_str("end")) or default_end
    # 默认显示全部周期信号
    all_signals = True if "all_signals" not in st.query_params else _qp_bool("all_signals")
    if start_d > end_d:
        st.error("开始日期不能晚于结束日期。")
        st.stop()

    st.markdown(
        f'<a href="{_back_href(entries, start_d, end_d, all_signals)}" '
        'style="color:#8b949e;text-decoration:none;">← 返回参数设置</a>',
        unsafe_allow_html=True,
    )

    start_ms = int(pd.Timestamp(start_d, tz="Asia/Shanghai").timestamp() * 1000)
    end_ms = int(pd.Timestamp(end_d, tz="Asia/Shanghai").replace(hour=23, minute=59, second=59).timestamp() * 1000)
    flight_url = kc.resolve_flight_url()

    groups = _group_entries(entries)
    with st.spinner("正在从 Flight 拉取 K 线…"):
        frames = _fetch_groups(groups, start_ms, end_ms, flight_url)

    if not frames:
        st.error("拉取失败或该时间范围内无数据：请确认 Flight 服务已启动，且已安装 `pyarrow`。")
        st.stop()

    charts, metas, bar_counts = _build_charts(entries, frames, start_d, end_d, all_signals=all_signals)
    if not charts:
        st.warning("未找到与请求匹配的标的行。")
        st.stop()

    full_html = kc.build_echarts_html(charts, metas)
    total_h = sum(c["height"] for c in charts) + len(charts) * 8 + 90
    st_html(full_html, height=total_h)

    total_bars = sum(bar_counts.values())
    st.caption(f"共 {len(bar_counts)} 个标的 · 总计 {total_bars} 根 K 线")


main()
