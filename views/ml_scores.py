"""ML 打分可视化：依赖独立包 signalml 训练产物，不与核心逻辑耦合。"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

st.header("ML Scores (signalml)")

try:
    import yaml
    from signalml.predict import load_artifact, predict_scores
except ImportError:
    st.warning(
        "未安装可选依赖 **signalml**。在仓库根目录执行：\n\n"
        "`uv sync --extra ml`\n\n"
        "训练示例：`signalml-train train --days 180 --horizon 5 --out ./artifacts/run1`"
    )
    st.stop()

default_dir = os.environ.get("SIGNALML_ARTIFACT_DIR", "").strip()
artifact_dir = st.sidebar.text_input(
    "signalml 产物目录（含 model.joblib）",
    value=default_dir,
    help="训练时 --out 指向的目录；也可设置环境变量 SIGNALML_ARTIFACT_DIR",
)
if not artifact_dir or not Path(artifact_dir).is_dir():
    st.info("请填写有效的产物目录，或先运行 `signalml-train train ... --out <dir>`。")
    st.stop()

model_path = Path(artifact_dir) / "model.joblib"
if not model_path.is_file():
    st.error(f"未找到 {model_path}")
    st.stop()

meta_path = Path(artifact_dir) / "meta.yaml"
meta = {}
if meta_path.is_file():
    meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}

df = st.session_state.df.copy()
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

# 最新一条/按业务展示：取每 symbol 最新信号
if "signal_date" in df.columns:
    df_show = df.loc[df.groupby("symbol")["signal_date"].idxmax()].copy()
else:
    df_show = df.copy()

try:
    scores = predict_scores(df_show, artifact_dir)
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
    c
    for c in [
        "symbol",
        "symbol_name",
        "signal_name",
        "signal_date",
        "exchange",
        "freq",
        "score",
    ]
    if c in out.columns
]
show_cols += [c for c in out.columns if c.startswith("pred_fwd_")]

st.dataframe(out[show_cols], width="stretch", height=480)

if meta:
    with st.expander("模型 meta.yaml"):
        st.code(yaml.safe_dump(meta, allow_unicode=True), language="yaml")
