from __future__ import annotations

from app.config import settings


def fuse_scores(
    ml_score: float,
    rule_score: float,
    *,
    age_disclosure_cluster: bool = False,
    grooming_sequence_high: bool = False,
) -> tuple[float, float, float]:
    # Keep both input scores in a safe 0..1 range.
    ml_score = max(0.0, min(1.0, float(ml_score)))
    rule_score = max(0.0, min(1.0, float(rule_score)))

    # Pick dynamic weights based on strong risk signals.
    # High-confidence grooming should trust rules the most.
    if grooming_sequence_high:
        w_m, w_r = 0.2, 0.8
    # Age-disclosure patterns or very high rule score still favor rules.
    elif age_disclosure_cluster or rule_score > 0.8:
        w_m, w_r = 0.3, 0.7
    # Very confident ML signal can lead the blend.
    elif ml_score > 0.85:
        w_m, w_r = 0.75, 0.25
    # Otherwise use default config weights.
    else:
        w_m = float(settings.ml_weight)
        w_r = float(settings.rule_weight)

    # Weighted blend of ML and rule scores.
    total = w_m + w_r
    fused = (w_m * ml_score + w_r * rule_score) / total

    # Small dampener when both systems are low-risk.
    if rule_score < 0.1 and ml_score < 0.4:
        fused *= 0.92

    # Return final fused score plus the actual weights used.
    return float(max(0.0, min(1.0, fused))), w_m, w_r


def tier_from_score(score: float) -> str:
    # Convert numeric score into the UI/API risk tier.
    if score < settings.tier_safe_max:
        return "safe"
    if score < settings.tier_suspicious_max:
        return "suspicious"
    return "high_risk"
