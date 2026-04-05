from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.json_store import AppStore, get_store_dep
from app.risk_serialize import risk_to_out
from app.schemas import ModeratorActionIn, ModeratorCaseOut

router = APIRouter(prefix="/api/moderator", tags=["moderator"])


def moderator_workflow_display(case) -> str:
    if case.status == "dismissed":
        return "Resolved (dismissed)"
    if case.status == "confirmed":
        return "Resolved (confirmed)"
    if getattr(case, "review_stage", None) == "in_review":
        return "Under review"
    return "Pending"


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
        rs = getattr(c, "review_stage", None)
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
                review_stage=rs,
                workflow_display=moderator_workflow_display(c),
                created_at=c.created_at,
                preview=preview_text(store, c.conversation_id),
                latest_risk=risk_to_out(lr),
            )
        )
    return out


@router.post("/cases/{case_id}/start-review")
def start_review(case_id: int, store: AppStore = Depends(get_store_dep)):
    case = store.get_moderation_case(case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    if case.status != "open":
        raise HTTPException(400, "case is not open")
    store.update_moderation_case(case_id, review_stage="in_review")
    return {"ok": True}


@router.post("/cases/{case_id}/dismiss")
def dismiss_case(case_id: int, body: ModeratorActionIn, store: AppStore = Depends(get_store_dep)):
    case = store.get_moderation_case(case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    store.update_moderation_case(
        case_id, status="dismissed", moderator_note=body.note, review_stage=None
    )
    conv = store.get_conversation(case.conversation_id)
    if conv is not None:
        store.update_conversation(case.conversation_id, send_restricted=False)
    return {"ok": True}


@router.post("/cases/{case_id}/confirm")
def confirm_case(case_id: int, body: ModeratorActionIn, store: AppStore = Depends(get_store_dep)):
    case = store.get_moderation_case(case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    store.update_moderation_case(
        case_id, status="confirmed", moderator_note=body.note, review_stage=None
    )
    conv = store.get_conversation(case.conversation_id)
    if conv is not None:
        store.update_conversation(case.conversation_id, send_restricted=True)
    return {"ok": True}
