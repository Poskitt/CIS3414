from __future__ import annotations

import re

from app.pipeline.rule_lexicons import (
    AGE_CUE_PATTERNS,
    BOUNDARY_WORRY_PARENT_PHRASES,
    GROOMING_PHRASES,
    PROSOCIAL_PARENT_PHRASES,
    RE_COME_ON,
    RE_ADULT_AGE_STATEMENT,
    RE_MINOR_AGE_STATEMENT,
    RISK_KEYWORDS,
    RISK_KEYWORDS_BOUNDARY,
    THREAT_PHRASES,
    THREAT_REGEX,
)


def _count_boundary_keyword_hits(lower_text: str) -> tuple[int, list[str]]:
    matched_keywords: list[str] = []
    total_hits = 0
    for keyword in RISK_KEYWORDS_BOUNDARY:
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])", re.I)
        matches = pattern.findall(lower_text)
        if matches:
            matched_keywords.append(keyword)
            total_hits += len(matches)
    return total_hits, matched_keywords


def _score_threat_language(lower_text: str, conversation_text: str) -> tuple[float, dict]:
    threat_hits: list[str] = []
    threat_score = 0.0

    for phrase in THREAT_PHRASES:
        if phrase in lower_text:
            threat_score += 0.22
            threat_hits.append(f"phrase:{phrase}")

    for pattern in THREAT_REGEX:
        if pattern.search(conversation_text):
            threat_score += 0.35
            threat_hits.append(f"re:{pattern.pattern[:48]}")

    if "bomb" in lower_text and any(
        word in lower_text for word in ("capital", "parliament", "government", "president", "embassy", "airport")
    ):
        threat_score = max(threat_score, 0.82)
        threat_hits.append("cooccur:bomb+civic_target")

    if "blow up" in lower_text and any(
        word in lower_text for word in ("building", "capital", "school", "mall", "station", "bridge")
    ):
        threat_score = max(threat_score, 0.78)
        threat_hits.append("cooccur:blowup+target")

    threat_score = float(max(0.0, min(1.0, threat_score)))
    return threat_score, {"threat_hits": threat_hits, "threat_score": round(threat_score, 4)}


def _normalize_apostrophes(text: str) -> str:
    return text.replace("'", "").replace("\u2019", "")


def _score_grooming_phrases(normalized_text: str) -> tuple[float, list[str]]:
    matched_phrases: list[str] = []
    seen_normalized_phrases: set[str] = set()
    phrase_score = 0.0
    for phrase in GROOMING_PHRASES:
        normalized_phrase = _normalize_apostrophes(phrase.lower())
        if normalized_phrase in normalized_text and normalized_phrase not in seen_normalized_phrases:
            seen_normalized_phrases.add(normalized_phrase)
            matched_phrases.append(phrase)
            phrase_score += 0.18
    return min(1.0, phrase_score), matched_phrases


def _has_minor_age_only_line(conversation_text: str) -> bool:
    for match in re.finditer(r"(?m)^user\d+:\s*(\d{1,2})\s*$", conversation_text.strip(), re.I):
        try:
            age = int(match.group(1))
            if 1 <= age <= 17:
                return True
        except ValueError:
            pass
    return False


def _has_adult_age_statement(normalized_text: str) -> bool:
    return bool(RE_ADULT_AGE_STATEMENT.search(normalized_text))


def _has_minor_age_statement(normalized_text: str) -> bool:
    return bool(RE_MINOR_AGE_STATEMENT.search(normalized_text))


def _mentions_parental_awareness(normalized_line: str) -> bool:
    return any(phrase in normalized_line for phrase in PROSOCIAL_PARENT_PHRASES)


def _shows_parent_boundary_worry(normalized_line: str) -> bool:
    if _mentions_parental_awareness(normalized_line):
        return False
    if any(phrase in normalized_line for phrase in BOUNDARY_WORRY_PARENT_PHRASES):
        return True
    if "parent" in normalized_line and any(
        phrase in normalized_line for phrase in ("wouldnt like", "wont like", "dont approve", "would disapprove")
    ):
        return True
    if "parent" in normalized_line and "dont know" in normalized_line and any(
        phrase in normalized_line for phrase in ("would", "like", "approve", "think")
    ):
        return True
    return False


