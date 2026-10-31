"""SIGNAL LAB 缩略图：窗口切片与 SVG 渲染测试（合成数据，不打网络）。"""
import pandas as pd
import pytest

from app_pages import _signal_lab_thumbs as t


@pytest.fixture
def bars() -> pd.DataFrame:
    """80 根合成日 K：_x + OHLC + volume。"""
    rows = []
    base = pd.Timestamp("2025-01-01")
    for i in range(80):
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
    svg = t.render_candle_svg(bars, "2025-03-01")
    assert svg is not None
    assert "nan" not in svg


def test_placeholder_svg():
    svg = t.placeholder_svg()
    assert svg.startswith("<svg") and "暂无" in svg
