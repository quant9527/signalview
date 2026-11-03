"""MLflow 回测：侧边栏每个 run 一页，用案例 K 线网格展示 top/bottom/recent 成交。

跟踪库与 quant-lab ``vbt.tracking`` 相同，默认 ``~/repo/quant-lab/mlflow.db``。
只列出产物里带有 trades_top / trades_bottom / trades_recent 的 run。
"""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import streamlit as st

from app_pages.signal_lab import render_case_gallery

TRACKING_DB = Path(os.environ.get("MLFLOW_TRACKING_DB", "~/repo/quant-lab/mlflow.db")).expanduser()
EXPERIMENT = "backtest"

# (文件名, 页面上的叫法)。顺序即 pills 顺序。
ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("trades_top.json", "收益最高"),
    ("trades_bottom.json", "亏损最大"),
    ("trades_recent.json", "最近"),
)


def kline_code(symbol_id: str) -> str:
    """``ths:885877:2h@bc_xd4`` 或带 ``:reverse`` 的列名 -> ``exchange:symbol:freq``。"""
    base = str(symbol_id or "").split("@", 1)[0]
    parts = [p for p in base.split(":") if p]
    if len(parts) >= 4 and parts[3] == "reverse":
        parts = parts[:3]
    if len(parts) >= 3:
        return ":".join(parts[:3])
    return base


def trades_to_cases(frame: pd.DataFrame) -> list[dict]:
    """MLflow 成交表 -> 案例卡片用的 case dict。标记日是入场日。"""
    if frame is None or frame.empty:
        return []
    cases = []
    seen: set[str] = set()
    for i, row in frame.iterrows():
        symbol_id = str(row.get("symbol_id") or "")
        entry = str(row.get("entry_ts") or "")
        exit_ = str(row.get("exit_ts") or "")
        case_id = f"{symbol_id}|{entry}"
        if case_id in seen:
            case_id = f"{case_id}|{i}"
        seen.add(case_id)
        direction = str(row.get("direction") or "")
        signal = "SELL" if direction.lower() == "short" else "BUY"
        ret = row.get("return_pct")
        ret_txt = ""
        try:
            if ret is not None and ret == ret:
                ret_txt = f"{float(ret):+.2f}%"
        except (TypeError, ValueError):
            ret_txt = ""
        span = entry[:16]
        if exit_:
            span = f"{span} → {exit_[:16]}"
        info = " · ".join(p for p in (ret_txt, span) if p)
        name = str(row.get("symbol_name") or "") or kline_code(symbol_id)
        cases.append({
            "id": case_id,
            "name": name,
            "date": entry[:10],
            "code": kline_code(symbol_id),
            "signal": signal,
            "strategy": str(row.get("signal_name") or ""),
            "info": info,
            "note": direction,
        })
    return cases


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{TRACKING_DB}?mode=ro", uri=True)


def _artifact_labels(artifact_uri: str) -> list[tuple[str, str]]:
    root = Path(artifact_uri)
    return [(name, label) for name, label in ARTIFACTS if (root / name).is_file()]


