"""CLI: train model."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from signalml.db import get_db_url, load_signals
from signalml.train import save_artifact, train_pipeline


def main() -> None:
    p = argparse.ArgumentParser(prog="signalml")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("train", help="Train model and save to --out")
    t.add_argument("--db-url", default=None, help="Postgres URL (else env or .streamlit/secrets.toml)")
    t.add_argument(
        "--secrets",
        default=None,
        metavar="PATH",
        help="Explicit path to Streamlit secrets.toml (default: search cwd/parents for .streamlit/secrets.toml)",
    )
    t.add_argument("--days", type=int, default=180, help="Rolling window days for signals")
    t.add_argument("--horizon", type=int, default=5, help="Forward return horizon (trading days)")
    t.add_argument("--out", type=str, required=True, help="Output directory for model.joblib + meta.yaml")
    t.add_argument("--cache", type=str, default=".cache/signalml", help="Parquet cache for daily bars")
    t.add_argument("--exchange", type=str, default="as", help="Filter signal.exchange (default as); empty = no filter")
    t.add_argument("--test-ratio", type=float, default=0.2)

    args = p.parse_args()
    if args.cmd == "train":
        url = get_db_url(args.db_url, secrets_path=args.secrets)
        if not url:
            raise SystemExit(
                "无法解析数据库连接串。任选其一：\n"
                "  1) 设置环境变量 POSTGRESQL_URL 或 DATABASE_URL\n"
                "  2) 在仓库根目录放置 `.streamlit/secrets.toml`（与 Streamlit 相同，`[connections.quantdb] url = \"...\"`）\n"
                "  3) `signalml-train train --db-url postgresql://...`\n"
                "  4) `signalml-train train --secrets /path/to/secrets.toml`"
            )
        ex = args.exchange.strip() if args.exchange else None
        df = load_signals(url, time_window_days=args.days)
        cache_dir = Path(args.cache)
        bundle = train_pipeline(
            df,
            horizon_days=args.horizon,
            cache_dir=cache_dir,
            test_ratio=args.test_ratio,
            exchange_filter=ex,
        )
        out = save_artifact(bundle, args.out)
        print("Saved:", out / "model.joblib")
        print("Metrics:", bundle["metrics"])
