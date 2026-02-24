"""Persistent per-troop-type rage trigger thresholds for main hero rage skills."""
from __future__ import annotations

from pathlib import Path
import json
import math
import threading
from typing import Dict, Mapping

UNIT_TYPES: tuple[str, ...] = ("pikemen", "archers", "infantry")
_DEFAULT_THRESHOLD = 1050
DEFAULT_SETTINGS: Dict[str, int] = {unit_type: _DEFAULT_THRESHOLD for unit_type in UNIT_TYPES}

_SETTINGS_FILE = Path(__file__).with_name("rage_threshold_settings.json")

_lock = threading.RLock()
_universal_settings: Dict[str, int] | None = None
_session_settings: Dict[str, int] | None = None


class RageThresholdConfigError(ValueError):
    """Raised when invalid values are supplied for rage thresholds."""


def _coerce_settings(overrides: Mapping[str, int], base: Mapping[str, int]) -> Dict[str, int]:
    merged = dict(base)
    for key, value in overrides.items():
        if key not in UNIT_TYPES:
            raise RageThresholdConfigError(f"Unknown troop type '{key}'")
        try:
            numeric = int(value)
        except (TypeError, ValueError) as exc:
            raise RageThresholdConfigError(f"Threshold for '{key}' must be an integer") from exc
        if not math.isfinite(float(numeric)):
            raise RageThresholdConfigError(f"Threshold for '{key}' must be finite")
        if numeric < 0:
            raise RageThresholdConfigError(f"Threshold for '{key}' cannot be negative")
        merged[key] = numeric
    return merged


def _load_universal_settings() -> None:
    global _universal_settings
    if not _SETTINGS_FILE.exists():
        _universal_settings = None
        return
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings must be stored as an object")
        _universal_settings = _coerce_settings(data, DEFAULT_SETTINGS)
    except (OSError, json.JSONDecodeError, RageThresholdConfigError, ValueError):
        _universal_settings = None


def _ensure_loaded() -> None:
    with _lock:
        if _universal_settings is None and _SETTINGS_FILE.exists():
            _load_universal_settings()


def get_settings() -> Dict[str, int]:
    _ensure_loaded()
    with _lock:
        result = dict(DEFAULT_SETTINGS)
        if _universal_settings:
            result.update(_universal_settings)
        if _session_settings:
            result.update(_session_settings)
        return result


def get_threshold(unit_type: str) -> int:
    return int(get_settings().get(unit_type, _DEFAULT_THRESHOLD))


def apply_session_settings(settings: Mapping[str, int]) -> Dict[str, int]:
    _ensure_loaded()
    with _lock:
        base = _universal_settings or DEFAULT_SETTINGS
        merged = _coerce_settings(settings, base)
        global _session_settings
        _session_settings = dict(merged)
        return dict(_session_settings)


def save_universal_settings(settings: Mapping[str, int]) -> Dict[str, int]:
    merged = _coerce_settings(settings, DEFAULT_SETTINGS)
    with _lock:
        _SETTINGS_FILE.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
        global _universal_settings, _session_settings
        _universal_settings = dict(merged)
        _session_settings = dict(merged)
        return dict(merged)


def reset_to_defaults() -> Dict[str, int]:
    with _lock:
        global _universal_settings, _session_settings
        _session_settings = None
        _universal_settings = None
        try:
            _SETTINGS_FILE.unlink()
        except FileNotFoundError:
            pass
        return dict(DEFAULT_SETTINGS)


__all__ = [
    "UNIT_TYPES",
    "DEFAULT_SETTINGS",
    "RageThresholdConfigError",
    "apply_session_settings",
    "get_settings",
    "get_threshold",
    "reset_to_defaults",
    "save_universal_settings",
]
