"""SIGNAL LAB 案例数据：加载（PG）、校验、筛选、分页（纯函数，便于测试）。"""
from __future__ import annotations

import json
import math
import os
import secrets
from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "signal_lab_cases.json"

# 筛选哨兵值：页面层下拉/pills 的「不过滤」首选项
ALL_STRATEGY = "全部策略"
ALL_SIGNAL = "全部"

REQUIRED_KEYS = ("id", "name", "date", "code", "signal", "strategy")
_CASE_KEYS = ("id", "name", "date", "code", "signal", "strategy", "info", "note")

_SELECT_SQL = (
    "SELECT id, name, signal_date, symbol_id, signal, strategy, info, note, signal_at "
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
    out = []
    for r in rows:
        at = _fmt_ts(r[8]) if len(r) > 8 else ""
        out.append({
            "id": str(r[0]), "name": str(r[1] or ""), "date": r[2].isoformat(),
            "code": str(r[3] or ""), "signal": str(r[4] or ""),
            "strategy": str(r[5] or ""), "info": str(r[6] or ""),
            "note": str(r[7] or ""), "at": at,
        })
    return out


def checked_strategy_name(name: str, exists: bool) -> str:
    """策略名必须能在 strategy 表里对上。不存在时抛 ValueError。"""
    cleaned = str(name or "").strip()
    if not exists:
        raise ValueError(f"策略「{cleaned}」不存在")
    return cleaned


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
    """页面入口：读 PG strategy_case 表（短缓存；写入后会清掉）。

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


def _fmt_ts(value) -> str:
    """时间戳显示为上海时间。空值返回空串。"""
    if value is None:
        return ""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if not isinstance(value, datetime):
        return str(value)
    if value.tzinfo is not None:
        value = value.astimezone(ZoneInfo("Asia/Shanghai"))
    return value.strftime("%Y-%m-%d %H:%M")


@st.cache_data(ttl=600, max_entries=8, show_spinner=False)
def get_strategy(name: str) -> dict | None:
    """读 strategy 表的一行。没有该策略时返回 None。"""
    url = _conn_str()
    if not url:
        raise ValueError(
            "未配置 PG 连接：请设置 DATABASE_URL 或 .streamlit/secrets.toml "
            "的 connections.quantdb.url"
        )
    import psycopg

    try:
        with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT name, core_idea, created_at, updated_at "
                "FROM strategy WHERE name = %s",
                (name,),
            )
            row = cur.fetchone()
    except psycopg.Error as e:
        raise ValueError(f"PG 查询 strategy 失败：{e}") from e
    if row is None:
        return None
    return {
        "name": str(row[0] or ""),
        "core_idea": str(row[1] or ""),
        "created_at": _fmt_ts(row[2]),
        "updated_at": _fmt_ts(row[3]),
    }


def _connect():
    """打开 quant 库连接。没配置或连不上时抛 ValueError。"""
    url = _conn_str()
    if not url:
        raise ValueError(
            "未配置 PG 连接：请设置 DATABASE_URL 或 .streamlit/secrets.toml "
            "的 connections.quantdb.url"
        )
    import psycopg

    try:
        return psycopg.connect(url, autocommit=True)
    except psycopg.Error as e:
        raise ValueError(f"PG 连接失败：{e}") from e


def strategy_exists(name: str) -> bool:
    """strategy 表里是否有这个名字。不走缓存，避免刚写入的策略被判不存在。"""
    import psycopg

    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM strategy WHERE name = %s", (name,))
            return cur.fetchone() is not None
    except psycopg.Error as e:
        raise ValueError(f"PG 查询 strategy 失败：{e}") from e


def update_case_when(case_id: str, when: datetime) -> None:
    """写入案例时间，并同步 signal_date 的日期部分。"""
    if when is None:
        raise ValueError("请选择时间")
    stamp = when.replace(tzinfo=None, second=0, microsecond=0)
    import psycopg

    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE strategy_case "
                "SET signal_at = %s, signal_date = %s, updated_at = now() "
                "WHERE id = %s",
                (stamp, stamp.date(), case_id),
            )
            changed = cur.rowcount
    except psycopg.Error as e:
        raise ValueError(f"更新案例时间失败：{e}") from e
    if changed != 1:
        raise ValueError("案例不存在，可能数据已更新。")
    get_cases.clear()


def prepare_new_case(
    name: str,
    code: str,
    strategy: str,
    signal: str,
    when: datetime | None,
    info: str = "",
    note: str = "",
    *,
    strategy_known: bool,
) -> dict:
    """校验新增案例。策略不存在、代码或名称不合法时抛 ValueError，不写库。"""
    cleaned_name = str(name or "").strip()
    if not cleaned_name:
        raise ValueError("请填写案例名称")
    parsed = parse_code(code)
    if parsed is None:
        raise ValueError("标的代码需要写成 交易所:代码:周期，例如 as:688549:1h")
    cleaned_signal = str(signal or "").strip()
    if not cleaned_signal:
        raise ValueError("请选择信号")
    if when is None:
        raise ValueError("请选择时间")
    stamp = when.replace(tzinfo=None, second=0, microsecond=0)
    return {
        "name": cleaned_name,
        "code": ":".join(parsed),
        "strategy": checked_strategy_name(strategy, strategy_known),
        "signal": cleaned_signal,
        "when": stamp,
        "info": str(info or "").strip(),
        "note": str(note or "").strip(),
    }


def insert_case(
    name: str,
    code: str,
    strategy: str,
    signal: str,
    when: datetime | None,
    info: str = "",
    note: str = "",
) -> str:
    """写入一条案例，返回新 id。id 以 sv 开头，和飞书记录 id 分开。"""
    fields = prepare_new_case(
        name, code, strategy, signal, when, info, note,
        strategy_known=strategy_exists(str(strategy or "").strip()),
    )
    case_id = "sv" + secrets.token_hex(8)
    import psycopg

    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO strategy_case "
                "(id, name, signal_date, signal_at, symbol_id, signal, strategy, info, note) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    case_id, fields["name"], fields["when"].date(), fields["when"],
                    fields["code"], fields["signal"], fields["strategy"],
                    fields["info"], fields["note"],
                ),
            )
    except psycopg.Error as e:
        raise ValueError(f"新增案例失败：{e}") from e
    get_cases.clear()
    return case_id


@st.cache_data(ttl=600, max_entries=2, show_spinner=False)
def list_strategy_names() -> list[str]:
    """strategy 表里的策略名，供新增案例选择。"""
    import psycopg

    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT name FROM strategy ORDER BY name")
            rows = cur.fetchall()
    except psycopg.Error as e:
        raise ValueError(f"PG 查询 strategy 失败：{e}") from e
    return [str(row[0]) for row in rows if row[0]]


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
