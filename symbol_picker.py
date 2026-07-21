"""
可复用的多交易所 Symbol 选择器组件。

提供四个函数：
- symbol_picker_add_ui — 交易所 + 可搜索代码下拉 + 添加按钮
- symbol_quick_add_ui — 渲染常用标的 pills，点击直接添加（如 asindex:sh000300）
- symbol_picker_selected_ui — 已选标的（exchange:symbol）展示 + 点击取消删除
- symbol_tokens_selected_ui — 已选编码 token（如 as:000001:1d）展示 + 点击取消删除

用途：用于 K 线页、信号搜索页等需要用户选择不同交易所标的的场景。
"""

from __future__ import annotations

from typing import Any, Callable, NamedTuple

import pandas as pd
import streamlit as st

from constants import KLINE_DEFAULT_FREQ, KLINE_EXCHANGE_OPTIONS, KLINE_FREQ_SET
from data import get_instruments_by_exchange


def _split_symbol_input(raw: str) -> list[str]:
    """将逗号/中文逗号分隔的代码串解析为列表。"""
    return [s.strip() for s in raw.replace("，", ",").split(",") if s.strip()]


def parse_symbols_with_exchange(
    raw: str, default_exchange: str
) -> list[tuple[str, str]]:
    """解析逗号分隔的 symbol 列表，支持 exchange:symbol 格式。"""
    result: list[tuple[str, str]] = []
    for s in _split_symbol_input(raw):
        if ":" in s:
            ex, sym = s.split(":", 1)
            ex = ex.strip().lower()
            sym = sym.strip()
        else:
            ex = default_exchange.lower()
            sym = s.strip()
        if not sym:
            continue
        if ex not in KLINE_EXCHANGE_OPTIONS:
            ex = default_exchange
        result.append((ex, sym))
    return result


def _clean_symbol_code(sym: str) -> str:
    """去掉 instrument 表的后缀元数据，只保留纯代码。

    某些 instrument 表的 symbol 列存储格式为 "代码_名称_拼音别名"（如
    "881145_电力_dl_DL"），而 Flight 查询只需要纯代码 6 位数字代码。
    """
    parts = sym.split("_")
    if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 6:
        return parts[0]
    return sym


# 合集交易所：as + ths + asindex
EXCHANGE_ALL = "as_all"
_EXCHANGE_WITH_ALL = (EXCHANGE_ALL,) + KLINE_EXCHANGE_OPTIONS
# _get_merged_instruments 内部使用的三个数据源交易所；不参与前缀解析
_MERGED_SOURCES: tuple[str, ...] = ("as", "ths", "asindex")


def _get_merged_instruments() -> pd.DataFrame:
    """获取 as_all（as + ths + asindex）的合并 instrument 列表。

    symbol 列保持 raw 原始值，_source_exchange 列携带来源交易所，
    供调用方通过 _source_exchange 还原 symbol 所属交易所。
    """
    dfs: list[pd.DataFrame] = []
    for ex in _MERGED_SOURCES:
        df = get_instruments_by_exchange(ex)
        if not df.empty:
            dfs.append(df.assign(_source_exchange=ex))
    if not dfs:
        return pd.DataFrame()
    merged = pd.concat(dfs, ignore_index=True)
    merged = merged.drop_duplicates(subset=["symbol"], keep="first")
    return merged


def _selectbox_or_search(
    add_inst: pd.DataFrame,
    key_prefix: str,
) -> str:
    """可打字的 symbol 搜索：selectbox 内搜索，先清空后搜索。

    使用 index=None 让 selectbox 默认为空，用户输入时直接搜索，
    不会被上一次的值干扰。
    """
    sym_list = sorted(add_inst["symbol"].tolist())
    name_map: dict[str, Any] = dict(
        zip(add_inst["symbol"], add_inst["name"], strict=False)
    )
    alias_map: dict[str, str] = {}
    if "alias" in add_inst.columns:
        # explode aliases to long-form, 过滤掉与 该行 symbol/name 重复的项，再聚合。
        long = (
            add_inst[["symbol", "name", "alias"]]
            .copy()
            .assign(_alias=add_inst["alias"])
            .explode("_alias")
        )
        long["_alias"] = long["_alias"].astype(str)
        _alias_low = long["_alias"].str.lower()
        _sym_low = long["symbol"].astype(str).str.lower()
        _nam_low = (
            long["name"].astype(str).str.lower()
            if "name" in long.columns
            else pd.Series([""] * len(long), index=long.index)
        )
        # 元素级比较，避免 isin 在多行情况下错位
        keep = (_alias_low != _sym_low) & (_alias_low != _nam_low)
        long = long[keep]
        if not long.empty:
            agg = (
                long.groupby("symbol", sort=False)["_alias"]
                .agg("_".join)
            )
            alias_map = {k: v for k, v in agg.items() if v}

    return st.selectbox(
        "代码",
        options=sym_list,
        index=None,
        format_func=lambda s: (
            f"{s}"
            + (f"_{name_map.get(s, '')}" if name_map.get(s, "") else "")
            + (f"_{alias_map.get(s, '')}" if alias_map.get(s) else "")
        ),
        key=f"{key_prefix}_symbol_select",
        label_visibility="collapsed",
        placeholder="输入代码或名称搜索...",
    )


