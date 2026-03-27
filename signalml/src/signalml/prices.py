"""A-share daily bars via akshare with simple parquet cache."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import akshare as ak
import pandas as pd


def normalize_symbol_6(symbol: str) -> str:
    s = str(symbol).strip()
    s = re.sub(r"^[sS][hH]|^[sS][zZ]", "", s)
    s = re.sub(r"\.[A-Za-z]+$", "", s)
    return s.strip().zfill(6)


def _cache_path(cache_dir: Path, symbol: str) -> Path:
    h = hashlib.sha256(symbol.encode()).hexdigest()[:16]
    return cache_dir / f"daily_{h}.parquet"


def fetch_daily_bars(symbol: str, cache_dir: Path | None = None, refresh: bool = False) -> pd.DataFrame:
    """Return columns: trade_date (date), close. Empty if fetch fails."""
    code = normalize_symbol_6(symbol)
    if not code.isdigit() or len(code) != 6:
        return pd.DataFrame(columns=["trade_date", "close"])
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cp = _cache_path(cache_dir, code)
        if not refresh and cp.exists():
            df = pd.read_parquet(cp)
            if not df.empty and "trade_date" in df.columns and "close" in df.columns:
                return df
    try:
        # akshare: 日线前复权
        raw = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20100101", adjust="qfq")
    except Exception:
        return pd.DataFrame(columns=["trade_date", "close"])
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["trade_date", "close"])
    # 列名因版本而异
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
