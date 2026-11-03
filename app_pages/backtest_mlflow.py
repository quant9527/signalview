"""MLflow 回测：侧边栏每个 run 一页，用案例 K 线网格展示 top/bottom/recent 成交。

跟踪库是现有 PostgreSQL 上的独立库 ``mlflow``，与 quant-lab ``vbt.tracking`` 相同。
成交表在 ``trade_table``，不读本机 artifact 文件。
"""
from __future__ import annotations

import io
import os
from collections.abc import Callable
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
import psycopg
import streamlit as st
from psycopg import sql
from psycopg.rows import dict_row

from app_pages.signal_lab import render_case_gallery

MLFLOW_DATABASE = "mlflow"
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


def replace_database(url: str, database: str) -> str:
    """保留账号和主机，只换库名。"""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path="/" + database))


def tracking_url() -> str | None:
    """与业务库同一个 PostgreSQL，库名是 ``mlflow``。``MLFLOW_TRACKING_URI`` 可覆盖。"""
    explicit = os.environ.get("MLFLOW_TRACKING_URI")
    if explicit:
        return explicit
    try:
        base = st.secrets["connections"]["quantdb"]["url"]
    except (KeyError, FileNotFoundError, Exception):
        base = os.environ.get("DATABASE_URL")
    if not base:
        return None
    return replace_database(base, MLFLOW_DATABASE)


def _connect() -> psycopg.Connection:
    url = tracking_url()
    if not url:
        raise RuntimeError("未配置数据库连接，读不到 MLflow。")
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)


def _labels_for(names: set[str]) -> list[tuple[str, str]]:
    return [(name, label) for name, label in ARTIFACTS if name in names]


@st.cache_data(ttl=60, show_spinner=False)
def list_runs() -> list[dict]:
    """实验 backtest 里、库中有成交表的 run，新的在前。"""
    if tracking_url() is None:
        return []
    with _connect() as con:
        rows = con.execute(
            """
            SELECT r.run_uuid, r.name, r.start_time, t.name AS artifact
            FROM runs r
            JOIN experiments e ON e.experiment_id = r.experiment_id
            JOIN trade_table t ON t.run_uuid = r.run_uuid
            WHERE e.name = %s AND r.status = 'FINISHED'
              AND r.lifecycle_stage = 'active'
            ORDER BY r.start_time DESC
            """,
            (EXPERIMENT,),
        ).fetchall()
    grouped: dict[str, dict] = {}
    for row in rows:
        item = grouped.get(row["run_uuid"])
        if item is None:
            item = {
                "id": row["run_uuid"],
                "name": row["name"] or row["run_uuid"][:8],
                "artifact_names": set(),
            }
            grouped[row["run_uuid"]] = item
        item["artifact_names"].add(row["artifact"])
    out = []
    for item in grouped.values():
        labels = _labels_for(item["artifact_names"])
        if not labels:
            continue
        out.append({
            "id": item["id"],
            "name": item["name"],
            "artifacts": labels,
        })
    return out


def _run_meta(run_id: str) -> tuple[dict[str, str], dict[str, float]]:
    with _connect() as con:
        params = {
            row["key"]: row["value"]
            for row in con.execute(
                "SELECT key, value FROM params WHERE run_uuid = %s", (run_id,)
            ).fetchall()
        }
        metrics = {}
        for row in con.execute(
            "SELECT key, value, is_nan FROM latest_metrics WHERE run_uuid = %s",
            (run_id,),
        ).fetchall():
            if row["is_nan"]:
                continue
            metrics[row["key"]] = float(row["value"])
    return params, metrics


@st.cache_data(ttl=600, show_spinner=False)
def load_trades(run_id: str, filename: str) -> pd.DataFrame:
    with _connect() as con:
        row = con.execute(
            "SELECT body FROM trade_table WHERE run_uuid = %s AND name = %s",
            (run_id, filename),
        ).fetchone()
    if row is None:
        raise FileNotFoundError(filename)
    body = row["body"]
    if not isinstance(body, str):
        import json
        body = json.dumps(body)
    return pd.read_json(io.StringIO(body), orient="split")


