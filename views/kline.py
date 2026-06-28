"""
K 线：通过 Flight 拉取 OHLC + 成交量 + 均线 + MACD（同一次 do_get），
ECharts 多标联动图表，用于走势对比。

- 支持同时选择多个标的进行对比
- ECharts 连线联动（crosshair 同步）
- 走势对比图（归一化百分比） + 各标的分图（K 线 + 量 + MACD）
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html as st_html

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flight_kline_client as fkc
from constants import (
    EXCHANGE_AS,
    KLINE_DEFAULT_FREQ,
    KLINE_EXCHANGE_OPTIONS,
    KLINE_FREQ_OPTIONS,
    KLINE_FREQ_SET,
)
from symbol_picker import symbol_picker_add_ui, symbol_picker_selected_ui

TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")

# ECharts 深色主题配色（用于多标的走势对比线）
ECHART_COLORS = [
    "#f5923e",
    "#3fb1e3",
    "#6be6c1",
    "#ff99cc",
    "#9fe6b8",
    "#ffcc66",
    "#73c0de",
    "#c487ff",
    "#e68ab8",
    "#91cc75",
]

# 均线颜色（与原来 Plotly 版一致）
MA_COLORS = ["#ffeb3b", "#29b6f6", "#ab47bc", "#66bb6a", "#ffa726", "#ec407a"]


# ===========================================================
# 以下保持与原有实现兼容的辅助函数
# ===========================================================


def _coerce_kline_freq(raw: str | None) -> str:
    s = (raw or "").strip() or KLINE_DEFAULT_FREQ
    return s if s in KLINE_FREQ_SET else KLINE_DEFAULT_FREQ


def _qp_get(qp, key: str) -> str | None:
    if key not in qp:
        return None
    v = qp[key]
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return str(v[0]).strip() if v else None
    s = str(v).strip()
    return s if s else None


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _query_params_fully_specified(qp) -> bool:
    """symbol 齐全（逗号分隔）、freq、start、end 齐全时自动拉图。"""
    if not _qp_get(qp, "symbol") or not _qp_get(qp, "freq"):
        return False
    if _parse_iso_date(_qp_get(qp, "start")) is None or _parse_iso_date(_qp_get(qp, "end")) is None:
        return False
    return True


def _truthy_param(s: str | None) -> bool:
    if s is None:
        return False
    return s.lower() in ("1", "true", "yes", "on")


def _sync_session_from_query_params(qp, *, full: bool, default_start: date, default_end: date) -> None:
    if full:
        ex = _qp_get(qp, "exchange") or EXCHANGE_AS
        st.session_state["kline_exchange"] = ex if ex in KLINE_EXCHANGE_OPTIONS else EXCHANGE_AS
        st.session_state["kline_symbol"] = _parse_symbols_with_exchange(
            _qp_get(qp, "symbol") or "",
            st.session_state.get("kline_exchange", EXCHANGE_AS),
        )
        st.session_state["kline_freq"] = _coerce_kline_freq(_qp_get(qp, "freq"))
        ds = _parse_iso_date(_qp_get(qp, "start"))
        de = _parse_iso_date(_qp_get(qp, "end"))
        st.session_state["kline_start"] = ds if ds is not None else default_start
        st.session_state["kline_end"] = de if de is not None else default_end
        st.session_state["kline_reverse"] = _truthy_param(_qp_get(qp, "reverse"))
        return

    if _qp_get(qp, "exchange") is not None:
        ex = _qp_get(qp, "exchange")
        if ex in KLINE_EXCHANGE_OPTIONS:
            st.session_state["kline_exchange"] = ex
    if _qp_get(qp, "symbol") is not None:
        st.session_state["kline_symbol"] = _parse_symbols_with_exchange(
            _qp_get(qp, "symbol") or "",
            st.session_state.get("kline_exchange", EXCHANGE_AS),
        )
    if _qp_get(qp, "freq") is not None:
        st.session_state["kline_freq"] = _coerce_kline_freq(_qp_get(qp, "freq"))
    if _qp_get(qp, "start") is not None:
        ds = _parse_iso_date(_qp_get(qp, "start"))
        if ds is not None:
            st.session_state["kline_start"] = ds
    if _qp_get(qp, "end") is not None:
        de = _parse_iso_date(_qp_get(qp, "end"))
        if de is not None:
            st.session_state["kline_end"] = de
    if _qp_get(qp, "reverse") is not None:
        st.session_state["kline_reverse"] = _truthy_param(_qp_get(qp, "reverse"))


def _ensure_kline_session_defaults(default_start: date, default_end: date) -> None:
    if "kline_exchange" not in st.session_state:
        st.session_state["kline_exchange"] = EXCHANGE_AS
    if "kline_symbol" not in st.session_state:
        st.session_state["kline_symbol"] = []
    # 迁移：旧格式 list[str] → list[tuple[str, str]]（exchange, symbol）
    elif st.session_state["kline_symbol"] and isinstance(st.session_state["kline_symbol"][0], str):
        ex = st.session_state.get("kline_exchange", EXCHANGE_AS)
        st.session_state["kline_symbol"] = [(ex, s) for s in st.session_state["kline_symbol"]]
    if "kline_freq" not in st.session_state or st.session_state["kline_freq"] not in KLINE_FREQ_SET:
        st.session_state["kline_freq"] = KLINE_DEFAULT_FREQ
    if "kline_start" not in st.session_state:
        st.session_state["kline_start"] = default_start
    if "kline_end" not in st.session_state:
        st.session_state["kline_end"] = default_end
    if "kline_reverse" not in st.session_state:
        st.session_state["kline_reverse"] = False


def _resolve_flight_url() -> str:
    try:
        sec = st.secrets
        if "FLIGHT_URL" in sec:
            u = sec["FLIGHT_URL"]
            if u is not None and str(u).strip():
                return str(u).strip()
        if "flight" in sec:
            block = sec["flight"]
            if isinstance(block, dict) and block.get("url"):
                u = str(block["url"]).strip()
                if u:
                    return u
    except (FileNotFoundError, KeyError, TypeError, RuntimeError):
        pass
    return fkc.default_flight_url()


def _symbol_key_from_tags(tags: list[str]) -> str | None:
    if not tags:
        return None
    parts = tags[0].split("_")
    if len(parts) < 3:
        return None
    if parts[0].lower() == fkc.EXCHANGE_ASINDEX:
        return parts[1].lower()
    return parts[1].lower()


def _pick_col(df: pd.DataFrame, *candidates: str) -> str | None:
    lower_map = {str(c).lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def _find_ma_columns(df: pd.DataFrame) -> list[str]:
    found: list[tuple[int, str]] = []
    for c in df.columns:
        lc = str(c).strip().lower()
        m = re.fullmatch(r"ma_?(\d+)", lc)
        if m:
            found.append((int(m.group(1)), c))
    found.sort(key=lambda x: x[0])
    return [c for _, c in found]


def _find_macd_columns(df: pd.DataFrame) -> dict[str, str]:
    lm = {str(c).lower().strip(): c for c in df.columns}
    roles: dict[str, str] = {}

    if "macd" in lm and "macdsignal" in lm:
        roles["dif"] = lm["macd"]
        roles["dea"] = lm["macdsignal"]
        if "macdhist" in lm:
            roles["hist"] = lm["macdhist"]
        return roles

    for k in ("macd_dif", "dif", "diff", "macd_diff", "macdline", "macd_line"):
        if k in lm:
            roles["dif"] = lm[k]
            break
    for k in ("macd_dea", "dea", "signal", "macd_signal"):
        if k in lm:
            roles["dea"] = lm[k]
            break
    for k in ("macd_hist", "macd_bar", "histogram", "hist", "macdhist", "macd_osc"):
        if k in lm:
            roles["hist"] = lm[k]
            break

    return roles


def _prepare_kline_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict] | None:
    """解析时间、OHLC、成交量、均线、MACD；返回排序后的表与元信息。"""
    if df.empty:
        return None
    ts_col = _pick_col(df, "end_ts", "timestamp", "datetime")
    if ts_col is None:
        return None
    o = _pick_col(df, "open", "Open")
    h = _pick_col(df, "high", "High")
    lo = _pick_col(df, "low", "Low")
    c = _pick_col(df, "close", "Close")
    if c is None:
        return None

    out = df.copy()
    ts_raw = out[ts_col]
    out["_x"] = pd.to_datetime(ts_raw, unit="ms", errors="coerce", utc=True)
    if out["_x"].isna().all():
        out["_x"] = pd.to_datetime(ts_raw, errors="coerce", utc=True)
    out["_x"] = out["_x"].dt.tz_convert(TZ_SHANGHAI).dt.tz_localize(None)

    for name, col in (("open", o), ("high", h), ("low", lo), ("close", c)):
        if col is None:
            if name == "close":
                return None
            continue
        out[name] = pd.to_numeric(out[col], errors="coerce")
    if "open" not in out.columns:
        out["open"] = out["close"]
    if "high" not in out.columns:
        out["high"] = out["close"]
    if "low" not in out.columns:
        out["low"] = out["close"]

    vol_src = _pick_col(out, "volume", "Volume", "vol", "Vol")
    has_volume = vol_src is not None
    if has_volume:
        out["volume"] = pd.to_numeric(out[vol_src], errors="coerce")

    ma_src_cols = _find_ma_columns(df)
    ma_plot: list[str] = []
    for col in ma_src_cols:
        lc = str(col).strip().lower()
        out[lc] = pd.to_numeric(out[col], errors="coerce")
        ma_plot.append(lc)

    macd_src = _find_macd_columns(df)
    macd_plot: dict[str, str] = {}
    for role, src in macd_src.items():
        key = f"_macd_{role}"
        out[key] = pd.to_numeric(out[src], errors="coerce")
        macd_plot[role] = key

    out = out.dropna(subset=["_x", "close"]).sort_values("_x")

    meta = {
        "has_volume": has_volume,
        "ma_cols": ma_plot,
        "macd": macd_plot,
    }
    return out, meta


# ===========================================================
# ECharts 渲染函数
# ===========================================================


def _normalize_pct(prices: pd.Series) -> pd.Series:
    """归一化为基准 100 后的涨跌幅 %（以第一个非空值为基准）。"""
    first = prices.dropna()
    if first.empty or first.iloc[0] == 0:
        return pd.Series(0.0, index=prices.index)
    return (prices / first.iloc[0] - 1) * 100


def _date_labels(s: pd.Series) -> list[str]:
    """ECharts 横轴分类标签（东八区墙钟）。"""
    return pd.to_datetime(s).dt.strftime("%Y-%m-%d").tolist()


def _split_symbol_input(raw: str) -> list[str]:
    """将逗号分隔的代码串解析为列表。"""
    return [s.strip() for s in raw.replace("，", ",").split(",") if s.strip()]


def _parse_symbols_with_exchange(raw: str, default_exchange: str) -> list[tuple[str, str]]:
    """解析逗号分隔的 symbol 列表，支持 exchange:symbol 格式。"""
    result: list[tuple[str, str]] = []
    for s in _split_symbol_input(raw):
        if ":" in s:
            ex, sym = s.split(":", 1)
            result.append((ex if ex in KLINE_EXCHANGE_OPTIONS else default_exchange, sym))
        else:
            result.append((default_exchange, s))
    return result


def _build_comparison_option(
    common_dates: pd.Series,
    price_map: dict[str, pd.Series],
) -> dict:
    """走势对比图：归一化百分比，所有标的共用一个 x 轴。"""
    labels = _date_labels(common_dates)
    series: list[dict] = []
    for i, (sym, prices) in enumerate(price_map.items()):
        norm = _normalize_pct(prices)
        data_vals: list[float | None] = []
        for v in norm.tolist():
            if pd.notna(v):
                data_vals.append(round(v, 2))
            else:
                data_vals.append(None)
        series.append(
            {
                "type": "line",
                "name": sym,
                "data": data_vals,
                "lineStyle": {"width": 2},
                "symbol": "none",
                "itemStyle": {"color": ECHART_COLORS[i % len(ECHART_COLORS)]},
            }
        )

    return {
        "title": {
            "text": "走势对比（归一化 %）",
            "left": "center",
            "textStyle": {"color": "#ccc", "fontSize": 14},
        },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross"},
        },
        "legend": {
            "data": list(price_map.keys()),
            "top": 30,
            "textStyle": {"color": "#ccc"},
        },
        "grid": {
            "left": "8%",
            "right": "8%",
            "top": 70,
            "bottom": 30,
        },
        "xAxis": {
            "type": "category",
            "data": labels,
            "axisLine": {"lineStyle": {"color": "#555"}},
            "axisLabel": {"color": "#aaa", "rotate": 45},
        },
        "yAxis": {
            "type": "value",
            "name": "涨跌幅 %",
            "nameTextStyle": {"color": "#aaa"},
            "axisLine": {"lineStyle": {"color": "#555"}},
            "axisLabel": {"color": "#aaa"},
            "splitLine": {"lineStyle": {"color": "#333"}},
        },
        "series": series,
        "dataZoom": [
            {"type": "inside"},
            {
                "type": "slider",
                "height": 15,
                "bottom": 5,
                "borderColor": "#555",
                "backgroundColor": "rgba(47,69,84,0)",
                "fillerColor": "rgba(167,183,204,0.4)",
                "labelStyle": {"color": "#aaa"},
            },
        ],
        "backgroundColor": "transparent",
    }


def _build_symbol_candle_option(
    symbol: str,
    labels: list[str],
    ohlc: list[list[float]],
    volume: list[float | None],
    ma_lines: list[dict[str, Any]],
    macd: dict[str, list[float | None]] | None,
    has_volume: bool,
) -> dict:
    """单个标的的 K 线 + 成交量 + MACD 三子图 ECharts option。"""
    has_macd = macd is not None

    # ---------- grids ----------
    if has_volume and has_macd:
        grids = [
            {"left": "8%", "right": "8%", "top": 50, "height": "40%"},
            {"left": "8%", "right": "8%", "top": "51%", "height": "15%"},
            {"left": "8%", "right": "8%", "top": "68%", "bottom": 28},
        ]
    elif has_volume:
        grids = [
            {"left": "8%", "right": "8%", "top": 50, "height": "48%"},
            {"left": "8%", "right": "8%", "top": "60%", "bottom": 28},
        ]
    elif has_macd:
        grids = [
            {"left": "8%", "right": "8%", "top": 50, "height": "48%"},
            {"left": "8%", "right": "8%", "top": "60%", "bottom": 28},
        ]
    else:
        grids = [{"left": "8%", "right": "8%", "top": 50, "bottom": 28}]

    n_grids = len(grids)

    # ---------- xAxes ----------
    x_axes: list[dict] = []
    for i in range(n_grids):
        x_axes.append(
            {
                "type": "category",
                "data": labels,
                "gridIndex": i,
                "axisLabel": {
                    "show": i == n_grids - 1,
                    "color": "#aaa",
                    "rotate": 45,
                },
                "axisLine": {"lineStyle": {"color": "#555"}},
                "axisTick": {"alignWithLabel": True},
            }
        )

    # ---------- yAxes ----------
    y_axes: list[dict] = []
    for i in range(n_grids):
        y_axes.append(
            {
                "type": "value",
                "gridIndex": i,
                "scale": i == 0,
                "axisLine": {"lineStyle": {"color": "#555"}},
                "axisLabel": {"color": "#aaa"},
                "splitLine": {"lineStyle": {"color": "#333"}},
            }
        )
    y_axes[0]["name"] = "价格"
    y_axes[0]["nameTextStyle"] = {"color": "#aaa"}
    if has_volume:
        y_axes[1]["name"] = "量"
        y_axes[1]["nameTextStyle"] = {"color": "#aaa"}
    if has_macd:
        mi = 2 if has_volume else 1
        y_axes[mi]["name"] = "MACD"
        y_axes[mi]["nameTextStyle"] = {"color": "#aaa"}

    # ---------- series ----------
    series: list[dict] = []

    # Candlestick
    series.append(
        {
            "type": "candlestick",
            "name": symbol,
            "data": ohlc,
            "xAxisIndex": 0,
            "yAxisIndex": 0,
            "itemStyle": {
                "color": "#26a69a",
                "color0": "#ef5350",
                "borderColor": "#26a69a",
                "borderColor0": "#ef5350",
            },
        }
    )

    # MA lines
    for ma in ma_lines:
        series.append(
            {
                "type": "line",
                "name": ma["name"],
                "data": ma["data"],
                "xAxisIndex": 0,
                "yAxisIndex": 0,
                "symbol": "none",
                "lineStyle": {"width": 1.2, "color": ma["color"]},
            }
        )

    # Volume
    if has_volume:
        vol_idx = 1 if has_macd else 1
        bar_data: list[dict] = []
        for i in range(len(ohlc)):
            v = volume[i]
            if v is None:
                bar_data.append({"value": None, "itemStyle": {"color": "#555"}})
            else:
                up = ohlc[i][0] <= ohlc[i][1]  # open <= close 为涨
                bar_data.append(
                    {
                        "value": v,
                        "itemStyle": {"color": "#26a69a" if up else "#ef5350"},
                    }
                )
        series.append(
            {
                "type": "bar",
                "name": "成交量",
                "data": bar_data,
                "xAxisIndex": vol_idx,
                "yAxisIndex": vol_idx,
            }
        )

    # MACD
    if has_macd and macd is not None:
        mi = 2 if has_volume else 1
        hist = macd.get("hist", [])
        dif = macd.get("dif", [])
        dea = macd.get("dea", [])
        # 带涨跌配色的 MACD 柱（正值绿、负值红）
        macd_bar_data: list[dict] = []
        for v in hist:
            if v is None:
                macd_bar_data.append({"value": None, "itemStyle": {"color": "#555"}})
            else:
                macd_bar_data.append({
                    "value": v,
                    "itemStyle": {"color": "#26a69a" if v >= 0 else "#ef5350"},
                })
        series.append(
            {
                "type": "bar",
                "name": "MACD",
                "data": macd_bar_data,
                "xAxisIndex": mi,
                "yAxisIndex": mi,
            }
        )
        series.append(
            {
                "type": "line",
                "name": "DIF",
                "data": dif,
                "xAxisIndex": mi,
                "yAxisIndex": mi,
                "symbol": "none",
                "lineStyle": {"width": 1.5, "color": "#ffeb3b"},
            }
        )
        series.append(
            {
                "type": "line",
                "name": "DEA",
                "data": dea,
                "xAxisIndex": mi,
                "yAxisIndex": mi,
                "symbol": "none",
                "lineStyle": {"width": 1.5, "color": "#29b6f6"},
            }
        )

    legend_names = [symbol] + [m["name"] for m in ma_lines]
    n_grids = len(grids)
    data_zoom = [
        {"type": "inside", "xAxisIndex": list(range(n_grids))},
        {
            "type": "slider",
            "xAxisIndex": list(range(n_grids)),
            "height": 15,
            "bottom": 5,
            "borderColor": "#555",
            "backgroundColor": "rgba(47,69,84,0)",
            "fillerColor": "rgba(167,183,204,0.4)",
            "labelStyle": {"color": "#aaa"},
        },
    ]

    return {
        "title": {
            "text": symbol,
            "left": "left",
            "textStyle": {"color": "#fff", "fontSize": 14},
        },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross"},
        },
        "legend": {
            "data": legend_names,
            "top": 5,
            "right": 20,
            "textStyle": {"color": "#ccc"},
            "selected": {symbol: True},
        },
        "grid": grids,
        "xAxis": x_axes,
        "yAxis": y_axes,
        "series": series,
        "dataZoom": data_zoom,
        "backgroundColor": "transparent",
    }


def _build_echarts_html(chart_configs: list[dict]) -> str:
    """渲染多个 ECharts 实例的 HTML，charts 之间 connect 实现联动。"""
    divs: list[str] = []
    inits: list[str] = []
    opts: list[str] = []

    for cfg in chart_configs:
        cid = cfg["id"]
        h = cfg["height"]
        divs.append(
            f'<div id="{cid}" style="width:100%;height:{h}px;margin-bottom:6px;"></div>'
        )
        inits.append(f'ch["{cid}"]=echarts.init(document.getElementById("{cid}"),"dark");')
        opts.append(f'ch["{cid}"].setOption({json.dumps(cfg["option"], ensure_ascii=False)});')

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>*{{margin:0;padding:0;box-sizing:border-box;}}body{{background:#0e1117;padding:6px;}}</style>
</head><body>
{"".join(divs)}
<script>
(function(){{var ch={{}};
{"".join(inits)}
var lst=Object.values(ch);
lst.forEach(function(c){{if(c)c.group='kl';}});
if(lst.length)echarts.connect('kl');
{"".join(opts)}
var syncZoom=function(params){{var p=params.batch?params.batch[0]:params;if(p.start==null||p.end==null)return;var src=this;lst.forEach(function(c){{if(c&&c!==src){{c.dispatchAction({{type:'dataZoom',start:p.start,end:p.end}});}}}});}};
lst.forEach(function(c){{if(c)c.on('dataZoom',syncZoom);}});
window.addEventListener("resize",function(){{lst.forEach(function(c){{if(c)c.resize();}});}});
}})();
</script></body></html>"""
    return html


