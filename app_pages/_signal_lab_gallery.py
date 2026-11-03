"""SIGNAL LAB 卡片墙 CCv2 组件：整面网格 1 个 widget，点击卡片回传 case id。"""
from __future__ import annotations

import streamlit as st

_SIGNAL_CLASS = {
    "BUY": "buy",
    "SELL": "sell",
    "IGNORE_BUY": "ignore",
    "NOT_BUY": "notbuy",
    "LONG / BUY": "long",
}


def signal_class(signal: str) -> str:
    """信号类型 -> CSS 修饰类；未知类型给中性色。"""
    cls = _SIGNAL_CLASS.get(str(signal).strip())
    if cls:
        return cls
    return "sig-" + "".join(ch if ch.isalnum() else "-" for ch in str(signal).lower())[:20]


INFO_MAX_CHARS = 60


def _info_summary(info: str) -> str:
    """信息字段截断摘要，超长补省略号。"""
    text = str(info).strip()
    if len(text) > INFO_MAX_CHARS:
        return text[:INFO_MAX_CHARS] + "…"
    return text


def build_cards_payload(cases: list[dict], thumbs: dict[str, str]) -> list[dict]:
    """把当前页案例 + 缩略图组装成组件 data；纯函数。"""
    cards = []
    for c in cases:
        key = f"{c['code']}|{c['date']}"
        cards.append({
            "id": str(c["id"]),
            "name": str(c["name"]),
            "dateLabel": str(c["date"]).replace("-", "."),
            "signal": str(c["signal"]),
            "signalClass": signal_class(str(c["signal"])),
            "code": str(c["code"]),
            "strategy": str(c.get("strategy") or ""),
            "info": _info_summary(str(c.get("info") or "")),
            "thumb": thumbs.get(key) or "<svg xmlns='http://www.w3.org/2000/svg'/>",
        })
    return cards


_HTML = "<div id=\"root\"></div>"

_CSS = """
#root{font-family:var(--st-font, sans-serif);color:var(--st-text-color)}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:18px}
.card{position:relative;border-radius:12px;overflow:hidden;cursor:pointer;
  background:var(--st-secondary-background-color,#fff);
  border:1px solid var(--st-border-color,rgba(0,0,0,.08));
  transition:box-shadow .18s ease,transform .18s ease}
.card:hover{box-shadow:0 8px 24px rgba(0,0,0,.12);transform:translateY(-2px)}
.thumb{aspect-ratio:16/9;background:var(--st-secondary-background-color,#f5f5f5);position:relative}
.thumb svg{width:100%;height:100%;display:block}
.badges{position:absolute;top:10px;left:10px;display:flex;gap:6px}
/* 统一风格：同形同底（半透明深底），仅用文字颜色区分信号类型与策略名 */
.badge{padding:2px 10px;border-radius:999px;font-size:11px;font-weight:600;
  letter-spacing:.04em;background:rgba(15,23,42,.72);color:#e2e8f0;
  backdrop-filter:blur(4px)}
/* 国内配色习惯：买入红、卖出绿 */
.badge-buy{color:#f87171}.badge-sell{color:#4ade80}
.badge-ignore{color:#cbd5e1}.badge-notbuy{color:#94a3b8}
.badge-long{color:#f87171}
.badge-strat{color:#93c5fd;font-weight:500;letter-spacing:0}
.hover{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  background:rgba(15,23,42,.45);opacity:0;transition:opacity .18s ease}
.card:hover .hover{opacity:1}
.hover span{color:#fff;font-size:13px;border:1px solid rgba(255,255,255,.7);
  border-radius:999px;padding:4px 14px}
.meta{padding:10px 12px 12px}
.name{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sub{display:flex;align-items:baseline;gap:6px;margin-top:3px;font-size:12px;opacity:.65}
.code{font-family:var(--st-mono-font,monospace);font-size:11px;opacity:.9}
.info{display:flex;align-items:flex-start;gap:6px;margin-top:7px;font-size:12px;
  opacity:.85;line-height:1.5}
.itext{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pager{display:flex;align-items:center;justify-content:center;gap:14px;margin-top:18px;
  font-size:13px;opacity:.85}
.pg{border:1px solid var(--st-border-color,rgba(0,0,0,.15));background:transparent;
  color:inherit;border-radius:8px;padding:3px 12px;cursor:pointer;font-size:14px}
.pg:disabled{opacity:.35;cursor:default}
.pg:not(:disabled):hover{background:var(--st-secondary-background-color,#f0f0f0)}
"""

_JS = """
export default function (component) {
  const { data, parentElement, setStateValue, setTriggerValue } = component;
  const root = parentElement.querySelector("#root");
  if (!root) return;
  const cards = (data && data.cards) || [];
  const page = (data && data.page) || 1;
  const total = (data && data.totalPages) || 1;
  const esc = (s) => String(s).replace(/[&<>'"]/g, (ch) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]
  ));
  root.innerHTML = `
    <div class="grid">
      ${cards.map((c) => `
        <div class="card" data-id="${esc(c.id)}">
          <div class="thumb">${c.thumb || ""}
            <div class="badges">
              ${c.strategy ? `<span class="badge badge-strat" title="${esc(c.strategy)}">${esc(c.strategy)}</span>` : ""}
              <span class="badge badge-${esc(c.signalClass)}">${esc(c.signal)}</span>
            </div>
            <div class="hover"><span>查看详情</span></div>
          </div>
          <div class="meta">
            <div class="name">${esc(c.name)}</div>
            <div class="sub"><span class="code">${esc(c.code)}</span><span>${esc(c.dateLabel)}</span></div>
            ${c.info ? `<div class="info"><span class="itext" title="${esc(c.info)}">${esc(c.info)}</span></div>` : ""}
          </div>
        </div>`).join("")}
    </div>
    <div class="pager">
      <button class="pg" type="button" data-p="${page - 1}" ${page <= 1 ? "disabled" : ""}>‹</button>
      <span>第 ${page} 页 · 共 ${total} 页</span>
      <button class="pg" type="button" data-p="${page + 1}" ${page >= total ? "disabled" : ""}>›</button>
    </div>`;
  root.querySelectorAll(".card").forEach((el) => {
    el.addEventListener("click", () => setTriggerValue("selected", el.dataset.id));
  });
  root.querySelectorAll(".pg").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = parseInt(btn.dataset.p, 10);
      if (p >= 1 && p <= total) setStateValue("page", p);
    });
  });
}
"""

# 模块级注册一次
_GALLERY = st.components.v2.component(
    "signal_lab_gallery", html=_HTML, css=_CSS, js=_JS
)


def render_gallery(
    cards: list[dict],
    page: int,
    total_pages: int,
    *,
    key: str = "sl_gallery",
) -> object:
    """渲染卡片墙；返回组件 result（.selected 为本次点击的 case id 触发值）。"""
    return _GALLERY(
        key=key,
        data={"cards": cards, "page": page, "totalPages": total_pages},
    )
