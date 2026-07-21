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


# ---------- auto_trigger 行为 ----------


def _install_streamlit_stub(monkeypatch, picked: list[str]) -> None:
    """为 symbol_picker_add_ui 装一个最小 streamlit 桩；picked 控制 selectbox 顺序返回值。"""
    state: dict[str, object] = {}

    class _ColumnsCtx:
        def __init__(self, slots):
            self._slots = slots

        def __enter__(self):
            return tuple(_Ctx() for _ in range(self._slots))

        def __exit__(self, *exc):
            return False

    class _Ctx:
        def __getattr__(self, name):
            return lambda *a, **k: None

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    pick_iter = iter(picked)

    def fake_selectbox(label, *args, **kwargs):
        if "options" in kwargs and kwargs.get("options"):
            # exchange selectbox: return first option (or value)
            return kwargs["options"][0]
        # symbol selectbox (no `options` or empty options) -> pop test value
        key = kwargs.get("key", "")
        if "exchange" in key:
            return "as_all"
        if key.endswith("_symbol_select"):
            try:
                return next(pick_iter)
            except StopIteration:
                return None
        return None

    def fake_button(*args, **kwargs):
        return False

    monkeypatch.setattr("streamlit.session_state", state, raising=False)
    monkeypatch.setattr("streamlit.columns", lambda *a, **k: _ColumnsCtx(3), raising=False)
    monkeypatch.setattr("streamlit.selectbox", fake_selectbox, raising=False)
    monkeypatch.setattr("streamlit.button", fake_button, raising=False)


def test_auto_trigger_emits_on_each_change(monkeypatch) -> None:
    """auto_trigger=True：每次 selectbox 选中新值返回一次 tuple，同值不重复。"""
    import streamlit as _st  # noqa: F401  (确认 import path)

    # 替代成真实的 module attribute stub
    state: dict[str, object] = {}
    pick_iter = iter(["sh000300", "sh000300", "881145_电力_dl_DL", "sh000300"])

    def fake_columns(*a, **k):
        # st.columns([1,2,1]) returns 3 ctxmgrs (one per weight slot).
        # Implementation unpacks as c1, c2, c3 = st.columns(...).
        class _W:
            def __getattr__(self, n): return lambda *a2, **k2: None
            def __enter__(self): return self
            def __exit__(self, *e): return False

        # build 3 ctx managers that each enter as a real `with` block
        weights = a[0] if a else []
        n = len(weights) if isinstance(weights, (list, tuple)) else (weights or 3)
        return [_W() for _ in range(n)]  # tuple-like iterator works for unpacking

    def fake_selectbox(label, *args, **kwargs):
        key = kwargs.get("key", "")
        if "exchange" in key:
            # exchange selectbox: always return as_all to keep merged-table path
            return "as_all"
        if key.endswith("_symbol_select"):
            try:
                return next(pick_iter)
            except StopIteration:
                return None
        return None

    monkeypatch.setattr("streamlit.session_state", state, raising=False)
    monkeypatch.setattr("streamlit.columns", fake_columns, raising=False)
    monkeypatch.setattr("streamlit.selectbox", fake_selectbox, raising=False)
    monkeypatch.setattr("streamlit.button", lambda *a, **k: False, raising=False)

    symbol_picker.get_instruments_by_exchange = (  # type: ignore[assignment]
        lambda ex: {
            "as": symbol_picker.pd.DataFrame(),
            "ths": symbol_picker.pd.DataFrame({
                "symbol": ["881145_电力_dl_DL"],
                "name": ["电力"],
                "alias": [["dl"]],
            }),
            "asindex": symbol_picker.pd.DataFrame({
                "symbol": ["sh000300"],
                "name": ["沪深300"],
                "alias": [["hs300"]],
            }),
        }.get(ex, symbol_picker.pd.DataFrame())
    )

    # 第一次：选中 sh000300 → 应 fire
    r1 = symbol_picker.symbol_picker_add_ui(key_prefix="kfs", auto_trigger=True)
    assert r1 == ("asindex", "sh000300"), f"got {r1}"

    # 第二次：still sh000300（state 内部仍选中同值）→ dedupe → 不 fire
    r2 = symbol_picker.symbol_picker_add_ui(key_prefix="kfs", auto_trigger=True)
    assert r2 is None, f"expected None, got {r2}"

    # 第三次：选中 881145_电力_dl_DL → 换了值，应 fire
    r3 = symbol_picker.symbol_picker_add_ui(key_prefix="kfs", auto_trigger=True)
    assert r3 == ("ths", "881145"), f"got {r3}"

    # 第四次：再次切回 sh000300 → 解锁后能 fire
    r4 = symbol_picker.symbol_picker_add_ui(key_prefix="kfs", auto_trigger=True)
    assert r4 == ("asindex", "sh000300"), f"got {r4}"