def _thread_has_parent_boundary_worry(conversation_text: str) -> bool:
    for line in conversation_text.splitlines():
        normalized_line = _normalize_apostrophes(line.strip().lower())
        if normalized_line and _shows_parent_boundary_worry(normalized_line):
            return True
    return False


def _score_age_disclosure_cluster(normalized_text: str, conversation_text: str) -> tuple[float, list[str]]:
    cluster_hits: list[str] = []
    if "how old are you" not in normalized_text:
        return 0.0, cluster_hits
    cluster_hits.append("cluster:age_question")
    cluster_score = 0.16
    if _has_minor_age_only_line(conversation_text) or _has_minor_age_statement(normalized_text):
        cluster_hits.append("cluster:minor_age_stated")
        cluster_score += 0.28
    if _has_adult_age_statement(normalized_text):
        cluster_hits.append("cluster:adult_age_stated")
        cluster_score += 0.22
    if _thread_has_parent_boundary_worry(conversation_text):
        cluster_hits.append("cluster:parent_boundary")
        cluster_score += 0.12
    if any(
        phrase in normalized_text
        for phrase in (
            "have to tell anyone",
            "have to tell anybody",
            "dont have to tell",
            "nobody has to know",
            "nobody will know",
            "our secret",
            "just between us",
        )
    ):
        cluster_hits.append("cluster:secrecy_after_discomfort")
        cluster_score += 0.26
    return min(1.0, cluster_score), cluster_hits


def _score_scam_financial_cluster(normalized_text: str) -> tuple[float, list[str]]:
    cluster_hits: list[str] = []
    cluster_score = 0.0
    has_gift_card_phrase = "gift card" in normalized_text or "gift cards" in normalized_text
    if has_gift_card_phrase and any(
        phrase in normalized_text
        for phrase in (
            "irs",
            "refund",
            "owe you",
            "tax ",
            "read code",
            "read codes",
        )
    ):
        cluster_score = max(cluster_score, 0.92)
        cluster_hits.append("cluster:advance_fee_gift_tax")
    if ("bitcoin" in normalized_text or "btc" in normalized_text or "crypto" in normalized_text) and any(
        phrase in normalized_text for phrase in ("double", "guaranteed", "wallet")
    ):
        cluster_score = max(cluster_score, 0.9)
        cluster_hits.append("cluster:crypto_double_scam")
    if any(
        phrase in normalized_text
        for phrase in (
            "processing fee",
            "via wire",
            "wire transfer",
            "wire to",
            "pay a $",
            "pay the fee",
        )
    ) and any(phrase in normalized_text for phrase in ("job", "got the job", "the job", "interview")):
        cluster_score = max(cluster_score, 0.9)
        cluster_hits.append("cluster:job_upfront_fee_scam")
    return min(1.0, cluster_score), cluster_hits


def _score_image_pressure_cluster(normalized_text: str) -> tuple[float, list[str]]:
    cluster_hits: list[str] = []
    has_image_request = any(
        phrase in normalized_text
        for phrase in (
            "send me a pic",
            "send me pic",
            "send a pic",
            "send pic",
            "send photo",
            "send nudes",
            "send noodz",
            "show me your",
        )
    )
    has_secrecy_or_pressure = any(
        phrase in normalized_text
        for phrase in (
            "just between us",
            "between us",
            "our secret",
            "dont tell",
            "nobody has to know",
            "dont be shy",
        )
    ) or bool(RE_COME_ON.search(normalized_text))
    if has_image_request and has_secrecy_or_pressure:
        cluster_hits.append("cluster:pic_secrecy_pressure")
        return 0.88, cluster_hits
    if has_image_request:
        cluster_hits.append("cluster:pic_request")
        return 0.58, cluster_hits
    return 0.0, cluster_hits


