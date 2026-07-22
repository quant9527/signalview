"""
K 线参数设置页：仅做参数选择，图表在新标签页（kline_fullscreen）打开。

- 业务状态全部保存在 URL query params，不使用 st.session_state 管理 symbol/freq/date 等页面状态
  （Streamlit 控件自身的 session_state key 仅用于 widget  plumbing）。
- `symbol` 参数编码所有标的：`exchange:symbol:freq[:reverse]`，逗号分隔多个
  例：`symbol=as:000001:1d,asindex:sh000300:1w:reverse`
- `start` / `end` 为全局日期参数：`start=2025-01-01&end=2025-12-31`
- 全局 freq / reverse 控件决定「新添加」标的的编码值
"""

from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import urlencode

import streamlit as st

from app_pages import _kline_common as kc
from constants import KLINE_DEFAULT_FREQ, KLINE_FREQ_OPTIONS
from data import get_instruments_by_exchange
from symbol_picker import (
    encode_symbol_token,
    parse_symbol_tokens,
    symbol_picker_add_ui,
    symbol_quick_add_ui,
    symbol_tokens_selected_ui,
)

# K 线页快捷添加的常用标的
KLINE_QUICK_ADD_PRESETS: list[tuple[str, str]] = [
    ("asindex", "sh000300"),
    ("asindex", "sh000001"),
    ("asindex", "sz399006"),
    ("asindex", "sh000688"),
    ("asindex", "sh000852"),
    ("ths", "883957"),
]


@st.cache_data(ttl=600, show_spinner=False)
def _build_kline_preset_name_map(
    presets: tuple[tuple[str, str], ...],
) -> dict[tuple[str, str], str]:
    """从 instrument 表查询预设标的的中文名称。"""
    result: dict[tuple[str, str], str] = {}
    exchanges = {ex for ex, _ in presets}
    for ex in exchanges:
        df = get_instruments_by_exchange(ex)
        if df.empty:
            continue
        df = df.copy()
        df["_sym_lower"] = df["symbol"].astype(str).str.lower()
        for ex_p, sym_p in presets:
            if ex_p.lower() != ex.lower():
                continue
            match = df[df["_sym_lower"] == sym_p.lower()]
            if not match.empty:
                result[(ex_p, sym_p)] = str(match.iloc[0].get("name", ""))
    return {preset: result.get(preset) or f"{preset[0]}:{preset[1]}" for preset in presets}


def _kline_preset_label(exchange: str, symbol: str) -> str:
    names = _build_kline_preset_name_map(tuple(KLINE_QUICK_ADD_PRESETS))
    return names.get((exchange, symbol), f"{exchange}:{symbol}")


def _qp_str(key: str) -> str:
    return kc.qp_str(key)


def _qp_bool(key: str) -> bool:
    return kc.qp_bool(key)


def _parse_iso_date(s: str) -> date | None:
    return kc.parse_iso_date(s)


def _set_tokens(tokens: list[str]) -> None:
    if tokens:
        st.query_params["symbol"] = ",".join(tokens)
    elif "symbol" in st.query_params:
        del st.query_params["symbol"]


def _chart_href(tokens: list[str], start_d: date, end_d: date, all_signals: bool) -> str:
    params = {
        "symbol": ",".join(tokens),
        "start": start_d.isoformat(),
        "end": end_d.isoformat(),
        "all_signals": "1" if all_signals else "0",
    }
    return f"kline_fullscreen?{urlencode(params)}"


