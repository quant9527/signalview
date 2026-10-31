"""SIGNAL LAB 案例数据：加载、校验、筛选、分页（纯函数，便于测试）。"""
from __future__ import annotations

import json
import math
from pathlib import Path

import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "signal_lab_cases.json"

REQUIRED_KEYS = ("id", "name", "date", "code", "signal", "strategy")
_CASE_KEYS = ("id", "name", "date", "code", "signal", "strategy", "info", "note")


def load_cases(path: Path = DATA_PATH) -> list[dict]:
    """读取并校验案例 JSON。缺失抛 FileNotFoundError，格式错抛 ValueError。

    缺少任一必填键的记录被跳过（不崩溃）。
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


@st.cache_data(ttl=600, max_entries=4)
def get_cases() -> list[dict]:
    """页面入口：读取仓库静态数据（短缓存，改 JSON 后最多 10 分钟生效）。"""
    return load_cases()


def parse_code(code: str) -> tuple[str, str, str] | None:
    """`as:000993:1h` -> `('as', '000993', '1h')`；不合法返回 None。"""
    parts = [p.strip() for p in str(code).split(":")]
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def filter_cases(
    cases: list[dict],
    strategy: str = "全部策略",
    keyword: str = "",
    signal: str = "全部",
) -> list[dict]:
    """按策略/名称关键词/信号类型过滤，date 降序。"""
    kw = keyword.strip().lower()
    out = []
    for c in cases:
        if strategy != "全部策略" and c["strategy"] != strategy:
            continue
        if signal != "全部" and c["signal"] != signal:
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
