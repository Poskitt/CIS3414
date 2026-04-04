from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline

from app.config import settings

# Multiclass label -> scalar harm for fusion (0..1).
MULTICLASS_SEVERITY: dict[int, float] = {
    0: 0.0,
    1: 0.42,
    2: 0.52,
    3: 0.74,
    4: 0.88,
}


def _legacy_paths() -> tuple[Path, Path]:
    d = settings.artifacts_dir
    return d / "vectorizer.joblib", d / "model.joblib"


def _calibrated_path() -> Path:
    return settings.artifacts_dir / "calibrated_pipeline.joblib"


def load_classifier() -> Pipeline | CalibratedClassifierCV | None:
    d = settings.artifacts_dir
    d.mkdir(parents=True, exist_ok=True)
    cal_path = _calibrated_path()
    if cal_path.exists():
        return joblib.load(cal_path)
    v_path, m_path = _legacy_paths()
    if v_path.exists() and m_path.exists():
        vectorizer = joblib.load(v_path)
        model = joblib.load(m_path)
        return Pipeline([("tfidf", vectorizer), ("clf", model)])
    return None


def _classes_for_pipe(pipe) -> list:
    if hasattr(pipe, "named_steps"):
        clf = pipe.named_steps["clf"]
        return list(getattr(clf, "classes_", []))
    return list(getattr(pipe, "classes_", []))


def ml_risk_score(pipe, conversation_text: str) -> float:
    if pipe is None or not conversation_text.strip():
        return 0.35
    proba = pipe.predict_proba([conversation_text])[0]
    classes = _classes_for_pipe(pipe)
    if len(proba) != len(classes):
        return float(np.max(proba))

    if len(classes) <= 2:
        try:
            idx = classes.index(1)
        except ValueError:
            idx = int(np.argmax(classes))
        return float(proba[idx])

    expected = 0.0
    for i, c in enumerate(classes):
        try:
            ci = int(c)
        except (TypeError, ValueError):
            continue
        sev = MULTICLASS_SEVERITY.get(ci, 0.55)
        expected += float(proba[i]) * sev
    return float(min(1.0, max(0.0, expected)))