# ===========================================================
# 数据提取与转换
# ===========================================================


def _extract_symbol_data(
    df: pd.DataFrame,
    sym_key: str,
) -> tuple[pd.DataFrame, dict] | None:
    """从混表中按 symbol 过滤并解析 K 线。"""
    raw = df.copy()
    if "symbol" in raw.columns:
        raw = raw[raw["symbol"].astype(str).str.lower() == sym_key.lower()]
    if raw.empty:
        return None
    return _prepare_kline_frame(raw)


def _to_echarts_ohlc(prep: pd.DataFrame) -> list[list[float]]:
    """ECharts candlestick 数据，[open, close, low, high] 格式。"""
    rows: list[list[float]] = []
    for _, r in prep.iterrows():
        rows.append([float(r["open"]), float(r["close"]), float(r["low"]), float(r["high"])])
    return rows


def _to_echarts_volume(prep: pd.DataFrame) -> list[float | None]:
    if "volume" not in prep.columns:
        return []
    return [
        None if pd.isna(v) else float(v)
        for v in prep["volume"]
    ]


def _to_echarts_ma(prep: pd.DataFrame, ma_cols: list[str]) -> list[dict[str, Any]]:
    lines: list[dict] = []
    for i, lc in enumerate(ma_cols):
        if lc not in prep.columns:
            continue
        s = prep[lc]
        if s.notna().sum() == 0:
            continue
        lines.append(
            {
                "name": lc.upper(),
                "data": [None if pd.isna(v) else round(float(v), 4) for v in s],
                "color": MA_COLORS[i % len(MA_COLORS)],
            }
        )
    return lines


