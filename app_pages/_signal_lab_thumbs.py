"""SIGNAL LAB 卡片缩略图：自绘 SVG 蜡烛图（MA5/MA10 + 成交量 + MACD + 案例日标记）。

不引入新依赖；K 线数据按 (exchange, freq) 分组经 flight 批量拉取，
MA 与 MACD 直接复用 flight 返回的预计算列（ma5/ma10/dif/dea/macd）。
"""
from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from app_pages._signal_lab_data import parse_code
from app_pages.kline_charts import extract_symbol_data
from flight_kline_client import build_kline_tags, fetch_kline_dataframe

# K线窗口（缩略图与详情大图共用同一语义，详情经 t.WINDOW_* 引用自动同步）
WINDOW_BEFORE = 220
WINDOW_AFTER = 40

# freq -> 回看日历天数（保证能取到 WINDOW_BEFORE + WINDOW_AFTER 根）
FREQ_LOOKBACK_DAYS = {
    "15m": 18, "30m": 34, "1h": 68, "2h": 136, "4h": 272,
    "1d": 400, "1w": 2800, "1M": 6000,
}
_DEFAULT_LOOKBACK_DAYS = 500
# freq -> 前瞻日历天数（保证案例日之后能取满 WINDOW_AFTER 根走势）
FREQ_FORWARD_DAYS = {
    "15m": 8, "30m": 14, "1h": 24, "2h": 48, "4h": 96,
    "1d": 120, "1w": 500, "1M": 2200,
}
_DEFAULT_FORWARD_DAYS = 60
# 案例日标记容差（单位：天；换算成秒与 _x 比较）
MARK_TOLERANCE_DAYS = 1.5
# 派生频率：服务端不直接入库，取 1d 数据由服务端聚合
DERIVED_FREQS = {"1w": "1d", "1M": "1d"}

# 国内习惯：红涨绿跌
_UP = "#ef5350"
_DOWN = "#26a69a"
_MARK = "#f59e0b"
_MA5 = "#f5a623"
_MA10 = "#4a90e2"
# 缩略图 viewBox（16:9，与卡片 thumb aspect-ratio 匹配）
_WIDTH, _HEIGHT = 640, 360
# 三区高度占比：K线主图 / 成交量 / MACD（剩余为区间隔）
_K_RATIO, _VOL_RATIO = 0.58, 0.14


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


def _polyline(points: list[tuple[float, float] | None], color: str, width: float = 1.0) -> str:
    """把 (x, y) 序列渲染成 polyline；None 处断段，不足两点的段丢弃。"""
    segs: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    for p in points:
        if p is None:
            if len(cur) > 1:
                segs.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) > 1:
        segs.append(cur)
    out = []
    for seg in segs:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in seg)
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linejoin="round"/>'
        )
    return "".join(out)


