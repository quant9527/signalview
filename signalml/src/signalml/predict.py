"""Load artifact and score a signal DataFrame."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from signalml.features import FeaturePipeline


def load_artifact(artifact_dir: str | Path) -> dict[str, Any]:
    artifact_dir = Path(artifact_dir)
    bundle = joblib.load(artifact_dir / "model.joblib")
    return bundle


def predict_scores(df: pd.DataFrame, artifact_dir: str | Path) -> pd.Series:
    bundle = load_artifact(artifact_dir)
    pipe: FeaturePipeline = bundle["feature_pipeline"]
    model = bundle["model"]
    X = pipe.transform(df)
    pred = model.predict(X)
    return pd.Series(pred, index=df.index, name="pred_fwd_ret")
