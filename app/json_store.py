# JSON store for users, chats, messages, risk rows, moderation cases.
# Mutations reload, patch, save under a lock. v1 files are migrated to v2 on read.
from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from app.config import settings


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _default_path() -> Path:
    if settings.data_json_path is not None:
        return Path(settings.data_json_path)
    return _root() / "data" / "app_data.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    s = value.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _empty_canonical() -> dict[str, Any]:
    return {
        "version": 2,
        "counters": {
            "user": 0,
            "conversation": 0,
            "message": 0,
            "risk_assessment": 0,
            "moderation_case": 0,
        },
        "users": [],
        "conversations": [],
        "messages": [],
        "risk_assessments": [],
        "moderation_cases": [],
    }


def _ns_conv(d: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=d["id"],
        public_id=d["public_id"],
        title=d["title"],
        send_restricted=d["send_restricted"],
        created_at=_parse_dt(d["created_at"]) if d.get("created_at") else None,
    )


def _ns_msg(d: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=d["id"],
        conversation_id=d["conversation_id"],
        sender_id=d["sender_id"],
        content=d["content"],
        created_at=_parse_dt(d["created_at"]),
    )


def _ns_risk(d: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=d["id"],
        conversation_id=d["conversation_id"],
        ml_score=d["ml_score"],
        rule_score=d["rule_score"],
        final_score=d["final_score"],
        tier=d["tier"],
        rule_hits=d.get("rule_hits"),
        created_at=_parse_dt(d["created_at"]),
    )


def _ns_case(d: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        id=d["id"],
        conversation_id=d["conversation_id"],
        status=d["status"],
        source=d["source"],
        reason=d.get("reason"),
        moderator_note=d.get("moderator_note"),
        priority=d["priority"],
        created_at=_parse_dt(d["created_at"]),
        updated_at=_parse_dt(d["updated_at"]) if d.get("updated_at") else None,
    )


def _v1_to_canonical(raw: dict[str, Any]) -> dict[str, Any]:
    by_c: dict[int, list[int]] = {}
    for p in raw.get("participants") or []:
        cid = int(p["conversation_id"])
        by_c.setdefault(cid, []).append(int(p["user_id"]))
    out = {
        "version": 2,
        "counters": dict(raw["counters"]),
        "users": [dict(u) for u in raw["users"]],
        "conversations": [],
        "messages": [dict(m) for m in raw.get("messages") or []],
        "risk_assessments": [dict(r) for r in raw.get("risk_assessments") or []],
        "moderation_cases": [dict(c) for c in raw.get("moderation_cases") or []],
    }
    out["counters"].pop("participant", None)
    for c in raw.get("conversations") or []:
        row = dict(c)
        row["member_ids"] = by_c.get(int(c["id"]), [])
        out["conversations"].append(row)
    return out


def _is_compact_v2(raw: dict[str, Any]) -> bool:
    if raw.get("version") != 2:
        return False
    u = raw.get("users")
    if not isinstance(u, list):
        return False
    if len(u) > 0:
        return isinstance(u[0], list)
    msgs = raw.get("messages") or []
    if len(msgs) > 0:
        return isinstance(msgs[0], list)
    convs = raw.get("conversations") or []
    if len(convs) > 0:
        return isinstance(convs[0], list)
    return False


