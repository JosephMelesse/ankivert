from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from card_parser import (
    build_deck_name,
    discover_classes,
    extract_cards_from_markdown,
    iter_md_files,
    stable_id_tag,
)


# ---------------------------------------------------------------------------
# stable_id_tag
# ---------------------------------------------------------------------------


def test_stable_id_tag_format(tmp_path):
    vault = tmp_path / "vault"
    md = vault / "notes.md"
    tag = stable_id_tag(vault, md, "What is Python?", 1)
    assert tag.startswith("ankivert_id_")
    assert len(tag) == len("ankivert_id_") + 12


def test_stable_id_tag_deterministic(tmp_path):
    vault = tmp_path / "vault"
    md = vault / "notes.md"
    t1 = stable_id_tag(vault, md, "What is Python?", 1)
    t2 = stable_id_tag(vault, md, "What is Python?", 1)
    assert t1 == t2


def test_stable_id_tag_different_question(tmp_path):
    vault = tmp_path / "vault"
    md = vault / "notes.md"
    assert stable_id_tag(vault, md, "Q1", 1) != stable_id_tag(vault, md, "Q2", 1)


def test_stable_id_tag_different_ordinal(tmp_path):
    vault = tmp_path / "vault"
    md = vault / "notes.md"
    assert stable_id_tag(vault, md, "Same?", 1) != stable_id_tag(vault, md, "Same?", 2)


def test_stable_id_tag_different_path(tmp_path):
    vault = tmp_path / "vault"
    md1 = vault / "a.md"
    md2 = vault / "b.md"
    assert stable_id_tag(vault, md1, "Q?", 1) != stable_id_tag(vault, md2, "Q?", 1)


# ---------------------------------------------------------------------------
# build_deck_name
# ---------------------------------------------------------------------------


def test_build_deck_name(tmp_path):
    vault = tmp_path / "vault"
    md = vault / "python" / "ch2.md"
    assert build_deck_name(vault, "python", md) == "python::ch2"


def test_build_deck_name_nested(tmp_path):
    vault = tmp_path / "vault"
    md = vault / "sql" / "week1" / "joins.md"
    assert build_deck_name(vault, "sql", md) == "sql::joins"


# ---------------------------------------------------------------------------
# extract_cards_from_markdown
# ---------------------------------------------------------------------------


def _write(tmp_path, content: str) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    vault.mkdir()
    md = vault / "notes.md"
    md.write_text(content, encoding="utf-8")
    return vault, md


def test_basic_card(tmp_path):
    vault, md = _write(tmp_path, "Q: What is 2+2?\nA: 4\n")
    cards = extract_cards_from_markdown(vault, md, "math", [])
    assert len(cards) == 1
    assert cards[0].front == "What is 2+2?"
    assert cards[0].back == "4"
    assert cards[0].deck == "math"


def test_multiline_answer(tmp_path):
    vault, md = _write(tmp_path, "Q: Explain TCP\nA: Connection-oriented\nReliable\nOrdered\n")
    cards = extract_cards_from_markdown(vault, md, "net", [])
    assert len(cards) == 1
    assert "Connection-oriented" in cards[0].back
    assert "Reliable" in cards[0].back
    assert "Ordered" in cards[0].back


def test_multiple_cards(tmp_path):
    vault, md = _write(
        tmp_path,
        "Q: Q1\nA: A1\n\nQ: Q2\nA: A2\n",
    )
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert len(cards) == 2
    assert cards[0].front == "Q1"
    assert cards[1].front == "Q2"


def test_answer_terminated_by_blank_line(tmp_path):
    vault, md = _write(tmp_path, "Q: Q1\nA: answer\n\nsome other text\n")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert len(cards) == 1
    assert cards[0].back == "answer"


def test_end_of_file_finalizes_card(tmp_path):
    vault, md = _write(tmp_path, "Q: Q1\nA: answer")  # no trailing newline
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert len(cards) == 1


def test_q_without_preceding_blank_not_parsed(tmp_path):
    # Q: must be preceded by a blank line (or start of file)
    vault, md = _write(tmp_path, "some text\nQ: Hidden\nA: answer\n")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert len(cards) == 0


