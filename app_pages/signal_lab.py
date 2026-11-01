"""SIGNAL LAB — 策略案例图库。

数据来自 data/signal_lab_cases.json（飞书策略库抓取），
卡片缩略图与详情大图按案例 symbol_id 实时渲染 K 线。
hyperliquid 等未支持交易所的案例（如 hyperliquid:BTCUSDT:1h）显示占位图，属已知限制。
两段式 code（如 as:603893，缺 freq 段）parse_code 返回 None，详情图降级为「暂不可用」提示。
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components_v1  # 与 kline_fullscreen 一致：内联 echarts HTML 用 components.html 渲染

from app_pages import _signal_lab_data as d
from app_pages import _signal_lab_filters as f
from app_pages import _signal_lab_gallery as g
from app_pages import _signal_lab_thumbs as t
from app_pages import kline_charts as kc
from flight_kline_client import build_kline_tags, fetch_kline_dataframe

PER_PAGE = 28
_GALLERY_KEY = "sl_gallery"
_STRATEGY_SEL_KEY = "sl_strategy_sel"


_CHART_HEIGHT = 520


@st.cache_data(ttl=600, max_entries=32, show_spinner=False)
def _case_chart_html_cached(code: str, date: str) -> str | None:
    """详情弹窗的完整 echarts K 线 HTML（按 code+date 缓存）；拉不到数据返回 None。"""
    parsed = d.parse_code(code)
    if parsed is None:
        return None
    ex, sym, freq = parsed
    lookback = t.FREQ_LOOKBACK_DAYS.get(freq, t._DEFAULT_LOOKBACK_DAYS)
    start = pd.Timestamp(date) - pd.Timedelta(days=lookback)
    end = pd.Timestamp(date) + pd.Timedelta(days=30)
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
        window = t.slice_window(bars, date, before=150, after=40)
        if window is None or window.empty:
            return None
        labels = kc.date_labels(window["_x"], freq=freq)
        ohlc = kc.to_echarts_ohlc(window)
        vol = kc.to_echarts_volume(window)
        ma_lines = kc.to_echarts_ma(window, meta["ma_cols"])
        macd = kc.to_echarts_macd(window, meta["macd"])
        has_vol = bool(meta["has_volume"] and window["volume"].notna().any())
        title = f"{code} · {date}"
        for c in d.get_cases():
            if c["code"] == code and c["date"] == date:
                title = f"{c['name']} · {code}"
                break
        option = kc.build_symbol_candle_option(
            title=title,
            labels=labels, ohlc=ohlc, volume=vol, ma_lines=ma_lines, macd=macd,
            has_volume=has_vol, signals=None, height=_CHART_HEIGHT, mark_date=date,
        )
        charts = [{"id": "ch_case", "height": _CHART_HEIGHT, "option": option}]
        metas = {"ch_case": kc.build_chart_meta(labels, ohlc, ma_lines, [])}
        return kc.build_echarts_html(charts, metas)
    except Exception as e:
        print(f"[SignalLab] chart failed for {code}: {e}")
        return None


def _case_chart_html(case: dict) -> str | None:
    """薄封装：按案例的 code+date 走缓存渲染详情 K 线。"""
    return _case_chart_html_cached(str(case["code"]), str(case["date"]))


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
            components_v1.html(html, height=_CHART_HEIGHT)
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
    # 更新 sl_case_id 后必须 scope="fragment" 重跑：弹窗 body 在按钮分支前已用旧值渲染完，
    # 只重跑弹窗 fragment 本身，不触发主脚本，X 关闭不误弹的行为不受影响
    if prev_b.button("← 上一个", key="sl_prev") and ids:
        st.session_state["sl_case_id"] = ids[(pos - 1) % len(ids)]
        st.rerun(scope="fragment")
    if next_b.button("下一个 →", key="sl_next") and ids:
        st.session_state["sl_case_id"] = ids[(pos + 1) % len(ids)]
        st.rerun(scope="fragment")


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

    # 策略用分组 CCv2 pills（同前缀一行，组间换行）；信号仍是原生 st.pills
    strategy_pick = f.render_strategy_groups(
        d.strategy_options(cases),
        str(st.session_state.get(_STRATEGY_SEL_KEY) or ""),
    )
    picked = getattr(strategy_pick, "select", None)
    if picked is not None:
        st.session_state[_STRATEGY_SEL_KEY] = picked
        # 组件本次已用旧 value 渲染完（高亮滞后一拍），立即重跑让它显示新选中态；
        # 触发值只消费一次，不会循环
        st.rerun()
    strategy = st.session_state.get(_STRATEGY_SEL_KEY) or d.ALL_STRATEGY
    keyword = st.text_input("搜索案例名称", key="sl_kw",
                            placeholder="搜索案例名称…", label_visibility="collapsed")
    signal = st.pills("信号", [d.ALL_SIGNAL] + d.signal_options(cases), key="sl_signal") or d.ALL_SIGNAL

    # 筛选条件变化时重置卡片墙的页码，避免停留在超出范围的旧页
    _filter_sig = f"{strategy}|{keyword.strip()}|{signal}"
    if st.session_state.get("sl_filter_sig") != _filter_sig:
        st.session_state["sl_filter_sig"] = _filter_sig
        # 整个 state key 弹掉：CCv2 组件状态的实际结构不保证是
        # {"page": int}，部分 pop 可能无效；清空全部状态即可回到第 1 页
        st.session_state.pop(_GALLERY_KEY, None)
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

    # 只在「当次」点击卡片（selected 触发值存在）时打开弹窗；
    # X 关闭后触发值已消费，后续任何 rerun（翻页/改筛选）都不会再误弹
    selected = getattr(result, "selected", None)
    if selected:
        by_id = {c["id"]: c for c in filtered}
        hit = by_id.get(selected)
        if hit is not None:
            st.session_state["sl_case_id"] = selected
            st.session_state["sl_case_ids"] = [
                c["id"] for c in filtered if c["strategy"] == hit["strategy"]
            ]
            _show_case_dialog({c["id"]: c for c in cases})

    st.markdown(
        f"<div style='text-align:center;opacity:.5;font-size:.8rem;padding:1.5rem 0'>"
        f"SIGNAL LAB © 2026 策略案例图库 · 共 {len(cases)} 个案例</div>",
        unsafe_allow_html=True,
    )
