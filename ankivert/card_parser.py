from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Iterable

from .models import Card


def stable_id_tag(vault_root: Path, md_path: Path, question: str, ordinal: int) -> str:
    """
    Create a stable tag for a card so re-running updates instead of duplicating.

    We use:
      - path relative to vault root (stable even if your absolute path changes)
      - question text
      - ordinal within file (handles multiple Q:: in same file)
    """
    rel = md_path.relative_to(vault_root).as_posix()
    raw = f"{rel}||{ordinal}||{question}".encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()  # stable, short enough
    return f"ankivert_id_{digest[:12]}"


def extract_cards_from_markdown( vault_root: Path, md_path: Path, deck: str, base_tags: list[str],) -> list[Card]:
    """
    Card syntax supported:
      Q: <question>
      A: <answer begins>  (answer may continue on subsequent lines)
    """
    text = md_path.read_text(encoding="utf-8", errors="replace")

    cards: list[Card] = []
    q: str | None = None
    a_lines: list[str] = []
    in_answer = False
    ordinal = 0
    last_blank = True  # require a blank line before Q:: (start-of-file counts)

    def finalize_card() -> None:
        nonlocal q, a_lines, in_answer
        if q is not None and a_lines:
            tag = stable_id_tag(vault_root, md_path, q, ordinal)
            cards.append(
                Card(
                    deck=deck,
                    front=q,
                    back="\n".join(a_lines).strip(),
                    tags=base_tags + [tag],
                    stable_tag=tag,
                    source_path=md_path.relative_to(vault_root).as_posix(),
                )
            )
        q = None
        a_lines = []
        in_answer = False

    for raw in text.splitlines():
        line = raw.rstrip("\n")

        if not line.strip():
            if in_answer:
                finalize_card()
            elif q is not None:
                q = None
                a_lines = []
                in_answer = False
            last_blank = True
            continue

        if line.startswith("Q:") and last_blank:
            ordinal += 1
            q = line[len("Q:") :].strip()
            a_lines = []
            in_answer = False
            last_blank = False
            continue

        if line.startswith("A:") and q is not None and not in_answer:
            in_answer = True
            rest = line[len("A:") :].lstrip()
            if rest:
                a_lines.append(rest)
            last_blank = False
            continue

        if in_answer and q is not None:
            a_lines.append(line)
            last_blank = False
            continue

        # Any other non-blank line breaks the current card capture.
        q = None
        a_lines = []
        in_answer = False
        last_blank = False

    if in_answer:
        finalize_card()

    return cards


def discover_classes(vault: Path) -> list[str]:
    if not vault.exists():
        return []
    return sorted(p.name for p in vault.iterdir() if p.is_dir() and not p.name.startswith("."))


def iter_md_files(vault: Path, class_names: list[str]) -> Iterable[tuple[str, Path]]:
    for cls_name in class_names:
        cls_dir = vault / cls_name
        if not cls_dir.exists():
            print(f"[warn] Missing class dir: {cls_dir}", file=sys.stderr)
            continue
        for p in sorted(cls_dir.rglob("*.md")):
            yield cls_name, p


def build_deck_name(vault: Path, class_name: str, md_path: Path) -> str:
    # Deck name: class_chx (chx derived from file name, e.g., ch2.md -> ch2)
    file_stem = md_path.stem
    return f"{class_name}::{file_stem}"
