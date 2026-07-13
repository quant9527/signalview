"""
可复用的多交易所 Symbol 选择器组件。

提供两个函数：
- symbol_picker_add_ui — 交易所 + 可搜索代码下拉 + 添加按钮
- symbol_picker_selected_ui — 已选标的展示 + × 删除按钮

用途：用于 K 线页、信号搜索页等需要用户选择不同交易所标的的场景。
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from constants import KLINE_EXCHANGE_OPTIONS
from data import get_instruments_by_exchange


def symbol_picker_add_ui(key_prefix: str = "sp") -> tuple[str, str] | None:
    """
    Render exchange selector + searchable symbol dropdown + add button.

    下拉选项包含「代码  名称  [别名]」，alias 中包含拼音首字母，
    Streamlit 自带搜索可直接匹配（如输入"jfy"找到"减肥药"）。

    Returns
    -------
    (exchange, symbol) | None
        点「＋ 添加」时返回 (exchange, symbol)，否则返回 None。
    """
    a_exchange: str = st.selectbox(
        "交易所",
        options=list(KLINE_EXCHANGE_OPTIONS),
        key=f"{key_prefix}_exchange",
    )

    add_inst = get_instruments_by_exchange(a_exchange)
    if not add_inst.empty:
        sym_list = sorted(add_inst["symbol"].tolist())
        name_map: dict[str, Any] = dict(
            zip(add_inst["symbol"], add_inst["name"], strict=False)
        )
        # alias_map: symbol -> extra identifiers (pinyin initials, etc.)
        if "alias" in add_inst.columns:
            alias_map: dict[str, str] = {}
            for _, row in add_inst.iterrows():
                aliases = row.get("alias")
                if isinstance(aliases, (list, tuple)):
                    sym_low = str(row["symbol"]).lower()
                    nam_low = str(row.get("name", "")).lower()
                    extra = [str(a) for a in aliases
                             if str(a).lower() not in (sym_low, nam_low)]
                    if extra:
                        alias_map[row["symbol"]] = "_".join(extra)
        else:
            alias_map = {}

        a_symbol: str = st.selectbox(
            "代码",
            options=sym_list,
            format_func=lambda s: (
                f"{s}"
                + (f"_{name_map.get(s, '')}" if name_map.get(s, "") else "")
                + (f"_{alias_map.get(s, '')}" if alias_map.get(s) else "")
            ),
            key=f"{key_prefix}_symbol_select",
        )
    else:
        a_symbol = st.text_input(
            "代码",
            key=f"{key_prefix}_symbol_input",
            placeholder="600519 / sh000300 / BTC",
        )

    if st.button("＋ 添加"):
        sym_val = str(a_symbol).strip()
        if sym_val:
            return (a_exchange, sym_val)
    return None


def symbol_picker_selected_ui(
    selected: list[tuple[str, str]],
    key_prefix: str = "sp",
) -> int | None:
    """
    已选标的：使用 multiselect tag 展示，点击 × 即可删除。

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
    if not selected:
        return None

    st.markdown(f"**已选标的（{len(selected)}）**  ·  点击标签右侧 `×` 删除")
    options = [f"{ex}:{sym}" for ex, sym in selected]
    source_key = f"{key_prefix}_selected_source"
    state_key = f"{key_prefix}_selected_tags"
    prev_source = st.session_state.get(source_key)
    if prev_source != options:
        st.session_state[source_key] = list(options)
        st.session_state[state_key] = list(options)

    curr_selected: list[str] = st.multiselect(
        "已选标的",
        options=options,
        key=state_key,
        label_visibility="collapsed",
        placeholder="点击标签右侧 × 删除",
    )
    removed = [x for x in options if x not in curr_selected]
    if removed:
        return options.index(removed[0])

    return None
