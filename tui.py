#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Input, Label, Static

from ankiconnect_client import ankiconnect
from config import DEFAULT_CLASSES, DEFAULT_VAULT_PATH
from ledger import load_ledger, record_cards_in_ledger, save_ledger
from sync_service import collect_cards, sync_cards

DEFAULT_VAULT = DEFAULT_VAULT_PATH

BANNER = """\
█████╗  ██╗    ██║█╗   ██╗██╗██╗   ██╗███████╗██████╗ ████████╗
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


ORANGE = "#e68200"
YELLOW = "#fff500"
BG = "#121212"
PANEL = "#1a1a1a"
DIM = "#7a4800"


class AnkiVertApp(App):
    CSS = f"""
    Screen {{
        background: {BG};
        color: {ORANGE};
    }}

    #banner {{
        height: 7;
        color: {ORANGE};
        content-align: center middle;
        background: {BG};
        padding: 1 2 0 2;
    }}

    Footer {{
        background: {PANEL};
        color: {ORANGE};
    }}

    Footer > FooterKey {{
        background: {PANEL};
        color: {ORANGE};
    }}

    Footer > FooterKey > .footer-key--key {{
        background: {BG};
        color: {YELLOW};
    }}

    Footer > FooterKey > .footer-key--description {{
        color: {ORANGE};
    }}

    #layout {{
        padding: 1 2;
        height: 1fr;
    }}

    #vault-row {{
        height: 3;
        margin-bottom: 1;
        align: left middle;
    }}

    #vault-label {{
        width: 8;
        content-align: left middle;
        color: {ORANGE};
    }}

    #vault-input {{
        width: 1fr;
        background: {PANEL};
        color: {ORANGE};
        border: tall {ORANGE};
    }}

    #vault-input:focus {{
        border: tall {YELLOW};
    }}

    #btn-edit {{
        margin-left: 1;
        background: {BG};
        color: {ORANGE};
        border: tall {ORANGE};
    }}

    #btn-edit:hover {{
        background: #2a1400;
        color: {YELLOW};
        border: tall {YELLOW};
    }}

    #btn-edit:focus {{
        border: tall {YELLOW};
        color: {YELLOW};
    }}

    #action-row {{
        height: 3;
        margin-bottom: 1;
        align: left middle;
    }}

    #action-row Button {{
        margin-right: 1;
        background: {BG};
        color: {ORANGE};
        border: tall {ORANGE};
    }}

    #action-row Button:hover {{
        background: #2a1400;
        color: {YELLOW};
        border: tall {YELLOW};
    }}

    #action-row Button:focus {{
        border: tall {YELLOW};
        color: {YELLOW};
    }}

    #status {{
        height: 1;
        margin-bottom: 1;
        color: {ORANGE};
    }}

    #anki-status {{
        height: 1;
        margin-bottom: 1;
        color: {DIM};
    }}

    DataTable {{
        height: 1fr;
        background: {BG};
        color: {ORANGE};
    }}

    DataTable > .datatable--header {{
        background: {PANEL};
        color: {YELLOW};
    }}

    DataTable > .datatable--cursor {{
        background: #2a1400;
        color: {YELLOW};
    }}

    DataTable > .datatable--even-row {{
        background: {PANEL};
    }}

    DataTable > .datatable--odd-row {{
        background: {BG};
    }}

    QuitConfirm {{
        align: center middle;
    }}

    #confirm-box {{
        background: {PANEL};
        border: tall {ORANGE};
        padding: 1 2;
        width: 40;
        height: auto;
        align: center middle;
    }}

    #confirm-title {{
        color: {ORANGE};
        content-align: center middle;
        width: 1fr;
        margin-bottom: 1;
    }}

    #confirm-btns {{
        align: center middle;
        height: 3;
    }}

    #confirm-btns Button {{
        margin: 0 1;
        background: {BG};
        color: {ORANGE};
        border: tall {ORANGE};
    }}

    #confirm-btns Button:hover {{
        background: #2a1400;
        color: {YELLOW};
        border: tall {YELLOW};
    }}

    #confirm-yes:focus, #confirm-no:focus {{
        border: tall {YELLOW};
        color: {YELLOW};
    }}
    """

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
            unique_cards, new_cards, md_dups = collect_cards(
                vault, list(DEFAULT_CLASSES), ledger=ledger, verbose=False
            )
            self._populate_table(new_cards)
            self.set_status(
                f"new {len(new_cards)}, synced {len(unique_cards) - len(new_cards)}"
            )
        except Exception as exc:
            self.set_status(f"error: {exc}")

    async def _do_sync(self, vault: Path, dry_run: bool) -> None:
        label = "dry-run" if dry_run else "syncing"
        self.set_status(f"{label}…")
        try:
            ledger = load_ledger()
            _, new_cards, _ = collect_cards(
                vault, list(DEFAULT_CLASSES), ledger=ledger, verbose=False
            )
            result = await sync_cards(new_cards, dry_run=dry_run, verbose=False)
            if not dry_run:
                record_cards_in_ledger(ledger, new_cards, result["note_ids"])
                save_ledger(ledger)
            prefix = "dry-run" if dry_run else "synced"
            self.set_status(f"{prefix}: {result['added']} add")
            await self.check_anki_status()
        except Exception as exc:
            self.set_status(f"error: {exc}")


if __name__ == "__main__":
    AnkiVertApp().run()
