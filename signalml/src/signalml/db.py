"""Load signals from PostgreSQL (standalone)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
import pandas as pd
import psycopg

from signalml.dates import normalize_signal_date_field


def _url_from_secrets_toml(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except Exception:
        return None
    conn = data.get("connections") or {}
    q = conn.get("quantdb") or {}
    url = q.get("url")
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    # 与 secrets.toml.example 完全一致的占位串则忽略，避免误连
    if "user:password@host:5432/dbname" in url.replace(" ", ""):
        return None
    return url


def discover_streamlit_secrets_path(start: Path | None = None) -> Path | None:
    """Find `.streamlit/secrets.toml` from cwd or parents (same layout as Streamlit app)."""
    cwd = (start or Path.cwd()).resolve()
    for base in [cwd, *cwd.parents]:
        p = base / ".streamlit" / "secrets.toml"
        if p.is_file():
            return p
        if base.parent == base:
            break
    return None


def get_db_url(
    explicit: str | None = None,
    *,
    secrets_path: str | Path | None = None,
) -> str | None:
    """Resolve DB URL: explicit arg > env > optional Streamlit secrets.toml."""
    if explicit:
        return explicit
    url = os.environ.get("POSTGRESQL_URL") or os.environ.get("DATABASE_URL")
    if url:
        return url
    if secrets_path:
        u = _url_from_secrets_toml(Path(secrets_path))
        if u:
            return u
    sp = discover_streamlit_secrets_path()
    if sp:
        return _url_from_secrets_toml(sp)
    return None


def load_signals(
    conn_url: str,
    time_window_days: int = 90,
    start_date: str | None = None,
    end_date: str | None = None,
    signal_name_prefix: str | None = None,
) -> pd.DataFrame:
    columns = (
        "id, pick_id, pick_dt, symbol_id, exchange, symbol, freq, symbol_name, "
        "signal_date, signal_name, signal, reason, price, score, shares, version, "
        "created_at, updated_at, reverse"
    )
    signal_filter = " AND signal_name LIKE %s" if signal_name_prefix else ""
    params: list = []
    with psycopg.connect(conn_url, connect_timeout=120) as conn:
        with conn.cursor() as cur:
            if start_date and end_date:
                query = f"""
                    SELECT {columns}
                    FROM signal
                    WHERE signal_date >= %s
                      AND signal_date < (%s::date + interval '1 day'){signal_filter}
                    ORDER BY signal_date DESC
                """
                params = [start_date, end_date]
                if signal_name_prefix:
                    params.append(signal_name_prefix + "%")
                cur.execute(query, params)
            else:
                ndays = int(time_window_days)
                if signal_name_prefix:
                    query = f"""
                        SELECT {columns}
                        FROM signal
                        WHERE signal_date >= now() - interval '{ndays} days'
                          AND signal_name LIKE %s
                        ORDER BY signal_date DESC
                    """
                    cur.execute(query, (signal_name_prefix + "%",))
                else:
                    query = f"""
                        SELECT {columns}
                        FROM signal
                        WHERE signal_date >= now() - interval '{ndays} days'
                        ORDER BY signal_date DESC
                    """
                    cur.execute(query)
            rows = cur.fetchall()
            colnames = [d[0] for d in cur.description]
    df = pd.DataFrame(rows, columns=colnames)
    if df.empty:
        return df
    df = normalize_signal_date_field(df, "signal_date", "Asia/Shanghai")
    df["display_symbol"] = df.apply(
        lambda r: f"{r['symbol']}:reverse" if r.get("reverse") else r["symbol"],
        axis=1,
    )
    return df