def detect_grooming_sequence(messages: list[str]) -> dict:
    has_flattery = has_age_question = has_minor_age = has_adult_age = False
    has_parent_resistance = has_isolation_push = has_meetup_escalation = False
    first_seen_index: dict[str, int] = {}

    for line_index, raw_message in enumerate(messages):
        normalized_line = _normalize_apostrophes(raw_message.lower())

        if not has_flattery and any(word in normalized_line for word in ("beautiful", "cute", "pretty")):
            has_flattery = True
            first_seen_index.setdefault("flattery", line_index)
        if not has_age_question and "how old are you" in normalized_line:
            has_age_question = True
            first_seen_index.setdefault("age_question", line_index)
        if not has_minor_age and RE_MINOR_AGE_STATEMENT.search(normalized_line):
            has_minor_age = True
            first_seen_index.setdefault("minor_detected", line_index)
        if not has_adult_age and RE_ADULT_AGE_STATEMENT.search(normalized_line):
            has_adult_age = True
            first_seen_index.setdefault("adult_detected", line_index)
        if not has_parent_resistance and _shows_parent_boundary_worry(normalized_line):
            has_parent_resistance = True
            first_seen_index.setdefault("parent_resistance", line_index)
        if not has_isolation_push and any(
            phrase in normalized_line
            for phrase in (
                "doesnt matter",
                "dont matter",
                "dont tell",
                "just us",
                "our secret",
                "nobody has to know",
                "have to tell anyone",
                "nobody will know",
            )
        ):
            has_isolation_push = True
            first_seen_index.setdefault("isolation_push", line_index)
        if not has_meetup_escalation and any(
            phrase in normalized_line
            for phrase in (
                "run away",
                "meet up",
                "lets meet",
                "let's meet",
                "come with me",
                "meet me",
                "come over",
                "pick you up",
            )
        ):
            has_meetup_escalation = True
            first_seen_index.setdefault("meeting_escalation", line_index)

    progression_score = (
        0.1 * int(has_flattery)
        + 0.2 * int(has_age_question)
        + 0.3 * int(has_minor_age)
        + 0.3 * int(has_adult_age)
        + 0.25 * int(has_parent_resistance)
        + 0.4 * int(has_isolation_push)
        + 0.5 * int(has_meetup_escalation)
    )
    progression_score = float(min(1.0, progression_score))

    sequence_label: str | None = None
    final_sequence_score = progression_score
    if has_minor_age and has_adult_age and (has_isolation_push or has_meetup_escalation):
        final_sequence_score = max(progression_score, 0.95)
        sequence_label = "grooming_high_confidence"

    has_parental_awareness = any(
        _mentions_parental_awareness(_normalize_apostrophes(message.lower())) for message in messages
    )
    has_parent_safe_context = bool(has_parental_awareness and not has_minor_age and not has_adult_age)
    if has_parent_safe_context:
        final_sequence_score = min(final_sequence_score, 0.33)

    sequence_flags = {
        "flattery": has_flattery,
        "age_question": has_age_question,
        "minor_detected": has_minor_age,
        "adult_detected": has_adult_age,
        "parent_resistance": has_parent_resistance,
        "isolation_push": has_isolation_push,
        "meeting_escalation": has_meetup_escalation,
    }
    return {
        "score": round(final_sequence_score, 4),
        "label": sequence_label,
        "flags": sequence_flags,
        "first_index": first_seen_index,
        "prosocial_parent_context": has_parent_safe_context,
    }


def per_message_line_markers(lines: list[str]) -> list[list[str]]:
    message_markers: list[list[str]] = []
    for line in lines:
        normalized_line = _normalize_apostrophes(line.lower())
        message_content = re.sub(r"^\s*user\d+\s*:\s*", "", normalized_line, count=1, flags=re.I)
        line_hits: list[str] = []
        for keyword in RISK_KEYWORDS:
            normalized_keyword = _normalize_apostrophes(keyword.lower())
            if normalized_keyword in message_content and keyword not in line_hits:
                line_hits.append(keyword)
                if len(line_hits) >= 6:
                    break
        if len(line_hits) < 8:
            for phrase in GROOMING_PHRASES:
                normalized_phrase = _normalize_apostrophes(phrase.lower())
                if normalized_phrase in message_content:
                    short_label = phrase if len(phrase) <= 36 else phrase[:33] + "..."
                    phrase_tag = f"phrase:{short_label}"
                    if phrase_tag not in line_hits:
                        line_hits.append(phrase_tag)
                    if len(line_hits) >= 8:
                        break
        for threat_phrase in THREAT_PHRASES:
            if threat_phrase in message_content:
                line_hits.append(f"threat:{threat_phrase}")
                break
        message_markers.append(line_hits[:10])
    return message_markers


