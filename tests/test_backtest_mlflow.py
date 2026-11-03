"""MLflow 成交表映射到案例卡片。"""
import pandas as pd

from app_pages.backtest_mlflow import kline_code, replace_database, trades_to_cases


def test_replace_database_keeps_credentials():
    url = "postgresql://postgres:secret@127.0.0.1:5432/quant?sslmode=disable"
    assert (
        replace_database(url, "mlflow")
        == "postgresql://postgres:secret@127.0.0.1:5432/mlflow?sslmode=disable"
    )


def test_kline_code_strips_signal_and_reverse():
    assert kline_code("ths:885877:2h@bc_xd4_macd_3b") == "ths:885877:2h"
    assert kline_code("binancespot:BTC:5m:reverse@bc_xd4_macd") == "binancespot:BTC:5m"
    assert kline_code("as:000993:1h") == "as:000993:1h"


def test_trades_to_cases_uses_entry_date_and_return():
    frame = pd.DataFrame([{
        "symbol_id": "ths:885877:2h@bc_xd4_macd_3b",
        "symbol_name": "转基因",
        "signal_name": "bc_xd4_macd_3b",
        "direction": "Long",
        "entry_ts": "2026-08-17 11:30",
        "exit_ts": "2026-09-07 11:30",
        "return_pct": 19.751497,
    }, {
        "symbol_id": "binancespot:BTC:5m:reverse@macd_3bc_short",
        "symbol_name": "Bitcoin",
        "signal_name": "macd_3bc_short",
        "direction": "Short",
        "entry_ts": "2026-02-02 10:00",
        "exit_ts": "2026-02-04 10:00",
        "return_pct": -25.0,
    }])
    cases = trades_to_cases(frame)
    assert cases[0]["code"] == "ths:885877:2h"
    assert cases[0]["date"] == "2026-08-17"
    assert cases[0]["signal"] == "BUY"
    assert cases[0]["strategy"] == "bc_xd4_macd_3b"
    assert cases[0]["name"] == "转基因"
    assert cases[0]["info"].startswith("+19.75%")
    assert cases[1]["code"] == "binancespot:BTC:5m"
    assert cases[1]["signal"] == "SELL"
    assert cases[1]["info"].startswith("-25.00%")