def _finite(v: object) -> float | None:
    """有限浮点值，否则 None（用于指标列 NaN 容错）。"""
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def render_candle_svg(
    bars: pd.DataFrame,
    case_date: str,
    width: int = _WIDTH,
    height: int = _HEIGHT,
) -> str | None:
    """把窗口 K 线渲染成 SVG（K线+MA5/MA10、成交量柱、MACD、案例日虚线标记）。"""
    if bars is None or len(bars) == 0:
        return None
    n = len(bars)
    pad_l, pad_r, pad_t, pad_b = 4.0, 4.0, 6.0, 2.0
    plot_h = height - pad_t - pad_b
    gap = plot_h * 0.02
    k_h = plot_h * _K_RATIO
    vol_h = plot_h * _VOL_RATIO
    macd_h = plot_h - k_h - vol_h - 2 * gap
    k_top = pad_t
    vol_top = k_top + k_h + gap
    macd_top = vol_top + vol_h + gap
    step = (width - pad_l - pad_r) / n
    body_w = max(1.2, step * 0.62)

    # 指标列（缺失或全 NaN 时对应区域自动退化为空）
    ma5 = pd.to_numeric(bars["ma5"], errors="coerce") if "ma5" in bars.columns else None
    ma10 = pd.to_numeric(bars["ma10"], errors="coerce") if "ma10" in bars.columns else None
    dif = pd.to_numeric(bars["_macd_dif"], errors="coerce") if "_macd_dif" in bars.columns else None
    dea = pd.to_numeric(bars["_macd_dea"], errors="coerce") if "_macd_dea" in bars.columns else None
    hist = pd.to_numeric(bars["_macd_hist"], errors="coerce") if "_macd_hist" in bars.columns else None
    has_macd = any(s is not None and s.notna().any() for s in (dif, dea, hist))

    hi = float(bars["high"].max())
    lo = float(bars["low"].min())
    for s in (ma5, ma10):
        if s is not None and s.notna().any():
            hi = max(hi, float(s.max()))
            lo = min(lo, float(s.min()))
    span = (hi - lo) or 1.0
    has_vol = "volume" in bars.columns and bars["volume"].notna().any()
    vmax = float(bars["volume"].max()) if has_vol else 0.0
    mmax = 1.0
    if has_macd:
        vals = [abs(f) for s in (dif, dea, hist) if s is not None
                for f in s.dropna().tolist()]
        if vals:
            mmax = max(mmax, max(vals))

    def y_k(v: float) -> float:
        return k_top + (hi - v) / span * k_h

    def y_m(v: float) -> float:
        return macd_top + macd_h / 2 - v / mmax * (macd_h / 2)

    target = pd.Timestamp(case_date)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        'preserveAspectRatio="none">'
    ]
    if has_macd:
        parts.append(
            f'<line x1="{pad_l:.1f}" y1="{macd_top + macd_h / 2:.1f}" '
            f'x2="{width - pad_r:.1f}" y2="{macd_top + macd_h / 2:.1f}" '
            'stroke="#888" stroke-width="0.5" opacity="0.6"/>'
        )
    mark_x: float | None = None
    for i, (_, b) in enumerate(bars.iterrows()):
        o, c = _finite(b["open"]), _finite(b["close"])
        h, l = _finite(b["high"]), _finite(b["low"])
        if o is None or c is None or h is None or l is None:
            continue
        vol = _finite(b.get("volume")) if has_vol else 0.0
        if has_vol and vol is None:
            vol = 0.0
        cx = pad_l + step * (i + 0.5)
        color = _UP if c >= o else _DOWN
        y_wick_top, y_wick_bot = y_k(h), y_k(l)
        y_top = y_k(max(o, c))
        bh = max(1.0, abs(c - o) / span * k_h)
        parts.append(
            f'<line x1="{cx:.1f}" y1="{y_wick_top:.1f}" x2="{cx:.1f}" '
            f'y2="{y_wick_bot:.1f}" stroke="{color}" stroke-width="1"/>'
        )
        parts.append(
            f'<rect x="{cx - body_w / 2:.1f}" y="{y_top:.1f}" width="{body_w:.1f}" '
            f'height="{bh:.1f}" fill="{color}"/>'
        )
        if has_vol and vol is not None:
            vh = (vol / vmax) * vol_h if vmax else 0.0
            y_vol = vol_top + (vol_h - vh)
            parts.append(
                f'<rect x="{cx - body_w / 2:.1f}" y="{y_vol:.1f}" width="{body_w:.1f}" '
                f'height="{max(0.5, vh):.1f}" fill="{color}" opacity="0.4"/>'
            )
        if has_macd:
            hv = _finite(hist.iloc[i]) if hist is not None else None
            if hv is not None:
                y0 = y_m(0)
                yv = y_m(hv)
                parts.append(
                    f'<rect x="{cx - body_w / 2:.1f}" y="{min(y0, yv):.1f}" '
                    f'width="{body_w:.1f}" height="{max(0.5, abs(y0 - yv)):.1f}" '
                    f'fill="{_UP if hv >= 0 else _DOWN}" opacity="0.55"/>'
                )
        if mark_x is None and abs((b["_x"] - target).total_seconds()) < 86400 * MARK_TOLERANCE_DAYS:
            mark_x = cx

    # MA 与 MACD 线（逐点 NaN 容错，分段绘制）
    def line_points(s: pd.Series | None, y_fn) -> list[tuple[float, float] | None]:
        if s is None:
            return []
        return [
            (pad_l + step * (i + 0.5), y_fn(v)) if (v := _finite(s.iloc[i])) is not None else None
            for i in range(n)
        ]

    parts.append(_polyline(line_points(ma5, y_k), _MA5))
    parts.append(_polyline(line_points(ma10, y_k), _MA10))
    parts.append(_polyline(line_points(dif, y_m), _MA5))
    parts.append(_polyline(line_points(dea, y_m), _MA10))
    if mark_x is not None:
        parts.append(
            f'<line x1="{mark_x:.1f}" y1="{k_top:.1f}" x2="{mark_x:.1f}" '
            f'y2="{macd_top + macd_h:.1f}" stroke="{_MARK}" stroke-width="1" '
            'stroke-dasharray="3,3"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def placeholder_svg(width: int = _WIDTH, height: int = _HEIGHT) -> str:
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
    for code, d in code_date_map.items():
        bars = bars_map.get(code)
        svg = render_candle_svg(slice_window(bars, d), d) if bars is not None else None
        out[f"{code}|{d}"] = svg or placeholder_svg()
    return out
