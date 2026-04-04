"""Train TF-IDF + calibrated logistic regression. Run from project root: python -m training.train_model --help"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.pipeline.conversation_features import augment_text_for_ml
from training.datasets import (
    HARMFUL_CSV,
    ROOT,
    SAFE_CSV,
    SYNTHETIC,
    balance_xy,
    load_labeled_csv,
    log_distribution,
)
from training.pan12_dataset import collect_pan12_xy, resolve_pan12_corpus_dir, resolve_pan12_paths

TRAINING_DIR = Path(__file__).resolve().parent
ART = ROOT / "app" / "ml_artifacts"
ART.mkdir(parents=True, exist_ok=True)


def collect_training_bundle(args: argparse.Namespace) -> tuple[list[str], list[int], list[str]]:
    """Returns texts, labels, source tags (synthetic | pan12 | safe_csv | harmful_csv)."""
    X: list[str] = []
    y: list[int] = []
    sources: list[str] = []

    if args.data in ("synthetic", "both"):
        if not SYNTHETIC.exists():
            raise SystemExit(f"Missing synthetic CSV: {SYNTHETIC}")
        sx, sy = load_labeled_csv(SYNTHETIC)
        X.extend(sx)
        y.extend(sy)
        sources.extend(["synthetic"] * len(sx))

    if args.data in ("pan12", "both"):
        pan12_root = resolve_pan12_corpus_dir(
            args.pan12_dir,
            project_root=ROOT,
            training_dir=TRAINING_DIR,
        )
        xml_path, gt_path = resolve_pan12_paths(pan12_root)
        print(f"PAN12 corpus: {pan12_root}\n  XML: {xml_path.name}")
        max_neg = args.max_negative_samples
        if max_neg is not None and max_neg <= 0:
            max_neg = None
        if args.data == "pan12" and max_neg is None:
            print("Warning: loading all negative PAN12 conversations uses a lot of RAM.")
        px, py = collect_pan12_xy(
            xml_path,
            gt_path,
            max_negative_samples=max_neg,
            random_seed=args.random_seed,
            max_chars=args.max_chars,
            max_messages=args.max_messages,
        )
        X.extend(px)
        y.extend(py)
        sources.extend(["pan12"] * len(px))

    if getattr(args, "extra_csvs", True):
        if SAFE_CSV.exists():
            sx, sy = load_labeled_csv(SAFE_CSV, forced_label=0)
            if sx:
                print(f"Added {len(sx)} rows from {SAFE_CSV.name}")
            X.extend(sx)
            y.extend(sy)
            sources.extend(["safe_csv"] * len(sx))
        elif args.require_extra_csvs:
            raise SystemExit(f"Missing required {SAFE_CSV}")

        if HARMFUL_CSV.exists():
            hx, hy = load_labeled_csv(HARMFUL_CSV)
            if hx:
                print(f"Added {len(hx)} rows from {HARMFUL_CSV.name}")
            X.extend(hx)
            y.extend(hy)
            sources.extend(["harmful_csv"] * len(hx))
        elif args.require_extra_csvs:
            raise SystemExit(f"Missing required {HARMFUL_CSV}")

    if not X:
        raise SystemExit("No training rows. Check --data and file paths.")
    return X, y, sources


def build_base_pipeline(max_features: int, min_df: int) -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=max_features,
                    ngram_range=(1, 2),
                    min_df=min_df,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1200,
                    class_weight="balanced",
                    solver="lbfgs",
                ),
            ),
        ]
    )


def calibration_cv(y: list[int]) -> int:
    least = min(Counter(y).values()) if y else 1
    return int(max(2, min(5, least)))


def train_and_save(X: list[str], y: list[int], args: argparse.Namespace) -> None:
    if len(set(y)) < 2:
        raise SystemExit("Need at least two distinct labels in the training set.")

    log_distribution(y, "Full data (before train/val split)")

    stratify = y if args.stratify else None
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=args.test_size,
            random_state=args.random_seed,
            stratify=stratify,
        )
    except ValueError:
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=args.test_size,
            random_state=args.random_seed,
            stratify=None,
        )

    if args.balance:
        X_train, y_train = balance_xy(X_train, y_train, random_state=args.random_seed)
        log_distribution(y_train, "Train after class balancing (oversampling)")

    X_train_a = [augment_text_for_ml(t) for t in X_train]
    X_test_a = [augment_text_for_ml(t) for t in X_test]

    base = build_base_pipeline(args.max_features, args.min_df)
    cv = calibration_cv(y_train)
    print(f"CalibratedClassifierCV(method=sigmoid, cv={cv})")
    cal = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=cv)
    cal.fit(X_train_a, y_train)

    pred = cal.predict(X_test_a)
    print(classification_report(y_test, pred, digits=3, zero_division=0))

    joblib.dump(cal, ART / "calibrated_pipeline.joblib")
    print(f"Wrote {ART / 'calibrated_pipeline.joblib'}")


def main() -> None:
    p = argparse.ArgumentParser(description="Train conversation risk classifier.")
    p.add_argument(
        "--data",
        choices=("synthetic", "pan12", "both"),
        default="both",
        help="Training data source (default: both PAN12 + synthetic).",
    )
    p.add_argument(
        "--pan12-dir",
        type=Path,
        default=None,
        help=(
            "PAN12 bundle folder (XML + groundtruth-problem1.txt). "
            "If omitted, uses training/pan12-sexual-predator-identification-test-corpus-2012-05-21 "
            "under the project root (works regardless of current working directory)."
        ),
    )
    p.add_argument(
        "--max-negative-samples",
        type=int,
        default=60_000,
        help="Reservoir cap for non-predator PAN12 rows. Use 0 for no cap (loads every negative; very high RAM).",
    )
    p.add_argument("--max-chars", type=int, default=80_000, help="Max chars per PAN12 conversation.")
    p.add_argument("--max-messages", type=int, default=400, help="Max messages per PAN12 conversation.")
    p.add_argument("--random-seed", type=int, default=42)
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--max-features", type=int, default=20_000)
    p.add_argument(
        "--min-df",
        type=int,
        default=1,
        help="TfidfVectorizer min_df; try 2–5 for very large PAN12-only runs to cut noise.",
    )
    p.add_argument(
        "--stratify",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Stratified train/test split when possible.",
    )
    p.add_argument(
        "--balance",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Oversample minority classes on the train split so each class count matches the largest.",
    )
    p.add_argument(
        "--require-extra-csvs",
        action="store_true",
        help=f"Fail if {SAFE_CSV.name} or {HARMFUL_CSV.name} is missing.",
    )
    p.add_argument(
        "--extra-csvs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=f"Merge {SAFE_CSV.name} and {HARMFUL_CSV.name} when present (default: on).",
    )
    args = p.parse_args()

    X, y, _sources = collect_training_bundle(args)
    dist = dict(sorted(Counter(y).items()))
    print(f"Training on {len(X)} conversations; label distribution {dist}")
    print("(Synthetic labels: 0=harmless 1=grooming 2=scam 3=crime 4=extremism; PAN12 uses 0/1 only)")
    train_and_save(X, y, args)


if __name__ == "__main__":
    main()
