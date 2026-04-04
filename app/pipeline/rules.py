from __future__ import annotations

import re

# Substring match on lowercased thread text (multi-word phrases reduce false hits).
RISK_KEYWORDS = [
    "meet up",
    "meet me",
    "lets meet",
    "let's meet",
    "pick you up",
    "pick u up",
    "come over",
    "come to my",
    "your house",
    "your home",
    "where do you live",
    "what school",
    "which school",
    "alone together",
    "just us",
    "when nobody",
    "when no one is",
    "sneak out",
    "run away",
    "leave your parents",
    "dont tell",
    "do not tell",
    "have to tell anyone",
    "have to tell anybody",
    "dont have to tell",
    "nobody needs to know",
    "no one needs to know",
    "dont let",
    "keep this secret",
    "our secret",
    "stay quiet",
    "delete the chat",
    "clear your history",
    "how old",
    "years old",
    "underage",
    "minor",
    "middle school",
    "high school freshman",
    "too young",
    "webcam",
    "facetime",
    "video call",
    "screen record",
    "screenshot this",
    "live pic",
    "mirror pic",
    "body shot",
    "shirtless",
    "in your underwear",
    "take it off",
    "turn around",
    "pose for",
    "phone number",
    "your number",
    "text me",
    "whatsapp",
    "telegram",
    "discord",
    "instagram",
    "snapchat",
    "add my snap",
    "kik",
    "wickr",
    "email me",
    "drop your @",
    "nude",
    "nudes",
    "naked",
    "nsfw",
    "dick pic",
    "send me a pic",
    "send pic",
    "send photo",
    "show me your",
    "flash me",
    "touch yourself",
    "moan for",
    "turn you on",
    "lose your virginity",
    "first time sex",
    "gift card",
    "venmo",
    "paypal",
    "cashapp",
    "send money",
    "ill buy you",
    "i'll buy you",
    "allowance",
    "if you send",
    "nobody understands",
    "only i understand",
    "special friendship",
    "mature for your age",
    "act older",
    "if you love me",
    "prove you love",
    "dont you trust",
    "don't you trust",
    "hurt my feelings",
    "ill leave",
    "i'll leave",
    "uncomfortable",
    "my parents",
    "tell my mum",
    "tell my mom",
    "tell my dad",
    "going to report",
    "block you",
    "kill yourself",
    "kys",
    "hurt yourself",
    "cut yourself",
]

# Short tokens; word-boundary match only.
RISK_KEYWORDS_BOUNDARY = [
    "alone",
    "secret",
    "pics",
    "picture",
    "photo",
    "snap",
    "address",
    "young",
    "rape",
    "porn",
]

GROOMING_PHRASES = [
    "just me and you",
    "dont tell anybody",
    "don't tell anybody",
    "dont tell anyone",
    "don't tell anyone",
    "have to tell anyone",
    "have to tell anybody",
    "dont have to tell",
    "don't have to tell",
    "nobody has to know",
    "nobody will know",
    "our little secret",
    "between us",
    "not a big deal if",
    "won't tell anyone",
    "wont tell anyone",
    "chebs",
    "send nudes",
    "send noodz",
    "lewd",
    "horny for you",
    "jerk off",
    "suck my",
    "blow me",
    "finger you",
    "eat you out",
    "get you pregnant",
    "hello beautiful",
    "hey beautiful",
    "hi beautiful",
    "youre beautiful",
    "you're beautiful",
    "prettier than girls",
    "special girl",
    "special boy",
    "boyfriend material",
    "like a girlfriend",
    "older guys",
    "older man",
    "experienced guy",
    "when they are asleep",
    "when parents sleep",
    "after your parents",
    "lock your door",
    "dont wake",
    "skip class",
    "fake sick",
    "disappearing message",
    "vanish mode",
    "burner phone",
    "alt account",
    "finsta",
    "private story",
]

THREAT_PHRASES = [
    "bomb the",
    "going to bomb",
    "blow up the",
    "blow up a",
    "blow up the school",
    "school shooting",
    "shoot up the",
    "active shooter",
    "mass shooting",
    "terrorist",
    "terror attack",
    "detonate",
    "shoot the president",
    "kill the president",
    "attack the capital",
    "attack parliament",
    "attack the government",
    "martyr operation",
    "jihad",
    "infidel",
    "kill everyone",
    "die for the cause",
    "stab you",
    "stab them",
    "kill you",
    "murder you",
    "kidnap",
    "chloroform",
    "pipe bomb",
    "molotov",
    "run them over",
    "rape you",
    "rape her",
    "rape him",
    "anthrax",
    "ricin",
    "sarin",
    "chemical weapon",
    "biological weapon",
    "hostage",
    "execute the",
    "behead",
    "lynch",
    "genocide",
    "ethnic cleansing",
]

