"""CLI: train model."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from signalml.db import get_db_url, load_signals
from signalml.train import save_artifact, train_pipeline


def _extract_env_file_from_argv(argv: list[str]) -> str | None:
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--env-file" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--env-file="):
            return a.partition("=")[2]
        i += 1
    return None


def _load_dotenv_early(cli_env_file: str | None) -> None:
    try:
        from dotenv import load_dotenv
        from dotenv.main import find_dotenv
    except ImportError:
        return
    if cli_env_file:
        load_dotenv(cli_env_file, override=False)
        return
    custom = (os.environ.get("SIGNALML_ENV_FILE") or "").strip()
    if custom:
        load_dotenv(custom, override=False)
        return
    found = find_dotenv(usecwd=True)
    if found:
        load_dotenv(found, override=False)


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return int(str(raw).strip())


def _env_float(key: str, default: float) -> float:
    raw = os.environ.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return float(str(raw).strip())


def _env_str(key: str, default: str | None = None) -> str | None:
    raw = os.environ.get(key)
    if raw is None:
        return default
    s = str(raw).strip()
    return s if s else default


def _env_truthy(key: str) -> bool:
    return os.environ.get(key, "").strip().lower() in ("1", "true", "yes", "on")


def main() -> None:
    argv = sys.argv[1:]
    _load_dotenv_early(_extract_env_file_from_argv(argv))

    p = argparse.ArgumentParser(prog="signalml")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("train", help="Train model and save to --out")
    t.add_argument(
        "--env-file",
        default=None,
        metavar="PATH",
        help="启动时加载的 dotenv 文件（亦可用环境变量 SIGNALML_ENV_FILE；否则从当前目录向上查找 .env）",
    )
    t.add_argument(
        "--db-url",
        default=_env_str("DATABASE_URL"),
        help="Postgres URL；默认读环境变量 DATABASE_URL（可在 .env 中设置）",
    )
    t.add_argument(
        "--secrets",
        default=_env_str("SIGNALML_SECRETS"),
        metavar="PATH",
        help="Explicit path to Streamlit secrets.toml (default: search cwd/parents for .streamlit/secrets.toml)",
    )
    t.add_argument(
        "--days",
        type=int,
        default=_env_int("SIGNALML_DAYS", 180),
        help="Rolling window days for signals（.env: SIGNALML_DAYS）",
    )
    t.add_argument(
        "--horizon",
        type=int,
        default=_env_int("SIGNALML_HORIZON", 5),
        help="Forward return horizon (trading days)（.env: SIGNALML_HORIZON）",
    )
    t.add_argument(
        "--out",
        type=str,
        default=_env_str("SIGNALML_OUT"),
        help="Output directory（.env: SIGNALML_OUT）；与命令行均未设置时会报错",
    )
    t.add_argument(
        "--cache",
        type=str,
        default=_env_str("SIGNALML_CACHE", ".cache/signalml") or ".cache/signalml",
        help="Parquet cache（.env: SIGNALML_CACHE）",
    )
    t.add_argument(
        "--exchange",
        type=str,
        default=_env_str("SIGNALML_EXCHANGE", "as") or "as",
        help="Filter signal.exchange；空字符串表示不过滤（.env: SIGNALML_EXCHANGE）",
    )
    t.add_argument(
        "--test-ratio",
        type=float,
        default=_env_float("SIGNALML_TEST_RATIO", 0.2),
    )
    t.add_argument(
        "--resonance-days",
        type=int,
        default=_env_int("SIGNALML_RESONANCE_DAYS", 5),
        help="共振回看窗口（日历天）：同 symbol 多信号 + 多 freq + 关联 THS 板块信号，均要求 signal_date 落在 [t-L,t]",
    )
    t.add_argument(
        "--no-kline-market",
        action="store_true",
        help="关闭相对沪深300日涨跌与 K 线 ma5ma10_sc/jc 等截面特征",
    )
    t.add_argument("--no-resonance", action="store_true", help="关闭共振特征")
    t.add_argument("--no-ths-resonance", action="store_true", help="仅关 THS 板块共振（仍保留同标的/多周期）")
    t.add_argument(
        "--ths-signal-filter",
        type=str,
        default=_env_str("SIGNALML_THS_SIGNAL_FILTER"),
        help="额外：仅统计 signal_name 包含该子串的 THS 信号（不区分大小写）；默认不过滤（.env: SIGNALML_THS_SIGNAL_FILTER）",
    )
    t.add_argument(
        "--ths-position",
        type=str,
        default=_env_str("SIGNALML_THS_POSITION"),
        metavar="long|short",
        help="THS 共振时仅统计 signal.side 等于该值（与库中存储比大小写不敏感，如 long / short）；默认不过滤（.env: SIGNALML_THS_POSITION）",
    )

    args = p.parse_args()
    if args.cmd == "train":
        if not args.out or not str(args.out).strip():
            raise SystemExit(
                "请指定输出目录：命令行 `--out` 或在 .env 中设置 SIGNALML_OUT（见 signalml README）"
            )
        args.no_resonance = bool(args.no_resonance) or _env_truthy("SIGNALML_NO_RESONANCE")
        args.no_ths_resonance = bool(args.no_ths_resonance) or _env_truthy("SIGNALML_NO_THS_RESONANCE")
        args.no_kline_market = bool(args.no_kline_market) or _env_truthy("SIGNALML_NO_KLINE_MARKET")
        url = get_db_url(args.db_url, secrets_path=args.secrets)
        if not url:
            raise SystemExit(
                "无法解析数据库连接串。任选其一：\n"
                "  1) 在 `.env` 或环境中设置 DATABASE_URL=postgresql://...\n"
                "  2) 在仓库根目录放置 `.streamlit/secrets.toml`（`[connections.quantdb] url = \"...\"`）\n"
                "  3) `signalml-train train --db-url postgresql://...`\n"
                "  4) `signalml-train train --secrets /path/to/secrets.toml`"
            )
        ex = args.exchange.strip() if args.exchange else None
        df = load_signals(url, time_window_days=args.days)
        cache_dir = Path(args.cache)
        ths_sub = (args.ths_signal_filter or "").strip() or None
        ths_pos = (args.ths_position or "").strip().lower() or None
        bundle = train_pipeline(
            df,
            horizon_days=args.horizon,
            cache_dir=cache_dir,
            test_ratio=args.test_ratio,
            exchange_filter=ex,
            conn_url=url,
            use_resonance=not args.no_resonance,
            resonance_lookback_days=max(1, int(args.resonance_days)),
            use_ths_resonance=not args.no_ths_resonance,
            ths_signal_name_substr=ths_sub,
            ths_position_filter=ths_pos,
            use_kline_market=not args.no_kline_market,
        )
        out = save_artifact(bundle, args.out)
        print("Saved:", out / "model.joblib")
        print("Metrics:", bundle["metrics"])
