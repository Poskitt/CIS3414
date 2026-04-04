"""
Train on 80%, hold out 20% validation: multiclass metrics + tier threshold tuning on fused scores.

Writes tuned tier_safe_max / tier_suspicious_max into app/config.py (marked block).
Run from project root: python -m training.evaluate --help
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split

from app.pipeline.classifier import ml_risk_score
from app.pipeline.conversation_features import augment_text_for_ml, count_messages_in_thread
from app.pipeline.fusion import fuse_scores
from app.pipeline.rules import rule_score_for_text
from training.datasets import ROOT, balance_xy, gold_tier, log_distribution
from training.train_model import ART, build_base_pipeline, calibration_cv, collect_training_bundle

CONFIG_PATH = ROOT / "app" / "config.py"


def tier_from_cuts(score: float, safe_max: float, susp_max: float) -> str:
    if score < safe_max:
        return "safe"
    if score < susp_max:
        return "suspicious"
    return "high_risk"


def static_fuse(ml: float, rule: float) -> float:
    return float(max(0.0, min(1.0, 0.6 * ml + 0.4 * rule)))


def fused_val_scores(
    model,
    X_val: list[str],
) -> tuple[list[float], list[float], list[float]]:
    """Returns dynamic fused, static fused, and ML-only scores per row (raw text for rules)."""
    dyn: list[float] = []
    stat: list[float] = []
    ml_only: list[float] = []

    for raw in X_val:
        n = count_messages_in_thread(raw)
        rule_s, hits = rule_score_for_text(raw, n)
        ml_s = ml_risk_score(model, augment_text_for_ml(raw))
        age_cluster = bool(hits.get("age_disclosure_cluster"))
        gs = hits.get("grooming_sequence") or {}
        grooming_high = gs.get("label") == "grooming_high_confidence"
        d = fuse_scores(
            ml_s,
            rule_s,
            age_disclosure_cluster=age_cluster,
            grooming_sequence_high=grooming_high,
        )
        s = static_fuse(ml_s, rule_s)
        dyn.append(d)
        stat.append(s)
        ml_only.append(ml_s)
    return dyn, stat, ml_only


def tune_tier_thresholds(
    val_scores: list[float],
    gold_tiers: list[str],
) -> tuple[float, float, float]:
    """Grid-search (safe_max, suspicious_max) to maximize macro-F1 on 3 tiers."""
    labels = ["safe", "suspicious", "high_risk"]
    best_f1 = -1.0
    best_pair = (0.35, 0.65)
    min_gap = 0.12
    for t1 in np.linspace(0.12, 0.52, 18):
        for t2 in np.linspace(t1 + min_gap, 0.92, 18):
            pred = [tier_from_cuts(s, t1, t2) for s in val_scores]
            f1 = f1_score(gold_tiers, pred, average="macro", labels=labels, zero_division=0)
            if f1 > best_f1:
                best_f1 = f1
                best_pair = (float(t1), float(t2))
    return best_pair[0], best_pair[1], best_f1


def tier_accuracy(gold: list[str], pred: list[str]) -> float:
    return float(accuracy_score(gold, pred))


def patch_config_thresholds(t_safe: float, t_susp: float) -> None:
    text = CONFIG_PATH.read_text(encoding="utf-8")
    block = (
        "    # --- begin auto tier thresholds (training/evaluate.py) ---\n"
        f"    tier_safe_max: float = {t_safe:.4f}\n"
        f"    tier_suspicious_max: float = {t_susp:.4f}\n"
        "    # --- end auto tier thresholds ---\n"
    )
    pattern = (
        r"    # --- begin auto tier thresholds \(training/evaluate\.py\) ---\n"
        r"    tier_safe_max: float = [\d.]+\n"
        r"    tier_suspicious_max: float = [\d.]+\n"
        r"    # --- end auto tier thresholds ---\n"
    )
    if not re.search(pattern, text):
        raise RuntimeError("Could not find tier threshold block in app/config.py")
    text = re.sub(pattern, block, text, count=1)
    CONFIG_PATH.write_text(text, encoding="utf-8")
    print(f"Updated {CONFIG_PATH} with tier_safe_max={t_safe:.4f}, tier_suspicious_max={t_susp:.4f}")


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate + tune tier thresholds on validation fused scores.")
    p.add_argument("--data", choices=("synthetic", "pan12", "both"), default="both")
    p.add_argument("--pan12-dir", type=Path, default=None)
    p.add_argument("--max-negative-samples", type=int, default=60_000)
    p.add_argument("--max-chars", type=int, default=80_000)
    p.add_argument("--max-messages", type=int, default=400)
    p.add_argument("--random-seed", type=int, default=42)
    p.add_argument("--val-size", type=float, default=0.2, help="Held-out validation fraction.")
    p.add_argument("--max-features", type=int, default=20_000)
    p.add_argument("--min-df", type=int, default=1)
    p.add_argument("--balance", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--write-config",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Patch app/config.py tier thresholds with tuned values.",
    )
    p.add_argument("--require-extra-csvs", action="store_true")
    p.add_argument(
        "--extra-csvs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Merge data/safe_conversations.csv and harmful_conversations.csv when present.",
    )
    args = p.parse_args()

    bundle_args = argparse.Namespace(
        data=args.data,
        pan12_dir=args.pan12_dir,
        max_negative_samples=args.max_negative_samples,
        max_chars=args.max_chars,
        max_messages=args.max_messages,
        random_seed=args.random_seed,
        require_extra_csvs=args.require_extra_csvs,
        extra_csvs=args.extra_csvs,
    )
    X, y, sources = collect_training_bundle(bundle_args)
    gold_all = [gold_tier(yi, si) for yi, si in zip(y, sources)]

    log_distribution(y, "Full data")

    X_train, X_val, y_train, y_val, g_train, g_val = train_test_split(
        X,
        y,
        gold_all,
        test_size=args.val_size,
        random_state=args.random_seed,
        stratify=y if len(set(y)) > 1 else None,
    )

    if args.balance:
        X_train, y_train = balance_xy(X_train, y_train, random_state=args.random_seed)
        log_distribution(y_train, "Train after balancing")

    X_train_a = [augment_text_for_ml(t) for t in X_train]
    X_val_a = [augment_text_for_ml(t) for t in X_val]

    base = build_base_pipeline(args.max_features, args.min_df)
    cv = calibration_cv(y_train)
    print(f"Fitting CalibratedClassifierCV(sigmoid, cv={cv}) on train...")
    cal = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=cv)
    cal.fit(X_train_a, y_train)

    pred_val = cal.predict(X_val_a)
    print("\n=== Validation classification (integer labels) ===")
    print(classification_report(y_val, pred_val, digits=3, zero_division=0))
    print("Confusion matrix (rows=true, cols=pred):")
    labels_sorted = sorted(set(y_val) | set(pred_val))
    cm = confusion_matrix(y_val, pred_val, labels=labels_sorted)
    print(f"labels={labels_sorted}")
    print(cm)
    print(f"Accuracy: {accuracy_score(y_val, pred_val):.4f}")

    joblib.dump(cal, ART / "calibrated_pipeline.joblib")
    print(f"\nSaved {ART / 'calibrated_pipeline.joblib'}")

    print("\n=== Fused scores on validation (dynamic fusion + rule leg) ===")
    dyn_scores, stat_scores, ml_scores = fused_val_scores(cal, X_val)

    old_safe, old_susp = 0.35, 0.65
    pred_tier_old = [tier_from_cuts(s, old_safe, old_susp) for s in dyn_scores]
    acc_old = tier_accuracy(g_val, pred_tier_old)
    f1_old = f1_score(
        g_val,
        pred_tier_old,
        average="macro",
        labels=["safe", "suspicious", "high_risk"],
        zero_division=0,
    )

    t_safe, t_susp, best_f1 = tune_tier_thresholds(dyn_scores, g_val)
    pred_tier_new = [tier_from_cuts(s, t_safe, t_susp) for s in dyn_scores]
    acc_new = tier_accuracy(g_val, pred_tier_new)
    f1_new = f1_score(
        g_val,
        pred_tier_new,
        average="macro",
        labels=["safe", "suspicious", "high_risk"],
        zero_division=0,
    )

    print(f"\nTier prediction (gold from labels+source) using OLD cuts ({old_safe}, {old_susp}): acc={acc_old:.4f} macro_f1={f1_old:.4f}")
    print(f"Tier prediction using NEW tuned cuts ({t_safe:.4f}, {t_susp:.4f}): acc={acc_new:.4f} macro_f1={f1_new:.4f}")
    print("\n=== Tier labels: precision / recall / F1 (tuned thresholds) ===")
    print(
        classification_report(
            g_val,
            pred_tier_new,
            labels=["safe", "suspicious", "high_risk"],
            digits=3,
            zero_division=0,
        )
    )

    print("\n=== Dynamic vs static fusion (mean abs delta on validation) ===")
    deltas = [abs(d - s) for d, s in zip(dyn_scores, stat_scores)]
    print(f"mean |dynamic - static|: {float(np.mean(deltas)):.4f}")

    # Highlight examples where dynamic fusion most exceeds static (usually grooming clusters)
    idx_sorted = np.argsort([-abs(d - s) for d, s in zip(dyn_scores, stat_scores)])[:5]
    def _ascii_snippet(s: str, lim: int = 120) -> str:
        chunk = s[:lim].replace("\n", " ")
        return chunk.encode("ascii", "replace").decode("ascii")

    print("\nTop validation rows by |dynamic - static| fused score (snippet):")
    for i in idx_sorted:
        raw = _ascii_snippet(X_val[int(i)])
        print(
            f"  i={int(i)} ml={ml_scores[int(i)]:.3f} dyn={dyn_scores[int(i)]:.3f} "
            f"stat={stat_scores[int(i)]:.3f} gold_tier={g_val[int(i)]} :: {raw!r}..."
        )

    if args.write_config:
        patch_config_thresholds(t_safe, t_susp)

    print("\n=== Summary (for report) ===")
    print(
        "Dynamic fusion up-weights rules when age_disclosure_cluster fires or rule_score>0.8, "
        "ML when ml_score>0.85, and nudges scores down when both ML and rules are low - "
        "improving grooming escalation without a new model architecture."
    )
    print(
        f"Thresholds: old ({old_safe}, {old_susp}) -> tuned ({t_safe:.4f}, {t_susp:.4f}) on validation fused scores; "
        "tier macro-F1 {:.4f} -> {:.4f}.".format(f1_old, f1_new)
    )


if __name__ == "__main__":
    main()
