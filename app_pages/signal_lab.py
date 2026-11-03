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
from datetime import datetime, timedelta

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


def format_case_when(date: str, bar_ts) -> str:
    """案例详情的时间，一律 YYYY.MM.DD HH:MM。没有 K 线时只显示日期。"""
    if bar_ts is None or pd.isna(bar_ts):
        return str(date)[:10].replace("-", ".")
    return pd.Timestamp(bar_ts).strftime("%Y.%m.%d %H:%M")


@st.cache_data(ttl=600, max_entries=32, show_spinner=False)
def _case_chart_html_cached(code: str, date: str, at: str = "") -> tuple[str | None, str]:
    """详情 K 线 HTML 和详情里要显示的时间。拉不到数据时 HTML 为 None。

    at 是已保存的案例时间（YYYY-MM-DD HH:MM）。有它时标记落在这个时刻，
    没有时仍按当天 K 线锚定。
    """
    parsed = d.parse_code(code)
    if parsed is None:
        return None, format_case_when(date, None)
    ex, sym, freq = parsed
    fallback = format_case_when(date, None)
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
            return None, fallback
        bars, meta = prepared
        # 多取 EXTRA_AFTER 根备用 bar（不进初始视口，dataZoom 可向右拖查看）
        stored = pd.Timestamp(at) if at else None
        window = t.slice_window(
            bars, at or date, before=_DETAIL_BEFORE, after=after_total,
        )
        if window is None or window.empty:
            return None, format_case_when(date, stored) if stored is not None else fallback
        if stored is not None:
            target = stored
            pool = window
        else:
            target = pd.Timestamp(date)
            # 案例只存了日期。优先落在当天的 K 线上，避免午夜就近落到前一根日终 bar。
            same_day = window["_x"].dt.normalize() == target.normalize()
            pool = window.loc[same_day] if bool(same_day.any()) else window
        anchor = pool.loc[(pool["_x"] - target).abs().idxmin(), "_x"]
        when = format_case_when(date, stored if stored is not None else anchor)
        mark = kc.date_labels(pd.Series([pd.Timestamp(anchor)]), freq=freq)[0]
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
            has_volume=has_vol, signals=None, height=_CHART_HEIGHT, mark_date=mark,
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
        return kc.build_echarts_html(charts, metas, embedded=True), when
    except Exception as e:
        print(f"[SignalLab] chart failed for {code}: {e}")
        return None, fallback


def _case_chart_html(case: dict) -> tuple[str | None, str]:
    """详情 K 线，以及右侧「日期」要显示的时间。"""
    return _case_chart_html_cached(
        str(case["code"]), str(case["date"]), str(case.get("at") or ""),
    )


def parse_case_when(text: str) -> datetime:
    """详情里的时间文本 -> datetime。支持 2026.04.03 10:30 和只有日期。"""
    raw = str(text).strip().replace(".", "-")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法识别的时间：{text}")


def _live_case(case_id: str, fallback: dict | None) -> dict | None:
    """优先读刚写过的案例。缓存未清时退回打开弹窗时的那份。"""
    try:
        for item in d.get_cases():
            if item["id"] == case_id:
                return item
    except ValueError:
        pass
    return fallback


def _dismiss_case_dialog() -> None:
    st.session_state["sl_dialog_open"] = False
    st.session_state["sl_edit"] = ""


def _cancel_edit(case_id: str) -> None:
    st.session_state["sl_edit"] = ""
    st.session_state.pop(f"sl_when_input_{case_id}", None)


def _open_editor(case_id: str, field: str) -> None:
    st.session_state["sl_edit"] = f"{case_id}:{field}"
    st.rerun(scope="fragment")


def _field_button(label: str, value: str, case_id: str, field: str) -> None:
    """未编辑时，点字段值进入编辑。"""
    st.markdown(f"**{label}**")
    if st.button(
        value or "—",
        key=f"sl_open_{field}_{case_id}",
        type="tertiary",
        help="点击修改",
        width="stretch",
    ):
        _open_editor(case_id, field)


def _save_editor(case_id: str, action) -> None:
    """执行保存。失败时把错误留在弹窗里，不退出编辑。"""
    try:
        action()
    except ValueError as e:
        st.error(str(e))
        return
    st.session_state["sl_edit"] = ""
    _case_chart_html_cached.clear()
    st.rerun()


