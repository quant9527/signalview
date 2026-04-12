"""
K 线：通过 Flight 拉取 OHLC + 成交量 + 均线 + MACD（同一次 do_get），Plotly 多子图；支持滚轮缩放。
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import os

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flight_kline_client as fkc
from constants import (
    EXCHANGE_AS,
    KLINE_DEFAULT_FREQ,
    KLINE_EXCHANGE_OPTIONS,
    KLINE_FREQ_OPTIONS,
    KLINE_FREQ_SET,
)

TZ_SHANGHAI = ZoneInfo("Asia/Shanghai")


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
    """symbol、freq、start、end 齐全且日期合法时视为完整，可自动拉图（无需点确定）。"""
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
    """full=True 时每轮用 URL 覆盖控件状态；full=False 时只覆盖 URL 里出现的键。"""
    if full:
        ex = _qp_get(qp, "exchange") or EXCHANGE_AS
        st.session_state["kline_exchange"] = ex if ex in KLINE_EXCHANGE_OPTIONS else EXCHANGE_AS
        st.session_state["kline_symbol"] = _qp_get(qp, "symbol") or ""
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
        st.session_state["kline_symbol"] = _qp_get(qp, "symbol")
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
        st.session_state["kline_symbol"] = "600519"
    if "kline_freq" not in st.session_state or st.session_state["kline_freq"] not in KLINE_FREQ_SET:
        st.session_state["kline_freq"] = KLINE_DEFAULT_FREQ
    if "kline_start" not in st.session_state:
        st.session_state["kline_start"] = default_start
    if "kline_end" not in st.session_state:
        st.session_state["kline_end"] = default_end
    if "kline_reverse" not in st.session_state:
        st.session_state["kline_reverse"] = False


def _resolve_flight_url() -> str:
    """优先 `.streamlit/secrets.toml` 的 FLIGHT_URL，否则环境变量或默认（与 `flight_kline_client.default_flight_url` 一致）。"""
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
    """Flight 常见列名：ma5、ma_10、MA20 等。"""
    found: list[tuple[int, str]] = []
    for c in df.columns:
        lc = str(c).strip().lower()
        m = re.fullmatch(r"ma_?(\d+)", lc)
        if m:
            found.append((int(m.group(1)), c))
    found.sort(key=lambda x: x[0])
    return [c for _, c in found]


def _find_macd_columns(df: pd.DataFrame) -> dict[str, str]:
    """
    将接口返回列映射为 dif / dea / hist，便于绑图。
    兼容 talib 风格 macd + macdsignal + macdhist，以及 dif/dea/hist、macd_* 等命名。
    """
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
    l = _pick_col(df, "low", "Low")
    c = _pick_col(df, "close", "Close")
    if c is None:
        return None

    out = df.copy()
    ts_raw = out[ts_col]
    # utc=True：毫秒 epoch 与无时区字符串均按 UTC 解析为带时区时间，再转东八区墙钟（去 tz 供 Plotly）
    out["_x"] = pd.to_datetime(ts_raw, unit="ms", errors="coerce", utc=True)
    if out["_x"].isna().all():
        out["_x"] = pd.to_datetime(ts_raw, errors="coerce", utc=True)
    out["_x"] = out["_x"].dt.tz_convert(TZ_SHANGHAI).dt.tz_localize(None)

    for name, col in (("open", o), ("high", h), ("low", l), ("close", c)):
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


def _ma_line_colors(n: int) -> list[str]:
    palette = ["#ffeb3b", "#29b6f6", "#ab47bc", "#66bb6a", "#ffa726", "#ec407a"]
    return [palette[i % len(palette)] for i in range(n)]


def _axis_time_formats(x) -> tuple[str, str]:
    """刻度与悬停时间格式：纯数字，避免 Plotly 默认英文月份缩写。"""
    ts = pd.to_datetime(pd.Series(x).dropna(), errors="coerce").dropna()
    if ts.empty:
        return "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"
    intraday = (
        (ts.dt.hour != 0).any()
        or (ts.dt.minute != 0).any()
        or (ts.dt.second != 0).any()
    )
    if intraday:
        return "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"
    return "%Y-%m-%d", "%Y-%m-%d"


def _x_labels_category(prep_x: pd.Series) -> list[str]:
    """
    横轴用分类标签（与数据行一一对应），避免 datetime 连续轴在休市日仍出刻度。
    标签为东八区墙钟按 strftime 格式化后的字符串。
    """
    _, fmt = _axis_time_formats(prep_x)
    return pd.to_datetime(prep_x, errors="coerce").dt.strftime(fmt).tolist()


def _build_figure(prep: pd.DataFrame, meta: dict) -> go.Figure:
    has_vol = meta["has_volume"] and prep["volume"].notna().any()
    macd_keys = meta["macd"]
    has_macd = bool(macd_keys) and any(prep.get(k, pd.Series(dtype=float)).notna().any() for k in macd_keys.values())

    row_heights: list[float]
    subplot_titles: tuple[str, ...]
    if has_vol and has_macd:
        rows = 3
        row_heights = [0.52, 0.18, 0.22]
        subplot_titles = ("K 线 · 均线", "成交量", "MACD")
    elif has_vol:
        rows = 2
        row_heights = [0.68, 0.28]
        subplot_titles = ("K 线 · 均线", "成交量")
    elif has_macd:
        rows = 2
        row_heights = [0.68, 0.28]
        subplot_titles = ("K 线 · 均线", "MACD")
    else:
        rows = 1
        row_heights = [1.0]
        subplot_titles = ("K 线 · 均线",)

    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06 if rows > 1 else 0,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    x_dt = prep["_x"]
    x_labels = _x_labels_category(x_dt)
    candle_hover = (
        "时间: %{x}<br>开盘: %{open:.4f}<br>最高: %{high:.4f}<br>最低: %{low:.4f}<br>收盘: %{close:.4f}<extra></extra>"
    )

    fig.add_trace(
        go.Candlestick(
            x=x_labels,
            open=prep["open"],
            high=prep["high"],
            low=prep["low"],
            close=prep["close"],
            name="K线",
            increasing_line_color="#ef5350",
            decreasing_line_color="#26a69a",
            hovertemplate=candle_hover,
        ),
        row=1,
        col=1,
    )

    ma_cols: list[str] = meta["ma_cols"]
    colors = _ma_line_colors(len(ma_cols))
    for i, lc in enumerate(ma_cols):
        if lc not in prep.columns:
            continue
        s = prep[lc]
        if s.notna().sum() == 0:
            continue
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=s,
                mode="lines",
                name=lc.upper(),
                line=dict(width=1.2, color=colors[i]),
                legendgroup="ma",
            ),
            row=1,
            col=1,
        )

    row_vol = 2 if has_vol else None
    row_macd = rows if has_macd else None
    if has_vol and has_macd:
        row_macd = 3
    elif has_macd and not has_vol:
        row_macd = 2

    if has_vol and row_vol is not None:
        vol = prep["volume"].fillna(0)
        bar_colors = [
            "#ef5350" if prep["close"].iloc[i] < prep["open"].iloc[i] else "#26a69a"
            for i in range(len(prep))
        ]
        fig.add_trace(
            go.Bar(x=x_labels, y=vol, name="成交量", marker_color=bar_colors, showlegend=False),
            row=row_vol,
            col=1,
        )

    if has_macd and row_macd is not None:
        hist_k = macd_keys.get("hist")
        if hist_k and prep[hist_k].notna().any():
            hist_vals = prep[hist_k]
            hist_colors = ["#ef5350" if v < 0 else "#26a69a" for v in hist_vals.fillna(0)]
            fig.add_trace(
                go.Bar(x=x_labels, y=hist_vals, name="MACD柱", marker_color=hist_colors, showlegend=True),
                row=row_macd,
                col=1,
            )
        dif_k = macd_keys.get("dif")
        if dif_k and prep[dif_k].notna().any():
            fig.add_trace(
                go.Scatter(x=x_labels, y=prep[dif_k], mode="lines", name="DIF", line=dict(width=1.5, color="#ffeb3b")),
                row=row_macd,
                col=1,
            )
        dea_k = macd_keys.get("dea")
        if dea_k and prep[dea_k].notna().any():
            fig.add_trace(
                go.Scatter(x=x_labels, y=prep[dea_k], mode="lines", name="DEA", line=dict(width=1.5, color="#29b6f6")),
                row=row_macd,
                col=1,
            )

    fig.update_layout(
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        dragmode="zoom",
        hovermode="x unified",
        height=280 + rows * 260,
        margin=dict(l=52, r=28, t=48, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="价格", row=1, col=1)
    if has_vol and row_vol is not None:
        fig.update_yaxes(title_text="量", row=row_vol, col=1)
    if has_macd and row_macd is not None:
        fig.update_yaxes(title_text="MACD", row=row_macd, col=1)

    last_row = rows
    for ri in range(1, last_row):
        fig.update_xaxes(showticklabels=False, row=ri, col=1)
    fig.update_xaxes(title_text="时间", row=last_row, col=1)

    for ri in range(1, rows + 1):
        fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor", row=ri, col=1)
        fig.update_yaxes(showspikes=True, spikemode="across", spikesnap="cursor", row=ri, col=1)

    # 分类横轴：仅出现数据里有的时点，休市日不会占刻度（与连续 datetime 轴不同）
    nlab = len(x_labels)
    fig.update_xaxes(
        type="category",
        tickangle=-45 if nlab > 24 else -25 if nlab > 12 else 0,
    )

    return fig


st.header("🕯️ K 线")
st.caption(
    "数据来自 Flight（同一次拉取）：OHLC、**成交量**、**ma5/ma10/…** 均线、**MACD**。"
    "服务地址在 `.streamlit/secrets.toml` 配置 `FLIGHT_URL`（或环境变量 `FLIGHT_URL`）。"
    "图表时间为**东八区**（Asia/Shanghai）墙钟；`pd.to_datetime(..., utc=True)` 按 **UTC** 解析后再转换。"
    "横轴为**分类轴**，只显示接口返回的有 K 线的时点，休市日不会出现空档刻度。"
    "完整查询参数示例：`?symbol=600519&exchange=as&freq=1d&start=2024-01-01&end=2025-01-01`（`exchange` 可为 `as` / `ths` / `asindex`；可选 `reverse=1`），"
    "带齐 **symbol、freq、start、end** 时自动拉图；否则点「确定」。"
)

default_end = date.today()
default_start = default_end - timedelta(days=365)

qp = st.query_params
url_complete = _query_params_fully_specified(qp)
_ensure_kline_session_defaults(default_start, default_end)
_sync_session_from_query_params(qp, full=url_complete, default_start=default_start, default_end=default_end)

c1, c2 = st.columns(2)
with c1:
    exchange = st.selectbox(
        "交易所 / 类型",
        options=list(KLINE_EXCHANGE_OPTIONS),
        key="kline_exchange",
    )
with c2:
    symbol = st.text_input("代码", key="kline_symbol", placeholder="600519 或 sh000300")

kline_freq = st.radio(
    "K 线周期",
    options=list(KLINE_FREQ_OPTIONS),
    key="kline_freq",
    horizontal=True,
    help="与 Flight tag 一致，对应 URL 参数 `freq`。不在列表中的 `freq` 会回落为 1d。",
)

c4, c5 = st.columns(2)
with c4:
    start_d = st.date_input("开始日期", key="kline_start")
with c5:
    end_d = st.date_input("结束日期", key="kline_end")

kline_reverse = st.checkbox(
    "kline_reverse（倒序返回）",
    key="kline_reverse",
    help="Flight 请求体 kline_reverse：服务端是否按时间倒序返回 K 线。",
)

submitted = st.button("确定", type="primary")
run_fetch = url_complete or submitted

if not run_fetch:
    st.info("填写参数后点击「确定」加载 K 线；或在 URL 中提供 **symbol、freq、start、end** 自动加载。")
    st.stop()

symbol = str(symbol).strip()
if not symbol:
    st.error("请输入代码。")
    st.stop()

if start_d > end_d:
    st.error("开始日期不能晚于结束日期。")
    st.stop()

tags = fkc.build_kline_tags([symbol], exchange, kline_freq)
if not tags:
    st.error("代码无效：个股请填 6 位数字；指数请用 sh/sz + 6 位，如 sh000300。")
    st.stop()

st.caption(f"tags = {tags!r}")

sym_key = _symbol_key_from_tags(tags)
if not sym_key:
    st.error("无法解析标的标识，请检查代码与交易所类型。")
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
    st.error(
        "拉取失败：请确认 Flight 服务已启动，且已安装 `pyarrow`。"
        "地址来自 `.streamlit/secrets.toml` 的 `FLIGHT_URL`（或 `[flight] url`），"
        "未配置时使用环境变量 `FLIGHT_URL`（默认 grpc://127.0.0.1:50001）。"
    )
    st.stop()

if raw.empty:
    st.warning("该时间范围内无数据。")
    st.stop()

ex_l = str(exchange).strip().lower()
if "exchange" in raw.columns:
    sub = raw[raw["exchange"].astype(str).str.lower() == ex_l].copy()
else:
    sub = raw.copy()

if "symbol" in sub.columns:
    sub = sub[sub["symbol"].astype(str).str.lower() == sym_key].copy()

if sub.empty:
    st.warning("未找到与请求匹配的标的行（请核对 exchange 与代码）。")
    st.stop()

prepared = _prepare_kline_frame(sub)
if prepared is None:
    st.warning("无法从返回表中解析时间或价格列。")
    st.stop()

prep, meta = prepared
if prep.empty:
    st.warning("该时间范围内无有效 K 线。")
    st.stop()

fig = _build_figure(prep, meta)
st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    },
)

bits = [f"共 {len(prep)} 根 K 线"]
if meta["has_volume"]:
    bits.append("成交量")
if meta["ma_cols"]:
    bits.append("均线 " + ",".join(meta["ma_cols"]))
if meta["macd"]:
    bits.append("MACD")
st.caption(
    " · ".join(bits)
    + " · 在图上**悬停并滚轮**可缩放；多子图**共享横轴**。"
)

if not meta["has_volume"] and not meta["ma_cols"] and not meta["macd"]:
    st.warning(
        "当前返回表未识别到 volume、ma* 或 MACD 列。若接口字段名不同，可在 `views/kline.py` 的 `_find_ma_columns` / `_find_macd_columns` 中补充别名。"
    )
