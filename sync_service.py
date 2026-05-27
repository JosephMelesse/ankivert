from __future__ import annotations

from pathlib import Path

from ankiconnect_client import (
    add_basic_note,
    delete_decks,
    ensure_deck,
    find_note_ids_by_tag,
    update_basic_note,
)
from card_parser import (
    build_deck_name,
    discover_classes,
    extract_cards_from_markdown,
    iter_md_files,
)
from ledger import record_cards_in_ledger, save_ledger
from models import Card


def collect_cards(
    vault: Path, classes: list[str], ledger: dict, verbose: bool = False
) -> tuple[list[Card], list[Card], int]:
    """
    Returns (unique_cards, sync_cards, markdown_dup_count).

    unique_cards    — all cards found in the vault, deduplicated by stable_tag
    sync_cards      — subset of unique_cards that are missing from the ledger
                      or differ from the ledger's recorded fields
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
    new_cards = [
        c for c in unique_cards
        if _needs_sync(c, ledger_cards.get(c.stable_tag, {}))
    ]

    if verbose and new_cards:
        for c in new_cards:
            print(f"  - {c.front[:70]!r}  [{c.stable_tag}]")

    return unique_cards, new_cards, markdown_dup_count


def _needs_sync(card: Card, ledger_entry: dict) -> bool:
    return (
        not ledger_entry
        or ledger_entry.get("deck") != card.deck
        or ledger_entry.get("front") != card.front
        or ledger_entry.get("back") != card.back
    )


def find_stale_decks(vault: Path, ledger: dict) -> list[str]:
    """Return deck names in the ledger whose top-level class dir no longer exists."""
    current_classes = set(discover_classes(vault))
    return [
        deck for deck in ledger.get("decks", {})
        if deck.split("::")[0] not in current_classes
    ]


async def remove_stale_decks(vault: Path, ledger: dict) -> list[str]:
    """Delete stale decks from Anki and clean them from the ledger. Returns removed deck names."""
    stale = find_stale_decks(vault, ledger)
    if not stale:
        return []
    await delete_decks(stale)
    stale_set = set(stale)
    for deck in stale:
        del ledger["decks"][deck]
    ledger["card_index"] = {
        tag: info for tag, info in ledger["card_index"].items()
        if info.get("deck") not in stale_set
    }
    return stale


async def sync_cards(
    cards: list[Card],
    dry_run: bool = False,
    verbose: bool = True,
    ledger: dict | None = None,
    save_each: bool = False,
) -> dict:
    decks = sorted({c.deck for c in cards})
    if not dry_run:
        for d in decks:
            await ensure_deck(d)
    note_ids: dict[str, int] = {}
    added = 0
    updated = 0
    for c in cards:
        existing_note_ids = [] if dry_run else await find_note_ids_by_tag(c.stable_tag)
        if existing_note_ids:
            note_id = await update_basic_note(existing_note_ids[0], c, verbose=verbose)
            updated += 1
        else:
            note_id = await add_basic_note(c, dry_run=dry_run, verbose=verbose)
            added += 1
        if note_id is not None:
            note_ids[c.stable_tag] = note_id
            if ledger is not None:
                record_cards_in_ledger(ledger, [c], {c.stable_tag: note_id})
                if save_each:
                    save_ledger(ledger)
    if dry_run:
        added = len(cards)
    return {"added": added, "updated": updated, "decks": decks, "note_ids": note_ids}
