from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Card:
    deck: str
    front: str
    back: str
    tags: list[str]
    stable_tag: str  # used for dedupe/update
    source_path: str
