"""Persistent configuration for per-troop-type base rage gain on basic attack.

Stores overrides keyed by unit_type (pikemen, archers, infantry). Missing keys
use default 100. Used when an army performs a basic attack to grant rage.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

__all__ = [
    "get_base_rage",
    "get_all_overrides",
    "save_overrides",
    "UNIT_TYPES",
    "DEFAULT_BASE_RAGE",
]

UNIT_TYPES: tuple[str, ...] = ("pikemen", "archers", "infantry")
DEFAULT_BASE_RAGE = 100
_MIN_RAGE = 0
_MAX_RAGE = 200

_LOCK = threading.RLock()
_SETTINGS_PATH = Path(__file__).with_name("rage_gain_per_troop_settings.json")
_overrides: dict[str, int] = {}


def _validate_base_rage(value: Any) -> int:
    """Validate base rage is an integer in valid range (0-200)."""
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Base rage must be an integer") from exc
    if not _MIN_RAGE <= number <= _MAX_RAGE:
        raise ValueError(f"Base rage must be between {_MIN_RAGE} and {_MAX_RAGE}")
    return number


def _load_from_disk() -> dict[str, int]:
    if not _SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, int] = {}
    for key, val in data.items():
        if not isinstance(key, str) or key.strip().lower() not in UNIT_TYPES:
            continue
        try:
            result[key.strip().lower()] = _validate_base_rage(val)
        except ValueError:
            continue
    return result


def _save_to_disk() -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        payload = dict(_overrides)
    _SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


with _LOCK:
    _overrides = _load_from_disk()


def get_base_rage(unit_type: str) -> int:
    """Return the base rage amount for the given troop type on basic attack.

    Uses override if present, else 100 (default).
    """
    key = unit_type.strip().lower() if unit_type else ""
    with _LOCK:
        if key and key in _overrides:
            return _overrides[key]
    return DEFAULT_BASE_RAGE


def get_all_overrides() -> dict[str, int]:
    """Return a copy of all current overrides."""
    with _LOCK:
        return dict(_overrides)


def save_overrides(overrides: dict[str, int]) -> None:
    """Replace all overrides with the given dict and persist to disk."""
    validated: dict[str, int] = {}
    for key, val in overrides.items():
        if isinstance(key, str) and key.strip().lower() in UNIT_TYPES:
            try:
                validated[key.strip().lower()] = _validate_base_rage(val)
            except ValueError:
                pass
    with _LOCK:
        _overrides.clear()
        _overrides.update(validated)
    _save_to_disk()
