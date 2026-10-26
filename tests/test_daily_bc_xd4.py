"""每日看点 bc_xd4 标的数曲线：纯函数单测，不连数据库。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app_pages.daily_bc_xd4 import (  # noqa: E402
    _clamp_range,
    daily_symbol_counts_by_freq,
    display_window,
)


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "exchange": ["as", "as", "as", "ths", "as", "as"],
            "signal_name": [
                "bc_xd4_a",
                "bc_xd4_a",
                "bc_xd4_b",
                "bc_xd4_a",
                "other",
                "bc_xd4_a",
            ],
            "symbol": ["000001", "000001", "000002", "000003", "000004", "000005"],
            "freq": ["1d", "1d", "1h", "1d", "1d", "1w"],
            "signal_date": pd.to_datetime(
                [
                    "2026-10-01 10:00",
                    "2026-10-01 15:00",
                    "2026-10-01 11:00",
                    "2026-10-01 11:00",
                    "2026-10-01 11:00",
                    "2026-10-03 11:00",
                ]
            ),
        }
    )


def test_counts_unique_symbols_per_freq_and_fills_gaps():
    chart = daily_symbol_counts_by_freq(_rows(), date(2026, 10, 1), date(2026, 10, 3))

    assert list(chart.index) == ["2026-10-01", "2026-10-02", "2026-10-03"]
    # 大周期在前；同日同周期重复 symbol 只计一次
    assert list(chart.columns) == ["1w", "1d", "1h"]
    assert chart.loc["2026-10-01", "1d"] == 1
    assert chart.loc["2026-10-01", "1h"] == 1
    assert chart.loc["2026-10-01", "1w"] == 0
    assert chart.loc["2026-10-02"].tolist() == [0, 0, 0]
    assert chart.loc["2026-10-03", "1w"] == 1


def test_display_window_defaults_to_half_year_and_can_span_all():
    start, end, selected = display_window(
        date(2026, 2, 2), date(2026, 10, 21), date(2026, 10, 22)
    )

    assert start == date(2026, 2, 2)
    assert end == date(2026, 10, 21)
    assert selected == (date(2026, 4, 21), date(2026, 10, 21))


def test_short_history_defaults_to_all():
    start, end, selected = display_window(
        date(2026, 9, 1), date(2026, 10, 1), date(2026, 10, 22)
    )

    assert (start, end) == (date(2026, 9, 1), date(2026, 10, 1))
    assert selected == (start, end)


def test_clamp_range_keeps_selection_inside_history():
    clamped = _clamp_range(
        (date(2025, 1, 1), date(2026, 12, 1)),
        date(2026, 2, 2),
        date(2026, 10, 21),
        (date(2026, 4, 21), date(2026, 10, 21)),
    )

    assert clamped == (date(2026, 2, 2), date(2026, 10, 21))


def test_excludes_rows_outside_window():
    chart = daily_symbol_counts_by_freq(_rows(), date(2026, 10, 2), date(2026, 10, 2))

    assert list(chart.index) == ["2026-10-02"]
    assert list(chart.columns) == []
