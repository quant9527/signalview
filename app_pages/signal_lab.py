"""SIGNAL LAB — 策略案例图库。

策略在侧边栏「案例库」下各占一个子页，进入页面即固定该策略。
「全部策略」对应 /signal_lab。
数据来自 PostgreSQL strategy_case；策略说明在 strategy 表。
卡片缩略图与详情大图按案例 symbol_id 实时渲染 K 线。
hyperliquid 等未支持交易所的案例（如 hyperliquid:BTCUSDT:1h）显示占位图，属已知限制。
两段式 code（如 as:603893，缺 freq 段）parse_code 返回 None，详情图降级为「暂不可用」提示。
"""
from __future__ import annotations

import html
from collections.abc import Callable

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components_v1  # 与 kline_fullscreen 一致：内联 echarts HTML 用 components.html 渲染

from app_pages import _signal_lab_data as d
from app_pages import _signal_lab_gallery as g
from app_pages import _signal_lab_thumbs as t
from app_pages import kline_charts as kc
from flight_kline_client import build_kline_tags, fetch_kline_dataframe

PER_PAGE = 28
_NAV_WARNED = False


# 详情图含 K 线、成交量、MACD 和底部缩放条，iframe 与图表同高
_CHART_HEIGHT = 680
# 详情大图视口：与缩略图完全一致，右侧另有 EXTRA_AFTER 根备用 bar
# （加载但不出现在初始视图，详情页拖 dataZoom 可向右查看）
_DETAIL_BEFORE = t.WINDOW_BEFORE
_DETAIL_AFTER = t.WINDOW_AFTER
_EXTRA_AFTER = 120


@st.cache_data(ttl=600, max_entries=32, show_spinner=False)
def _case_chart_html_cached(code: str, date: str) -> str | None:
    """详情弹窗的完整 echarts K 线 HTML（按 code+date 缓存）；拉不到数据返回 None。"""
    parsed = d.parse_code(code)
    if parsed is None:
        return None
    ex, sym, freq = parsed
    lookback = t.FREQ_LOOKBACK_DAYS.get(freq, t._DEFAULT_LOOKBACK_DAYS)
    # 前瞻天数覆盖 视口 + 备用段：缩略图前瞻表按 WINDOW_AFTER 设计，按倍数放大
    after_total = _DETAIL_AFTER + _EXTRA_AFTER
    forward = max(
        t.FREQ_FORWARD_DAYS.get(freq, t._DEFAULT_FORWARD_DAYS)
        * after_total // t.WINDOW_AFTER,
        30,
    )
    start = pd.Timestamp(date) - pd.Timedelta(days=lookback)
    end = pd.Timestamp(date) + pd.Timedelta(days=forward)
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
        # 多取 EXTRA_AFTER 根备用 bar（不进初始视口，dataZoom 可向右拖查看）
        window = t.slice_window(bars, date, before=_DETAIL_BEFORE, after=after_total)
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
        # 初始视口固定为 WINDOW_BEFORE+WINDOW_AFTER 根（与缩略图一致），
        # 右侧备用 bar 不显示，拖 dataZoom slider / 滚轮可向右查看
        visible_n = min(len(labels), _DETAIL_BEFORE + _DETAIL_AFTER)
        for zoom in option.get("dataZoom", []):
            zoom.pop("start", None)
            zoom.pop("end", None)
            zoom["startValue"] = 0
            zoom["endValue"] = visible_n - 1
        charts = [{"id": "ch_case", "height": _CHART_HEIGHT, "option": option}]
        metas = {"ch_case": kc.build_chart_meta(labels, ohlc, ma_lines, [])}
        return kc.build_echarts_html(charts, metas, embedded=True)
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

    # 大图为主：图占 80%，字段面板收窄成一列
    left, right = st.columns([4, 1])
    with left:
        html = _case_chart_html(case)
        if html:
            # 边框各 1px，框高略大于图表，避免缩放条被切掉
            components_v1.html(html, height=_CHART_HEIGHT + 2, scrolling=False)
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

    # 翻页按钮：底部居中并排（左右留白对称）
    _, prev_b, next_b, _ = st.columns([2, 1, 1, 2])
    # 更新 sl_case_id 后必须 scope="fragment" 重跑：弹窗 body 在按钮分支前已用旧值渲染完，
    # 只重跑弹窗 fragment 本身，不触发主脚本，X 关闭不误弹的行为不受影响
    if prev_b.button("← 上一个", key="sl_prev") and ids:
        st.session_state["sl_case_id"] = ids[(pos - 1) % len(ids)]
        st.rerun(scope="fragment")
    if next_b.button("下一个 →", key="sl_next") and ids:
        st.session_state["sl_case_id"] = ids[(pos + 1) % len(ids)]
        st.rerun(scope="fragment")


def _scope_key(strategy: str) -> str:
    """session state 后缀：每个策略子页各自记住搜索、信号和页码。"""
    return "all" if strategy == d.ALL_STRATEGY else strategy


