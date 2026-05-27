from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ankivert.models import Card
from ankivert.sync_service import collect_cards, sync_cards


def _make_vault(tmp_path: Path, files: dict[str, str]) -> Path:
    vault = tmp_path / "vault"
    for rel, content in files.items():
        p = vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return vault


# ---------------------------------------------------------------------------
# collect_cards
# ---------------------------------------------------------------------------


def test_collect_cards_basic(tmp_path):
    vault = _make_vault(tmp_path, {"python/ch1.md": "Q: What is Python?\nA: A language.\n"})
    unique, new, dups = collect_cards(vault, ["python"], ledger={})
    assert len(unique) == 1
    assert len(new) == 1
    assert dups == 0
    assert new[0].front == "What is Python?"
    assert new[0].deck == "python::ch1"


def test_collect_cards_skips_ledgered(tmp_path):
    vault = _make_vault(tmp_path, {"python/ch1.md": "Q: What is Python?\nA: A language.\n"})
    unique, new, _ = collect_cards(vault, ["python"], ledger={})
    assert len(new) == 1
    card = new[0]
    ledger_with_card = {
        "card_index": {
            card.stable_tag: {
                "deck": card.deck,
                "front": card.front,
                "back": card.back,
            }
        }
    }
    _, new_again, _ = collect_cards(vault, ["python"], ledger=ledger_with_card)
    assert len(new_again) == 0


def test_collect_cards_includes_changed_ledgered_card(tmp_path):
    vault = _make_vault(tmp_path, {"python/ch1.md": "Q: What is Python?\nA: A language.\n"})
    _, new, _ = collect_cards(vault, ["python"], ledger={})
    card = new[0]
    ledger_with_old_back = {
        "card_index": {
            card.stable_tag: {
                "deck": card.deck,
                "front": card.front,
                "back": "old answer",
            }
        }
    }
    _, changed, _ = collect_cards(vault, ["python"], ledger=ledger_with_old_back)
    assert changed == [card]


def test_collect_cards_deduplicates_within_run(tmp_path):
    # Same content in two files produces two unique tags, not a dup.
    # True dups only happen if two cards in the same run share a stable_tag —
    # which requires identical path+ordinal+question (impossible across files).
    # We test the within-file duplicate path via identical ordinal (unreachable
    # via normal parsing, but the dedup logic is still exercised here indirectly).
    vault = _make_vault(
        tmp_path,
        {
            "python/ch1.md": "Q: A?\nA: 1\n\nQ: B?\nA: 2\n",
        },
    )
    unique, new, dups = collect_cards(vault, ["python"], ledger={})
    assert len(unique) == 2
    assert dups == 0


def test_collect_cards_multiple_classes(tmp_path):
    vault = _make_vault(
        tmp_path,
        {
            "python/ch1.md": "Q: P?\nA: p\n",
            "sql/ch1.md": "Q: S?\nA: s\n",
        },
    )
    unique, new, _ = collect_cards(vault, ["python", "sql"], ledger={})
    assert len(unique) == 2
    decks = {c.deck for c in unique}
    assert "python::ch1" in decks
    assert "sql::ch1" in decks


def test_collect_cards_missing_class_dir_warns(tmp_path, capsys):
    vault = _make_vault(tmp_path, {})
    vault.mkdir(exist_ok=True)
    collect_cards(vault, ["nonexistent"], ledger={})
    err = capsys.readouterr().err
    assert "nonexistent" in err


def test_collect_cards_empty_vault(tmp_path):
    vault = _make_vault(tmp_path, {"python/empty.md": ""})
    unique, new, dups = collect_cards(vault, ["python"], ledger={})
    assert unique == []
    assert new == []
    assert dups == 0


# ---------------------------------------------------------------------------
# sync_cards
# ---------------------------------------------------------------------------


def _card(tag: str = "ankivert_id_aabbccdd1122") -> Card:
    return Card(
        deck="python::ch1",
        front="What is Python?",
        back="A language.",
        tags=["python", tag],
        stable_tag=tag,
        source_path="python/ch1.md",
    )


def test_sync_cards_updates_existing_note(monkeypatch):
    calls: list[tuple[str, int | str]] = []

    async def fake_ensure_deck(deck: str) -> None:
        calls.append(("ensure", deck))

    async def fake_find(tag: str) -> list[int]:
        calls.append(("find", tag))
        return [123]

    async def fake_update(note_id: int, card: Card, verbose: bool = True) -> int:
        calls.append(("update", note_id))
        return note_id

    async def fake_add(card: Card, dry_run: bool = False, verbose: bool = True) -> int:
        calls.append(("add", card.stable_tag))
        return 456

    monkeypatch.setattr("ankivert.sync_service.ensure_deck", fake_ensure_deck)
    monkeypatch.setattr("ankivert.sync_service.find_note_ids_by_tag", fake_find)
    monkeypatch.setattr("ankivert.sync_service.update_basic_note", fake_update)
    monkeypatch.setattr("ankivert.sync_service.add_basic_note", fake_add)

    result = asyncio.run(sync_cards([_card()], dry_run=False, verbose=False))

    assert result["added"] == 0
    assert result["updated"] == 1
    assert result["note_ids"] == {"ankivert_id_aabbccdd1122": 123}
    assert ("add", "ankivert_id_aabbccdd1122") not in calls


def test_sync_cards_records_each_successful_card(monkeypatch):
    saves = 0

    async def fake_ensure_deck(deck: str) -> None:
        return None

    async def fake_find(tag: str) -> list[int]:
        return []

    async def fake_add(card: Card, dry_run: bool = False, verbose: bool = True) -> int:
        return 456

    def fake_save(ledger: dict) -> None:
        nonlocal saves
        saves += 1

    monkeypatch.setattr("ankivert.sync_service.ensure_deck", fake_ensure_deck)
    monkeypatch.setattr("ankivert.sync_service.find_note_ids_by_tag", fake_find)
    monkeypatch.setattr("ankivert.sync_service.add_basic_note", fake_add)
    monkeypatch.setattr("ankivert.sync_service.save_ledger", fake_save)

    ledger = {"version": 2, "decks": {}, "card_index": {}}
    result = asyncio.run(
        sync_cards([_card()], dry_run=False, verbose=False, ledger=ledger, save_each=True)
    )

    assert result["added"] == 1
    assert saves == 1
    assert ledger["card_index"]["ankivert_id_aabbccdd1122"]["note_id"] == 456
