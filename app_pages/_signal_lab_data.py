"""SIGNAL LAB 案例数据：加载（PG）、校验、筛选、分页（纯函数，便于测试）。"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "signal_lab_cases.json"

# 筛选哨兵值：页面层下拉/pills 的「不过滤」首选项
ALL_STRATEGY = "全部策略"
ALL_SIGNAL = "全部"

REQUIRED_KEYS = ("id", "name", "date", "code", "signal", "strategy")
_CASE_KEYS = ("id", "name", "date", "code", "signal", "strategy", "info", "note")

_SELECT_SQL = (
    "SELECT id, name, signal_date, symbol_id, signal, strategy, info, note "
    "FROM strategy_case ORDER BY signal_date DESC, id DESC"
)


def _conn_str() -> str | None:
    """PG 连接串：DATABASE_URL 环境变量优先，其次 secrets.toml 的 quantdb。"""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        return st.secrets["connections"]["quantdb"]["url"]
    except Exception:
        return None


def _rows_to_cases(rows: list[tuple]) -> list[dict]:
    """DB 行 -> 页面 case dict（date 统一 ISO 字符串）；纯函数。"""
    return [
        {
            "id": str(r[0]), "name": str(r[1] or ""), "date": r[2].isoformat(),
            "code": str(r[3] or ""), "signal": str(r[4] or ""),
            "strategy": str(r[5] or ""), "info": str(r[6] or ""),
            "note": str(r[7] or ""),
        }
        for r in rows
    ]


def load_cases(path: Path = DATA_PATH) -> list[dict]:
    """读取并校验案例 JSON（迁移脚本与测试用；页面运行时不再读 JSON）。

    缺失抛 FileNotFoundError，格式错抛 ValueError；缺少必填键的记录被跳过。
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(cases, list):
        raise ValueError("signal_lab_cases.json 缺少 cases 列表")
    out = []
    for c in cases:
        if isinstance(c, dict) and all(k in c for k in REQUIRED_KEYS):
            out.append({k: c.get(k, "") for k in _CASE_KEYS})
    return out


@st.cache_data(ttl=600, max_entries=4, show_spinner=False)
def get_cases() -> list[dict]:
    """页面入口：读 PG strategy_case 表（短缓存；迁移后最多 10 分钟生效）。

    连接/查询失败统一转 ValueError，页面层据此显示错误提示。
    """
    url = _conn_str()
    if not url:
        raise ValueError(
            "未配置 PG 连接：请设置 DATABASE_URL 或 .streamlit/secrets.toml "
            "的 connections.quantdb.url"
        )
    import psycopg

    try:
        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(_SELECT_SQL)
            rows = cur.fetchall()
    except psycopg.Error as e:
        raise ValueError(f"PG 查询 strategy_case 失败：{e}") from e
    return _rows_to_cases(rows)


def parse_code(code: str) -> tuple[str, str, str] | None:
    """`as:000993:1h` -> `('as', '000993', '1h')`；不合法返回 None。"""
    parts = [p.strip() for p in str(code).split(":")]
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def filter_cases(
    cases: list[dict],
    strategy: str = ALL_STRATEGY,
    keyword: str = "",
    signal: str = ALL_SIGNAL,
) -> list[dict]:
    """按策略/名称关键词/信号类型过滤，date 降序。"""
    kw = keyword.strip().lower()
    out = []
    for c in cases:
        if strategy != ALL_STRATEGY and c["strategy"] != strategy:
            continue
        if signal != ALL_SIGNAL and c["signal"] != signal:
            continue
        if kw and kw not in str(c["name"]).lower():
            continue
        out.append(c)
    return sorted(out, key=lambda c: (str(c["date"]), str(c["id"])), reverse=True)


def paginate(
    cases: list[dict], page: int, per_page: int = 28
) -> tuple[list[dict], int, int]:
    """返回 (当前页案例, 钳制后的页码, 总页数)。"""
    total_pages = max(1, math.ceil(len(cases) / per_page))
    page = min(max(1, int(page)), total_pages)
    start = (page - 1) * per_page
    return cases[start:start + per_page], page, total_pages


def strategy_options(cases: list[dict]) -> list[str]:
    return sorted({str(c["strategy"]) for c in cases if c["strategy"]})


def signal_options(cases: list[dict]) -> list[str]:
    return sorted({str(c["signal"]) for c in cases if c["signal"]})
