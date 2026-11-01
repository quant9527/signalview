"""SIGNAL LAB 数据层纯函数测试。"""
import json
from datetime import date
from pathlib import Path

import pytest

from app_pages import _signal_lab_data as d


@pytest.fixture
def cases() -> list[dict]:
    return [
        {"id": "r1", "name": "闽东电力", "date": "2025-07-27", "code": "as:000993:1h",
         "signal": "BUY", "strategy": "bc_xd4", "info": "a", "note": ""},
        {"id": "r2", "name": "创业板", "date": "2026-01-01", "code": "asindex:sz399006:2h",
         "signal": "SELL", "strategy": "bc_xd4", "info": "", "note": "n"},
        {"id": "r3", "name": "沐曦股份", "date": "2025-10-19", "code": "as:688802:2h",
         "signal": "BUY", "strategy": "cl2b", "info": "i", "note": ""},
    ]


def test_parse_code_valid():
    assert d.parse_code("as:000993:1h") == ("as", "000993", "1h")
    assert d.parse_code("asindex:sz399006:2h") == ("asindex", "sz399006", "2h")


def test_parse_code_invalid():
    assert d.parse_code("as:000993") is None
    assert d.parse_code("::1h") is None
    assert d.parse_code("") is None


def test_filter_cases_all(cases):
    out = d.filter_cases(cases)
    # date 降序
    assert [c["id"] for c in out] == ["r2", "r3", "r1"]


def test_filter_cases_by_strategy_and_signal(cases):
    assert [c["id"] for c in d.filter_cases(cases, strategy="cl2b")] == ["r3"]
    assert [c["id"] for c in d.filter_cases(cases, signal="BUY")] == ["r3", "r1"]
    assert d.filter_cases(cases, keyword="沐曦")[0]["id"] == "r3"
    assert d.filter_cases(cases, keyword="沐曦", signal="SELL") == []


def test_paginate(cases):
    # paginate 不做排序，先经过 filter_cases 得到 date 降序: r2, r3, r1
    ordered = d.filter_cases(cases)
    page_cases, page_no, total = d.paginate(ordered, page=1, per_page=2)
    assert page_no == 1 and total == 2 and len(page_cases) == 2
    page_cases, page_no, total = d.paginate(ordered, page=99, per_page=2)
    assert page_no == 2 and [c["id"] for c in page_cases] == ["r1"]


def test_strategy_and_signal_options(cases):
    assert d.strategy_options(cases) == ["bc_xd4", "cl2b"]
    assert d.signal_options(cases) == ["BUY", "SELL"]


def test_rows_to_cases_maps_db_row():
    rows = [("r1", "闽东电力", date(2025, 7, 27), "as:000993:1h",
             "BUY", "bc_xd4", "info", "note")]
    out = d._rows_to_cases(rows)
    assert out == [{"id": "r1", "name": "闽东电力", "date": "2025-07-27",
                    "code": "as:000993:1h", "signal": "BUY",
                    "strategy": "bc_xd4", "info": "info", "note": "note"}]


def test_rows_to_cases_nulls_become_empty():
    rows = [("r1", None, date(2025, 1, 1), None, None, None, None, None)]
    out = d._rows_to_cases(rows)
    assert out[0]["name"] == "" and out[0]["code"] == ""
    assert out[0]["signal"] == "" and out[0]["info"] == ""


def test_load_cases_from_file(tmp_path: Path):
    p = tmp_path / "cases.json"
    p.write_text(json.dumps({"count": 1, "cases": [
        {"id": "x", "name": "n", "date": "2025-01-01", "code": "as:000001:1d",
         "signal": "BUY", "strategy": "s", "info": "", "note": ""},
        {"id": "bad"},  # 缺必填键，被跳过
    ]}), encoding="utf-8")
    out = d.load_cases(p)
    assert len(out) == 1 and out[0]["id"] == "x"


def test_load_cases_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        d.load_cases(tmp_path / "nope.json")


def test_load_cases_bad_format(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"count": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        d.load_cases(p)
