"""SIGNAL LAB 缩略图：窗口切片与 SVG 渲染测试（合成数据，不打网络）。"""
import pandas as pd
import pytest

from app_pages import _signal_lab_thumbs as t


@pytest.fixture
def bars() -> pd.DataFrame:
    """400 根合成日 K：_x + OHLC + volume（覆盖 WINDOW_BEFORE+WINDOW_AFTER）。"""
    rows = []
    base = pd.Timestamp("2025-01-01")
    for i in range(400):
        o = 10.0 + i * 0.1
        rows.append({
            "_x": base + pd.Timedelta(days=i),
            "open": o, "high": o + 0.5, "low": o - 0.4, "close": o + 0.2,
            "volume": 1000.0 + i,
        })
    return pd.DataFrame(rows)


def test_slice_window_anchors_case_date(bars):
    w = t.slice_window(bars, "2025-03-01")
    # 案例日在窗口内，且长度不超过 before+after+1
    assert len(w) <= t.WINDOW_BEFORE + t.WINDOW_AFTER + 1
    assert w["_x"].min() <= pd.Timestamp("2025-03-01") <= w["_x"].max()


def test_slice_window_edges(bars):
    # 案例日期远超数据范围时取最近一根（最后一根），窗口被数据尾部截断，不抛异常
    w = t.slice_window(bars, "2030-01-01")
    assert len(w) == t.WINDOW_BEFORE + 1
    assert w["_x"].max() == bars["_x"].max()


def test_slice_window_empty():
    assert t.slice_window(pd.DataFrame(), "2025-01-01") is None


def test_render_candle_svg_contains_candles(bars):
    svg = t.render_candle_svg(bars, "2025-03-01")
    assert svg is not None and svg.startswith("<svg") and svg.endswith("</svg>")
    assert 'stroke-dasharray' in svg  # 案例日标记线存在


def test_render_candle_svg_empty():
    assert t.render_candle_svg(pd.DataFrame(), "2025-01-01") is None


def test_render_candle_svg_skips_nan_rows(bars):
    # 含 NaN 的行不应产出 "nan" 字符串
    bars.loc[10, "open"] = float("nan")
    bars.loc[20, "volume"] = float("nan")  # OHLC 有限但 volume=NaN
    svg = t.render_candle_svg(bars, "2025-03-01")
    assert svg is not None
    assert "nan" not in svg


def test_render_candle_svg_with_indicators(bars):
    # 带 MA/MACD 列：折线与 MACD 柱都渲染出来
    bars = bars.copy()
    bars["ma5"] = bars["close"].rolling(5).mean()
    bars["ma10"] = bars["close"].rolling(10).mean()
    bars["_macd_dif"] = bars["close"] * 0.01
    bars["_macd_dea"] = bars["close"] * 0.008
    bars["_macd_hist"] = (bars["close"] * 0.002).where(
        bars.index % 2 == 0, -bars["close"] * 0.002
    )
    svg = t.render_candle_svg(bars, "2025-03-01")
    assert svg is not None
    assert svg.count("<polyline") >= 4  # MA5/MA10 + DIF/DEA
    assert f'viewBox="0 0 {t._WIDTH} {t._HEIGHT}"' in svg


def test_render_candle_svg_nan_indicators_skipped(bars):
    # 指标列含 NaN 不产生 "nan" 字符串；全 NaN 的指标列不渲染对应线
    bars = bars.copy()
    bars["ma5"] = float("nan")
    bars.loc[5, "ma10"] = float("nan")
    bars["_macd_dif"] = float("nan")
    svg = t.render_candle_svg(bars, "2025-03-01")
    assert svg is not None and "nan" not in svg


def test_placeholder_svg():
    svg = t.placeholder_svg()
    assert svg.startswith("<svg") and "暂无" in svg


def test_thumbs_for_page_builds_svg_per_case(monkeypatch, bars):
    # 回归：迭代 dict 必须用 .items()；fetch_case_bars 打桩，不打网络
    t.thumbs_for_page.clear()
    monkeypatch.setattr(t, "fetch_case_bars", lambda m: {"as:000001:1d": bars})
    out = t.thumbs_for_page((("as:000001:1d", "2025-01-01", ""),))
    assert "as:000001:1d|2025-01-01|" in out
    assert out["as:000001:1d|2025-01-01|"].startswith("<svg")


def test_thumbs_for_page_missing_bars_uses_placeholder(monkeypatch):
    t.thumbs_for_page.clear()
    monkeypatch.setattr(t, "fetch_case_bars", lambda m: {})
    out = t.thumbs_for_page((("as:000001:1d", "2025-01-01", ""),))
    assert out["as:000001:1d|2025-01-01|"].startswith("<svg")
    assert "暂无" in out["as:000001:1d|2025-01-01|"]


def test_anchor_timestamp_uses_saved_clock():
    times = pd.date_range("2026-11-04 09:35", periods=60, freq="5min")
    bars = pd.DataFrame({"_x": times, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0})
    assert t.anchor_timestamp(bars, "2026-11-04", "2026-11-04 13:35") == pd.Timestamp("2026-11-04 13:35")


def test_anchor_timestamp_without_clock_prefers_same_day():
    # 午夜离前一根日终 bar 更近，但只存了日期时应落在当天第一根。
    bars = pd.DataFrame({
        "_x": [pd.Timestamp("2026-11-03 15:00"), pd.Timestamp("2026-11-04 09:35")],
        "open": [1.0, 1.0], "high": [1.0, 1.0], "low": [1.0, 1.0], "close": [1.0, 1.0],
    })
    assert t.anchor_timestamp(bars, "2026-11-04", "") == pd.Timestamp("2026-11-04 09:35")


def test_render_candle_svg_marks_saved_clock():
    times = pd.date_range("2026-11-04 09:35", periods=60, freq="5min")
    rows = []
    for ts in times:
        rows.append({
            "_x": ts, "open": 10.0, "high": 10.5, "low": 9.6, "close": 10.2, "volume": 1000.0,
        })
    bars = pd.DataFrame(rows)
    at = "2026-11-04 13:35"
    svg = t.render_candle_svg(bars, "2026-11-04", at=at)
    pos = int((bars["_x"] == pd.Timestamp(at)).idxmax())
    step = (t._WIDTH - 8) / len(bars)
    expected = 4.0 + step * (pos + 0.5)
    mark = svg.split('stroke-dasharray="3,3"')[0].rsplit('x1="', 1)[1].split('"', 1)[0]
    assert abs(float(mark) - expected) < 0.05
    # 不用保存时刻时，标记落在当天第一根，而不是 13:35。
    plain = t.render_candle_svg(bars, "2026-11-04")
    plain_mark = plain.split('stroke-dasharray="3,3"')[0].rsplit('x1="', 1)[1].split('"', 1)[0]
    assert plain_mark != mark
