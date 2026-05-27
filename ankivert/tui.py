#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Input, Label, Static

from .ankiconnect_client import ankiconnect
from .card_parser import discover_classes
from .config import DEFAULT_CLASSES, DEFAULT_VAULT_PATH
from .ledger import load_ledger, save_ledger
from .sync_service import collect_cards, find_stale_decks, remove_stale_decks, sync_cards

DEFAULT_VAULT = DEFAULT_VAULT_PATH

BANNER = """\
  ███╗  ██╗    ██║██╗  ██╗██╗██╗   ██╗███████╗██████╗ ████████╗
██╔══██╗████╗  ██║██║ ██╔╝██║██║   ██║██╔════╝██╔══██╗╚══██╔══╝
███████║██╔██╗ ██║█████╔╝ ██║██║   ██║█████╗  ██████╔╝   ██║
██╔══██║██║╚██╗██║██╔═██╗ ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗   ██║
██║  ██║██║ ╚████║██║  ██╗██║ ╚████╔╝ ███████╗██║  ██║   ██║
╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝   ╚═╝   \
"""


class QuitConfirm(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static("quit anki_vert?", id="confirm-title")
            with Horizontal(id="confirm-btns"):
                yield Button("yes", id="confirm-yes")
                yield Button("no", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_cancel(self) -> None:
        self.dismiss(False)


class StatusBar(Static):
    def set_status(self, text: str) -> None:
        self.update(f"status: {text}")


class AnkiVertApp(App):
    CSS_PATH = "tui.tcss"

    BINDINGS = [
        Binding("ctrl+c", "confirm_quit", "Quit"),
        Binding("e", "edit_path", "Edit"),
        Binding("s", "scan", "Scan"),
        Binding("y", "sync", "Sync"),
        Binding("d", "dry_run", "Dry-run"),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static(BANNER, id="banner")
        with Vertical(id="layout"):
            with Horizontal(id="vault-row"):
                yield Label("path", id="vault-label")
                yield Input(
                    value=DEFAULT_VAULT, placeholder="vault path", id="vault-input"
                )
                yield Button("edit", id="btn-edit")
            with Horizontal(id="action-row"):
                yield Button("scan", id="btn-scan", variant="default")
                yield Button("sync", id="btn-sync", variant="success")
                yield Button("dry-run", id="btn-dry-run", variant="warning")
            yield StatusBar("status: idle", id="status")
            yield Static("anki: checking…", id="anki-status")
            yield DataTable(id="card-table")
        yield Footer()

    async def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("deck", "front", "back")
        table.focus()
        await self.check_anki_status()
        self.set_interval(3, self.check_anki_status)

    async def check_anki_status(self) -> None:
        anki_label = self.query_one("#anki-status", Static)
        try:
            await ankiconnect("version")
            anki_label.update("anki: online")
        except Exception:
            anki_label.update("anki: offline")

    @property
    def vault_path(self) -> str:
        return self.query_one("#vault-input", Input).value.strip()

    def set_status(self, text: str) -> None:
        self.query_one(StatusBar).set_status(text)

    def _populate_table(self, cards: list) -> None:
        table = self.query_one(DataTable)
        table.clear()
        for c in cards:
            table.add_row(c.deck, c.front, c.back)

    def action_confirm_quit(self) -> None:
        def handle(confirmed: bool) -> None:
            if confirmed:
                self.exit()

        self.push_screen(QuitConfirm(), handle)

    def action_edit_path(self) -> None:
        inp = self.query_one("#vault-input", Input)
        inp.focus()

    def on_key(self, event) -> None:
        inp = self.query_one("#vault-input", Input)
        if event.key == "escape" and inp.has_focus:
            event.stop()
            self.query_one(DataTable).focus()

    async def action_scan(self) -> None:
        await self.on_button_pressed_by_id("btn-scan")

    async def action_sync(self) -> None:
        await self.on_button_pressed_by_id("btn-sync")

    async def action_dry_run(self) -> None:
        await self.on_button_pressed_by_id("btn-dry-run")

    def action_scroll_down(self) -> None:
        self.query_one(DataTable).action_scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one(DataTable).action_scroll_up()

    async def on_button_pressed_by_id(self, button_id: str) -> None:
        vault_str = self.vault_path
        if not vault_str:
            self.set_status("error: vault path is empty")
            return
        vault = Path(vault_str).expanduser().resolve()
        if not vault.exists():
            self.set_status(f"error: path not found: {vault}")
            return

        if button_id == "btn-edit":
            self.action_edit_path()
            return
        if button_id == "btn-scan":
            await self._do_scan(vault)
        elif button_id == "btn-sync":
            await self._do_sync(vault, dry_run=False)
        elif button_id == "btn-dry-run":
            await self._do_sync(vault, dry_run=True)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        await self.on_button_pressed_by_id(event.button.id)

    async def _do_scan(self, vault: Path) -> None:
        self.set_status("scanning…")
        try:
            ledger = load_ledger()
            classes = DEFAULT_CLASSES or discover_classes(vault)
            unique_cards, new_cards, md_dups = collect_cards(
                vault, classes, ledger=ledger, verbose=False
            )
            stale = find_stale_decks(vault, ledger)
            self._populate_table(new_cards)
            ledger_cards = ledger.get("card_index", {})
            add_count = sum(1 for c in new_cards if c.stable_tag not in ledger_cards)
            update_count = len(new_cards) - add_count
            parts = [
                f"add {add_count}",
                f"update {update_count}",
                f"current {len(unique_cards) - len(new_cards)}",
            ]
            if stale:
                parts.append(f"stale {len(stale)}")
            self.set_status(", ".join(parts))
        except Exception as exc:
            self.set_status(f"error: {exc}")

    async def _do_sync(self, vault: Path, dry_run: bool) -> None:
        label = "dry-run" if dry_run else "syncing"
        self.set_status(f"{label}…")
        try:
            ledger = load_ledger()
            classes = DEFAULT_CLASSES or discover_classes(vault)
            _, new_cards, _ = collect_cards(
                vault, classes, ledger=ledger, verbose=False
            )
            if dry_run:
                stale = find_stale_decks(vault, ledger)
                ledger_cards = ledger.get("card_index", {})
                add_count = sum(1 for c in new_cards if c.stable_tag not in ledger_cards)
                update_count = len(new_cards) - add_count
                parts = [f"dry-run: {add_count} add", f"{update_count} update"]
                if stale:
                    parts.append(f"{len(stale)} remove")
                self.set_status(", ".join(parts))
            else:
                stale = await remove_stale_decks(vault, ledger)
                result = await sync_cards(
                    new_cards,
                    dry_run=False,
                    verbose=False,
                    ledger=ledger,
                    save_each=True,
                )
                save_ledger(ledger)
                parts = [
                    f"synced: {result['added']} add",
                    f"{result['updated']} update",
                ]
                if stale:
                    parts.append(f"{len(stale)} removed")
                self.set_status(", ".join(parts))
            await self.check_anki_status()
        except Exception as exc:
            self.set_status(f"error: {exc}")


def main() -> None:
    AnkiVertApp().run()


if __name__ == "__main__":
    main()