def delete_run(run_id: str) -> None:
    """删掉这次回测及其成交表。先删引用 runs 的表，再删 run 本身。"""
    with _connect() as conn:
        refs = conn.execute(
            """
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
              AND ccu.table_name = 'runs'
              AND ccu.column_name = 'run_uuid'
            """
        ).fetchall()
        for ref in refs:
            conn.execute(
                sql.SQL("DELETE FROM {} WHERE {} = %s").format(
                    sql.Identifier(ref["table_name"]),
                    sql.Identifier(ref["column_name"]),
                ),
                (run_id,),
            )
        conn.execute("DELETE FROM trade_table WHERE run_uuid = %s", (run_id,))
        conn.execute("DELETE FROM runs WHERE run_uuid = %s", (run_id,))


def _after_delete(run_id: str) -> None:
    list_runs.clear()
    load_trades.clear()
    nxt = next((page for page in _NAV_PAGES if page.url_path != f"bt_{run_id}"), None)
    if nxt is not None:
        st.switch_page(nxt)
    st.rerun()


@st.dialog("删除回测")
def _confirm_delete(run_id: str, name: str) -> None:
    st.write(f"删除「{name}」后不能恢复。")
    if st.button("确认删除", type="primary", icon=":material/delete:", key=f"bt_del_{run_id}"):
        try:
            delete_run(run_id)
        except psycopg.Error as e:
            st.error(f"删除失败：{e}")
            return
        _after_delete(run_id)


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def _header(run_id: str, name: str, params: dict[str, str], metrics: dict[str, float]) -> None:
    top = st.container(horizontal=True, vertical_alignment="center")
    with top:
        st.markdown(
            f"<div style='font-size:1.4rem;font-weight:700'>{name}</div>",
            unsafe_allow_html=True,
            width="stretch",
        )
        if st.button("删除", icon=":material/delete:", type="tertiary", key=f"bt_del_open_{run_id}"):
            _confirm_delete(run_id, name)
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
    except psycopg.Error as e:
        st.error(f"读取 MLflow 失败：{e}")
        return
    _header(run_id, run["name"], params, metrics)

    labels = [label for _, label in run["artifacts"]]
    choice = st.pills("成交", labels, default=labels[0], key=f"bt_art_{run_id}") or labels[0]
    by_label = {label: name for name, label in run["artifacts"]}
    filename = by_label[choice]
    try:
        frame = load_trades(run["id"], filename)
    except (OSError, ValueError) as e:
        st.error(f"读不到 {filename}：{e}")
        return
    render_case_gallery(
        trades_to_cases(frame),
        key=f"bt_gallery_{run_id}_{filename}",
        cycle="all",
        editable=False,
    )


def page_for_run(run_id: str) -> Callable[[], None]:
    def _page() -> None:
        _render_run(run_id)

    _page.__name__ = f"page_bt_{run_id}"
    return _page


def _source_where() -> str:
    """数据所在的库，不含账号。"""
    url = tracking_url()
    if not url:
        return "未配置。页面使用业务库连接，只把库名换成 mlflow。"
    parts = urlsplit(url)
    host = parts.hostname or "—"
    port = str(parts.port or "—")
    database = (parts.path or "").strip("/") or MLFLOW_DATABASE
    return f"{host}:{port} / {database}"


def page_backtest_empty() -> None:
    st.set_page_config(layout="wide", page_title="回测", page_icon="📈")
    st.error("没有可展示的 MLflow 回测。")
    st.subheader("数据来源")
    st.markdown(
        f"- 数据库：`{_source_where()}`\n"
        f"- 实验：`{EXPERIMENT}`\n"
        "- 写入：quant-lab 每次回测结束时写入这个库"
    )


_NAV_PAGES: list[st.Page] = []


def backtest_pages() -> list[st.Page]:
    """回测分区：每个带成交产物的 run 一个子页。读不到库时只留一个说明页。"""
    try:
        runs = list_runs()
    except Exception as e:
        print(f"[Backtest] MLflow 回测未注册：{e}")
        runs = []
    if not runs:
        pages = [st.Page(page_backtest_empty, title="回测", icon="📈", url_path="backtest")]
        _NAV_PAGES[:] = pages
        return pages
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
    _NAV_PAGES[:] = pages
    return pages