def _edit_when(case: dict, shown: str) -> None:
    case_id = case["id"]
    if st.session_state.get("sl_edit") != f"{case_id}:when":
        _field_button("日期", shown, case_id, "when")
        return
    st.markdown("**日期**")
    widget_key = f"sl_when_input_{case_id}"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = parse_case_when(shown)
    with st.form(f"sl_when_form_{case_id}"):
        picked = st.datetime_input(
            "日期",
            key=widget_key,
            step=timedelta(minutes=1),
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("保存", type="primary", width="stretch")
    if st.button(
        "取消", key=f"sl_when_cancel_{case_id}", width="stretch",
        on_click=_cancel_edit, args=(case_id,),
    ):
        st.rerun(scope="fragment")
    if submitted:
        _save_editor(case_id, lambda: d.update_case_when(case_id, picked))


@st.dialog("案例详情", width="large", on_dismiss=_dismiss_case_dialog)
def _show_case_dialog(cases_lookup: dict[str, dict]) -> None:
    """详情弹窗；底部在 sl_case_ids 内循环翻动。"""
    cur_id = st.session_state.get("sl_case_id", "")
    ids = st.session_state.get("sl_case_ids", [])
    case = _live_case(cur_id, cases_lookup.get(cur_id))
    if case is None:
        st.warning("案例不存在，可能数据已更新。")
        return
    edit = st.session_state.get("sl_edit") or ""
    if edit and not edit.startswith(f"{cur_id}:"):
        st.session_state["sl_edit"] = ""
    pos = ids.index(cur_id) if cur_id in ids else 0
    editable = bool(st.session_state.get("sl_case_editable"))

    # 大图为主：图占 80%，字段面板收窄成一列
    left, right = st.columns([4, 1])
    with left:
        html_doc, when = _case_chart_html(case)
        if html_doc:
            # 边框各 1px，框高略大于图表，避免缩放条被切掉
            components_v1.html(html_doc, height=_CHART_HEIGHT + 2, scrolling=False)
        else:
            st.info("K 线数据暂不可用（标的代码无法解析或数据源无此合约）。")
    shown = case["at"].replace("-", ".") if case.get("at") else when
    with right:
        st.markdown(f"#### {case['name']}")
        if editable:
            _edit_when(case, shown)
        else:
            st.markdown("**日期**")
            st.markdown(str(shown))
        st.markdown("**标的代码**")
        st.markdown(f"`{case['code']}`")
        st.markdown("**策略**")
        st.markdown(case["strategy"] or "—")
        for label, value in (
            ("信号", case["signal"]),
            ("信息", case["info"] or "—"),
            ("注意点", case["note"] or "—"),
        ):
            st.markdown(f"**{label}**")
            st.markdown(str(value))

    # 翻页按钮：底部居中并排（左右留白对称）
    _, prev_b, next_b, _ = st.columns([2, 1, 1, 2])
    # 更新 sl_case_id 后必须 scope="fragment" 重跑：弹窗 body 在按钮分支前已用旧值渲染完，
    # 只重跑弹窗 fragment 本身，不触发主脚本，X 关闭不误弹的行为不受影响
    if prev_b.button("← 上一个", key="sl_prev") and ids:
        st.session_state["sl_case_id"] = ids[(pos - 1) % len(ids)]
        st.session_state["sl_edit"] = ""
        st.rerun(scope="fragment")
    if next_b.button("下一个 →", key="sl_next") and ids:
        st.session_state["sl_case_id"] = ids[(pos + 1) % len(ids)]
        st.session_state["sl_edit"] = ""
        st.rerun(scope="fragment")


def _strategy_panel(name: str) -> None:
    """指定策略页展示 strategy 表：核心思想、创建和更新时间。"""
    try:
        row = d.get_strategy(name)
    except ValueError as e:
        st.warning(str(e))
        return
    if row is None:
        st.caption("策略表里没有这条说明。")
        return
    with st.container(border=True):
        st.markdown(row["core_idea"] or "还没有核心思想。")
        bits = []
        if row["created_at"]:
            bits.append(f"创建 {row['created_at']}")
        if row["updated_at"]:
            bits.append(f"更新 {row['updated_at']}")
        if bits:
            st.caption(" · ".join(bits))


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


_NEW_CASE_KEYS = (
    "sl_new_name", "sl_new_when", "sl_new_code", "sl_new_strategy",
    "sl_new_signal", "sl_new_info", "sl_new_note",
)


def _new_case_panel(cases: list[dict]) -> None:
    """全部策略页的新增案例，直接展示在图库上方。"""
    if st.session_state.pop("sl_new_reset", False):
        for key in _NEW_CASE_KEYS:
            st.session_state.pop(key, None)
    try:
        strategies = d.list_strategy_names()
    except ValueError as e:
        st.warning(str(e))
        return
    if not strategies:
        st.warning("策略表是空的，还不能新增案例。")
        return
    signals = d.signal_options(cases) or ["BUY", "SELL"]
    st.subheader("新增案例")
    with st.container(border=True):
        with st.form("sl_new_case", clear_on_submit=False):
            left, right = st.columns(2)
            name = left.text_input("案例名称", key="sl_new_name")
            when = right.datetime_input(
                "时间", key="sl_new_when", step=timedelta(minutes=1),
            )
            code = left.text_input(
                "标的代码", key="sl_new_code", placeholder="as:688549:1h",
            )
            signal = right.selectbox("信号", signals, key="sl_new_signal")
            strategy = st.selectbox("策略", strategies, key="sl_new_strategy")
            info = st.text_area("信息", key="sl_new_info", height=80)
            note = st.text_area("注意点", key="sl_new_note", height=80)
            submitted = st.form_submit_button("新增", type="primary")
        if submitted:
            try:
                d.insert_case(name, code, strategy, signal, when, info, note)
            except ValueError as e:
                st.error(str(e))
            else:
                st.session_state["sl_new_reset"] = True
                st.rerun()


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
    if not cases and strategy != d.ALL_STRATEGY:
        st.error("案例数据为空。")
        return

    scoped = (
        cases if strategy == d.ALL_STRATEGY
        else [c for c in cases if c["strategy"] == strategy]
    )
    _topbar(scoped, strategy)
    if strategy == d.ALL_STRATEGY:
        _new_case_panel(cases)
    else:
        _strategy_panel(strategy)
    if strategy != d.ALL_STRATEGY and not scoped:
        st.warning(f"策略「{strategy}」没有案例。")
        return

    # 指定策略的页面由侧边栏固定，不再提供名称搜索；全部策略才需要。
    suffix = _scope_key(strategy)
    keyword = ""
    if strategy == d.ALL_STRATEGY:
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
        st.session_state["sl_dialog_open"] = False
        st.session_state["sl_edit"] = ""

    filtered = d.filter_cases(cases, strategy=strategy, keyword=keyword, signal=signal)
    render_case_gallery(filtered, key=gallery_key)

    st.markdown(
        f"<div style='text-align:center;opacity:.5;font-size:.8rem;padding:1.5rem 0'>"
        f"SIGNAL LAB © 2026 策略案例图库 · 共 {len(scoped)} 个案例</div>",
        unsafe_allow_html=True,
    )


def render_case_gallery(
    cases: list[dict], *, key: str, cycle: str = "strategy", editable: bool = True,
) -> None:
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

    # 点击卡片时记下打开状态。保存后整页重跑仍要留着弹窗；
    # 点 X 会清掉这个状态，之后的翻页和筛选不会再把弹窗带回来。
    st.session_state["sl_case_editable"] = editable
    selected = getattr(result, "selected", None)
    if selected:
        by_id = {c["id"]: c for c in cases}
        hit = by_id.get(selected)
        if hit is not None:
            st.session_state["sl_case_id"] = selected
            st.session_state["sl_dialog_open"] = True
            if cycle == "all":
                st.session_state["sl_case_ids"] = [c["id"] for c in cases]
            else:
                st.session_state["sl_case_ids"] = [
                    c["id"] for c in cases if c["strategy"] == hit["strategy"]
                ]
    if st.session_state.get("sl_dialog_open") and st.session_state.get("sl_case_id"):
        by_id = {c["id"]: c for c in cases}
        cur = st.session_state["sl_case_id"]
        if cur not in by_id:
            live = _live_case(cur, None)
            if live is None:
                st.session_state["sl_dialog_open"] = False
                return
            by_id[cur] = live
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
