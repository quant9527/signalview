"""K 线：优先 quant-lab Flight RPC（与 signalview data.py 约定一致），失败时可回退 akshare。"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import akshare as ak
import pandas as pd

from signalml.flight_kline import fetch_klines_by_symbols_flight, normalize_asindex_symbol


def normalize_symbol_6(symbol: str) -> str:
    s = str(symbol).strip()
    s = re.sub(r"^[sS][hH]|^[sS][zZ]", "", s)
    s = re.sub(r"\.[A-Za-z]+$", "", s)
    return s.strip().zfill(6)


def _cache_path(cache_dir: Path, symbol: str) -> Path:
    h = hashlib.sha256(symbol.encode()).hexdigest()[:16]
    return cache_dir / f"daily_{h}.parquet"


def _kline_source_mode() -> str:
    """
    flight       仅 Flight，失败则空表
    akshare      仅 akshare
    flight_first 先 Flight，缺标的再 akshare（默认）
    """
    return os.environ.get("SIGNALML_KLINE_SOURCE", "flight_first").strip().lower() or "flight_first"


def _fetch_bars_akshare(code: str, cache_dir: Path | None, refresh: bool) -> pd.DataFrame:
    if not code.isdigit() or len(code) != 6:
        return pd.DataFrame(columns=["trade_date", "close"])
    if cache_dir is not None and not refresh:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cp = _cache_path(cache_dir, code)
        if cp.exists():
            df = pd.read_parquet(cp)
            if not df.empty and "trade_date" in df.columns and "close" in df.columns:
                return df
    try:
        raw = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20100101", adjust="qfq")
    except Exception:
        return pd.DataFrame(columns=["trade_date", "close"])
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["trade_date", "close"])
    date_col = "日期" if "日期" in raw.columns else raw.columns[0]
    close_col = "收盘" if "收盘" in raw.columns else "close" if "close" in raw.columns else None
    if close_col is None:
        for c in raw.columns:
            if "收盘" in str(c) or str(c).lower() == "close":
                close_col = c
                break
    if close_col is None:
        return pd.DataFrame(columns=["trade_date", "close"])
    out = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(raw[date_col], errors="coerce").dt.normalize(),
            "close": pd.to_numeric(raw[close_col], errors="coerce"),
        }
    )
    out = out.dropna(subset=["trade_date", "close"]).sort_values("trade_date").drop_duplicates("trade_date")
    if cache_dir is not None:
        out.to_parquet(_cache_path(cache_dir, code), index=False)
    return out.reset_index(drop=True)


def fetch_bars_map(
    symbols: list[str],
    cache_dir: Path | None = None,
    exchange: str = "as",
    kline_freq: str = "1d",
    refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """
    多标的 K 线字典 code -> DataFrame。
    默认一次 Flight 批量拉取；`SIGNALML_KLINE_SOURCE` 控制与 akshare 回退。
    指数 exchange=asindex 时 key 为 sh000300 / sz399001 形式（与 Flight symbol 一致），勿用 6 位纯数字。
    """
    ex_lc = str(exchange).strip().lower() or "as"
    if ex_lc == "asindex":
        codes = sorted({normalize_asindex_symbol(s) for s in symbols})
        codes = [c for c in codes if c]
    else:
        codes = sorted({normalize_symbol_6(s) for s in symbols})
        codes = [c for c in codes if len(c) == 6 and c.isdigit()]
    mode = _kline_source_mode()
    out: dict[str, pd.DataFrame] = {}
    need_network: list[str] = []

    for c in codes:
        if cache_dir is not None and not refresh:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cp = _cache_path(cache_dir, c)
            if cp.exists():
                df = pd.read_parquet(cp)
                if not df.empty and "trade_date" in df.columns and "close" in df.columns:
                    out[c] = df
                    continue
        need_network.append(c)

    if not need_network:
        return out

    flight_allowed = mode in ("flight", "flight_first", "auto")
    ak_allowed = mode in ("akshare", "flight_first", "auto")

    flight_map: dict[str, pd.DataFrame] | None = None
    if flight_allowed and mode != "akshare":
        flight_map = fetch_klines_by_symbols_flight(
            need_network,
            exchange=ex_lc if ex_lc == "asindex" else exchange,
            kline_freq=kline_freq,
        )

    for c in need_network:
        got: pd.DataFrame | None = None
        if flight_map and c in flight_map and not flight_map[c].empty:
            got = flight_map[c]
        elif ak_allowed and mode != "flight":
            got = _fetch_bars_akshare(c, cache_dir, refresh)
        elif mode == "flight" and (not flight_map or c not in flight_map or flight_map[c].empty):
            got = pd.DataFrame(columns=["trade_date", "close"])
        if got is not None and not got.empty:
            out[c] = got
            if cache_dir is not None:
                got.to_parquet(_cache_path(cache_dir, c), index=False)

    return out


def fetch_daily_bars(symbol: str, cache_dir: Path | None = None, refresh: bool = False, exchange: str = "as") -> pd.DataFrame:
    """单标的；内部走 fetch_bars_map。"""
    code = normalize_symbol_6(symbol)
    m = fetch_bars_map([code], cache_dir=cache_dir, exchange=exchange, refresh=refresh)
    return m.get(code, pd.DataFrame(columns=["trade_date", "close"])).copy()
