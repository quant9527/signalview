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
            "thumb": thumbs.get(key) or "<svg xmlns='http://www.w3.org/2000/svg'/>",
        })
    return cards


_HTML = "<div id=\"root\"></div>"

_CSS = """
#root{font-family:var(--st-font, sans-serif);color:var(--st-text-color)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}
.card{position:relative;border-radius:12px;overflow:hidden;cursor:pointer;
  background:var(--st-secondary-background-color,#fff);
  border:1px solid var(--st-border-color,rgba(0,0,0,.08));
  transition:box-shadow .18s ease,transform .18s ease}
.card:hover{box-shadow:0 8px 24px rgba(0,0,0,.12);transform:translateY(-2px)}
.thumb{aspect-ratio:16/9;background:var(--st-secondary-background-color,#f5f5f5)}
.thumb svg{width:100%;height:100%;display:block}
.badge{position:absolute;top:10px;left:10px;padding:2px 10px;border-radius:999px;
  font-size:11px;font-weight:600;letter-spacing:.04em;color:#fff;background:#64748b}
.badge-buy{background:#5f8d78}.badge-sell{background:#c0504d}
.badge-ignore{background:#8a8f98}.badge-notbuy{background:#4b5563}
.badge-long{background:#4a7bb5}
.hover{position:absolute;inset:0 0 44px 0;display:flex;align-items:center;justify-content:center;
  background:rgba(15,23,42,.45);opacity:0;transition:opacity .18s ease}
.card:hover .hover{opacity:1}
.hover span{color:#fff;font-size:13px;border:1px solid rgba(255,255,255,.7);
  border-radius:999px;padding:4px 14px}
.meta{padding:10px 12px 12px}
.name{font-size:14px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.date{font-size:12px;opacity:.6;margin-top:2px}
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
          <div class="thumb">${c.thumb || ""}</div>
          <span class="badge badge-${esc(c.signalClass)}">${esc(c.signal)}</span>
          <div class="hover"><span>查看详情</span></div>
          <div class="meta">
            <div class="name">${esc(c.name)}</div>
            <div class="date">${esc(c.dateLabel)}</div>
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