def test_q_at_start_of_file_is_valid(tmp_path):
    vault, md = _write(tmp_path, "Q: First\nA: yes\n")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert len(cards) == 1


def test_q_without_answer_skipped(tmp_path):
    vault, md = _write(tmp_path, "Q: No answer\n\nQ: Has answer\nA: yes\n")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert len(cards) == 1
    assert cards[0].front == "Has answer"


def test_base_tags_included(tmp_path):
    vault, md = _write(tmp_path, "Q: Q?\nA: A\n")
    cards = extract_cards_from_markdown(vault, md, "deck", ["python", "su26"])
    assert "python" in cards[0].tags
    assert "su26" in cards[0].tags


def test_stable_tag_in_tags(tmp_path):
    vault, md = _write(tmp_path, "Q: Q?\nA: A\n")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert cards[0].stable_tag in cards[0].tags
    assert cards[0].stable_tag.startswith("ankivert_id_")


def test_source_path_is_relative(tmp_path):
    vault, md = _write(tmp_path, "Q: Q?\nA: A\n")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert not Path(cards[0].source_path).is_absolute()


def test_empty_file(tmp_path):
    vault, md = _write(tmp_path, "")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert cards == []


def test_no_cards_in_plain_text(tmp_path):
    vault, md = _write(tmp_path, "Just some notes\nwith no flashcard syntax\n")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert cards == []


def test_interleaved_text_breaks_card(tmp_path):
    # Non-blank, non-A: line after Q: resets parsing
    vault, md = _write(tmp_path, "Q: Question\nsome prose\nA: answer\n")
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert len(cards) == 0


def test_ordinal_makes_duplicate_questions_unique(tmp_path):
    vault, md = _write(
        tmp_path, "Q: Same?\nA: first\n\nQ: Same?\nA: second\n"
    )
    cards = extract_cards_from_markdown(vault, md, "deck", [])
    assert len(cards) == 2
    assert cards[0].stable_tag != cards[1].stable_tag


# ---------------------------------------------------------------------------
# iter_md_files
# ---------------------------------------------------------------------------


def test_iter_md_files_yields_correct_pairs(tmp_path):
    vault = tmp_path / "vault"
    cls_dir = vault / "python"
    cls_dir.mkdir(parents=True)
    (cls_dir / "ch1.md").write_text("content")
    (cls_dir / "ch2.md").write_text("content")

    results = list(iter_md_files(vault, ["python"]))
    class_names = [r[0] for r in results]
    paths = [r[1] for r in results]

    assert all(c == "python" for c in class_names)
    assert len(paths) == 2
    assert all(p.suffix == ".md" for p in paths)


def test_iter_md_files_warns_on_missing_dir(tmp_path, capsys):
    vault = tmp_path / "vault"
    vault.mkdir()
    list(iter_md_files(vault, ["nonexistent"]))
    err = capsys.readouterr().err
    assert "nonexistent" in err


# ---------------------------------------------------------------------------
# discover_classes
# ---------------------------------------------------------------------------


def test_discover_classes_returns_subdirs(tmp_path):
    vault = tmp_path / "vault"
    (vault / "python").mkdir(parents=True)
    (vault / "sql").mkdir()
    (vault / "notes.md").write_text("content")
    assert discover_classes(vault) == ["python", "sql"]


def test_discover_classes_excludes_hidden(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "python").mkdir()
    (vault / ".obsidian").mkdir()
    (vault / ".git").mkdir()
    assert discover_classes(vault) == ["python"]


def test_discover_classes_sorted(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    for name in ["zzz", "aaa", "mmm"]:
        (vault / name).mkdir()
    assert discover_classes(vault) == ["aaa", "mmm", "zzz"]


def test_discover_classes_missing_vault(tmp_path):
    assert discover_classes(tmp_path / "nonexistent") == []


def test_iter_md_files_recurses(tmp_path):
    vault = tmp_path / "vault"
    nested = vault / "sql" / "week1"
    nested.mkdir(parents=True)
    (nested / "joins.md").write_text("content")

    results = list(iter_md_files(vault, ["sql"]))
    assert len(results) == 1
    assert results[0][1].name == "joins.md"
