from __future__ import annotations

from pathlib import Path

from ankiconnect_client import add_basic_note, ensure_deck
from card_parser import build_deck_name, extract_cards_from_markdown, iter_md_files
from models import Card


def collect_cards(
    vault: Path, classes: list[str], ledger: dict, verbose: bool = False
) -> tuple[list[Card], list[Card], int]:
    """
    Returns (unique_cards, new_cards, markdown_dup_count).

    unique_cards    — all cards found in the vault, deduplicated by stable_tag
    new_cards       — subset of unique_cards not yet recorded in the ledger
    markdown_dup_count — cards skipped because a prior card in the same run
                         shared the same stable_tag (true markdown duplicates)
    """
    all_cards: list[Card] = []
    for cls_name, md_path in iter_md_files(vault, classes):
        deck = build_deck_name(vault, cls_name, md_path)
        base_tags = [cls_name, vault.name]
        cards = extract_cards_from_markdown(vault, md_path, deck, base_tags)
        if verbose and cards:
            rel = md_path.relative_to(vault).as_posix()
            print(f"\n{deck} :: {rel}  -> {len(cards)} card(s)")
        all_cards.extend(cards)

    seen: dict[str, Card] = {}
    markdown_dup_count = 0
    for card in all_cards:
        if card.stable_tag in seen:
            markdown_dup_count += 1
        else:
            seen[card.stable_tag] = card
    unique_cards = list(seen.values())

    ledger_cards = ledger.get("card_index", {})
    new_cards = [c for c in unique_cards if c.stable_tag not in ledger_cards]

    if verbose and new_cards:
        for c in new_cards:
            print(f"  - {c.front[:70]!r}  [{c.stable_tag}]")

    return unique_cards, new_cards, markdown_dup_count


async def sync_cards(cards: list[Card], dry_run: bool = False, verbose: bool = True) -> dict:
    decks = sorted({c.deck for c in cards})
    if not dry_run:
        for d in decks:
            await ensure_deck(d)
    note_ids: dict[str, int] = {}
    for c in cards:
        note_id = await add_basic_note(c, dry_run=dry_run, verbose=verbose)
        if note_id is not None:
            note_ids[c.stable_tag] = note_id
    # dry_run: report how many would be added; live: count only confirmed note_ids
    added = len(cards) if dry_run else len(note_ids)
    return {"added": added, "decks": decks, "note_ids": note_ids}
