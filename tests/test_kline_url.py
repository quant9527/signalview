"""K 线 URL 编解码与信号字段映射的验证测试。"""

from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from symbol_picker import (
    SymbolToken,
    _clean_symbol_code,
    _get_merged_instruments,
    encode_symbol_token,
    parse_symbol_tokens,
)
import symbol_picker
from views.kline_charts import (
    _build_signal_arrow_series,
    build_chart_meta,
    build_echarts_html,
    date_labels,
    extract_symbol_data,
    map_signals_to_bars,
)


# ---------- URL 编解码 ----------


def test_encode_basic() -> None:
    assert encode_symbol_token("as", "000001", "1d", False) == "as:000001:1d"


def test_encode_reverse() -> None:
    assert encode_symbol_token("asindex", "sh000300", "1w", True) == "asindex:sh000300:1w:reverse"


def test_encode_invalid_freq_falls_back() -> None:
    assert encode_symbol_token("as", "000001", "9x", False) == "as:000001:1d"


def test_parse_multiple_tokens() -> None:
    entries = parse_symbol_tokens("as:000001:1d,asindex:sh000300:1w:reverse")
    assert entries == [
        SymbolToken("as", "000001", "1d", False),
        SymbolToken("asindex", "sh000300", "1w", True),
    ]


def test_parse_roundtrip() -> None:
    raw = "as:000001:1d,ths:600519:30m,hyperliquid:BTC:1h:reverse"
    entries = parse_symbol_tokens(raw)
    assert ",".join(e.token for e in entries) == raw


def test_parse_garbage_skipped_and_freq_fixed() -> None:
    entries = parse_symbol_tokens("as:000001,,:badfreq,as:000002:5m")
    assert entries == [
        SymbolToken("as", "000001", "1d", False),
        SymbolToken("as", "000002", "5m", False),
    ]


def test_parse_empty() -> None:
    assert parse_symbol_tokens("") == []
    assert parse_symbol_tokens(None) == []


# ---------- symbol 清洗 / 合并 instrument ----------


def test_clean_symbol_code_strips_suffix() -> None:
    """Instrument 表的 symbol 形如 881145_电力_dl_DL，提取 6 位代码。"""
    assert _clean_symbol_code("881145_电力_dl_DL") == "881145"
    assert _clean_symbol_code("600519") == "600519"
    assert _clean_symbol_code("sh000300") == "sh000300"


def test_clean_symbol_code_does_not_strip_exchange_prefix() -> None:
    """重构后不再从合并表中剥离 exchange_ 前缀；统一由 _source_exchange 解析。"""
    assert _clean_symbol_code("asindex_sh000300") == "asindex_sh000300"
    assert _clean_symbol_code("ths_881145") == "ths_881145"


def test_merged_instruments_keeps_raw_symbols() -> None:
    """_get_merged_instruments 必须保留原始 symbol，不做 exchange_ 前缀拼接。

    替换 get_instruments_by_exchange stub：
    - as 返回空
    - ths 含 ths 表典型后缀格式
    - asindex 含指数代码
    """
    symbol_picker.get_instruments_by_exchange = (  # type: ignore[assignment]
        lambda ex: {
            "ths": pd.DataFrame({
                "symbol": ["881145_电力_dl_DL"],
                "name": ["电力"],
                "alias": [["dl", "DL"]],
            }),
            "asindex": pd.DataFrame({
                "symbol": ["sh000300"],
                "name": ["沪深300"],
                "alias": [["hs300"]],
            }),
        }.get(ex, pd.DataFrame())
    )
    merged = _get_merged_instruments()
    assert set(merged["symbol"].tolist()) == {"881145_电力_dl_DL", "sh000300"}
    assert "_source_exchange" in merged.columns
    src = dict(zip(merged["symbol"], merged["_source_exchange"]))
    assert src["881145_电力_dl_DL"] == "ths"
    assert src["sh000300"] == "asindex"
    # 必须没有前缀拼接
    assert "asindex_sh000300" not in merged["symbol"].tolist()
    assert "ths_881145_电力_dl_DL" not in merged["symbol"].tolist()


def test_parse_preserves_underscore_in_symbol() -> None:
    """解析器不再剥离前缀，符号中的下划线被原样保留。"""
    tokens = parse_symbol_tokens("as:asindex_sh000300:1d")
    assert tokens == [SymbolToken("as", "asindex_sh000300", "1d", False)]