def rule_score_for_text(
    conversation_text: str,
    num_messages: int,
    messages: list[str] | None = None,
) -> tuple[float, dict]:
    lower_text = conversation_text.lower()
    normalized_text = _normalize_apostrophes(lower_text)
    rule_hits: dict[str, int | list[str] | dict] = {"keywords": 0, "age_cues": []}

    keyword_hit_count = 0
    for keyword in RISK_KEYWORDS:
        normalized_keyword = _normalize_apostrophes(keyword)
        if normalized_keyword in normalized_text:
            occurrences = normalized_text.count(normalized_keyword)
            keyword_hit_count += occurrences
            rule_hits["keywords"] = int(rule_hits["keywords"]) + occurrences

    boundary_hit_count, boundary_keywords = _count_boundary_keyword_hits(lower_text)
    keyword_hit_count += boundary_hit_count
    rule_hits["keywords"] = int(rule_hits["keywords"]) + boundary_hit_count
    rule_hits["boundary_keywords"] = boundary_keywords

    age_cue_patterns = []
    for pattern in AGE_CUE_PATTERNS:
        if pattern.search(conversation_text):
            age_cue_patterns.append(pattern.pattern)
    rule_hits["age_cues"] = age_cue_patterns

    phrase_score, grooming_phrases = _score_grooming_phrases(normalized_text)
    rule_hits["grooming_phrases"] = grooming_phrases

    age_cluster_score, age_cluster_hits = _score_age_disclosure_cluster(normalized_text, conversation_text)
    rule_hits["age_disclosure_cluster"] = age_cluster_hits

    scam_cluster_score, scam_cluster_hits = _score_scam_financial_cluster(normalized_text)
    rule_hits["scam_cluster"] = scam_cluster_hits

    image_cluster_score, image_cluster_hits = _score_image_pressure_cluster(normalized_text)
    rule_hits["image_pressure_cluster"] = image_cluster_hits

    thread_lines = messages if messages is not None else [
        ln.strip() for ln in conversation_text.splitlines() if ln.strip()
    ]
    grooming_sequence = detect_grooming_sequence(thread_lines)
    rule_hits["grooming_sequence"] = grooming_sequence

    message_denominator = max(num_messages, 1)
    keyword_density = min(1.0, keyword_hit_count / (message_denominator * 4.0))
    age_boost = 0.32 if age_cue_patterns else 0.0
    escalation_signal = min(1.0, keyword_hit_count / 18.0)

    base_grooming_score = 0.45 * keyword_density + 0.35 * age_boost + 0.2 * escalation_signal
    grooming_score = float(max(0.0, min(1.0, base_grooming_score)))
    grooming_score = max(
        grooming_score,
        phrase_score,
        age_cluster_score,
        scam_cluster_score,
        image_cluster_score,
        float(grooming_sequence["score"]),
    )
    if grooming_sequence.get("prosocial_parent_context"):
        grooming_score = min(grooming_score, 0.18)  # lower score when parents are clearly involved

    threat_score, threat_meta = _score_threat_language(lower_text, conversation_text)
    rule_hits["threat"] = threat_meta

    final_rule_score = max(grooming_score, threat_score)
    rule_hits["grooming_component"] = round(grooming_score, 4)
    rule_hits["keyword_density"] = round(keyword_density, 4)
    rule_hits["escalation"] = round(escalation_signal, 4)
    return final_rule_score, rule_hits
