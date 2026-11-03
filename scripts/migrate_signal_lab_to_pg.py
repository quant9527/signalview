"""把 data/signal_lab_cases.json 迁移到 PG（quant 库 strategy_case 表）。

用法：
    uv run python scripts/migrate_signal_lab_to_pg.py [json路径]

连接串取 DATABASE_URL 环境变量或 .streamlit/secrets.toml 的
connections.quantdb.url；表不存在时自动创建，按飞书 record id upsert
（可重复执行）。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_JSON = REPO / "data" / "signal_lab_cases.json"

DDL = """
CREATE TABLE IF NOT EXISTS strategy_case (
    id          text PRIMARY KEY,
    name        text NOT NULL DEFAULT '',
    signal_date date NOT NULL,
    symbol_id   text NOT NULL,
    signal      text NOT NULL DEFAULT '',
    strategy    text NOT NULL DEFAULT '',
    info        text NOT NULL DEFAULT '',
    note        text NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_strategy_case_date
    ON strategy_case (signal_date DESC);
"""

UPSERT = """
INSERT INTO strategy_case
    (id, name, signal_date, symbol_id, signal, strategy, info, note)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    signal_date = EXCLUDED.signal_date,
    symbol_id = EXCLUDED.symbol_id,
    signal = EXCLUDED.signal,
    strategy = EXCLUDED.strategy,
    info = EXCLUDED.info,
    note = EXCLUDED.note,
    updated_at = now();
"""


def conn_str() -> str | None:
    """优先 DATABASE_URL 环境变量，其次 secrets.toml 的 quantdb 连接。"""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        import streamlit as st
        return st.secrets["connections"]["quantdb"]["url"]
    except Exception:
        return None


def load_cases(path: Path) -> list[dict]:
    """读取抓取落盘的 JSON，返回 cases 列表。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = raw.get("cases") if isinstance(raw, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"{path} 缺少 cases 列表")
    return cases


def main(argv: list[str]) -> int:
    json_path = Path(argv[1]) if len(argv) == 2 else DEFAULT_JSON
    if not json_path.exists():
        print(f"JSON 不存在: {json_path}")
        return 2
    url = conn_str()
    if not url:
        print("未配置 PG 连接：请设置 DATABASE_URL 或 .streamlit/secrets.toml")
        return 2

    import psycopg

    cases = load_cases(json_path)
    rows = [
        (str(c["id"]), str(c["name"]), str(c["date"]), str(c["code"]),
         str(c.get("signal") or ""), str(c.get("strategy") or ""),
         str(c.get("info") or ""), str(c.get("note") or ""))
        for c in cases
    ]
    with psycopg.connect(url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(DDL)
        cur.executemany(UPSERT, rows)
        cur.execute("SELECT count(*) FROM strategy_case")
        total = cur.fetchone()[0]
    print(f"迁移完成：upsert {len(rows)} 条，表内共 {total} 条（{json_path}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