THREAT_REGEX = [
    re.compile(r"\bgoing\s+to\s+bomb\b", re.I),
    re.compile(r"\bbomb\s+the\s+\w+", re.I),
    re.compile(r"\b(i\s+will|i'm\s+going\s+to|we\s+will)\s+.*\bbomb\b", re.I),
    re.compile(r"\battack\s+the\s+(capital|city|parliament|government)\b", re.I),
    re.compile(r"\b(shoot|stab|kill)\s+(you|them|him|her|everyone)\b", re.I),
    re.compile(r"\b(i'll|i\s+will)\s+\w*\s*(kill|hurt|shoot|stab)\b", re.I),
]

_RE_COME_ON = re.compile(r"\bcome on\b", re.I)

AGE_CUE_PATTERNS = [
    re.compile(r"\bhow\s+old\s+are\s+you\b", re.I),
    re.compile(r"\b(i am|i'm|im)\s+\d{1,2}\b", re.I),
    re.compile(r"\bare\s+you\s+\d{1,2}\b", re.I),
    re.compile(r"\b(i'm|i am|im)\s+only\s+\d{1,2}\b", re.I),
    re.compile(r"\b(i'm|i am|im)\s+a\s+\d{1,2}\s+year\s+old\b", re.I),
    re.compile(r"\byears?\s+old\b", re.I),
    re.compile(r"\bin\s+\d{1,2}(st|nd|rd|th)?\s+grade\b", re.I),
    re.compile(r"\bgrade\s+\d{1,2}\b", re.I),
]


def _boundary_keyword_hits(text_lower: str) -> tuple[int, list[str]]:
    hits: list[str] = []
    n = 0
    for kw in RISK_KEYWORDS_BOUNDARY:
        pat = re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", re.I)
        found = pat.findall(text_lower)
        if found:
            hits.append(kw)
            n += len(found)
    return n, hits


def _threat_score(text_lower: str, conversation_text: str) -> tuple[float, dict]:
    hits: list[str] = []
    score = 0.0

    for phrase in THREAT_PHRASES:
        if phrase in text_lower:
            score += 0.22
            hits.append(f"phrase:{phrase}")

    for pat in THREAT_REGEX:
        if pat.search(conversation_text):
            score += 0.35
            hits.append(f"re:{pat.pattern[:48]}")

    if "bomb" in text_lower and any(
        w in text_lower for w in ("capital", "parliament", "government", "president", "embassy", "airport")
    ):
        score = max(score, 0.82)
        hits.append("cooccur:bomb+civic_target")

    if "blow up" in text_lower and any(
        w in text_lower for w in ("building", "capital", "school", "mall", "station", "bridge")
    ):
        score = max(score, 0.78)
        hits.append("cooccur:blowup+target")

    score = float(max(0.0, min(1.0, score)))
    return score, {"threat_hits": hits, "threat_score": round(score, 4)}


def _fold_apostrophe(s: str) -> str:
    return s.replace("'", "").replace("\u2019", "")


def _grooming_phrase_score(fold: str) -> tuple[float, list[str]]:
    found: list[str] = []
    seen_folded: set[str] = set()
    s = 0.0
    for phrase in GROOMING_PHRASES:
        p = _fold_apostrophe(phrase.lower())
        if p in fold and p not in seen_folded:
            seen_folded.add(p)
            found.append(phrase)
            s += 0.18
    return min(1.0, s), found


def _minor_stated_solo_age(conversation_text: str) -> bool:
    for m in re.finditer(r"(?m)^user\d+:\s*(\d{1,2})\s*$", conversation_text.strip(), re.I):
        try:
            a = int(m.group(1))
            if 1 <= a <= 17:
                return True
        except ValueError:
            pass
    return False


_RE_MINOR_AGE_STATEMENT = re.compile(
    r"\b(i\s*am|im)\s+(1[0-7]|[1-9])\b", re.I
)
_RE_ADULT_AGE_STATEMENT = re.compile(
    r"\b(i\s*am|im)\s+(1[8-9]|[2-9][0-9])\b", re.I
)


def _adult_stated_age_fold(fold: str) -> bool:
    return bool(_RE_ADULT_AGE_STATEMENT.search(fold))


def _minor_age_natural_in_fold(fold: str) -> bool:
    return bool(_RE_MINOR_AGE_STATEMENT.search(fold))