def _expand_compact_v2(raw: dict[str, Any]) -> dict[str, Any]:
    users = [
        {"id": int(t[0]), "username": t[1], "role": t[2]} for t in (raw.get("users") or [])
    ]
    conversations = []
    for t in raw.get("conversations") or []:
        conversations.append(
            {
                "id": int(t[0]),
                "public_id": t[1],
                "title": t[2],
                "send_restricted": bool(t[3]),
                "created_at": t[4],
                "member_ids": list(t[5]) if t[5] is not None else [],
            }
        )
    messages = [
        {
            "id": int(t[0]),
            "conversation_id": int(t[1]),
            "sender_id": int(t[2]),
            "created_at": t[3],
            "content": t[4],
        }
        for t in (raw.get("messages") or [])
    ]
    risks = []
    for t in raw.get("risk_assessments") or []:
        hits = t[7] if len(t) > 7 else None
        risks.append(
            {
                "id": int(t[0]),
                "conversation_id": int(t[1]),
                "ml_score": float(t[2]),
                "rule_score": float(t[3]),
                "final_score": float(t[4]),
                "tier": t[5],
                "created_at": t[6],
                **({"rule_hits": hits} if hits is not None else {}),
            }
        )
    cases = []
    for t in raw.get("moderation_cases") or []:
        cases.append(
            {
                "id": int(t[0]),
                "conversation_id": int(t[1]),
                "status": t[2],
                "source": t[3],
                "reason": t[4],
                "priority": int(t[5]),
                "created_at": t[6],
                "updated_at": t[7],
                "moderator_note": t[8] if len(t) > 8 else None,
            }
        )
    ct = dict(raw["counters"])
    ct.pop("participant", None)
    return {
        "version": 2,
        "counters": ct,
        "users": users,
        "conversations": conversations,
        "messages": messages,
        "risk_assessments": risks,
        "moderation_cases": cases,
    }


