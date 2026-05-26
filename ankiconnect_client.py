from __future__ import annotations

import httpx

from config import ANKI_CONNECT_VERSION, ANKI_URL
from models import Card


async def ankiconnect(action: str, params: dict | None = None):
    payload = {
        "action": action,
        "version": ANKI_CONNECT_VERSION,
        "params": params or {},
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(ANKI_URL, json=payload, timeout=10.0)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"AnkiConnect error for {action}: {data['error']}")
    return data.get("result")


async def ensure_deck(deck_name: str) -> None:
    await ankiconnect("createDeck", {"deck": deck_name})


async def add_basic_note(card: Card, dry_run: bool = False, verbose: bool = True) -> int | None:
    if dry_run:
        if verbose:
            print(f"[dry-run] addNote -> {card.deck} [{card.stable_tag}] {card.front[:60]!r}")
        return None

    result = await ankiconnect(
        "addNote",
        {
            "note": {
                "deckName": card.deck,
                "modelName": "Basic",
                "fields": {"Front": card.front, "Back": card.back},
                "tags": card.tags,
            }
        },
    )
    if verbose:
        print(f"[add] note_id={result} deck={card.deck} tag={card.stable_tag}")
    return int(result) if result is not None else None