def test_parse_asindex_canonical_roundtrip() -> None:
    """asindex:sh000300:1d canonical token 双向 OK。"""
    tokens = parse_symbol_tokens("asindex:sh000300:1d")
    assert tokens == [SymbolToken("asindex", "sh000300", "1d", False)]
    raw = "asindex:sh000300:1d"
    assert ",".join(t.token for t in tokens) == raw


def test_alias_pipeline_drops_per_row_overlap() -> None:
    """重构后用 explode + groupby 聚合 alias：每行 alias 与该行 symbol/name（精确字符串）相等则丢弃。

    保留：
    - gzmt（不与 symbol=600519 或 name=贵州茅台 相等）
    - 茅台（同理不与 name 严格相等）
    - byd（同理）

    丢弃：
    - 比亚迪（与 name 严格相等）
    - 002594（与 symbol 严格相等）
    """
    df = pd.DataFrame({
        "symbol": ["600519", "002594"],
        "name": ["贵州茅台", "比亚迪"],
        "alias": [["gzmt", "茅台"], ["byd", "比亚迪", "002594"]],
    })
    long = df[["symbol", "name", "alias"]].copy().assign(_alias=df["alias"]).explode("_alias")
    long["_alias"] = long["_alias"].astype(str)
    keep = (long["_alias"].str.lower() != long["symbol"].astype(str).str.lower()) & (
        long["_alias"].str.lower() != long["name"].astype(str).str.lower()
    )
    filtered = long[keep]
    agg = filtered.groupby("symbol", sort=False)["_alias"].agg("_".join)
    assert agg["600519"] == "gzmt_茅台"
    assert agg["002594"] == "byd"


# ---------- 信号字段映射 ----------


def _fake_prep() -> pd.DataFrame:
    return pd.DataFrame({"_x": pd.to_datetime(["2025-01-02", "2025-01-03"])})


def _fake_signals() -> pd.DataFrame:
    return pd.DataFrame({
        "signal_date": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-03"]),
        "signal_name": ["strat_a", "strat_b", "strat_a"],
        "side": ["long", "long", "short"],
        "signal": ["BUY", "BUY", "SELL"],
        "freq": ["1d", "1d", "1d"],
        "price": [10.5, 10.6, 11.2],
        "reason": ["r1", "r2", "r3"],
        "score": [0.87, None, -0.5],
    })


def test_map_signals_fields() -> None:
    mapped = map_signals_to_bars(_fake_prep(), _fake_signals())
    assert [m["barIndex"] for m in mapped] == [0, 0, 1]
    first = mapped[0]
    assert first["side"] == "long"
    assert first["signal_name"] == "strat_a"
    assert first["price"] == 10.5
    assert first["freq"] == "1d"
    assert first["reason"] == "r1"
    assert first["score"] == 0.87
    # score 为 None/NaN 时映射为 None
    assert mapped[1]["score"] is None
    assert mapped[2]["score"] == -0.5


def test_arrow_series_direction_and_stacking() -> None:
    mapped = map_signals_to_bars(_fake_prep(), _fake_signals())
    ohlc = [[10.0, 10.5, 9.8, 10.8], [11.0, 11.2, 10.9, 11.5]]
    series = _build_signal_arrow_series(mapped, ohlc)
    buy = next(s for s in series if s["name"] == "买入")
    sell = next(s for s in series if s["name"] == "卖出")
    # signal 列 BUY -> 买入（上箭头，low 下方，同 bar 堆叠偏移递增）
    assert [p["symbolOffset"] for p in buy["data"]] == [[0, 12], [0, 28]]
    assert buy["data"][0]["value"] == [0, 9.8]
    # signal 列 SELL -> 卖出（下箭头，high 上方）
    assert sell["data"][0]["value"] == [1, 11.5]
    assert sell["data"][0]["symbolOffset"] == [0, -12]


def test_map_signals_direction_prefers_signal_column() -> None:
    """箭头方向优先以 signal 列为准，即使 side 列与之相反。"""
    prep = _fake_prep()
    signals = pd.DataFrame({
        "signal_date": pd.to_datetime(["2025-01-02"]),
        "signal_name": ["strat_x"],
        "side": ["long"],
        "signal": ["SELL"],
        "freq": ["1d"],
        "price": [10.0],
        "reason": ["r"],
        "score": [0.5],
    })
    mapped = map_signals_to_bars(prep, signals)
    assert mapped[0]["kind"] == "SELL"
    series = _build_signal_arrow_series(mapped, [[10, 10.2, 9.8, 10.5]])
    assert any(s["name"] == "卖出" for s in series)


