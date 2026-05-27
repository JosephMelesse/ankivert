from __future__ import annotations

import json
from pathlib import Path

import pytest

from ankivert.ledger import load_ledger, record_cards_in_ledger, save_ledger
from ankivert.models import Card


def _card(front: str = "Q?", back: str = "A", deck: str = "deck", tag: str = "ankivert_id_aabbccdd1122") -> Card:
    return Card(deck=deck, front=front, back=back, tags=[tag], stable_tag=tag, source_path="notes.md")


# ---------------------------------------------------------------------------
# load_ledger
# ---------------------------------------------------------------------------


def test_load_ledger_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("ankivert.ledger.LEDGER_PATH", tmp_path / "no_ledger.json")
    data = load_ledger()
    assert data == {"version": 2, "decks": {}, "card_index": {}}


def test_load_ledger_invalid_json(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setattr("ankivert.ledger.LEDGER_PATH", path)
    data = load_ledger()
    assert data == {"version": 2, "decks": {}, "card_index": {}}


def test_load_ledger_non_dict_json(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setattr("ankivert.ledger.LEDGER_PATH", path)
    data = load_ledger()
    assert data == {"version": 2, "decks": {}, "card_index": {}}


def test_load_ledger_v1_migration(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    v1 = {
        "cards": {
            "ankivert_id_abc123": {
                "deck": "python::ch1",
                "front": "What is a list?",
                "back": "A mutable sequence.",
                "source_path": "python/ch1.md",
                "created_at": "2025-01-01T00:00:00+00:00",
                "note_id": 42,
            }
        }
    }
    path.write_text(json.dumps(v1), encoding="utf-8")
    monkeypatch.setattr("ankivert.ledger.LEDGER_PATH", path)
    data = load_ledger()
    assert "card_index" in data
    assert "ankivert_id_abc123" in data["card_index"]
    assert data["card_index"]["ankivert_id_abc123"]["front"] == "What is a list?"
    assert "python::ch1" in data["decks"]


def test_load_ledger_v2_round_trip(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    v2 = {
        "version": 2,
        "decks": {"d": {"cards": []}},
        "card_index": {"tag1": {"deck": "d", "front": "F", "back": "B", "source_path": "", "created_at": "", "note_id": 1}},
    }
    path.write_text(json.dumps(v2), encoding="utf-8")
    monkeypatch.setattr("ankivert.ledger.LEDGER_PATH", path)
    data = load_ledger()
    assert data["version"] == 2
    assert "tag1" in data["card_index"]


# ---------------------------------------------------------------------------
# save_ledger / round-trip
# ---------------------------------------------------------------------------


def test_save_and_reload(tmp_path, monkeypatch):
    path = tmp_path / "ledger.json"
    monkeypatch.setattr("ankivert.ledger.LEDGER_PATH", path)
    original = {"version": 2, "decks": {}, "card_index": {"t": {"deck": "d"}}}
    save_ledger(original)
    assert json.loads(path.read_text()) == original
    loaded = load_ledger()
    assert loaded["card_index"]["t"]["deck"] == "d"


# ---------------------------------------------------------------------------
# record_cards_in_ledger
# ---------------------------------------------------------------------------


def test_record_cards_adds_to_index(tmp_path):
    ledger = {"version": 2, "decks": {}, "card_index": {}}
    card = _card()
    record_cards_in_ledger(ledger, [card], {card.stable_tag: 99})
    assert card.stable_tag in ledger["card_index"]
    entry = ledger["card_index"][card.stable_tag]
    assert entry["note_id"] == 99
    assert entry["front"] == card.front
    assert entry["deck"] == card.deck


def test_record_cards_creates_deck_entry(tmp_path):
    ledger = {"version": 2, "decks": {}, "card_index": {}}
    card = _card(deck="sql::joins")
    record_cards_in_ledger(ledger, [card], {})
    assert "sql::joins" in ledger["decks"]
    assert ledger["decks"]["sql::joins"]["cards"][0]["front"] == card.front


def test_record_cards_note_id_none_when_missing(tmp_path):
    ledger = {"version": 2, "decks": {}, "card_index": {}}
    card = _card()
    record_cards_in_ledger(ledger, [card], {})
    assert ledger["card_index"][card.stable_tag]["note_id"] is None


def test_record_cards_replaces_existing_deck_entry(tmp_path):
    ledger = {"version": 2, "decks": {}, "card_index": {}}
    original = _card(back="old")
    changed = _card(back="new")
    record_cards_in_ledger(ledger, [original], {original.stable_tag: 99})
    record_cards_in_ledger(ledger, [changed], {changed.stable_tag: 99})

    assert ledger["card_index"][changed.stable_tag]["back"] == "new"
    assert ledger["decks"][changed.deck]["cards"] == [
        {"front": changed.front, "back": "new", "stable_tag": changed.stable_tag}
    ]
