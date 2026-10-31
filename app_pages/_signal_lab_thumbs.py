"""SIGNAL LAB 卡片缩略图：自绘 SVG 迷你蜡烛图（含成交量柱 + 案例日标记）。

不引入新依赖；K 线数据按 (exchange, freq) 分组经 flight 批量拉取。
"""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from app_pages._signal_lab_data import parse_code
from app_pages.kline_charts import extract_symbol_data
from flight_kline_client import build_kline_tags, fetch_kline_dataframe

WINDOW_BEFORE = 60
WINDOW_AFTER = 20

# freq -> 回看日历天数（保证能取到 WINDOW_BEFORE + WINDOW_AFTER 根）
FREQ_LOOKBACK_DAYS = {
    "15m": 5, "30m": 10, "1h": 30, "2h": 60, "4h": 120,
    "1d": 400, "1w": 2800, "1M": 6000,
}
_DEFAULT_LOOKBACK_DAYS = 400
# freq -> 前瞻日历天数（保证案例日之后能取满 WINDOW_AFTER 根走势）
FREQ_FORWARD_DAYS = {
    "15m": 3, "30m": 6, "1h": 12, "2h": 24, "4h": 48,
    "1d": 60, "1w": 200, "1M": 700,
}
_DEFAULT_FORWARD_DAYS = 60
# 案例日标记容差（单位：天；换算成秒与 _x 比较）
MARK_TOLERANCE_DAYS = 1.5
# 派生频率：服务端不直接入库，取 1d 数据由服务端聚合
DERIVED_FREQS = {"1w": "1d", "1M": "1d"}

_UP = "#26a69a"
_DOWN = "#ef5350"
_MARK = "#f59e0b"


def slice_window(
    bars: pd.DataFrame,
    case_date: str,
    before: int = WINDOW_BEFORE,
    after: int = WINDOW_AFTER,
) -> pd.DataFrame | None:
    """取案例日期前 before 根 + 后 after 根；案例日无精确匹配时锚定最近一根。"""
    if bars is None or bars.empty:
        return None
    bars = bars.reset_index(drop=True)
    target = pd.Timestamp(case_date)
    idx = (bars["_x"] - target).abs().idxmin()
    pos = bars.index.get_loc(idx)
    start = max(0, pos - before)
    end = min(len(bars), pos + after + 1)
    return bars.iloc[start:end]


