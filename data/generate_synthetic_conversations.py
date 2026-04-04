# Writes synthetic_conversations.csv; labels 0 harmless .. 4 extremism.
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "synthetic_conversations.csv"

def conv(lines: list[tuple[str, str]]) -> str:
    parts = []
    for i, (u, msg) in enumerate(lines):
        ts = f"{8 + (i % 12):02d}:{(i * 7) % 60:02d}"
        parts.append(f"{u} [{ts}]: {msg}")
    return "\n".join(parts)


def gen_harmless(n: int, rng: random.Random) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    u = [("u3", "u9"), ("u12", "u4"), ("u7", "u22"), ("u1", "u2")]
    for _ in range(n):
        a, b = rng.choice(u)
        templates = [
            [(a, "nah bruv thats peak"), (b, "fr fr 💀"), (a, "lesson was dead today")],
            [(a, "gonna fail maths lol"), (b, "same"), (a, "might actually revise tho")],
            [(a, "u up for valorant later"), (b, "ye after dinner"), (a, "bet")],
            [(a, "teacher said my essay was mid"), (b, "ouch"), (a, "its calm")],
            [(a, "im gonna rob a bank lol jk"), (b, "😂😂 stop"), (a, "jk jk unless... no jk")],
            [(a, "that meme about stealing is so unfunny"), (b, "yeah crime jokes r tired"), (a, "fr")],
            [(a, "my mum thinks im on discord 24/7"), (b, "are u"), (a, "maybe")],
            [(a, "cant believe we have homework on friday"), (b, "inhumane"), (a, "fr")],
            [(a, "yo did u see the match"), (b, "which one"), (a, "city game was wild")],
            [(a, "im so tired rn"), (b, "go sleep then"), (a, "cant gotta finish this")],
            [(a, "bro said he was gonna 'hack the school' as a joke in class"), (b, "teachers face 💀"), (a, "detention speedrun")],
            [(a, "is it weird i dont use insta much"), (b, "nah some people dont"), (a, "cool")],
            [(a, "ty for the notes yesterday"), (b, "np anytime"), (a, "saved my life")],
            [(a, "rain again ffs"), (b, "classic"), (a, "want summer already")],
            [(a, "helo how r u"), (b, "hey im good u"), (a, "god thx")],  # typos harmless
            [(a, "short msg"), (b, "same")],
        ]
        rows.append((conv(rng.choice(templates)), 0))
    return rows


def gen_grooming(n: int, rng: random.Random) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for _ in range(n):
        a, b = ("uPred", "u14") if rng.random() > 0.3 else ("uX", "uY")
        templates = [
            [(a, "you seem rlly mature compared to ppl ur age"), (b, "idk"), (a, "thats a compliment btw")],
            [(a, "do ur mates know we talk"), (b, "no"), (a, "good lets keep it that way")],
            [(a, "ur parents strict about ur phone"), (b, "kinda"), (a, "thought so")],
            [(a, "just between us yeah"), (b, "ok"), (a, "i trust u")],
            [(a, "ever sent a selfie to someone online before"), (b, "no"), (a, "no pressure just curious")],
            [(a, "how old r u again i forgot"), (b, "15"), (a, "cool im a bit older hope thats ok")],
            [(a, "when everyones asleep we could vc"), (b, "idk"), (a, "only if u want")],
            [(a, "youre pretty mature for a freshman ngl"), (b, "thanks??"), (a, "mean it")],
            [(a, "dont screenshot our chats ok"), (b, "why"), (a, "private stuff")],
            [(a, "if u loved me u wouldnt question it"), (b, "were not dating"), (a, "you know what i mean")],
        ]
        rows.append((conv(rng.choice(templates)), 1))
    return rows


