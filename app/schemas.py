from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int
    sender_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageIn(BaseModel):
    conversation_id: int
    sender_id: int
    content: str = Field(min_length=1, max_length=8000)


class RiskOut(BaseModel):
    ml_score: float
    rule_score: float
    final_score: float
    tier: str
    rule_hits: dict[str, Any] | None = None


class ConversationSummaryOut(BaseModel):
    id: int
    public_id: str
    title: str
    message_count: int
    last_preview: str
    latest_tier: str | None = None
    latest_final_score: float | None = None


class ConversationOut(BaseModel):
    id: int
    public_id: str
    title: str
    send_restricted: bool
    messages: list[MessageOut]
    latest_risk: RiskOut | None = None


class AnalyzeOut(BaseModel):
    assessment: RiskOut


class FlagIn(BaseModel):
    source: str = "user"
    reason: str | None = None


class ModeratorCaseOut(BaseModel):
    id: int
    conversation_id: int
    conversation_public_id: str | None = None
    conversation_title: str | None = None
    status: str
    source: str
    reason: str | None
    moderator_note: str | None
    priority: int
    created_at: datetime
    preview: str
    latest_risk: RiskOut | None


class ModeratorActionIn(BaseModel):
    note: str | None = None


class CreateConversationIn(BaseModel):
    title: str | None = Field(default=None, max_length=128)


class BootstrapOut(BaseModel):
    users: list[dict]
    conversations: list[ConversationSummaryOut]
    conversation_id: int
