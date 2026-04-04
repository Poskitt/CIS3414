"""Shared data loading for train_model.py and evaluate.py."""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC = ROOT / "data" / "synthetic_conversations.csv"
SAFE_CSV = ROOT / "data" / "safe_conversations.csv"
HARMFUL_CSV = ROOT / "data" / "harmful_conversations.csv"


def load_labeled_csv(path: Path, forced_label: int | None = None) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    if not path.exists():
        return texts, labels
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("text") or "").strip()
            if not t:
                continue
            if forced_label is not None:
                y = forced_label
            else:
                y = int(row["label"])
            texts.append(t)
            labels.append(y)
    return texts, labels


def gold_tier(label: int, source: str) -> str:
    if source == "pan12":
        return "safe" if label == 0 else "high_risk"
    if source == "safe_csv":
        return "safe"
    if label == 0:
        return "safe"
    if label in (1, 2):
        return "suspicious"
    return "high_risk"


def balance_xy(X: list[str], y: list[int], random_state: int = 42) -> tuple[list[str], list[int]]:
    """Oversample minority integer labels so each class matches the largest class count."""
    rng = np.random.RandomState(random_state)
    by_class: dict[int, list[str]] = {}
    for xi, yi in zip(X, y):
        by_class.setdefault(yi, []).append(xi)

    n_target = max(len(v) for v in by_class.values())
    Xo: list[str] = []
    yo: list[int] = []
    for cls, items in sorted(by_class.items()):
        idx = np.arange(len(items))
        pick = list(items)
        if len(pick) < n_target:
            extra = rng.choice(idx, size=n_target - len(pick), replace=True)
            for i in extra:
                pick.append(items[int(i)])
        rng.shuffle(pick)
        for x in pick:
            Xo.append(x)
            yo.append(cls)

    perm = rng.permutation(len(Xo))
    return [Xo[i] for i in perm], [yo[i] for i in perm]


def log_distribution(y: list[int], title: str) -> None:
    dist = dict(sorted(Counter(y).items()))
    print(f"{title}: n={len(y)} label distribution {dist}")
