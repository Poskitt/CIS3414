from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.analysis import run_pipeline
from app.json_store import AppStore, get_store_dep
from app.schemas import (
    BootstrapOut,
    ConversationOut,
    ConversationSummaryOut,
    CreateConversationIn,
    FlagIn,
    MessageOut,
    RiskOut,
    SendMessageIn,
)

router = APIRouter(prefix="/api", tags=["chat"])


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


def build_summary(store: AppStore, conv) -> ConversationSummaryOut:
    n = store.count_messages(conv.id)
    msgs = store.list_messages(conv.id)
    last = msgs[-1] if msgs else None
    if last is None:
        preview = "(no messages yet)"
    elif len(last.content) > 100:
        preview = last.content[:100] + "..."
    else:
        preview = last.content
    lr = store.latest_risk(conv.id)
    return ConversationSummaryOut(
        id=conv.id,
        public_id=conv.public_id,
        title=conv.title,
        message_count=int(n),
        last_preview=preview,
        latest_tier=lr.tier if lr else None,
    )


def _ensure_demo_conversations(store: AppStore) -> None:
    if store.has_conversation_title("Homework group (safe)"):
        return
    users = store.non_moderator_users()
    if len(users) < 2:
        return
    u_alice, u_bob = users[0], users[1]

    def add_conv(title: str, lines: list[tuple[int, str]]) -> None:
        c = store.add_conversation(title, send_restricted=False)
        store.add_participants(c.id, [u_alice.id, u_bob.id])
        for sender_id, content in lines:
            store.add_message(c.id, sender_id, content)
        if lines:
            run_pipeline(store, c.id)

    add_conv(
        "Homework group (safe)",
        [
            (u_alice.id, "Hey did you finish the math worksheet?"),
            (u_bob.id, "Almost done. Want to compare answers after class?"),
        ],
    )
    add_conv(
        "Soccer club (safe)",
        [
            (u_bob.id, "Practice moved to 4pm Thursday."),
            (u_alice.id, "Thanks, I will tell everyone."),
        ],
    )
    add_conv("Empty thread (completely ok)", [])
    add_conv("Sandbox chat", [])


@router.post("/bootstrap", response_model=BootstrapOut)
def bootstrap(store: AppStore = Depends(get_store_dep)):
    if store.users_empty():
        store.add_users(
            [
                ("alice", "user"),
                ("bob", "user"),
                ("moderator", "moderator"),
            ]
        )

    _ensure_demo_conversations(store)

    users = store.list_users()
    convs = store.list_conversations()
    if not convs:
        raise HTTPException(500, "bootstrap failed: no conversations")
    summaries = [build_summary(store, c) for c in convs]
    return BootstrapOut(
        users=[{"id": u.id, "username": u.username, "role": u.role} for u in users],
        conversations=summaries,
        conversation_id=convs[0].id,
    )


@router.get("/conversations", response_model=list[ConversationSummaryOut])
def list_conversations(store: AppStore = Depends(get_store_dep)):
    convs = store.list_conversations()
    return [build_summary(store, c) for c in convs]


@router.post("/conversations", response_model=ConversationSummaryOut)
def create_conversation(body: CreateConversationIn, store: AppStore = Depends(get_store_dep)):
    users = store.non_moderator_users()
    if len(users) < 2:
        raise HTTPException(400, "need at least two user accounts")
    title = (body.title or "New chat").strip() or "New chat"
    c = store.add_conversation(title, send_restricted=False)
    store.add_participants(c.id, [users[0].id, users[1].id])
    return build_summary(store, c)


@router.post("/send_message")
def send_message(body: SendMessageIn, store: AppStore = Depends(get_store_dep)):
    conv = store.get_conversation(body.conversation_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")
    mod_ids = store.moderator_ids()
    if conv.send_restricted and body.sender_id not in mod_ids:
        raise HTTPException(
            403,
            "Messaging is restricted for this conversation until a moderator reviews it.",
        )
    msg = store.add_message(body.conversation_id, body.sender_id, body.content)
    assessment = run_pipeline(store, body.conversation_id)
    conv = store.get_conversation(body.conversation_id)
    return {
        "message": MessageOut.model_validate(msg),
        "risk": risk_out(assessment),
        "send_restricted": conv.send_restricted if conv else False,
    }


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: int, store: AppStore = Depends(get_store_dep)):
    conv = store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")
    msgs = store.list_messages(conversation_id)
    lr = store.latest_risk(conversation_id)
    return ConversationOut(
        id=conv.id,
        public_id=conv.public_id,
        title=conv.title,
        send_restricted=conv.send_restricted,
        messages=[MessageOut.model_validate(m) for m in msgs],
        latest_risk=risk_out(lr),
    )


@router.post("/conversations/{conversation_id}/analyze")
def analyze_conversation(conversation_id: int, store: AppStore = Depends(get_store_dep)):
    conv = store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")
    assessment = run_pipeline(store, conversation_id)
    return {"assessment": risk_out(assessment)}


@router.post("/conversations/{conversation_id}/flag")
def flag_conversation(conversation_id: int, body: FlagIn, store: AppStore = Depends(get_store_dep)):
    conv = store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(404, "conversation not found")
    store.add_moderation_case(
        conversation_id,
        "open",
        body.source,
        body.reason or "user_report",
        1,
    )
    return {"ok": True}
