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
        latest_final_score=float(lr.final_score) if lr else None,
    )


# (title, lines) where each line is ("a" | "b", message) for alice / first user, bob / second.
_DEMO_CONVERSATIONS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Homework group (safe)",
        [
            ("a", "Hey did you finish the math worksheet?"),
            ("b", "Almost done. Want to compare answers after class?"),
        ],
    ),
    (
        "Soccer club (safe)",
        [
            ("b", "Practice moved to 4pm Thursday."),
            ("a", "Thanks, I will tell everyone."),
        ],
    ),
    ("Empty thread (completely ok)", []),
    ("Sandbox chat", []),
    (
        "Movie night Friday (safe)",
        [
            ("a", "Still on for the film at 7?"),
            ("b", "Yep, I will grab snacks."),
        ],
    ),
    (
        "Physics lab partner (safe)",
        [
            ("b", "Can you send the graph from last week?"),
            ("a", "Sure, uploading to the drive now."),
        ],
    ),
    (
        "Chess club ladder (safe)",
        [
            ("a", "Good game yesterday."),
            ("b", "Rematch next Tuesday?"),
        ],
    ),
    (
        "Carpool to airport (safe)",
        [
            ("b", "I can pick you up at 6 if that works."),
            ("a", "Perfect, see you then."),
        ],
    ),
    (
        "Family BBQ Saturday (safe)",
        [
            ("a", "Mom says bring a salad if you can."),
            ("b", "Will do, text me the address again?"),
        ],
    ),
    (
        "Lost phone wrong number (safe)",
        [
            ("b", "Sorry wrong number!"),
            ("a", "No worries, happens all the time."),
        ],
    ),
    (
        "Weather small talk (safe)",
        [
            ("a", "Finally stopped raining."),
            ("b", "About time. Weekend hike?"),
        ],
    ),
    (
        "Compliment from stranger (suspicious)",
        [
            ("b", "hey beautiful you look amazing today"),
            ("a", "Thanks? I think you have the wrong person."),
        ],
    ),
    (
        "Game lobby age ask (borderline)",
        [
            ("b", "nice clutch. how old are you?"),
            ("a", "16, you?"),
            ("b", "22 lol we should duo more"),
        ],
    ),
    (
        "Vague meetup secrecy (suspicious)",
        [
            ("b", "lets meet up tonight dont tell anyone"),
            ("a", "That sounds weird, why secret?"),
        ],
    ),
    (
        "Grooming escalation arc (high risk)",
        [
            ("b", "hey beautiful"),
            ("a", "hello stranger"),
            ("b", "how old are you?"),
            ("a", "i am 13"),
            ("b", "i am 43"),
            ("a", "i dont know if my parents would like this"),
            ("b", "that doesnt matter, we can run away together"),
        ],
    ),
    (
        "Isolation and meet pressure (high risk)",
        [
            ("b", "youre mature for your age"),
            ("a", "i am 14"),
            ("b", "pick you up after school, nobody has to know"),
        ],
    ),
    (
        "Gift card scam (scam)",
        [
            ("b", "IRS owes you a refund, buy gift cards and read codes here"),
            ("a", "This sounds fake."),
        ],
    ),
    (
        "Crypto double money (scam)",
        [
            ("b", "Send bitcoin to this wallet, we double it in 24h guaranteed"),
            ("a", "Yeah right."),
        ],
    ),
    (
        "Fake job fee (scam)",
        [
            ("b", "You got the job! Pay a $50 processing fee via wire to start."),
            ("a", "Real employers do not do that."),
        ],
    ),
    (
        "Hyperbolic vent (mixed)",
        [
            ("a", "I am so mad I could scream at the wall for an hour."),
            ("b", "Want to talk about it?"),
        ],
    ),
    (
        "Study group memes (safe)",
        [
            ("b", "Did you see the profs meme in the slides?"),
            ("a", "Lol yes, accidental comedy gold."),
        ],
    ),
    (
        "Nudes pressure thread (high risk)",
        [
            ("b", "send me a pic, just between us"),
            ("a", "no thats not ok"),
            ("b", "come on dont be shy"),
        ],
    ),
    (
        "Threat style wording (threat)",
        [
            ("b", "I will blow up the whole server if they ban me"),
            ("a", "Please calm down, its just a game."),
        ],
    ),
    (
        "Informed parents hangout (safe)",
        [
            ("b", "lets meet up cuh"),
            ("a", "yeah nws, let me tell my parents"),
            ("b", "ok nws!"),
            ("a", "ok, ive told my parents, they said its fine"),
            ("b", "ok how old are you?"),
        ],
    ),
    (
        "Discord mod help (safe)",
        [
            ("a", "Can you unlock the voice channel for the event?"),
            ("b", "Done. Starts at 8."),
        ],
    ),
]


def _ensure_demo_conversations(store: AppStore) -> None:
    users = store.non_moderator_users()
    if len(users) < 2:
        return
    ua, ub = users[0].id, users[1].id

    def add_conv(title: str, lines: list[tuple[int, str]]) -> None:
        if store.has_conversation_title(title):
            return
        c = store.add_conversation(title, send_restricted=False)
        store.add_participants(c.id, [ua, ub])
        for sender_id, content in lines:
            store.add_message(c.id, sender_id, content)
        run_pipeline(store, c.id)

    for title, pairs in _DEMO_CONVERSATIONS:
        mapped = [(ua if who == "a" else ub, text) for who, text in pairs]
        add_conv(title, mapped)


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
