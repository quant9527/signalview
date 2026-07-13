"""
K 线全屏图表页：仅渲染图表，不显示参数配置区。
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as st_html

import data
import views.kline as kv


def main() -> None:
    st.markdown(
        "<style>div.block-container{padding-top:1rem;padding-bottom:0.5rem;}</style>",
        unsafe_allow_html=True,
    )
    st.header("🖥️ K 线 · 全屏图表")
    if st.button("← 返回参数设置", use_container_width=True):
        st.switch_page("views/kline.py")

    default_end = date.today()
    default_start = default_end - timedelta(days=365)
    qp = st.query_params
    url_complete = kv._query_params_fully_specified(qp)
    kv._ensure_kline_session_defaults(default_start, default_end)
    kv._sync_session_from_query_params(qp, full=url_complete, default_start=default_start, default_end=default_end)

    selected = st.session_state.get("kline_symbol", [])
    if not selected:
        st.info("当前没有已选标的，请先到参数设置页选择后再查看图表。")
        st.stop()

    start_d = st.session_state.get("kline_start", default_start)
    end_d = st.session_state.get("kline_end", default_end)
    if start_d > end_d:
        st.error("开始日期不能晚于结束日期。")
        st.stop()

    kline_freq = st.session_state.get("kline_freq", kv.KLINE_DEFAULT_FREQ)
    kline_reverse = st.session_state.get("kline_reverse", False)

    tags: list[str] = []
    sym_keys: list[str] = []
    for sym_exchange, sym_symbol in selected:
        t = kv.fkc.build_kline_tags([sym_symbol], sym_exchange, kline_freq)
        if not t:
            st.error(f"代码「{sym_exchange}:{sym_symbol}」无效，请返回参数页检查。")
            st.stop()
        tags.extend(t)
        sk = kv._symbol_key_from_tags(t)
        if sk:
            sym_keys.append(sk)

    if not sym_keys:
        st.error("无法解析标的标识。")
        st.stop()

    start_ms = int(pd.Timestamp(start_d).timestamp() * 1000)
    end_ms = int(pd.Timestamp(end_d).replace(hour=23, minute=59, second=59).timestamp() * 1000)
    flight_url = kv._resolve_flight_url()

    with st.spinner("正在从 Flight 拉取 K 线…"):
        raw = kv.fkc.fetch_kline_dataframe(
            tags,
            start_ms,
            end_ms,
            flight_url=flight_url or None,
            kline_reverse=kline_reverse,
        )

    if raw is None:
        st.error("拉取失败：请确认 Flight 服务已启动，且已安装 `pyarrow`。")
        st.stop()
    if raw.empty:
        st.warning("该时间范围内无数据。")
        st.stop()

    sym_data: dict[str, tuple[pd.DataFrame, dict]] = {}
    for sk in sym_keys:
        parsed = kv._extract_symbol_data(raw, sk)
        if parsed is not None:
            sym_data[sk] = parsed

    if not sym_data:
        st.warning("未找到与请求匹配的标的行。")
        st.stop()

    found_syms = list(sym_data.keys())
    st.caption(f"已获取 {len(found_syms)} 个标的：{'、'.join(found_syms)}")

    all_charts: list[dict] = []
    if len(found_syms) > 1:
        common_dates: pd.Series | None = None
        price_map: dict[str, pd.Series] = {}
        for sk, (prep, _) in sym_data.items():
            dates = prep["_x"]
            if common_dates is None:
                common_dates = dates
            else:
                common_dates = pd.Series(sorted(set(common_dates) & set(dates)))
        if common_dates is not None and not common_dates.empty:
            for sk, (prep, _) in sym_data.items():
                aligned = prep.set_index("_x").reindex(common_dates)["close"]
                price_map[sk] = aligned
            cmp_option = kv._build_comparison_option(common_dates, price_map)
            all_charts.append({"id": "cmp", "height": 420, "option": cmp_option})

    for (ex, sym), sk in zip(selected, sym_keys):
        if sk not in sym_data:
            continue
        prep, meta = sym_data[sk]
        labels = kv._date_labels(prep["_x"])
        ohlc = kv._to_echarts_ohlc(prep)
        vol = kv._to_echarts_volume(prep)
        ma_lines = kv._to_echarts_ma(prep, meta["ma_cols"])
        macd = kv._to_echarts_macd(prep, meta["macd"])
        has_vol = meta["has_volume"] and prep["volume"].notna().any()

        # 获取该标的的多空信号并匹配到 K 线 bar
        signals_df = data.get_kline_signals(ex, sym, start_d, end_d)
        signal_markers = kv._map_signals_to_bars(prep, signals_df)
        signal_scatter = kv._build_signal_scatter_data(signal_markers, ohlc)

        opt = kv._build_symbol_candle_option(
            symbol=sk,
            labels=labels,
            ohlc=ohlc,
            volume=vol,
            ma_lines=ma_lines,
            macd=macd,
            has_volume=has_vol,
            signal_scatter=signal_scatter if signal_scatter else None,
        )
        all_charts.append({"id": f"ch_{sk}", "height": 680, "option": opt})

    if not all_charts:
        st.warning("所选标的无共同交易日，无法绘制对比图。")
        st.stop()

    full_html = kv._build_echarts_html(all_charts)
    total_h = sum(c["height"] for c in all_charts) + len(all_charts) * 8 + 10
    st_html(full_html, height=total_h)

    total_bars = sum(len(prep) for prep, _ in sym_data.values())
    st.caption(f"共 {len(found_syms)} 个标的 · 总计 {total_bars} 根 K 线")


if __name__ == "__main__":
    main()
