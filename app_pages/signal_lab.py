"""SIGNAL LAB — 策略案例图库。

数据来自 data/signal_lab_cases.json（飞书策略库抓取），
卡片缩略图与详情大图按案例 symbol_id 实时渲染 K 线。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components_v1  # 与 kline_fullscreen 一致：内联 echarts HTML 用 components.html 渲染

from app_pages import _signal_lab_data as d
from app_pages import _signal_lab_gallery as g
from app_pages import _signal_lab_thumbs as t
from app_pages import kline_charts as kc
from flight_kline_client import build_kline_tags, fetch_kline_dataframe

PER_PAGE = 28
_GALLERY_KEY = "sl_gallery"


def _case_chart_html(case: dict, height: int = 520) -> str | None:
    """详情弹窗的完整 echarts K 线 HTML；拉不到数据返回 None。"""
    parsed = d.parse_code(case["code"])
    if parsed is None:
        return None
    ex, sym, freq = parsed
    lookback = t.FREQ_LOOKBACK_DAYS.get(freq, t._DEFAULT_LOOKBACK_DAYS)
    start = pd.Timestamp(case["date"]) - pd.Timedelta(days=lookback)
    end = pd.Timestamp(case["date"]) + pd.Timedelta(days=30)
    try:
        tags = build_kline_tags([sym], ex, kline_freq=t.DERIVED_FREQS.get(freq, freq))
        df = fetch_kline_dataframe(
            tags, int(start.value // 1e6), int(end.value // 1e6),
            # 派生频率（1w/1M）服务端不直接入库：tag 用 1d，aggregate 传 freq 本身
            kline_aggregate=freq if freq in t.DERIVED_FREQS else "",
        )
        prepared = kc.extract_symbol_data(df, sym, exchange=ex) if df is not None else None
        if prepared is None:
            return None
        bars, meta = prepared
        window = t.slice_window(bars, case["date"], before=150, after=40)
        if window is None or window.empty:
            return None
        labels = kc.date_labels(window["_x"], freq=freq)
        ohlc = kc.to_echarts_ohlc(window)
        vol = kc.to_echarts_volume(window)
        ma_lines = kc.to_echarts_ma(window, meta["ma_cols"])
        macd = kc.to_echarts_macd(window, meta["macd"])
        has_vol = bool(meta["has_volume"] and window["volume"].notna().any())
        option = kc.build_symbol_candle_option(
            title=f"{case['name']} · {case['code']}",
            labels=labels, ohlc=ohlc, volume=vol, ma_lines=ma_lines, macd=macd,
            has_volume=has_vol, signals=None, height=height, mark_date=case["date"],
        )
        charts = [{"id": "ch_case", "height": height, "option": option}]
        metas = {"ch_case": kc.build_chart_meta(labels, ohlc, ma_lines, [])}
        return kc.build_echarts_html(charts, metas)
    except Exception:
        return None


@st.dialog("案例详情", width="large")
def _show_case_dialog(cases_lookup: dict[str, dict]) -> None:
    """详情弹窗；底部在 sl_case_ids 内循环翻动。"""
    cur_id = st.session_state.get("sl_case_id", "")
    ids = st.session_state.get("sl_case_ids", [])
    case = cases_lookup.get(cur_id)
    if case is None:
        st.warning("案例不存在，可能数据已更新。")
        return
    pos = ids.index(cur_id) if cur_id in ids else 0

    left, right = st.columns([3, 2])
    with left:
        html = _case_chart_html(case)
        if html:
            components_v1.html(html, height=540)
        else:
            st.info("K 线数据暂不可用（标的代码无法解析或数据源无此合约）。")
    with right:
        st.markdown(f"#### {case['name']}")
        rows = [
            ("日期", case["date"].replace("-", ".")),
            ("标的代码", f"`{case['code']}`"),
            ("策略", case["strategy"] or "—"),
            ("信号", case["signal"]),
            ("信息", case["info"] or "—"),
            ("注意点", case["note"] or "—"),
        ]
        for label, value in rows:
            st.markdown(f"**{label}**")
            st.markdown(str(value))

    prev_b, next_b, _ = st.columns([1, 1, 4])
    if prev_b.button("← 上一个", key="sl_prev") and ids:
        st.session_state["sl_case_id"] = ids[(pos - 1) % len(ids)]
        st.rerun()
    if next_b.button("下一个 →", key="sl_next") and ids:
        st.session_state["sl_case_id"] = ids[(pos + 1) % len(ids)]
        st.rerun()


def _topbar(cases: list[dict]) -> None:
    n_cases = len(cases)
    n_signals = len(d.signal_options(cases))
    st.markdown(
        f"""
        <div style="padding:.25rem 0 .5rem 0;display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap">
          <span style="font-size:1.6rem;font-weight:700;letter-spacing:.35em">SIGNAL LAB</span>
          <span style="font-size:.85rem;opacity:.65">策略案例图库</span>
          <span style="font-size:.8rem;opacity:.5;margin-left:auto">{n_cases} 个案例 · {n_signals} 类信号</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_signal_lab() -> None:
    st.set_page_config(layout="wide", page_title="SIGNAL LAB", page_icon="🔬")
    try:
        cases = d.get_cases()
    except (FileNotFoundError, ValueError) as e:
        st.error(
            f"案例数据不可用：{e}。"
            "请运行 scripts/fetch_signal_lab.py 重新生成 data/signal_lab_cases.json。"
        )
        return
    if not cases:
        st.error("案例数据为空。")
        return

    _topbar(cases)

    c_strat, c_kw = st.columns([1, 2])
    with c_strat:
        strategy = st.selectbox(
            "策略", [d.ALL_STRATEGY] + d.strategy_options(cases),
            key="sl_strategy", label_visibility="collapsed",
        )
    with c_kw:
        keyword = st.text_input("搜索案例名称", key="sl_kw",
                                placeholder="搜索案例名称…", label_visibility="collapsed")
    # st.pills 无默认选择时返回 None，需要回落到「全部」哨兵
    signal = st.pills("信号", [d.ALL_SIGNAL] + d.signal_options(cases), key="sl_signal") or d.ALL_SIGNAL

    # 筛选条件变化时重置卡片墙的页码，避免停留在超出范围的旧页
    _filter_sig = f"{strategy}|{keyword.strip()}|{signal}"
    if st.session_state.get("sl_filter_sig") != _filter_sig:
        st.session_state["sl_filter_sig"] = _filter_sig
        if _GALLERY_KEY in st.session_state and isinstance(st.session_state[_GALLERY_KEY], dict):
            st.session_state[_GALLERY_KEY].pop("page", None)
        # 筛选变化意味着用户离开了当前浏览上下文，同步清理弹窗状态，
        # 避免关闭弹窗后任意 rerun 又把详情弹回来
        st.session_state.pop("sl_case_id", None)
        st.session_state.pop("sl_case_ids", None)

    filtered = d.filter_cases(cases, strategy=strategy, keyword=keyword, signal=signal)
    cur_page = 1
    state = st.session_state.get(_GALLERY_KEY)
    if isinstance(state, dict) and isinstance(state.get("page"), int):
        cur_page = state["page"]
    page_cases, page_no, total_pages = d.paginate(filtered, cur_page, PER_PAGE)

    thumbs = t.thumbs_for_page(tuple((c["code"], c["date"]) for c in page_cases))
    cards = g.build_cards_payload(page_cases, thumbs)
    result = g.render_gallery(cards, page_no, total_pages, key=_GALLERY_KEY)

    selected = getattr(result, "selected", None)
    if selected:
        by_id = {c["id"]: c for c in filtered}
        hit = by_id.get(selected)
        if hit is not None:
            st.session_state["sl_case_id"] = selected
            st.session_state["sl_case_ids"] = [
                c["id"] for c in filtered if c["strategy"] == hit["strategy"]
            ]

    if st.session_state.get("sl_case_id"):
        _show_case_dialog({c["id"]: c for c in cases})

    st.markdown(
        f"<div style='text-align:center;opacity:.5;font-size:.8rem;padding:1.5rem 0'>"
        f"SIGNAL LAB © 2026 策略案例图库 · 共 {len(cases)} 个案例</div>",
        unsafe_allow_html=True,
    )
