"""
Conversation-level signals appended as text before ML vectorization (train + inference).

Keeps rules on raw thread text; only the ML leg sees [FEATURES] block.
"""
from __future__ import annotations

import re

from app.pipeline.rules import RISK_KEYWORDS

# Subset of rule keywords long enough to count as "risk terms" in the tail / repetition heuristics.
_FEATURE_TERMS: tuple[str, ...] = tuple(
    kw for kw in RISK_KEYWORDS if len(kw) >= 4
)[:45]


def count_messages_in_thread(text: str) -> int:
    n = len(re.findall(r"\buser\d+\s*:", text, re.I))
    if n > 0:
        return n
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return max(len(lines), 1)


def unique_speakers(text: str) -> int:
    ids = re.findall(r"(?m)^\s*user(\d+)\s*:", text, re.I)
    if ids:
        return len(set(ids))
    ids2 = re.findall(r"\buser(\d+)\s*:", text, re.I)
    return len(set(ids2)) if ids2 else 0


def _lines(text: str) -> list[str]:
    if "\n" in text.strip():
        return [ln for ln in text.splitlines() if ln.strip()]
    return [text.strip()] if text.strip() else []


def late_stage_risk_term_count(text: str) -> int:
    lines = _lines(text)
    n = len(lines)
    start = int(n * 0.7) if n else 0
    tail = "\n".join(lines[start:]).lower()
    return sum(tail.count(kw.lower()) for kw in _FEATURE_TERMS)


def repeated_risk_term_count(text: str) -> int:
    tl = text.lower()
    extra = 0
    for kw in _FEATURE_TERMS:
        c = tl.count(kw.lower())
        if c >= 2:
            extra += c - 1
    return extra


def first_risk_speaker(text: str) -> str:
    lines = _lines(text)
    for line in lines:
        m = re.match(r"^\s*user(\d+)\s*:", line.strip(), re.I)
        if not m:
            continue
        low = line.lower()
        if any(kw.lower() in low for kw in _FEATURE_TERMS):
            return m.group(1)
    return "none"


def build_feature_block(text: str) -> str:
    """Structured suffix appended to thread text for TF-IDF (train + API)."""
    n = count_messages_in_thread(text)
    sp = unique_speakers(text)
    late = late_stage_risk_term_count(text)
    rep = repeated_risk_term_count(text)
    initiator = first_risk_speaker(text)
    return (
        "\n[FEATURES]\n"
        f"message_count={n}\n"
        f"unique_speakers={sp}\n"
        f"late_stage_risk_terms={late}\n"
        f"repeated_risk_terms={rep}\n"
        f"first_risk_speaker_user={initiator}\n"
    )


def augment_text_for_ml(raw_thread: str) -> str:
    if not raw_thread.strip():
        return raw_thread
    return raw_thread.strip() + build_feature_block(raw_thread)