def _text_input_fallback(key_prefix: str) -> str:
    """当 instrument 表无数据时的纯文本输入兜底。"""
    return st.text_input(
        "代码",
        key=f"{key_prefix}_symbol_input",
        placeholder="600519 / sh000300 / BTC",
        label_visibility="collapsed",
    )


def symbol_picker_add_ui(key_prefix: str = "sp") -> tuple[str, str] | None:
    """
    Render exchange selector + searchable symbol dropdown + add button in one row.

    下拉选项包含「代码  名称  [别名]」，alias 中包含拼音首字母，
    Streamlit 自带搜索可直接匹配（如输入"jfy"找到"减肥药"）。
    symbol selectbox 使用 index=None，输入即搜索，不会被旧值干扰。

    Returns
    -------
    (exchange, symbol) | None
        点「添加」时返回 (exchange, symbol)，否则返回 None。
    """
    c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="bottom")
    with c1:
        a_exchange: str = st.selectbox(
            "交易所",
            options=list(_EXCHANGE_WITH_ALL),
            index=list(_EXCHANGE_WITH_ALL).index(EXCHANGE_ALL),
            key=f"{key_prefix}_exchange",
            label_visibility="collapsed",
            placeholder="交易所",
        )

    # 根据所选交易所获取 instrument 列表
    if a_exchange == EXCHANGE_ALL:
        add_inst = _get_merged_instruments()
        actual_exchange = a_exchange  # 后续由 _resolve_exchange 确定具体 exchange
    else:
        add_inst = get_instruments_by_exchange(a_exchange)

    with c2:
        if not add_inst.empty:
            a_symbol = _selectbox_or_search(add_inst, key_prefix)
        else:
            a_symbol = _text_input_fallback(key_prefix)

    with c3:
        add_clicked = st.button("添加", key=f"{key_prefix}_add", width="stretch")

    if add_clicked:
        if not a_symbol:
            return None
        raw_sym = str(a_symbol).strip()
        # symbol 现在已是 raw 值（合并表不再前缀化），但 instrument 表
        # 仍可能带 "代码_名称_拼音别名" 后缀；该 helper 只清后缀。
        sym_val = _clean_symbol_code(raw_sym)
        if sym_val:
            # 如果是 as_all，从合并表中找到该 symbol 的实际 exchange
            if a_exchange == EXCHANGE_ALL and not add_inst.empty:
                matched = add_inst[add_inst["symbol"].astype(str).str.strip() == raw_sym]
                if not matched.empty:
                    actual_exchange = str(matched.iloc[0].get("_source_exchange", a_exchange))
                else:
                    actual_exchange = "as"
            else:
                actual_exchange = a_exchange
            return (actual_exchange, sym_val)
    return None


def symbol_quick_add_ui(
    presets: list[tuple[str, str]],
    label_func: Callable[[str, str], str] | None = None,
    selected: set[tuple[str, str]] | None = None,
    key_prefix: str = "sp_quick",
) -> tuple[str, str] | None:
    """
    快捷添加标的：渲染一排可切换的按钮，点击后返回该标的。

    按钮会根据当前是否已选切换样式：已选为 primary，未选为 tertiary。

    Parameters
    ----------
    presets : list[tuple[str, str]]
        预设的 (exchange, symbol) 列表，如 [("asindex", "sh000300"), ...]。
    label_func : Callable[[str, str], str] | None
        自定义按钮显示文本，接收 (exchange, symbol) 返回 label；
        为空时默认显示 "exchange:symbol"。
    selected : set[tuple[str, str]] | None
        当前已选中的预设标的集合，用于决定按钮样式。
    key_prefix : str
        Streamlit widget key 前缀。

    Returns
    -------
    tuple[str, str] | None
        用户点击某个按钮时返回对应的 (exchange, symbol)；否则返回 None。
    """
    if not presets:
        return None

    _label = label_func if label_func is not None else lambda ex, sym: f"{ex}:{sym}"
    selected_set = selected if selected is not None else set()

    with st.container(horizontal=True):
        for i, (ex, sym) in enumerate(presets):
            is_selected = (ex, sym) in selected_set
            display = _label(ex, sym)
            if st.button(
                display,
                key=f"{key_prefix}_btn_{i}",
                type="primary" if is_selected else "tertiary",
                help=f"{'取消选择' if is_selected else '选择'} {ex}:{sym}",
            ):
                return (ex, sym)
    return None


