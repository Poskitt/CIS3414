from __future__ import annotations

from app.config import settings


def fuse_scores(
    ml_score: float,
    rule_score: float,
    *,
    age_disclosure_cluster: bool = False,
    grooming_sequence_high: bool = False,
) -> float:
    ml_score = max(0.0, min(1.0, float(ml_score)))
    rule_score = max(0.0, min(1.0, float(rule_score)))

    if grooming_sequence_high:
        w_m, w_r = 0.2, 0.8
    elif age_disclosure_cluster or rule_score > 0.8:
        w_m, w_r = 0.3, 0.7
    elif ml_score > 0.85:
        w_m, w_r = 0.75, 0.25
    else:
        w_m = float(settings.ml_weight)
        w_r = float(settings.rule_weight)

    total = w_m + w_r
    fused = (w_m * ml_score + w_r * rule_score) / total

    if rule_score < 0.1 and ml_score < 0.4:
        fused *= 0.92

    return float(max(0.0, min(1.0, fused)))


def tier_from_score(score: float) -> str:
    if score < settings.tier_safe_max:
        return "safe"
    if score < settings.tier_suspicious_max:
        return "suspicious"
    return "high_risk"
