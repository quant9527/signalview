"""SIGNAL LAB 策略分组选择器：按前缀分组的 CCv2 单选 pills。

原生 st.pills 无法在单 widget 内把选项分组换行（40 个策略一行太长），
这里用 CCv2 自渲染：同一前缀（按首个 ``_`` 切分）的策略排一行，组间换行。
"""
from __future__ import annotations

import streamlit as st

ALL_LABEL = "全部策略"
ALL_VALUE = ""  # 组件内部用空串表示「不过滤」，页面层映射回 ALL_LABEL 哨兵


def strategy_prefix(strategy: str) -> str:
    """分组键：首个 ``_`` 前的第一段（如 ``bc_xd4_macd`` -> ``bc``）。"""
    return str(strategy).split("_", 1)[0]


def group_strategies(strategies: list[str]) -> list[list[str]]:
    """按前缀分组，保持首次出现的顺序；纯函数。"""
    order: list[str] = []
    grouped: dict[str, list[str]] = {}
    for s in strategies:
        prefix = strategy_prefix(s)
        if prefix not in grouped:
            grouped[prefix] = []
            order.append(prefix)
        grouped[prefix].append(s)
    return [grouped[p] for p in order]


_HTML = "<div id=\"root\"></div>"

_CSS = """
#root{font-family:var(--st-font, sans-serif);color:var(--st-text-color)}
.lbl{font-size:.8rem;opacity:.7;margin-bottom:4px}
.row{display:flex;flex-wrap:wrap;gap:6px 6px;margin-bottom:8px}
.chip{border:1px solid var(--st-border-color,rgba(0,0,0,.15));background:transparent;
  color:inherit;border-radius:999px;padding:3px 12px;cursor:pointer;font-size:13px;
  font-family:inherit}
.chip:hover{background:var(--st-secondary-background-color,#f0f0f0)}
.chip.on{color:#fff;background:var(--st-primary-color,#4a7bb5);
  border-color:var(--st-primary-color,#4a7bb5);font-weight:600}
"""

_JS = """
export default function (component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector("#root");
  if (!root) return;
  const groups = (data && data.groups) || [];
  const value = (data && data.value) || "";
  const esc = (s) => String(s).replace(/[&<>'"]/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
  ));
  const chip = (label, v) => `
    <button class="chip ${v === value ? "on" : ""}" data-v="${esc(v)}">${esc(label)}</button>`;
  root.innerHTML = `
    <div class="lbl">策略</div>
    <div class="row">${chip("全部策略", "")}</div>
    ${groups.map((g) => `
      <div class="row">
        ${g.map((name) => chip(name, name)).join("")}
      </div>`).join("")}
  `;
  root.querySelectorAll(".chip").forEach((el) => {
    el.addEventListener("click", () => setTriggerValue("select", el.dataset.v));
  });
}
"""

# 模块级注册一次
_STRATEGY_PILLS = st.components.v2.component(
    "signal_lab_strategy_pills", html=_HTML, css=_CSS, js=_JS
)


def render_strategy_groups(
    strategies: list[str], value: str, *, key: str = "sl_strategy_pills"
) -> object:
    """渲染分组 pills；返回组件 result（.select 为本次点击的策略触发值）。"""
    return _STRATEGY_PILLS(
        key=key,
        data={"groups": group_strategies(strategies), "value": value},
    )
