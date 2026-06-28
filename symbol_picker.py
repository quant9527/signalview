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

    当有 instruments 数据时显示可搜索的下拉框（代码 + 名称），否则回退为文本输入框。

    Returns
    -------
    (exchange, symbol) | None
        点「＋ 添加」时返回 (exchange, symbol)，否则返回 None。

    内部使用 st.session_state 管理以下 key（受 key_prefix 隔离）：
        {key_prefix}_exchange      — 当前选择的交易所
        {key_prefix}_symbol_select — 有 instrument 时的下拉值
        {key_prefix}_symbol_input  — 无 instrument 时的文本输入
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
        a_symbol: str = st.selectbox(
            "代码",
            options=sym_list,
            format_func=lambda s: f"{s}  {name_map.get(s, '')}",
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
    已选标的：行内标签展示 + 紧凑删除按钮。

    Parameters
    ----------
    selected : list[tuple[str, str]]
        当前已选的 (exchange, symbol) 列表。
    key_prefix : str
        Streamlit widget key 前缀。

    Returns
    -------
    int | None
        用户点击了哪个 index 的 ✕ 按钮，否则 None。
    """
    if not selected:
        return None

    # 一行内展示所有已选标签
    tag_str = "  ".join(f"**{ex}**`{sym}`" for ex, sym in selected)
    st.markdown(f"**已选标的：** {tag_str}")

    # 紧凑删除按钮（最多 4 列，换行排列）
    remove_idx: int | None = None
    n = min(4, len(selected))
    cols = st.columns(n)
    for i, (ex, sym) in enumerate(selected):
        with cols[i % n]:
            if st.button(f"✕ {ex}:{sym}", key=f"{key_prefix}_rm_{ex}_{sym}", use_container_width=True):
                remove_idx = i
    return remove_idx