def _topbar(cases: list[dict], strategy: str) -> None:
    n_cases = len(cases)
    n_signals = len(d.signal_options(cases))
    subtitle = html.escape(
        "策略案例图库" if strategy == d.ALL_STRATEGY else strategy
    )
    # K 线窗口根数与缩略图/详情大图共用同一常量，改 t.WINDOW_* 此处自动同步
    st.markdown(
        f"""
        <div style="padding:.25rem 0 .5rem 0;display:flex;align-items:baseline;gap:1rem;flex-wrap:wrap">
          <span style="font-size:1.6rem;font-weight:700;letter-spacing:.35em">SIGNAL LAB</span>
          <span style="font-size:.85rem;opacity:.65">{subtitle}</span>
          <span style="font-size:.8rem;opacity:.5;margin-left:auto">
            {n_cases} 个案例 · {n_signals} 类信号 · K线窗口 {t.WINDOW_BEFORE}+{t.WINDOW_AFTER} 根
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render(strategy: str) -> None:
    title = "SIGNAL LAB" if strategy == d.ALL_STRATEGY else f"SIGNAL LAB · {strategy}"
    st.set_page_config(layout="wide", page_title=title, page_icon="🔬")
    try:
        cases = d.get_cases()
    except (FileNotFoundError, ValueError) as e:
        st.error(
            f"案例数据不可用：{e}。"
            "请运行 scripts/migrate_signal_lab_to_pg.py 重新导入数据。"
        )
        return
    if not cases:
        st.error("案例数据为空。")
        return

    scoped = (
        cases if strategy == d.ALL_STRATEGY
        else [c for c in cases if c["strategy"] == strategy]
    )
    if strategy != d.ALL_STRATEGY and not scoped:
        st.warning(f"策略「{strategy}」没有案例。")
        return

    _topbar(scoped, strategy)

    # 策略由侧边栏子页固定；这里只留名称搜索和信号筛选
    suffix = _scope_key(strategy)
    keyword = st.text_input(
        "搜索案例名称", key=f"sl_kw_{suffix}",
        placeholder="搜索案例名称…", label_visibility="collapsed",
    )
    signal = st.pills(
        "信号", [d.ALL_SIGNAL] + d.signal_options(scoped), key=f"sl_signal_{suffix}",
    ) or d.ALL_SIGNAL

    gallery_key = f"sl_gallery_{suffix}"
    # 筛选条件变化时重置卡片墙的页码，避免停留在超出范围的旧页
    sig_key = f"sl_filter_sig_{suffix}"
    _filter_sig = f"{strategy}|{keyword.strip()}|{signal}"
    if st.session_state.get(sig_key) != _filter_sig:
        st.session_state[sig_key] = _filter_sig
        # 整个 state key 弹掉：CCv2 组件状态的实际结构不保证是
        # {"page": int}，部分 pop 可能无效；清空全部状态即可回到第 1 页
        st.session_state.pop(gallery_key, None)
        # 筛选变化意味着用户离开了当前浏览上下文，同步清理弹窗状态，
        # 避免关闭弹窗后任意 rerun 又把详情弹回来
        st.session_state.pop("sl_case_id", None)
        st.session_state.pop("sl_case_ids", None)

    filtered = d.filter_cases(cases, strategy=strategy, keyword=keyword, signal=signal)
    render_case_gallery(filtered, key=gallery_key)

    st.markdown(
        f"<div style='text-align:center;opacity:.5;font-size:.8rem;padding:1.5rem 0'>"
        f"SIGNAL LAB © 2026 策略案例图库 · 共 {len(scoped)} 个案例</div>",
        unsafe_allow_html=True,
    )


def render_case_gallery(cases: list[dict], *, key: str, cycle: str = "strategy") -> None:
    """案例 K 线卡片墙。回测页把成交映射成同样的 case 结构后调用。

    ``cycle="strategy"`` 时详情里上一个/下一个只在同一策略内翻；
    ``cycle="all"`` 时在传入的整份列表里翻。
    """
    if not cases:
        st.info("没有可展示的记录。")
        return
    cur_page = 1
    state = st.session_state.get(key)
    if isinstance(state, dict) and isinstance(state.get("page"), int):
        cur_page = state["page"]
    page_cases, page_no, total_pages = d.paginate(cases, cur_page, PER_PAGE)

    thumbs = t.thumbs_for_page(tuple((c["code"], c["date"]) for c in page_cases))
    cards = g.build_cards_payload(page_cases, thumbs)
    result = g.render_gallery(cards, page_no, total_pages, key=key)

    # 只在「当次」点击卡片（selected 触发值存在）时打开弹窗；
    # X 关闭后触发值已消费，后续任何 rerun（翻页/改筛选）都不会再误弹
    selected = getattr(result, "selected", None)
    if selected:
        by_id = {c["id"]: c for c in cases}
        hit = by_id.get(selected)
        if hit is not None:
            st.session_state["sl_case_id"] = selected
            if cycle == "all":
                st.session_state["sl_case_ids"] = [c["id"] for c in cases]
            else:
                st.session_state["sl_case_ids"] = [
                    c["id"] for c in cases if c["strategy"] == hit["strategy"]
                ]
            _show_case_dialog(by_id)


def page_signal_lab() -> None:
    """全部策略：/signal_lab。"""
    _render(d.ALL_STRATEGY)


def page_for_strategy(strategy: str) -> Callable[[], None]:
    """返回只展示指定策略的页面函数。st.Page 的 callable 不能带参数。"""
    def _page() -> None:
        _render(strategy)

    _page.__name__ = f"page_signal_lab_{strategy}"
    return _page


def signal_lab_pages() -> list[st.StreamlitPage]:
    """案例库分区：全部策略 + 每个策略一个子页。

    案例库暂时读不到时只保留「全部策略」，页面内再提示错误，
    避免导航注册失败把整个应用拖垮。
    """
    global _NAV_WARNED
    pages: list[st.StreamlitPage] = [
        st.Page(page_signal_lab, title="全部策略", icon="🔬", url_path="signal_lab"),
    ]
    try:
        names = d.strategy_options(d.get_cases())
    except Exception as e:
        if not _NAV_WARNED:
            print(f"[SignalLab] 策略子页未注册：{e}")
            _NAV_WARNED = True
        return pages
    seen = {"signal_lab"}
    for name in names:
        url_path = f"signal_lab_{name}"
        if "/" in url_path or url_path in seen:
            continue
        seen.add(url_path)
        pages.append(st.Page(page_for_strategy(name), title=name, url_path=url_path))
    return pages
