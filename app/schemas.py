from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    # Response model for one chat message.
    id: int
    sender_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class SendMessageIn(BaseModel):
    # Request model for sending a message.
    conversation_id: int
    sender_id: int
    content: str = Field(min_length=1, max_length=8000)


class RiskOut(BaseModel):
    # Response model for one risk assessment snapshot.
    ml_score: float
    rule_score: float
    final_score: float
    tier: str
    rule_hits: dict[str, Any] | None = None
    fusion_ml_weight: float | None = None
    fusion_rule_weight: float | None = None
    ml_confidence_band: str | None = None
    rule_trigger_summary: list[str] | None = None
    message_markers: list[list[str]] | None = None


class ConversationSummaryOut(BaseModel):
    # Lightweight conversation row for list views.
    id: int
    public_id: str
    title: str
    message_count: int
    last_preview: str
    latest_tier: str | None = None
    latest_final_score: float | None = None


class ConversationOut(BaseModel):
    # Full conversation payload including messages and latest risk.
    id: int
    public_id: str
    title: str
    send_restricted: bool
    messages: list[MessageOut]
    latest_risk: RiskOut | None = None


class AnalyzeOut(BaseModel):
    # Response model for manual re-analysis.
    assessment: RiskOut


class FlagIn(BaseModel):
    # Request model for user-flagged moderation cases.
    source: str = "user"
    reason: str | None = None


class ModeratorCaseOut(BaseModel):
    # Response model for moderator queue entries.
    id: int
    conversation_id: int
    conversation_public_id: str | None = None
    conversation_title: str | None = None
    status: str
    source: str
    reason: str | None
    moderator_note: str | None
    priority: int
    review_stage: str | None = None
    workflow_display: str = "Pending"
    created_at: datetime
    preview: str
    latest_risk: RiskOut | None


class ModeratorActionIn(BaseModel):
    # Request model for moderator actions with optional note.
    note: str | None = None


class CreateConversationIn(BaseModel):
    # Request model for creating a new conversation.
    title: str | None = Field(default=None, max_length=128)


class BootstrapOut(BaseModel):
    # Initial payload used by the chat UI on startup.
    users: list[dict]
    conversations: list[ConversationSummaryOut]
    conversation_id: int