def page_kline() -> None:
    st.set_page_config(layout="wide", page_title="K 线参数设置")
    st.header("K 线 · 参数设置")
    st.caption("选择标的与日期范围，在新标签页查看 K 线对比图。")

    # Bidirectional link to the fullscreen page (keeps current query params).
    from app_pages.kline_fullscreen import page_kline_fullscreen
    _FULLSCREEN_PAGE = st.Page(
        page_kline_fullscreen, title="K 线全屏", icon="📈",
        url_path="kline_fullscreen",
    )
    with st.container(horizontal=True, horizontal_alignment="right"):
        st.page_link(
            _FULLSCREEN_PAGE, label="进入全屏",
            icon=":material/open_in_full:",
        )

    default_end = date.today()
    default_start = default_end - timedelta(days=365)

    entries = parse_symbol_tokens(_qp_str("symbol"))
    tokens = [e.token for e in entries]
    start_d = _parse_iso_date(_qp_str("start")) or default_start
    end_d = _parse_iso_date(_qp_str("end")) or default_end
    # 默认显示全部周期信号
    all_signals = True if "all_signals" not in st.query_params else _qp_bool("all_signals")

    # ---------- 全局参数 ----------
    st.subheader("全局参数", divider=True)
    default_freq = entries[-1].freq if entries else KLINE_DEFAULT_FREQ
    default_reverse = entries[-1].reverse if entries else False

    kline_freq: str = st.radio(
        "K 线周期",
        options=list(KLINE_FREQ_OPTIONS),
        index=list(KLINE_FREQ_OPTIONS).index(default_freq),
        horizontal=True,
        key="kline_freq_radio",
    )
    kline_reverse: bool = st.checkbox(
        "镜像反转 K 线",
        value=default_reverse,
        key="kline_reverse_checkbox",
        help="将 K 线沿价格轴镜像反转显示（最高价/最低价互换，阴阳线反转）",
    )
    all_signals_checkbox: bool = st.checkbox(
        "显示全部周期信号",
        value=all_signals,
        key="kline_all_signals_checkbox",
        help="开启后叠加所有周期（15m/30m/1h/1d/1w）的买卖信号，关闭时只显示当前 K 线周期的信号",
    )

    c1, c2 = st.columns(2)
    with c1:
        start_input = st.date_input("开始日期", value=start_d, key="kline_start")
    with c2:
        end_input = st.date_input("结束日期", value=end_d, key="kline_end")

    if start_input > end_input:
        st.error("开始日期不能晚于结束日期。")
        st.stop()

    if start_input != start_d:
        st.query_params["start"] = start_input.isoformat()
        st.rerun()
    if end_input != end_d:
        st.query_params["end"] = end_input.isoformat()
        st.rerun()

    if all_signals_checkbox != all_signals:
        st.query_params["all_signals"] = "1" if all_signals_checkbox else "0"
        st.rerun()

    # ---------- 快捷添加 ----------
    st.subheader("快捷添加", divider=True)
    preset_set = set(KLINE_QUICK_ADD_PRESETS)
    selected_presets = [
        (e.exchange, e.symbol) for e in entries if (e.exchange, e.symbol) in preset_set
    ]
    non_preset_tokens = [
        e.token for e in entries if (e.exchange, e.symbol) not in preset_set
    ]

    clicked_preset = symbol_quick_add_ui(
        KLINE_QUICK_ADD_PRESETS,
        label_func=_kline_preset_label,
        selected=set(selected_presets),
    )
    if clicked_preset is not None:
        ex, sym = clicked_preset
        if (ex, sym) in selected_presets:
            new_selected_presets = [p for p in selected_presets if p != (ex, sym)]
        else:
            new_selected_presets = [*selected_presets, (ex, sym)]
        preset_tokens = [
            encode_symbol_token(ex_p, sym_p, kline_freq, kline_reverse)
            for ex_p, sym_p in new_selected_presets
        ]
        _set_tokens([*non_preset_tokens, *preset_tokens])
        st.rerun()

    # ---------- 已选标的 ----------
    st.subheader("已选标的", divider=True)
    remove_idx = symbol_tokens_selected_ui(tokens, show_clear_button=True)
    if remove_idx == "clear":
        _set_tokens([])
        st.rerun()
    if remove_idx is not None:
        _set_tokens([t for i, t in enumerate(tokens) if i != remove_idx])
        st.rerun()

    # ---------- 添加标的 ----------
    st.subheader("添加标的", divider=True)
    result = symbol_picker_add_ui()
    if result is not None:
        tok = encode_symbol_token(result[0], result[1], kline_freq, kline_reverse)
        if tok not in tokens:
            _set_tokens([*tokens, tok])
        st.rerun()

    # ---------- 查看图表 ----------
    st.subheader("查看图表", divider=True)
    if not tokens:
        st.info("请先通过「快捷添加」或「添加标的」选择至少一个标的。")
        st.stop()

    href = _chart_href(tokens, start_d, end_d, all_signals)
    st.markdown(
        f'<a href="{href}" target="_blank" '
        'style="display:block;text-align:center;padding:0.55rem 1rem;'
        'background-color:#ff4b4b;color:#fff;text-decoration:none;'
        'border-radius:0.5rem;font-weight:500;margin-top:0.5rem;">'
        '查看图表 ↗</a>',
        unsafe_allow_html=True,
    )
