"""规范化浏览器抓取的 SIGNAL LAB 案例数据并写入 data/signal_lab_cases.json。

用法：
    1. 在飞书策略库页面执行 scripts/signal_lab_fetch.js 的 signalLabFetch()
    2. 把返回数组保存为 JSON（如 /tmp/signal_lab_raw.json）
    3. uv run python scripts/fetch_signal_lab.py /tmp/signal_lab_raw.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "signal_lab_cases.json"


def normalize(raw: list[dict]) -> tuple[list[dict], int]:
    """丢弃缺 id/code 的记录；按 date 降序。返回 (cases, dropped)。"""
    cases = [c for c in raw if str(c.get("id", "")).strip() and str(c.get("code", "")).strip()]
    cases.sort(key=lambda c: (str(c.get("date") or ""), str(c.get("id") or "")), reverse=True)
    return cases, len(raw) - len(cases)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    raw = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    cases, dropped = normalize(raw)
    payload = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(cases),
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"写入 {OUT}: {len(cases)} 条（丢弃 {dropped} 条缺 id/code 的记录）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