# "Told parents / they said ok" lines are not treated as boundary worry.
_PROSOCIAL_PARENT_PHRASES = (
    "let me tell my parents",
    "gonna tell my parents",
    "going to tell my parents",
    "ill tell my parents",
    "ive told my parents",
    "told my parents",
    "telling my parents",
    "ask my parents",
    "asked my parents",
    "asking my parents",
    "check with my parents",
    "checking with my parents",
    "run it by my parents",
    "parents said",
    "parents say",
    "my mom said",
    "my dad said",
    "they said its fine",
    "they said ok",
    "they said yes",
    "theyre ok with",
    "they are ok with",
)
_BOUNDARY_WORRY_PARENT_PHRASES = (
    "my parents wouldnt",
    "my parents wont",
    "my parents wouldnt like",
    "my parents dont know",
    "my parents dont like",
    "if my parents",
    "parents would be mad",
    "parents cant know",
    "without my parents knowing",
    "parents would kill",
    "parents wouldnt approve",
    "scared of my parents",
)


def _prosocial_parent_disclosure_fold(f: str) -> bool:
    return any(p in f for p in _PROSOCIAL_PARENT_PHRASES)


def _parent_boundary_worry_fold(f: str) -> bool:
    if _prosocial_parent_disclosure_fold(f):
        return False
    if any(p in f for p in _BOUNDARY_WORRY_PARENT_PHRASES):
        return True
    if "parent" in f and any(
        x in f for x in ("wouldnt like", "wont like", "dont approve", "would disapprove")
    ):
        return True
    if "parent" in f and "dont know" in f and any(
        x in f for x in ("would", "like", "approve", "think")
    ):
        return True
    return False


def _conversation_has_parent_boundary_worry(conversation_text: str) -> bool:
    for ln in conversation_text.splitlines():
        f = _fold_apostrophe(ln.strip().lower())
        if f and _parent_boundary_worry_fold(f):
            return True
    return False


def _age_disclosure_cluster(fold: str, conversation_text: str) -> tuple[float, list[str]]:
    hits: list[str] = []
    if "how old are you" not in fold:
        return 0.0, hits
    hits.append("cluster:age_question")
    s = 0.16
    if _minor_stated_solo_age(conversation_text) or _minor_age_natural_in_fold(fold):
        hits.append("cluster:minor_age_stated")
        s += 0.28
    if _adult_stated_age_fold(fold):
        hits.append("cluster:adult_age_stated")
        s += 0.22
    if _conversation_has_parent_boundary_worry(conversation_text):
        hits.append("cluster:parent_boundary")
        s += 0.12
    if any(
        x in fold
        for x in (
            "have to tell anyone",
            "have to tell anybody",
            "dont have to tell",
            "nobody has to know",
            "nobody will know",
            "our secret",
            "just between us",
        )
    ):
        hits.append("cluster:secrecy_after_discomfort")
        s += 0.26
    return min(1.0, s), hits


def _scam_financial_cluster(fold: str) -> tuple[float, list[str]]:
    hits: list[str] = []
    s = 0.0
    gift = "gift card" in fold or "gift cards" in fold
    if gift and any(
        x in fold
        for x in (
            "irs",
            "refund",
            "owe you",
            "tax ",
            "read code",
            "read codes",
        )
    ):
        s = max(s, 0.92)
        hits.append("cluster:advance_fee_gift_tax")
    if ("bitcoin" in fold or "btc" in fold or "crypto" in fold) and any(
        x in fold for x in ("double", "guaranteed", "wallet")
    ):
        s = max(s, 0.9)
        hits.append("cluster:crypto_double_scam")
    if any(
        x in fold
        for x in (
            "processing fee",
            "via wire",
            "wire transfer",
            "wire to",
            "pay a $",
            "pay the fee",
        )
    ) and any(x in fold for x in ("job", "got the job", "the job", "interview")):
        s = max(s, 0.9)
        hits.append("cluster:job_upfront_fee_scam")
    return min(1.0, s), hits


