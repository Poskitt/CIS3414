# Extra lines appended for TF-IDF only (rules use raw thread).
from __future__ import annotations

import re

from app.pipeline.rules import RISK_KEYWORDS

_FEATURE_TERMS: tuple[str, ...] = tuple(
    kw for kw in RISK_KEYWORDS if len(kw) >= 4
)[:45]


def count_messages_in_thread(text: str) -> int:
    # Counts messages from user labels, with a non-empty line fallback.
    n = len(re.findall(r"\buser\d+\s*:", text, re.I))
    if n > 0:
        return n
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return max(len(lines), 1)


def unique_speakers(text: str) -> int:
    # Counts distinct user IDs found in the thread.
    ids = re.findall(r"(?m)^\s*user(\d+)\s*:", text, re.I)
    if ids:
        return len(set(ids))
    ids2 = re.findall(r"\buser(\d+)\s*:", text, re.I)
    return len(set(ids2)) if ids2 else 0


def _lines(text: str) -> list[str]:
    # Returns trimmed non-empty lines, handling one-line input cleanly.
    if "\n" in text.strip():
        return [ln for ln in text.splitlines() if ln.strip()]
    return [text.strip()] if text.strip() else []


def late_stage_risk_term_count(text: str) -> int:
    # Counts risk terms in the final 30% of the conversation.
    lines = _lines(text)
    n = len(lines)
    start = int(n * 0.7) if n else 0
    tail = "\n".join(lines[start:]).lower()
    return sum(tail.count(kw.lower()) for kw in _FEATURE_TERMS)


def repeated_risk_term_count(text: str) -> int:
    # Counts repeated risk terms beyond their first occurrence.
    tl = text.lower()
    extra = 0
    for kw in _FEATURE_TERMS:
        c = tl.count(kw.lower())
        if c >= 2:
            extra += c - 1
    return extra


def first_risk_speaker(text: str) -> str:
    # Returns the first user ID that uses any tracked risk term.
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
    # Builds a compact feature block appended to ML input text.
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
    # Appends derived features to raw thread text for classifier input.
    if not raw_thread.strip():
        return raw_thread
    return raw_thread.strip() + build_feature_block(raw_thread)
