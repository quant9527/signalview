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


def test_fmt_ts_uses_shanghai_clock():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    utc = datetime(2026, 11, 3, 12, 8, tzinfo=ZoneInfo("UTC"))
    assert d._fmt_ts(utc) == "2026-11-03 20:08"
    assert d._fmt_ts(None) == ""


def test_format_case_when_always_includes_clock():
    from app_pages.signal_lab import format_case_when

    assert format_case_when("2026-04-03", "2026-04-03 10:30") == "2026.04.03 10:30"
    assert format_case_when("2026-04-03", "2026-04-03 15:00") == "2026.04.03 15:00"
    assert format_case_when("2026-04-03", None) == "2026.04.03"


def test_case_signal_for_save_splits_pick_and_ban():
    from app_pages.signal_lab import case_signal_for_save

    assert case_signal_for_save("pick", "BUY") == "BUY"
    assert case_signal_for_save("pick", "SELL") == "SELL"
    assert case_signal_for_save("pick", "") == "BUY"
    assert case_signal_for_save("ban", "BUY") == "NOT_BUY"
    assert case_signal_for_save("ban", "SELL") == "NOT_BUY"


def test_parse_case_when_accepts_dotted_clock():
    from datetime import datetime

    from app_pages.signal_lab import parse_case_when

    assert parse_case_when("2026.04.03 10:30") == datetime(2026, 4, 3, 10, 30)
    assert parse_case_when("2026.04.03") == datetime(2026, 4, 3)


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


def test_strategy_page_names_keeps_strategies_without_cases():
    assert d.strategy_page_names(
        ["bc_xd4"], ["bc_xd4", "xd3_reb2x_break_macd"],
    ) == ["bc_xd4", "xd3_reb2x_break_macd"]
    assert d.strategy_page_names(["orphan"], []) == ["orphan"]


def test_rows_to_cases_maps_db_row():
    from datetime import datetime

    rows = [(
        "r1", "闽东电力", date(2025, 7, 27), "as:000993:1h",
        "BUY", "bc_xd4", "info", "note", datetime(2025, 7, 27, 10, 30),
    )]
    out = d._rows_to_cases(rows)
    assert out == [{
        "id": "r1", "name": "闽东电力", "date": "2025-07-27",
        "code": "as:000993:1h", "signal": "BUY",
        "strategy": "bc_xd4", "info": "info", "note": "note",
        "at": "2025-07-27 10:30",
    }]


def test_rows_to_cases_without_clock():
    rows = [("r1", "闽东电力", date(2025, 7, 27), "as:000993:1h",
             "BUY", "bc_xd4", "info", "note", None)]
    assert d._rows_to_cases(rows)[0]["at"] == ""


def test_case_title_uses_instrument_name():
    assert d.case_title("as", "688549", ["中巨芯"]) == "中巨芯"
    assert d.case_title("as", "000001", [None, " 平安银行 "]) == "平安银行"
    with pytest.raises(ValueError, match="不存在"):
        d.case_title("as", "000000", None)
    with pytest.raises(ValueError, match="没有名称"):
        d.case_title("as", "000000", ["", None])


def test_prepare_new_case_checks_name_code_and_strategy():
    from datetime import datetime

    when = datetime(2026, 4, 3, 10, 30, 15)
    with pytest.raises(ValueError, match="没有名称"):
        d.prepare_new_case("  ", "as:688549:1h", "bc", "BUY", when, strategy_known=True)
    with pytest.raises(ValueError, match="标的代码"):
        d.prepare_new_case("中巨芯", "688549", "bc", "BUY", when, strategy_known=True)
    with pytest.raises(ValueError, match="不存在"):
        d.prepare_new_case("中巨芯", "as:688549:1h", "nope", "BUY", when, strategy_known=False)
    out = d.prepare_new_case(
        " 中巨芯 ", " as:688549:1h ", " bc_xd4_macd ", "BUY", when,
        info=" i ", note=" ", strategy_known=True,
    )
    assert out["name"] == "中巨芯"
    assert out["code"] == "as:688549:1h"
    assert out["strategy"] == "bc_xd4_macd"
    assert out["when"] == datetime(2026, 4, 3, 10, 30)
    assert out["info"] == "i" and out["note"] == ""


def test_checked_strategy_name_rejects_unknown():
    import pytest

    assert d.checked_strategy_name(" bc_xd4_macd ", True) == "bc_xd4_macd"
    with pytest.raises(ValueError, match="不存在"):
        d.checked_strategy_name("no_such", False)


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
