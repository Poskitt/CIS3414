from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.json_store import AppStore, get_store_dep
from app.schemas import ModeratorActionIn, ModeratorCaseOut, RiskOut

router = APIRouter(prefix="/api/moderator", tags=["moderator"])


def risk_out(r) -> RiskOut | None:
    if r is None:
        return None
    return RiskOut(
        ml_score=r.ml_score,
        rule_score=r.rule_score,
        final_score=r.final_score,
        tier=r.tier,
        rule_hits=r.rule_hits,
    )


def preview_text(store: AppStore, conversation_id: int, limit: int = 240) -> str:
    msgs = store.list_messages(conversation_id)
    tail = msgs[-5:] if len(msgs) > 5 else msgs
    parts = [m.content for m in tail]
    blob = " | ".join(parts)
    return blob if len(blob) <= limit else blob[: limit - 3] + "..."


@router.get("/conversations", response_model=list[ModeratorCaseOut])
def moderator_conversations(store: AppStore = Depends(get_store_dep)):
    cases = store.list_open_cases()
    out: list[ModeratorCaseOut] = []
    for c in cases:
        lr = store.latest_risk(c.conversation_id)
        conv = store.get_conversation(c.conversation_id)
        out.append(
            ModeratorCaseOut(
                id=c.id,
                conversation_id=c.conversation_id,
                conversation_public_id=conv.public_id if conv else None,
                conversation_title=conv.title if conv else None,
                status=c.status,
                source=c.source,
                reason=c.reason,
                moderator_note=c.moderator_note,
                priority=c.priority,
                created_at=c.created_at,
                preview=preview_text(store, c.conversation_id),
                latest_risk=risk_out(lr),
            )
        )
    return out


@router.post("/cases/{case_id}/dismiss")
def dismiss_case(case_id: int, body: ModeratorActionIn, store: AppStore = Depends(get_store_dep)):
    case = store.get_moderation_case(case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    store.update_moderation_case(case_id, status="dismissed", moderator_note=body.note)
    conv = store.get_conversation(case.conversation_id)
    if conv is not None:
        store.update_conversation(case.conversation_id, send_restricted=False)
    return {"ok": True}


@router.post("/cases/{case_id}/confirm")
def confirm_case(case_id: int, body: ModeratorActionIn, store: AppStore = Depends(get_store_dep)):
    case = store.get_moderation_case(case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    store.update_moderation_case(case_id, status="confirmed", moderator_note=body.note)
    conv = store.get_conversation(case.conversation_id)
    if conv is not None:
        store.update_conversation(case.conversation_id, send_restricted=True)
    return {"ok": True}
