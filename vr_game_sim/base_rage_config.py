"""Persistent configuration for per-hero base rage generation.

Stores overrides keyed by hero_preset_id (lowercase). Missing keys use default 100.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

__all__ = [
    "get_base_rage",
    "get_all_overrides",
    "clear_all_overrides",
    "set_overrides",
]

_LOCK = threading.RLock()
_DEFAULT_BASE_RAGE = 100
_SETTINGS_PATH = Path(
    __file__).with_name("base_rage_settings.json")
_overrides: dict[str, int] = {}


def _validate_base_rage(value: Any) -> int:
    """Validate base rage is an integer in valid range (0-200)."""
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Base rage must be an integer") from exc
    if not 0 <= number <= 200:
        raise ValueError("Base rage must be between 0 and 200")
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
    for hero_key, val in data.items():
        if not isinstance(hero_key, str) or not hero_key.strip():
            continue
        try:
            result[hero_key.strip().lower()] = _validate_base_rage(val)
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


def get_base_rage(hero_key: str) -> int:
    """Return the base rage amount for the given hero preset.

    Uses override if present, else 100 (default).
    """
    key = hero_key.strip().lower() if hero_key else ""
    with _LOCK:
        if key and key in _overrides:
            return _overrides[key]
    return _DEFAULT_BASE_RAGE


def get_all_overrides() -> dict[str, int]:
    """Return a copy of all current overrides."""
    with _LOCK:
        return dict(_overrides)


def clear_all_overrides() -> None:
    """Remove all overrides."""
    with _LOCK:
        _overrides.clear()
    _save_to_disk()


def set_overrides(overrides: dict[str, int]) -> None:
    """Replace all overrides with the given dict and persist."""
    validated: dict[str, int] = {}
    for hero_key, val in overrides.items():
        if isinstance(hero_key, str) and hero_key.strip():
            try:
                validated[hero_key.strip().lower()] = _validate_base_rage(val)
            except ValueError:
                pass
    with _LOCK:
        _overrides.clear()
        _overrides.update(validated)
    _save_to_disk()