def symbol_picker_selected_ui(
    selected: list[tuple[str, str]],
    key_prefix: str = "sp",
) -> int | None:
    """
    已选标的：使用按钮展示，点击即可删除。

    Parameters
    ----------
    selected : list[tuple[str, str]]
        当前已选的 (exchange, symbol) 列表。
    key_prefix : str
        Streamlit widget key 前缀。

    Returns
    -------
    int | None
        用户删除了哪个 index 的项，否则 None。
    """
    st.markdown(f"**已选标的（{len(selected)}）**")
    options = [f"{ex}:{sym}" for ex, sym in selected]
    if not options:
        return None

    clicked_idx: int | None = None
    with st.container(horizontal=True):
        for i, label in enumerate(options):
            if st.button(f"{label} ×", key=f"{key_prefix}_del_{i}", type="tertiary"):
                clicked_idx = i
    return clicked_idx


# ============================================================
# K 线 URL symbol 编码：exchange:symbol:freq[:reverse]，逗号分隔多个
# ============================================================


class SymbolToken(NamedTuple):
    """K 线单个标的的完整参数（对应 URL 中一段 token）。"""

    exchange: str
    symbol: str
    freq: str = KLINE_DEFAULT_FREQ
    reverse: bool = False

    @property
    def token(self) -> str:
        return encode_symbol_token(self.exchange, self.symbol, self.freq, self.reverse)


def encode_symbol_token(
    exchange: str,
    symbol: str,
    freq: str = KLINE_DEFAULT_FREQ,
    reverse: bool = False,
) -> str:
    """编码为 URL token：`as:000001:1d` 或 `asindex:sh000300:1w:reverse`。"""
    ex = str(exchange).strip().lower()
    sym = str(symbol).strip()
    fq = freq if freq in KLINE_FREQ_SET else KLINE_DEFAULT_FREQ
    base = f"{ex}:{sym}:{fq}"
    return f"{base}:reverse" if reverse else base


def parse_symbol_tokens(raw: str | None) -> list[SymbolToken]:
    """解析 URL `symbol` 参数（逗号分隔的 token 列表）。"""
    if not raw:
        return []
    entries: list[SymbolToken] = []
    for tok in _split_symbol_input(raw):
        parts = tok.split(":")
        if len(parts) < 2:
            continue
        ex = parts[0].strip().lower()
        sym = parts[1].strip()
        freq = parts[2].strip() if len(parts) > 2 else ""
        reverse = len(parts) > 3 and parts[3].strip().lower() == "reverse"
        if not ex or not sym:
            continue
        if freq not in KLINE_FREQ_SET:
            freq = KLINE_DEFAULT_FREQ
        entries.append(SymbolToken(ex, sym, freq, reverse))
    return entries


def symbol_tokens_selected_ui(
    tokens: list[str],
    key_prefix: str = "spt",
    show_clear_button: bool = False,
) -> int | str | None:
    """
    已选 token 展示（如 `as:000001:1d`、`asindex:sh000300:1w:reverse`），
    以可点击的 pills 按钮形式展示，点击即可删除。

    Parameters
    ----------
    tokens : list[str]
        当前已选 token 列表。
    key_prefix : str
        Streamlit widget key 前缀。
    show_clear_button : bool
        是否在标题右侧显示「清空」按钮。

    Returns
    -------
    int | str | None
        用户删除了哪个 index 的项；点「清空」时返回 "clear"；否则返回 None。
    """
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    with c1:
        st.markdown(f"**已选标的（{len(tokens)}）**")
    with c2:
        clear_clicked = (
            show_clear_button
            and tokens
            and st.button("清空", key=f"{key_prefix}_clear", type="tertiary")
        )

    options = list(tokens)
    state_key = f"{key_prefix}_selected_tags"
    options_key = f"{key_prefix}_options"
    if not options:
        # 清理旧状态，避免下次新增 token 时被旧选项干扰
        if state_key in st.session_state:
            del st.session_state[state_key]
        if options_key in st.session_state:
            del st.session_state[options_key]
        return "clear" if clear_clicked else None

    # 当 options 列表发生变化（URL 新增/删除 token）时，重置选中态为当前全部
    prev_options = st.session_state.get(options_key)
    if prev_options != options:
        st.session_state[state_key] = options
        st.session_state[options_key] = options

    # 避免同时传 default 和通过 session_state 设值而触发 Streamlit 警告
    kwargs: dict[str, Any] = {"label_visibility": "collapsed"}
    if state_key not in st.session_state:
        kwargs["default"] = options

    curr_selected = st.pills(
        "已选标的",
        options=options,
        selection_mode="multi",
        key=state_key,
        **kwargs,
    )
    curr_selected = curr_selected if isinstance(curr_selected, list) else []
    removed = [x for x in options if x not in curr_selected]
    if removed:
        return options.index(removed[0])
    if clear_clicked:
        return "clear"

    return None