def gen_scam(n: int, rng: random.Random) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for _ in range(n):
        a, b = ("uSupport", "uVictim") if rng.random() > 0.4 else ("u0", "u1")
        templates = [
            [(a, "hi this is delivery we couldnt reach you pay redelivery fee £2.99"), (b, "i didnt order"), (a, "tracking ref 8X2 confirm address")],
            [(a, "your netflix payment failed update card here"), (b, "which link"), (a, "secure-billing-verify.net/nf")],
            [(a, "congrats selected for tax refund claim within 24h"), (b, "is this real"), (a, "gov-refund-apply.co.uk enter ni number")],
            [(a, "im stuck abroad need western union £200 ill pay back"), (b, "who is this"), (a, "its me check the display name")],
            [(a, "crypto opportunity 40% weekly dm for details"), (b, "sounds like scam"), (a, "risk free trial deposit")],
            [(a, "your cousin asked me to message you theyre in hospital"), (b, "which cousin"), (a, "the one you dont talk to often wire help")],
            [(a, "verify your account unusual login turkey"), (b, "i wasnt in turkey"), (a, "click link to secure")],
            [(a, "invoice attached for software you purchased"), (b, "i didnt buy"), (a, "open attachment to dispute")],
        ]
        rows.append((conv(rng.choice(templates)), 2))
    return rows


def gen_crime(n: int, rng: random.Random) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for _ in range(n):
        a, b = rng.choice([("uA", "uB"), ("u5", "u6")])
        templates = [
            [(a, "where do they keep the keys overnight"), (b, "why"), (a, "curious about the building")],
            [(a, "could you move product for cut"), (b, "what product"), (a, "dont ask online")],
            [(a, "need someone to hold something no questions"), (b, "nah"), (a, "500 cash")],
            [(a, "how hot is it if i walk out with a cart"), (b, "youre joking"), (a, "hypothetical")],
            [(a, "know anyone who does fake documents"), (b, "no"), (a, "asking for a friend obvs")],
            [(a, "car with no plates still drivable short distance"), (b, "thats illegal"), (a, "yeah just theory")],
            [(a, "best way to wipe serial numbers asking for screenplay"), (b, "weird flex"), (a, "research")],
            [(a, "if someone wanted tools for breaking in what would they need"), (b, "im not helping"), (a, "ok chill")],
        ]
        rows.append((conv(rng.choice(templates)), 3))
    return rows


def gen_extremism(n: int, rng: random.Random) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    for _ in range(n):
        a, b = rng.choice([("uE1", "uE2"), ("uZ", "uQ")])
        templates = [
            [(a, "some groups say direct action is the only language they hear"), (b, "thats edgy"), (a, "read more before judging")],
            [(a, "manifesto style posts are circulating"), (b, "where"), (a, "private channels not linking")],
            [(a, "they want recruits who wont ask questions"), (b, "sounds culty"), (a, "or committed")],
            [(a, "violence against civilians is never justified change my mind"), (b, "depends on context"), (a, "interesting")],
            [(a, "training materials for urban ops exist online"), (b, "report that"), (a, "freedom of info")],
            [(a, "the capital is a symbol taking it sends a message"), (b, "youre insane"), (a, "history proves otherwise")],
            [(a, "martyr videos are motivational for some"), (b, "thats messed up"), (a, "perspective")],
            [(a, "going to bomb the bridge was discussed in chat logs"), (b, "wtf"), (a, "leaked trial evidence")],
        ]
        rows.append((conv(rng.choice(templates)), 4))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=240, help="Approx total rows (split across 5 classes)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    base = args.rows // 5
    rem = args.rows % 5
    counts = [base + (1 if i < rem else 0) for i in range(5)]

    all_rows: list[tuple[str, int]] = []
    all_rows.extend(gen_harmless(counts[0], rng))
    all_rows.extend(gen_grooming(counts[1], rng))
    all_rows.extend(gen_scam(counts[2], rng))
    all_rows.extend(gen_crime(counts[3], rng))
    all_rows.extend(gen_extremism(counts[4], rng))

    rng.shuffle(all_rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "label"])
        for text, label in all_rows:
            w.writerow([text, label])

    dist = {i: sum(1 for _, lb in all_rows if lb == i) for i in range(5)}
    print(f"Wrote {len(all_rows)} rows to {args.out}")
    print(f"Label counts: {dist}")


if __name__ == "__main__":
    main()