def _to_echarts_macd(prep: pd.DataFrame, macd_keys: dict[str, str]) -> dict[str, list[float | None]] | None:
    if not macd_keys:
        return None
    out: dict[str, list[float | None]] = {}
    for role, col in macd_keys.items():
        if col not in prep.columns:
            out[role] = []
        else:
            out[role] = [None if pd.isna(v) else round(float(v), 6) for v in prep[col]]
    return out


# ===========================================================
# 页面入口
# ===========================================================


def main() -> None:
    st.header("🕯️ K 线 · 多标对比")
    st.caption(
        "数据来自 Flight（同一次拉取）：OHLC、**成交量**、**ma5/ma10/…** 均线、**MACD**。"
        "支持同时选择多个标的进行对比，ECharts 连线联动，hover 任一图表时其他图表同步显示 crosshair。"
        "服务地址在 `.streamlit/secrets.toml` 配置 `FLIGHT_URL`（或环境变量 `FLIGHT_URL`）。"
        "图表时间均为**东八区**墙钟。"
    )

    default_end = date.today()
    default_start = default_end - timedelta(days=365)

    qp = st.query_params
    url_complete = _query_params_fully_specified(qp)
    _ensure_kline_session_defaults(default_start, default_end)
    _sync_session_from_query_params(qp, full=url_complete, default_start=default_start, default_end=default_end)

    # ---------- 已选标的（可删除） ----------
    remove_idx = symbol_picker_selected_ui(st.session_state["kline_symbol"])
    if remove_idx is not None:
        st.session_state["kline_symbol"].pop(remove_idx)
        st.rerun()

    # ---------- 添加标的 ----------
    st.markdown("**添加标的**")
    result = symbol_picker_add_ui()
    if result is not None:
        ex, sym = result
        pair = (ex, sym)
        if pair not in st.session_state["kline_symbol"]:
            st.session_state["kline_symbol"].append(pair)
        st.rerun()

    kline_freq = st.radio(
        "K 线周期",
        options=list(KLINE_FREQ_OPTIONS),
        key="kline_freq",
        horizontal=True,
    )

    c4, c5 = st.columns(2)
    with c4:
        start_d = st.date_input("开始日期", key="kline_start")
    with c5:
        end_d = st.date_input("结束日期", key="kline_end")

    kline_reverse = st.checkbox("kline_reverse（倒序返回）", key="kline_reverse")

    submitted = st.button("确定", type="primary")
    run_fetch = url_complete or submitted

    if not run_fetch:
        st.info("选择标的、周期、日期范围后点击「确定」加载 K 线对比图。")
        st.stop()

    if not st.session_state["kline_symbol"]:
        st.error("请至少选择一个标的代码。")
        st.stop()

    if start_d > end_d:
        st.error("开始日期不能晚于结束日期。")
        st.stop()

    # ---------- 构建 tags 并拉取 ----------
    tags: list[str] = []
    sym_keys: list[str] = []
    for sym_exchange, sym_symbol in st.session_state["kline_symbol"]:
        t = fkc.build_kline_tags([sym_symbol], sym_exchange, kline_freq)
        if not t:
            st.error(f"代码「{sym_exchange}:{sym_symbol}」无效，请检查。")
            st.stop()
        tags.extend(t)
        sk = _symbol_key_from_tags(t)
        if sk:
            sym_keys.append(sk)

    if not sym_keys:
        st.error("无法解析标的标识。")
        st.stop()

    start_ms = int(pd.Timestamp(start_d).timestamp() * 1000)
    end_ms = int(pd.Timestamp(end_d).replace(hour=23, minute=59, second=59).timestamp() * 1000)
    flight_url = _resolve_flight_url()

    with st.spinner("正在从 Flight 拉取 K 线…"):
        raw = fkc.fetch_kline_dataframe(
            tags,
            start_ms,
            end_ms,
            flight_url=flight_url or None,
            kline_reverse=kline_reverse,
        )

    if raw is None:
        st.error("拉取失败：请确认 Flight 服务已启动，且已安装 `pyarrow`。")
        st.stop()

    if raw.empty:
        st.warning("该时间范围内无数据。")
        st.stop()

    # ---------- 按 symbol 过滤并解析 ----------

    sym_data: dict[str, tuple[pd.DataFrame, dict]] = {}
    for sk in sym_keys:
        parsed = _extract_symbol_data(raw, sk)
        if parsed is not None:
            sym_data[sk] = parsed

    if not sym_data:
        st.warning("未找到与请求匹配的标的行。")
        st.stop()

    found_syms = list(sym_data.keys())
    st.caption(f"已获取 {len(found_syms)} 个标的：{'、'.join(found_syms)}")

    # ---------- 走势对比图 + 各标的详细图 (合并到一个 HTML/iframe) ----------
    all_charts: list[dict] = []

    if len(found_syms) > 1:
        common_dates: pd.Series | None = None
        price_map: dict[str, pd.Series] = {}
        for sk, (prep, _) in sym_data.items():
            dates = prep["_x"]
            if common_dates is None:
                common_dates = dates
            else:
                common_dates = pd.Series(sorted(set(common_dates) & set(dates)))
        if common_dates is not None and not common_dates.empty:
            for sk, (prep, _) in sym_data.items():
                aligned = prep.set_index("_x").reindex(common_dates)["close"]
                price_map[sk] = aligned

            cmp_option = _build_comparison_option(common_dates, price_map)
            all_charts.append({"id": "cmp", "height": 360, "option": cmp_option})

    for sk, (prep, meta) in sym_data.items():
        labels = _date_labels(prep["_x"])
        ohlc = _to_echarts_ohlc(prep)
        vol = _to_echarts_volume(prep)
        ma_lines = _to_echarts_ma(prep, meta["ma_cols"])
        macd = _to_echarts_macd(prep, meta["macd"])
        has_vol = meta["has_volume"] and prep["volume"].notna().any()

        opt = _build_symbol_candle_option(
            symbol=sk,
            labels=labels,
            ohlc=ohlc,
            volume=vol,
            ma_lines=ma_lines,
            macd=macd,
            has_volume=has_vol,
        )
        all_charts.append({"id": f"ch_{sk}", "height": 520, "option": opt})

    if all_charts:
        full_html = _build_echarts_html(all_charts)
        total_h = sum(c["height"] for c in all_charts) + len(all_charts) * 8 + 10
        st_html(full_html, height=total_h)
    else:
        st.warning("所选标的无共同交易日，无法绘制对比图。")

    # ---------- 摘要 ----------
    bits = [f"共 {len(found_syms)} 个标的"]
    total_bars = sum(len(prep) for prep, _ in sym_data.values())
    bits.append(f"总计 {total_bars} 根 K 线")
    st.caption(" · ".join(bits) + " · 图表已通过 ECharts connect 联动，hover 任一图表时其它图表同步 crosshair。")


main()