def fetch_case_bars(code_dates: dict[str, str]) -> dict[str, pd.DataFrame]:
    """批量拉取 {code: 案例日期} 的 K 线；返回 {code: bars}，失败的不出现。"""
    groups: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for code, d in code_dates.items():
        parsed = parse_code(code)
        if parsed:
            ex, sym, freq = parsed
            groups.setdefault((ex, freq), []).append((sym, d))

    out: dict[str, pd.DataFrame] = {}
    for (ex, freq), items in groups.items():
        syms = [s for s, _ in items]
        dates = [pd.Timestamp(d) for _, d in items]
        lookback = FREQ_LOOKBACK_DAYS.get(freq, _DEFAULT_LOOKBACK_DAYS)
        start_ms = int((min(dates) - pd.Timedelta(days=lookback)).value // 1e6)
        end_ms = int((max(dates) + pd.Timedelta(days=FREQ_FORWARD_DAYS.get(freq, _DEFAULT_FORWARD_DAYS))).value // 1e6)
        tag_freq = DERIVED_FREQS.get(freq, freq)
        try:
            tags = build_kline_tags(syms, ex, kline_freq=tag_freq)
            df = fetch_kline_dataframe(
                tags, start_ms, end_ms,
                kline_aggregate=freq if freq in DERIVED_FREQS else "",
            )
        except Exception as e:
            print(f"[SignalLabThumbs] fetch failed for ({ex}, {freq}): {e}")
            continue
        if df is None:
            continue
        for sym, d in items:
            parsed = extract_symbol_data(df, sym, exchange=ex)
            if parsed is not None:
                out[f"{ex}:{sym}:{freq}"] = parsed[0]
    return out


def render_candle_svg(
    bars: pd.DataFrame,
    case_date: str,
    width: int = 264,
    height: int = 148,
    vol_ratio: float = 0.22,
) -> str | None:
    """把窗口 K 线渲染成迷你蜡烛 SVG（成交量柱 + 案例日虚线标记）。"""
    if bars is None or len(bars) == 0:
        return None
    n = len(bars)
    pad_l, pad_r, pad_t = 4.0, 4.0, 6.0
    plot_h = height - pad_t - 4.0
    vol_h = plot_h * vol_ratio
    k_h = plot_h - vol_h - 4.0
    step = (width - pad_l - pad_r) / n
    body_w = max(1.5, step * 0.66)
    hi = float(bars["high"].max())
    lo = float(bars["low"].min())
    span = (hi - lo) or 1.0
    has_vol = "volume" in bars.columns and bars["volume"].notna().any()
    vmax = float(bars["volume"].max()) if has_vol else 0.0

    target = pd.Timestamp(case_date)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none">']
    mark_x: float | None = None
    for i, (_, b) in enumerate(bars.iterrows()):
        o, c = float(b["open"]), float(b["close"])
        if not (math.isfinite(o) and math.isfinite(c)
                and math.isfinite(float(b["high"])) and math.isfinite(float(b["low"]))
                and (not has_vol or math.isfinite(float(b.get("volume", 0.0) or 0.0)))):
            continue
        cx = pad_l + step * (i + 0.5)
        up = c >= o
        color = _UP if up else _DOWN
        y_wick_top = pad_t + (hi - float(b["high"])) / span * k_h
        y_wick_bot = pad_t + (hi - float(b["low"])) / span * k_h
        y_top = pad_t + (hi - max(o, c)) / span * k_h
        bh = max(1.0, abs(c - o) / span * k_h)
        parts.append(
            f'<line x1="{cx:.1f}" y1="{y_wick_top:.1f}" x2="{cx:.1f}" y2="{y_wick_bot:.1f}" '
            f'stroke="{color}" stroke-width="1"/>'
        )
        parts.append(
            f'<rect x="{cx - body_w / 2:.1f}" y="{y_top:.1f}" width="{body_w:.1f}" '
            f'height="{bh:.1f}" fill="{color}"/>'
        )
        if has_vol:
            vh = (float(b.get("volume", 0.0) or 0.0) / vmax) * vol_h if vmax else 0.0
            y_vol = pad_t + k_h + 4.0 + (vol_h - vh)
            parts.append(
                f'<rect x="{cx - body_w / 2:.1f}" y="{y_vol:.1f}" width="{body_w:.1f}" '
                f'height="{max(0.5, vh):.1f}" fill="{color}" opacity="0.4"/>'
            )
        if mark_x is None and abs((b["_x"] - target).total_seconds()) < 86400 * MARK_TOLERANCE_DAYS:
            mark_x = cx
    if mark_x is not None:
        parts.append(
            f'<line x1="{mark_x:.1f}" y1="{pad_t:.1f}" x2="{mark_x:.1f}" '
            f'y2="{pad_t + k_h + 4.0 + vol_h:.1f}" stroke="{_MARK}" stroke-width="1" stroke-dasharray="2,2"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def placeholder_svg(width: int = 264, height: int = 148) -> str:
    """K 线不可用时的占位图。"""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none"><text x="50%" y="50%" text-anchor="middle" '
        f'dominant-baseline="middle" fill="#98a2b3" font-size="13">暂无 K 线数据</text></svg>'
    )


@st.cache_data(ttl=3600, max_entries=64, show_spinner=False)
def thumbs_for_page(code_dates: tuple[tuple[str, str], ...]) -> dict[str, str]:
    """为一页案例生成缩略图；key 为 `code|date`，value 为 SVG 字符串。"""
    code_date_map = {code: d for code, d in code_dates}
    bars_map = fetch_case_bars(code_date_map)
    out: dict[str, str] = {}
    for code, d in code_date_map:
        bars = bars_map.get(code)
        svg = render_candle_svg(slice_window(bars, d), d) if bars is not None else None
        out[f"{code}|{d}"] = svg or placeholder_svg()
    return out