@st.cache_data(ttl=60, show_spinner=False)
def list_runs() -> list[dict]:
    """实验 backtest 里、产物含成交表的 run，新的在前。"""
    if not TRACKING_DB.is_file():
        return []
    with _connect() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            SELECT r.run_uuid, r.name, r.artifact_uri, r.start_time
            FROM runs r
            JOIN experiments e ON e.experiment_id = r.experiment_id
            WHERE e.name = ? AND r.status = 'FINISHED'
            ORDER BY r.start_time DESC
            """,
            (EXPERIMENT,),
        ).fetchall()
    out = []
    for row in rows:
        labels = _artifact_labels(row["artifact_uri"])
        if not labels:
            continue
        out.append({
            "id": row["run_uuid"],
            "name": row["name"] or row["run_uuid"][:8],
            "artifact_uri": row["artifact_uri"],
            "artifacts": labels,
        })
    return out


def _run_meta(run_id: str) -> tuple[dict[str, str], dict[str, float]]:
    with _connect() as con:
        params = dict(con.execute(
            "SELECT key, value FROM params WHERE run_uuid = ?", (run_id,)
        ).fetchall())
        metrics = {
            key: float(value)
            for key, value in con.execute(
                "SELECT key, value FROM latest_metrics WHERE run_uuid = ?", (run_id,)
            ).fetchall()
        }
    return params, metrics


@st.cache_data(ttl=600, show_spinner=False)
def load_trades(artifact_uri: str, filename: str) -> pd.DataFrame:
    path = Path(artifact_uri) / filename
    return pd.read_json(path, orient="split")


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def _header(name: str, params: dict[str, str], metrics: dict[str, float]) -> None:
    st.markdown(
        f"<div style='font-size:1.4rem;font-weight:700'>{name}</div>",
        unsafe_allow_html=True,
    )
    bits = [
        params.get("pick_id") or "",
        " → ".join(p for p in (params.get("start"), params.get("end")) if p),
        params.get("freqs") or "",
        params.get("target") or "",
    ]
    caption = " · ".join(b for b in bits if b)
    if caption:
        st.caption(caption)
    row = st.container(horizontal=True)
    specs = (
        ("总收益", _fmt_pct(metrics.get("total_return_pct"))),
        ("夏普", "—" if "sharpe_ratio" not in metrics else f"{metrics['sharpe_ratio']:.2f}"),
        ("最大回撤", _fmt_pct(metrics.get("max_dd_pct"))),
        ("成交笔数", "—" if "trade_count" not in metrics else f"{int(metrics['trade_count'])}"),
    )
    with row:
        for label, value in specs:
            st.metric(label, value)


def _render_run(run_id: str) -> None:
    runs = {r["id"]: r for r in list_runs()}
    run = runs.get(run_id)
    title = run["name"] if run else "回测"
    st.set_page_config(layout="wide", page_title=title, page_icon="📈")
    if run is None:
        st.error("这次回测不在 MLflow 里，或产物里没有成交表。")
        return
    try:
        params, metrics = _run_meta(run_id)
    except sqlite3.Error as e:
        st.error(f"读取 MLflow 失败：{e}")
        return
    _header(run["name"], params, metrics)

    labels = [label for _, label in run["artifacts"]]
    choice = st.pills("成交", labels, default=labels[0], key=f"bt_art_{run_id}") or labels[0]
    by_label = {label: name for name, label in run["artifacts"]}
    filename = by_label[choice]
    try:
        frame = load_trades(run["artifact_uri"], filename)
    except (OSError, ValueError) as e:
        st.error(f"读不到 {filename}：{e}")
        return
    render_case_gallery(
        trades_to_cases(frame),
        key=f"bt_gallery_{run_id}_{filename}",
        cycle="all",
    )


def page_for_run(run_id: str) -> Callable[[], None]:
    def _page() -> None:
        _render_run(run_id)

    _page.__name__ = f"page_bt_{run_id}"
    return _page


def page_backtest_empty() -> None:
    st.set_page_config(layout="wide", page_title="回测", page_icon="📈")
    st.error(f"没有可展示的 MLflow 回测。跟踪库：{TRACKING_DB}")


def backtest_pages() -> list[st.Page]:
    """回测分区：每个带成交产物的 run 一个子页。读不到库时只留一个说明页。"""
    try:
        runs = list_runs()
    except Exception as e:
        print(f"[Backtest] MLflow 回测未注册：{e}")
        runs = []
    if not runs:
        return [st.Page(page_backtest_empty, title="回测", icon="📈", url_path="backtest")]
    pages: list[st.Page] = []
    seen: set[str] = set()
    for run in runs:
        url_path = f"bt_{run['id']}"
        if url_path in seen:
            continue
        seen.add(url_path)
        pages.append(st.Page(
            page_for_run(run["id"]),
            title=run["name"],
            url_path=url_path,
        ))
    return pages
