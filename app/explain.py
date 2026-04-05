# Short labels for hybrid scoring UI (from rule_hits).


def ml_confidence_band(ml_score: float) -> str:
    if ml_score >= 0.75:
        return "high"
    if ml_score >= 0.4:
        return "moderate"
    return "low"


def _cluster_lines(hits: dict, key: str) -> list[str]:
    v = hits.get(key)
    return v if isinstance(v, list) else []


def rule_trigger_summary(hits: dict) -> list[str]:
    if not hits:
        return ["No rule detail stored"]
    out: list[str] = []
    cluster_blob = " ".join(
        str(x).lower()
        for k in ("age_disclosure_cluster", "image_pressure_cluster", "scam_cluster")
        for x in _cluster_lines(hits, k)
    )
    if "secrecy" in cluster_blob:
        out.append("Secrecy / don't-tell-anyone cues")
    if hits.get("age_disclosure_cluster"):
        out.append("Age disclosure cluster")
    if hits.get("scam_cluster"):
        out.append("Scam / financial cluster")
    if hits.get("image_pressure_cluster"):
        out.append("Image request / pressure")
    gs = hits.get("grooming_sequence") or {}
    if gs.get("label") == "grooming_high_confidence":
        out.append("Grooming sequence (high confidence)")
    elif float(gs.get("score") or 0) >= 0.45:
        out.append("Grooming sequence signals")
    th = hits.get("threat") or {}
    if float(th.get("threat_score") or 0) > 0.2:
        out.append("Threat or severe harm wording")
    gp = hits.get("grooming_phrases") or []
    if gp:
        out.append("Grooming phrase matches")
    kw = int(hits.get("keywords") or 0)
    if kw > 0 and not out:
        out.append("Risk keyword matches")
    if not out:
        out.append("Baseline / lexical check")
    return out[:12]
