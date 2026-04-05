from __future__ import annotations

from types import SimpleNamespace

from app.json_store import AppStore
from app.pipeline.classifier import load_classifier, ml_risk_score
from app.pipeline.conversation_features import augment_text_for_ml
from app.pipeline.fusion import fuse_scores, tier_from_score
from app.pipeline.rules import per_message_line_markers, rule_score_for_text

_pipe = None  # loaded once


def get_pipe():
    global _pipe
    if _pipe is None:
        _pipe = load_classifier()
    return _pipe


def thread_text(store: AppStore, conversation_id: int, last_n: int | None = None) -> tuple[str, int]:
    rows = store.list_messages(conversation_id)
    if last_n is not None and last_n > 0:
        rows = rows[-last_n:]
    lines = [f"user{m.sender_id}: {m.content}" for m in rows]
    return "\n".join(lines), len(rows)


def upsert_moderation_case(
    store: AppStore, conversation_id: int, tier: str, source: str = "system"
) -> None:
    if tier not in ("suspicious", "high_risk"):
        return
    existing = store.find_open_case(conversation_id)
    priority = 2 if tier == "high_risk" else 1
    if existing:
        if priority > existing.priority:
            store.update_moderation_case(existing.id, priority=priority)
        return
    store.add_moderation_case(
        conversation_id, "open", source, f"auto:{tier}", priority
    )


def run_pipeline(
    store: AppStore, conversation_id: int, last_n: int | None = None
) -> SimpleNamespace:
    # rules on raw thread; ML on augmented text; then fuse and persist tier
    text, n = thread_text(store, conversation_id, last_n)
    msg_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    rule_s, hits = rule_score_for_text(text, n, messages=msg_lines)
    hits = dict(hits)
    hits["message_markers"] = per_message_line_markers(msg_lines)
    text_ml = augment_text_for_ml(text)
    ml_s = ml_risk_score(get_pipe(), text_ml)
    age_cluster = bool(hits.get("age_disclosure_cluster"))
    gs = hits.get("grooming_sequence") or {}
    grooming_high = gs.get("label") == "grooming_high_confidence"
    final, fusion_w_ml, fusion_w_rule = fuse_scores(
        ml_s,
        rule_s,
        age_disclosure_cluster=age_cluster,
        grooming_sequence_high=grooming_high,
    )
    tier = tier_from_score(final)
    ra = store.add_risk_assessment(
        conversation_id,
        round(ml_s, 4),
        round(rule_s, 4),
        round(final, 4),
        tier,
        hits,
        fusion_ml_weight=fusion_w_ml,
        fusion_rule_weight=fusion_w_rule,
    )
    conv = store.get_conversation(conversation_id)
    if conv is not None:
        if tier == "high_risk":
            store.update_conversation(conversation_id, send_restricted=True)
        upsert_moderation_case(store, conversation_id, tier, source="system")
    return ra
