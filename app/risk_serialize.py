from __future__ import annotations

from app.explain import ml_confidence_band, rule_trigger_summary
from app.schemas import RiskOut


def risk_to_out(r) -> RiskOut | None:
    if r is None:
        return None
    hits = r.rule_hits or {}
    if not isinstance(hits, dict):
        hits = {}
    markers = hits.get("message_markers")
    w_ml = getattr(r, "fusion_ml_weight", None)
    w_rule = getattr(r, "fusion_rule_weight", None)
    return RiskOut(
        ml_score=float(r.ml_score),
        rule_score=float(r.rule_score),
        final_score=float(r.final_score),
        tier=r.tier,
        rule_hits=r.rule_hits,
        fusion_ml_weight=float(w_ml) if w_ml is not None else None,
        fusion_rule_weight=float(w_rule) if w_rule is not None else None,
        ml_confidence_band=ml_confidence_band(float(r.ml_score)),
        rule_trigger_summary=rule_trigger_summary(hits),
        message_markers=markers,
    )
