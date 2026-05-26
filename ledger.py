from __future__ import annotations

import json
from datetime import datetime, timezone

from config import LEDGER_PATH
from models import Card


def load_ledger() -> dict:
    if not LEDGER_PATH.exists():
        return {"version": 2, "decks": {}, "card_index": {}}
    try:
        data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 2, "decks": {}, "card_index": {}}
    if not isinstance(data, dict):
        return {"version": 2, "decks": {}, "card_index": {}}
    if "cards" in data and "card_index" not in data:
        migrated = {"version": 2, "decks": {}, "card_index": {}}
        cards = data.get("cards", {})
        if isinstance(cards, dict):
            for stable_tag, info in cards.items():
                if not isinstance(info, dict):
                    continue
                deck = info.get("deck", "unknown")
                front = info.get("front", "")
                back = info.get("back", "")
                migrated["card_index"][stable_tag] = {
                    "deck": deck,
                    "front": front,
                    "back": back,
                    "source_path": info.get("source_path", ""),
                    "created_at": info.get("created_at", ""),
                    "note_id": info.get("note_id"),
                }
                migrated["decks"].setdefault(deck, {"cards": []})
                migrated["decks"][deck]["cards"].append(
                    {"front": front, "back": back}
                )
        return migrated
    data.setdefault("version", 2)
    data.setdefault("decks", {})
    data.setdefault("card_index", {})
    if not isinstance(data["decks"], dict):
        data["decks"] = {}
    if not isinstance(data["card_index"], dict):
        data["card_index"] = {}
    return data


def save_ledger(data: dict) -> None:
    LEDGER_PATH.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def record_cards_in_ledger( ledger: dict, cards: list[Card], note_ids: dict[str, int]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for card in cards:
        ledger["card_index"][card.stable_tag] = {
            "deck": card.deck,
            "front": card.front,
            "back": card.back,
            "source_path": card.source_path,
            "created_at": now,
            "note_id": note_ids.get(card.stable_tag),
        }
        ledger["decks"].setdefault(card.deck, {"cards": []})
        ledger["decks"][card.deck]["cards"].append(
            {"front": card.front, "back": card.back}
        )