def _image_pressure_cluster(fold: str) -> tuple[float, list[str]]:
    hits: list[str] = []
    pic = any(
        p in fold
        for p in (
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
    secrecy_or_pressure = any(
        x in fold
        for x in (
            "just between us",
            "between us",
            "our secret",
            "dont tell",
            "nobody has to know",
            "dont be shy",
        )
    ) or bool(_RE_COME_ON.search(fold))
    if pic and secrecy_or_pressure:
        hits.append("cluster:pic_secrecy_pressure")
        return 0.88, hits
    if pic:
        hits.append("cluster:pic_request")
        return 0.58, hits
    return 0.0, hits


def detect_grooming_sequence(messages: list[str]) -> dict:
    flattery = age_q = minor = adult = parent_r = iso = meet = False
    first: dict[str, int] = {}

    for i, raw in enumerate(messages):
        f = _fold_apostrophe(raw.lower())

        if not flattery and any(w in f for w in ("beautiful", "cute", "pretty")):
            flattery = True
            first.setdefault("flattery", i)
        if not age_q and "how old are you" in f:
            age_q = True
            first.setdefault("age_question", i)
        if not minor and _RE_MINOR_AGE_STATEMENT.search(f):
            minor = True
            first.setdefault("minor_detected", i)
        if not adult and _RE_ADULT_AGE_STATEMENT.search(f):
            adult = True
            first.setdefault("adult_detected", i)
        if not parent_r and _parent_boundary_worry_fold(f):
            parent_r = True
            first.setdefault("parent_resistance", i)
        if not iso and any(
            x in f
            for x in (
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
            iso = True
            first.setdefault("isolation_push", i)
        if not meet and any(
            x in f
            for x in (
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
            meet = True
            first.setdefault("meeting_escalation", i)

    prog = (
        0.1 * int(flattery)
        + 0.2 * int(age_q)
        + 0.3 * int(minor)
        + 0.3 * int(adult)
        + 0.25 * int(parent_r)
        + 0.4 * int(iso)
        + 0.5 * int(meet)
    )
    prog = float(min(1.0, prog))

    label: str | None = None
    score = prog
    if minor and adult and (iso or meet):
        score = max(prog, 0.95)
        label = "grooming_high_confidence"

    prosocial_parent = any(
        _prosocial_parent_disclosure_fold(_fold_apostrophe(m.lower())) for m in messages
    )
    prosocial_parent_context = bool(prosocial_parent and not minor and not adult)
    if prosocial_parent_context:
        score = min(score, 0.33)

    flags = {
        "flattery": flattery,
        "age_question": age_q,
        "minor_detected": minor,
        "adult_detected": adult,
        "parent_resistance": parent_r,
        "isolation_push": iso,
        "meeting_escalation": meet,
    }
    return {
        "score": round(score, 4),
        "label": label,
        "flags": flags,
        "first_index": first,
        "prosocial_parent_context": prosocial_parent_context,
    }


def rule_score_for_text(
    conversation_text: str,
    num_messages: int,
    messages: list[str] | None = None,
) -> tuple[float, dict]:
    text_lower = conversation_text.lower()
    fold = _fold_apostrophe(text_lower)
    hits: dict[str, int | list[str] | dict] = {"keywords": 0, "age_cues": []}

    kw_hits = 0
    for kw in RISK_KEYWORDS:
        kf = _fold_apostrophe(kw)
        if kf in fold:
            c = fold.count(kf)
            kw_hits += c
            hits["keywords"] = int(hits["keywords"]) + c

    b_n, b_list = _boundary_keyword_hits(text_lower)
    kw_hits += b_n
    hits["keywords"] = int(hits["keywords"]) + b_n
    hits["boundary_keywords"] = b_list

    age_hits = []
    for pat in AGE_CUE_PATTERNS:
        if pat.search(conversation_text):
            age_hits.append(pat.pattern)
    hits["age_cues"] = age_hits

    phrase_s, phrase_hits = _grooming_phrase_score(fold)
    hits["grooming_phrases"] = phrase_hits

    cluster_s, cluster_hits = _age_disclosure_cluster(fold, conversation_text)
    hits["age_disclosure_cluster"] = cluster_hits

    scam_s, scam_hits = _scam_financial_cluster(fold)
    hits["scam_cluster"] = scam_hits

    img_s, img_hits = _image_pressure_cluster(fold)
    hits["image_pressure_cluster"] = img_hits

    msg_lines = messages if messages is not None else [
        ln.strip() for ln in conversation_text.splitlines() if ln.strip()
    ]
    gs = detect_grooming_sequence(msg_lines)
    hits["grooming_sequence"] = gs

    denom = max(num_messages, 1)
    density = min(1.0, kw_hits / (denom * 4.0))
    age_boost = 0.32 if age_hits else 0.0
    escalation = min(1.0, kw_hits / 18.0)

    grooming_raw = 0.45 * density + 0.35 * age_boost + 0.2 * escalation
    grooming_score = float(max(0.0, min(1.0, grooming_raw)))
    grooming_score = max(
        grooming_score,
        phrase_s,
        cluster_s,
        scam_s,
        img_s,
        float(gs["score"]),
    )
    if gs.get("prosocial_parent_context"):
        grooming_score = min(grooming_score, 0.18)  # cap when parents looped in, no ages

    threat_s, threat_meta = _threat_score(text_lower, conversation_text)
    hits["threat"] = threat_meta

    score = max(grooming_score, threat_s)
    hits["grooming_component"] = round(grooming_score, 4)
    hits["keyword_density"] = round(density, 4)
    hits["escalation"] = round(escalation, 4)
    return score, hits