def test_map_signals_filter_by_chart_freq() -> None:
    """提供 chart_freq 时只保留同周期信号。"""
    prep = _fake_prep()
    signals = pd.DataFrame({
        "signal_date": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-03"]),
        "signal_name": ["a", "a", "b"],
        "side": ["long", "long", "long"],
        "signal": ["BUY", "BUY", "SELL"],
        "freq": ["1d", "30m", "1d"],
        "price": [10.0, 10.0, 11.0],
        "reason": ["", "", ""],
        "score": [None, None, None],
    })
    mapped = map_signals_to_bars(prep, signals, chart_freq="1d")
    assert len(mapped) == 2
    assert set(m["freq"] for m in mapped) == {"1d"}


def test_chart_meta_signal_grouping() -> None:
    mapped = map_signals_to_bars(_fake_prep(), _fake_signals())
    meta = build_chart_meta(
        ["2025-01-02", "2025-01-03"],
        [[10.0, 10.5, 9.8, 10.8], [11.0, 11.2, 10.9, 11.5]],
        [],
        mapped,
    )
    sigs0 = meta["signals"][0]
    assert len(sigs0) == 2
    assert sigs0[0]["type"] == "BUY"
    assert sigs0[0]["strategy"] == "strat_a"
    assert sigs0[0]["strength"] == 0.87
    assert sigs0[1]["strength"] is None
    assert meta["signals"][1][0]["type"] == "SELL"
    assert meta["signals"][1][0]["strength"] == -0.5


# ---------- review-fix 回归测试 ----------


def test_extract_symbol_data_filters_by_exchange() -> None:
    df = pd.DataFrame({
        "exchange": ["as", "ths", "as"],
        "symbol": ["600519", "600519", "600519"],
        "end_ts": [1735689600000, 1735689600000, 1735689600000],
        "close": [100.0, 200.0, 100.0],
    })
    prep_as, _ = extract_symbol_data(df, "600519", exchange="as")
    prep_ths, _ = extract_symbol_data(df, "600519", exchange="ths")
    assert prep_as is not None
    assert prep_ths is not None
    assert len(prep_as) == 2
    assert len(prep_ths) == 1


def test_date_labels_include_time_for_intraday() -> None:
    s = pd.Series(pd.to_datetime(["2025-01-02 09:30", "2025-01-02 10:00"]))
    labels = date_labels(s)
    assert labels == ["2025-01-02 09:30", "2025-01-02 10:00"]


def test_date_labels_daily_freq_ignores_time() -> None:
    """日线/周线明确按日期展示，不受收盘时间戳影响。"""
    s = pd.Series(pd.to_datetime(["2025-01-02 15:00", "2025-01-03 15:00"]))
    assert date_labels(s, freq="1d") == ["2025-01-02", "2025-01-03"]
    assert date_labels(s, freq="1w") == ["2025-01-02", "2025-01-03"]


def test_date_labels_date_only_for_daily() -> None:
    s = pd.Series(pd.to_datetime(["2025-01-02", "2025-01-03"]))
    labels = date_labels(s)
    assert labels == ["2025-01-02", "2025-01-03"]


def test_map_signals_intraday_nearest_bar() -> None:
    prep = pd.DataFrame({
        "_x": pd.to_datetime(["2025-01-02 09:30", "2025-01-02 10:00", "2025-01-02 10:30"]),
    })
    signals = pd.DataFrame({
        "signal_date": pd.to_datetime(["2025-01-02 09:46"]),
        "signal_name": ["strat_a"],
        "side": ["long"],
        "signal": ["BUY"],
        "freq": ["30m"],
        "price": [10.0],
        "reason": ["r1"],
        "score": [0.5],
    })
    mapped = map_signals_to_bars(prep, signals)
    assert len(mapped) == 1
    assert mapped[0]["barIndex"] == 1  # nearest to 10:00


def test_build_echarts_html_escapes_script_tag() -> None:
    charts = [{
        "id": "ch_x",
        "height": 100,
        "option": {
            "title": {"text": "</script><script>alert(1)</script>"},
            "series": [],
            "xAxis": {},
            "yAxis": {},
        },
    }]
    metas = {"ch_x": {"dates": [], "kline": [], "mas": [], "signals": {}}}
    html = build_echarts_html(charts, metas)
    # The dangerous literal from the title must be escaped inside the option JSON.
    assert '"</script><script>alert(1)</script>"' not in html
    assert '"<\\/script><\\/script>"' in html or '"<\\/script><script>alert(1)<\\/script>"' in html