def _ensure_member_ids_verbose_v2(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("participants"):
        by_c: dict[int, list[int]] = {}
        for p in raw["participants"]:
            cid = int(p["conversation_id"])
            by_c.setdefault(cid, []).append(int(p["user_id"]))
        for c in raw.get("conversations") or []:
            if "member_ids" not in c:
                c["member_ids"] = by_c.get(int(c["id"]), [])
        raw.pop("participants", None)
    else:
        for c in raw.get("conversations") or []:
            c.setdefault("member_ids", [])
    raw["counters"] = dict(raw["counters"])
    raw["counters"].pop("participant", None)
    return raw


def _normalize_to_canonical(raw: dict[str, Any]) -> dict[str, Any]:
    v = int(raw.get("version", 1))
    if v == 1:
        return _v1_to_canonical(raw)
    if v == 2:
        if _is_compact_v2(raw):
            return _expand_compact_v2(raw)
        return _ensure_member_ids_verbose_v2(raw)
    raise ValueError(f"Unsupported app_data.json version: {v}")


def _canonical_to_compact_disk(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 2,
        "counters": dict(data["counters"]),
        "users": [[u["id"], u["username"], u["role"]] for u in data["users"]],
        "conversations": [
            [
                c["id"],
                c["public_id"],
                c["title"],
                c["send_restricted"],
                c["created_at"],
                c.get("member_ids") or [],
            ]
            for c in data["conversations"]
        ],
        "messages": [
            [
                m["id"],
                m["conversation_id"],
                m["sender_id"],
                m["created_at"],
                m["content"],
            ]
            for m in data["messages"]
        ],
        "risk_assessments": [
            [
                r["id"],
                r["conversation_id"],
                r["ml_score"],
                r["rule_score"],
                r["final_score"],
                r["tier"],
                r["created_at"],
                r.get("rule_hits"),
            ]
            for r in data["risk_assessments"]
        ],
        "moderation_cases": [
            [
                c["id"],
                c["conversation_id"],
                c["status"],
                c["source"],
                c["reason"],
                c["priority"],
                c["created_at"],
                c["updated_at"],
                c.get("moderator_note"),
            ]
            for c in data["moderation_cases"]
        ],
    }


class AppStore:
    def __init__(self, path: Path | None = None):
        self.path = path or _default_path()
        self._lock = threading.Lock()

    def _read(self) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            data = _empty_canonical()
            self._write_unlocked(data)
            return data
        text = self.path.read_text(encoding="utf-8")
        if not text.strip():
            data = _empty_canonical()
            self._write_unlocked(data)
            return data
        raw = json.loads(text)
        return _normalize_to_canonical(raw)

    def _write_unlocked(self, data: dict[str, Any]) -> None:
        disk = _canonical_to_compact_disk(data)
        text = json.dumps(disk, ensure_ascii=False, indent=2, default=str) + "\n"
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self.path)

    def _next_id(self, data: dict[str, Any], key: str) -> int:
        data["counters"][key] = int(data["counters"][key]) + 1
        return data["counters"][key]

    def _mutate(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            data = self._read()
            out = fn(data)
            self._write_unlocked(data)
            return out

    def _view(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            return fn(deepcopy(self._read()))

    # users
    def users_empty(self) -> bool:
        return self._view(lambda d: len(d["users"]) == 0)

    def add_users(self, specs: list[tuple[str, str]]) -> None:
        def op(data: dict[str, Any]) -> None:
            for username, role in specs:
                uid = self._next_id(data, "user")
                data["users"].append(
                    {"id": uid, "username": username, "role": role}
                )

        self._mutate(op)

    def list_users(self) -> list[SimpleNamespace]:
        return self._view(
            lambda d: sorted(
                (SimpleNamespace(**u) for u in d["users"]),
                key=lambda x: x.id,
            )
        )

    def get_user(self, user_id: int) -> SimpleNamespace | None:
        def find(data: dict[str, Any]) -> SimpleNamespace | None:
            for u in data["users"]:
                if u["id"] == user_id:
                    return SimpleNamespace(**u)
            return None

        return self._view(find)

    def moderator_ids(self) -> set[int]:
        return self._view(
            lambda d: {u["id"] for u in d["users"] if u["role"] == "moderator"}
        )

    def non_moderator_users(self) -> list[SimpleNamespace]:
        return self._view(
            lambda d: sorted(
                (SimpleNamespace(**u) for u in d["users"] if u["role"] == "user"),
                key=lambda x: x.id,
            )
        )

    def has_conversation_title(self, title: str) -> bool:
        return self._view(lambda d: any(c["title"] == title for c in d["conversations"]))

    # conversations
    def add_conversation(self, title: str, send_restricted: bool = False) -> SimpleNamespace:
        def op(data: dict[str, Any]) -> SimpleNamespace:
            cid = self._next_id(data, "conversation")
            row = {
                "id": cid,
                "public_id": str(uuid.uuid4()),
                "title": title,
                "send_restricted": send_restricted,
                "created_at": _now_iso(),
                "member_ids": [],
            }
            data["conversations"].append(row)
            return _ns_conv(row)

        return self._mutate(op)

    def add_participants(self, conversation_id: int, user_ids: list[int]) -> None:
        def op(data: dict[str, Any]) -> None:
            for c in data["conversations"]:
                if c["id"] == conversation_id:
                    m = c.setdefault("member_ids", [])
                    for uid in user_ids:
                        if uid not in m:
                            m.append(uid)
                    return
            raise KeyError(conversation_id)

        self._mutate(op)

    def get_conversation(self, conversation_id: int) -> SimpleNamespace | None:
        return self._view(
            lambda d: next(
                (_ns_conv(c) for c in d["conversations"] if c["id"] == conversation_id),
                None,
            )
        )

    def list_conversations(self) -> list[SimpleNamespace]:
        return self._view(
            lambda d: sorted((_ns_conv(c) for c in d["conversations"]), key=lambda x: x.id)
        )

    def update_conversation(self, conversation_id: int, **fields: Any) -> None:
        def op(data: dict[str, Any]) -> None:
            for c in data["conversations"]:
                if c["id"] == conversation_id:
                    for k, v in fields.items():
                        if k != "member_ids":
                            c[k] = v
                    return
            raise KeyError(conversation_id)

        self._mutate(op)

    # messages
    def add_message(self, conversation_id: int, sender_id: int, content: str) -> SimpleNamespace:
        def op(data: dict[str, Any]) -> SimpleNamespace:
            mid = self._next_id(data, "message")
            row = {
                "id": mid,
                "conversation_id": conversation_id,
                "sender_id": sender_id,
                "content": content,
                "created_at": _now_iso(),
            }
            data["messages"].append(row)
            return _ns_msg(row)

        return self._mutate(op)

    def list_messages(self, conversation_id: int) -> list[SimpleNamespace]:
        return self._view(
            lambda d: sorted(
                (_ns_msg(m) for m in d["messages"] if m["conversation_id"] == conversation_id),
                key=lambda m: m.created_at,
            )
        )

    def count_messages(self, conversation_id: int) -> int:
        return self._view(
            lambda d: sum(1 for m in d["messages"] if m["conversation_id"] == conversation_id)
        )

    # risk
    def add_risk_assessment(
        self,
        conversation_id: int,
        ml_score: float,
        rule_score: float,
        final_score: float,
        tier: str,
        rule_hits: dict[str, Any] | None,
    ) -> SimpleNamespace:
        def op(data: dict[str, Any]) -> SimpleNamespace:
            rid = self._next_id(data, "risk_assessment")
            row: dict[str, Any] = {
                "id": rid,
                "conversation_id": conversation_id,
                "ml_score": ml_score,
                "rule_score": rule_score,
                "final_score": final_score,
                "tier": tier,
                "created_at": _now_iso(),
            }
            if rule_hits is not None:
                row["rule_hits"] = rule_hits
            data["risk_assessments"].append(row)
            return _ns_risk(row)

        return self._mutate(op)

    def latest_risk(self, conversation_id: int) -> SimpleNamespace | None:
        def pick(data: dict[str, Any]) -> SimpleNamespace | None:
            rows = [r for r in data["risk_assessments"] if r["conversation_id"] == conversation_id]
            if not rows:
                return None
            rows.sort(key=lambda r: r["created_at"], reverse=True)
            return _ns_risk(rows[0])

        return self._view(pick)

    # moderation
    def add_moderation_case(
        self,
        conversation_id: int,
        status: str,
        source: str,
        reason: str | None,
        priority: int,
    ) -> None:
        def op(data: dict[str, Any]) -> None:
            cid = self._next_id(data, "moderation_case")
            now = _now_iso()
            data["moderation_cases"].append(
                {
                    "id": cid,
                    "conversation_id": conversation_id,
                    "status": status,
                    "source": source,
                    "reason": reason,
                    "moderator_note": None,
                    "priority": priority,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        self._mutate(op)

    def find_open_case(self, conversation_id: int) -> SimpleNamespace | None:
        return self._view(
            lambda d: next(
                (
                    _ns_case(c)
                    for c in d["moderation_cases"]
                    if c["conversation_id"] == conversation_id and c["status"] == "open"
                ),
                None,
            )
        )

    def list_open_cases(self) -> list[SimpleNamespace]:
        return self._view(
            lambda d: sorted(
                (_ns_case(c) for c in d["moderation_cases"] if c["status"] == "open"),
                key=lambda c: (-c.priority, c.created_at.isoformat()),
            )
        )

    def get_moderation_case(self, case_id: int) -> SimpleNamespace | None:
        return self._view(
            lambda d: next(
                (_ns_case(c) for c in d["moderation_cases"] if c["id"] == case_id),
                None,
            )
        )

    def update_moderation_case(self, case_id: int, **fields: Any) -> None:
        def op(data: dict[str, Any]) -> None:
            for c in data["moderation_cases"]:
                if c["id"] == case_id:
                    for k, v in fields.items():
                        c[k] = v
                    c["updated_at"] = _now_iso()
                    return
            raise KeyError(case_id)

        self._mutate(op)


_store_singleton: AppStore | None = None


def get_store() -> AppStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = AppStore()
    return _store_singleton


def init_store() -> None:
    get_store()._read()  # noqa: SLF001


def get_store_dep():
    yield get_store()
