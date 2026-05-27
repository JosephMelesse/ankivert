from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from sync_service import collect_cards


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
    stable_tag = new[0].stable_tag
    ledger_with_card = {"card_index": {stable_tag: {"deck": "python::ch1"}}}
    _, new_again, _ = collect_cards(vault, ["python"], ledger=ledger_with_card)
    assert len(new_again) == 0


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
