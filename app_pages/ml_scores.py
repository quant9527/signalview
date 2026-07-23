"""ML scores page (url_path=ml_scores)."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from utils import get_cached_data

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ARTIFACT_DIR = _REPO_ROOT / "artifacts" / "run1"


def _default_artifact_dir_str() -> str:
    env = os.environ.get("SIGNALML_ARTIFACT_DIR", "").strip()
    if env:
        return env
    return str(_DEFAULT_ARTIFACT_DIR)


def page_ml_scores() -> None:
    """ML scores (url_path=ml_scores)."""
    st.set_page_config(layout="wide", page_title="ML Scores")
    st.header("ML Scores (signalml)")

    # signalml is an optional dependency ([project.optional-dependencies] ml).
    # yaml comes as a transitive of signalml, so we check for signalml and
    # guide the user with the same message in either missing case.
    try:
        import yaml as _yaml_mod  # noqa: F401
        from signalml.predict import predict_scores
    except ImportError:
        st.warning(
            "未安装可选依赖 **signalml**。在仓库根目录执行：\n\n"
            "`uv sync --extra ml`\n\n"
            "训练示例：`signalml-train train --days 180 --horizon 5 --out ./artifacts/run1`"
        )
        st.stop()

    artifact_dir = st.sidebar.text_input(
        "signalml 产物目录（含 model.joblib）",
        value=_default_artifact_dir_str(),
        help=(
            "默认：仓库内 artifacts/run1（未设置 SIGNALML_ARTIFACT_DIR 时）。"
            "训练示例：signalml-train train ... --out ./artifacts/run1"
        ),
    )
    if not artifact_dir or not Path(artifact_dir).is_dir():
        st.info("请填写有效的产物目录，或先运行 `signalml-train train ... --out <dir>`。")
        st.stop()

    model_path = Path(artifact_dir) / "model.joblib"
    if not model_path.is_file():
        st.error(f"未找到 {model_path}")
        st.stop()

    meta_path = Path(artifact_dir) / "meta.yaml"
    meta: dict = {}
    if meta_path.is_file():
        # yaml import is paired with predict_scores at the top of this function
        # so once we reach this line yaml has been imported successfully.
        meta = _yaml_mod.safe_load(meta_path.read_text(encoding="utf-8")) or {}

    df = get_cached_data(45)
    ex_f = meta.get("exchange_filter")
    if ex_f and "exchange" in df.columns:
        df = df[df["exchange"].astype(str) == str(ex_f)].copy()
        st.caption(f"已按模型训练时的 exchange=`{ex_f}` 筛选。")

    selected = st.session_state.get("selected_signals") or []
    if selected and "signal_name" in df.columns:
        df = df[df["signal_name"].isin(selected)].copy()

    if df.empty:
        st.warning("当前筛选下无数据。")
        st.stop()

    if "signal_date" in df.columns:
        df_show = df.loc[df.groupby("symbol")["signal_date"].idxmax()].copy()
    else:
        df_show = df.copy()

    try:
        scores = predict_scores(df_show, artifact_dir, context_df=df)
    except Exception as e:
        st.error(f"预测失败: {e}")
        st.stop()

    out = df_show.reset_index(drop=True)
    out["pred_fwd_ret"] = scores.values

    if meta.get("horizon_days") is not None:
        out = out.rename(
            columns={"pred_fwd_ret": f"pred_fwd_ret_{meta['horizon_days']}d_model"}
        )

    sort_col = [c for c in out.columns if c.startswith("pred_fwd_")]
    if sort_col:
        out = out.sort_values(sort_col[0], ascending=False)

    show_cols = [
        c for c in [
            "symbol", "symbol_name", "signal_name", "signal_date",
            "exchange", "freq", "score",
        ] if c in out.columns
    ]
    show_cols += [c for c in out.columns if c.startswith("pred_fwd_")]

    st.dataframe(out[show_cols], width="stretch", height=480)

    if meta:
        with st.expander("模型 meta.yaml"):
            st.code(_yaml_mod.safe_dump(meta, allow_unicode=True), language="yaml")