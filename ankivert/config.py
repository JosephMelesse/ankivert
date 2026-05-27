from __future__ import annotations

import json
from pathlib import Path


ANKI_URL = "http://127.0.0.1:8765"
ANKI_CONNECT_VERSION = 6

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = _PROJECT_ROOT / ".ankivert_ledger.json"

_LOCAL_CONFIG_PATH = _PROJECT_ROOT / "local_config.json"


def _load_local_config() -> dict:
    if not _LOCAL_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(_LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


LOCAL_CONFIG = _load_local_config()
DEFAULT_VAULT_PATH: str = LOCAL_CONFIG.get("vault_path", "")
DEFAULT_CLASSES: list[str] | None = LOCAL_CONFIG.get("classes", None)
