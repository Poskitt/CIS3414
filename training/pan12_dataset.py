# PAN12 XML via iterparse (large files). Problem 1 author list = predator label.
from __future__ import annotations

import random
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path


def load_predator_authors(groundtruth_problem1: Path) -> set[str]:
    lines = groundtruth_problem1.read_text(encoding="utf-8", errors="replace").splitlines()
    return {ln.strip() for ln in lines if ln.strip()}


def _message_parts(message_el: ET.Element) -> tuple[str, str]:
    author = ""
    text = ""
    for child in message_el:
        tag = child.tag.split("}")[-1]
        if tag == "author" and child.text:
            author = child.text.strip()
        elif tag == "text":
            text = (child.text or "").strip()
    return author, text


def iter_pan12_conversations(
    xml_path: Path,
    predator_authors: set[str],
    *,
    max_chars: int = 80_000,
    max_messages: int = 400,
) -> Iterator[tuple[str, int]]:
    for _event, elem in ET.iterparse(str(xml_path), events=("end",)):
        tag = elem.tag.split("}")[-1]
        if tag != "conversation":
            continue

        label = 0
        lines: list[str] = []
        char_budget = max_chars

        for msg in elem:
            if msg.tag.split("}")[-1] != "message":
                continue
            author, text = _message_parts(msg)
            if author in predator_authors:
                label = 1
            line = f"{author}: {text}"
            if char_budget <= 0:
                continue
            if len(line) > char_budget:
                line = line[:char_budget] + "..."
                char_budget = 0
            else:
                char_budget -= len(line) + 1
            lines.append(line)
            if len(lines) >= max_messages:
                break

        full = "\n".join(lines)
        elem.clear()
        if not full.strip():
            continue
        yield full, label


def collect_pan12_xy(
    xml_path: Path,
    groundtruth_problem1: Path,
    *,
    max_negative_samples: int | None,
    random_seed: int,
    max_chars: int,
    max_messages: int,
) -> tuple[list[str], list[int]]:
    predators = load_predator_authors(groundtruth_problem1)
    rng = random.Random(random_seed)

    positives: list[str] = []
    negatives: list[str] = []
    neg_seen = 0

    for text, y in iter_pan12_conversations(
        xml_path,
        predators,
        max_chars=max_chars,
        max_messages=max_messages,
    ):
        if y == 1:
            positives.append(text)
            continue
        neg_seen += 1
        if max_negative_samples is None:
            negatives.append(text)
        elif len(negatives) < max_negative_samples:
            negatives.append(text)
        else:
            j = rng.randint(0, neg_seen - 1)
            if j < max_negative_samples:
                negatives[j] = text

    X = positives + negatives
    y = [1] * len(positives) + [0] * len(negatives)
    order = list(range(len(X)))
    rng.shuffle(order)
    X = [X[i] for i in order]
    y = [y[i] for i in order]
    return X, y


PAN12_FOLDER_NAME = "pan12-sexual-predator-identification-test-corpus-2012-05-21"


def default_pan12_dir(training_dir: Path) -> Path:
    return training_dir / PAN12_FOLDER_NAME


def resolve_pan12_corpus_dir(
    pan12_dir: Path | None,
    *,
    project_root: Path,
    training_dir: Path,
) -> Path:
    tried: list[str] = []
    candidates: list[Path] = []

    if pan12_dir is None:
        candidates.append((training_dir / PAN12_FOLDER_NAME).resolve())
    else:
        raw = pan12_dir.expanduser()
        if raw.is_absolute():
            candidates.append(raw.resolve())
        candidates.append((project_root / raw).resolve())
        candidates.append((training_dir / raw).resolve())
        candidates.append((training_dir / raw.name).resolve())

    seen: set[Path] = set()
    ordered = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            ordered.append(c)

    for c in ordered:
        tried.append(str(c))
        if c.is_dir():
            xmls = list(c.glob("*.xml")) + list(c.rglob("*.xml"))
            xmls = list(dict.fromkeys(xmls))
            if xmls:
                return c

    hint = (
        "Expected the folder that contains the large ``*.xml`` and "
        "``pan12-sexual-predator-identification-groundtruth-problem1.txt``. "
        f"Default: {training_dir / PAN12_FOLDER_NAME}"
    )
    raise FileNotFoundError(
        "PAN12 corpus folder not found or contains no .xml.\n"
        f"Tried:\n  " + "\n  ".join(tried) + f"\n\n{hint}"
    )


def resolve_pan12_paths(pan12_dir: Path) -> tuple[Path, Path]:
    xml_candidates = list(pan12_dir.glob("*.xml"))
    if not xml_candidates:
        xml_candidates = list(pan12_dir.rglob("*.xml"))
    if not xml_candidates:
        raise FileNotFoundError(f"No .xml under {pan12_dir}")
    xml_path = sorted(xml_candidates, key=lambda p: len(str(p)))[0]
    gt = pan12_dir / "pan12-sexual-predator-identification-groundtruth-problem1.txt"
    if not gt.is_file():
        raise FileNotFoundError(f"Missing Problem 1 ground truth: {gt}")
    return xml_path, gt
