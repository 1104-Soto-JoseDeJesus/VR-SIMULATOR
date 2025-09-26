"""Helpers for dynamic unrevivable ratio configuration.

The simulator previously relied on hard-coded coefficients when converting combat
and skill losses into unrevivable troop counts.  This module exposes a thin
configuration layer that allows those coefficients to be tweaked at runtime and
optionally persisted to disk.  Callers can fetch the current effective settings
with :func:`get_settings`, apply temporary session overrides with
:func:`apply_session_settings`, save universal (persisted) settings via
:func:`save_universal_settings`, or revert back to the baked-in defaults through
:func:`reset_to_defaults`.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import threading
from typing import Dict, Mapping


DEFAULT_SETTINGS: Dict[str, float] = {
    "combat_base": 0.2,
    "combat_bonus_multiplier": 0.35,
    "skill_base": 0.2,
    "skill_bonus_multiplier": 0.60,
    "non_mutual_base": 0.2,
    "non_mutual_bonus_multiplier": 0.60,
    "pikemen_multiplier": 1.0,
    "archers_multiplier": 1.0,
    "infantry_multiplier": 1.0,
}

_SETTINGS_FILE = Path(__file__).with_name("dynamic_unrevivable_settings.json")

_lock = threading.RLock()
_universal_settings: Dict[str, float] | None = None
_session_settings: Dict[str, float] | None = None


class DynamicConfigError(ValueError):
    """Raised when invalid values are supplied for the configuration."""


def _validate_keys(settings: Mapping[str, float]) -> None:
    unknown = set(settings) - set(DEFAULT_SETTINGS)
    if unknown:
        raise DynamicConfigError(
            f"Unknown dynamic unrevivable setting(s): {', '.join(sorted(unknown))}"
        )


def _coerce_values(
    overrides: Mapping[str, float],
    base: Mapping[str, float],
) -> Dict[str, float]:
    """Return ``base`` merged with ``overrides`` after validating values."""

    _validate_keys(overrides)
    merged = dict(base)
    for key, value in overrides.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise DynamicConfigError(
                f"Setting '{key}' must be a real number"
            ) from exc
        if not math.isfinite(numeric):
            raise DynamicConfigError(f"Setting '{key}' must be finite")
        if numeric < 0.0:
            raise DynamicConfigError(f"Setting '{key}' cannot be negative")
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
        merged = _coerce_values(data, DEFAULT_SETTINGS)
    except (OSError, json.JSONDecodeError, DynamicConfigError, ValueError):
        _universal_settings = None
        return
    _universal_settings = merged


def _ensure_loaded() -> None:
    with _lock:
        if _universal_settings is None and _SETTINGS_FILE.exists():
            _load_universal_settings()


def get_settings() -> Dict[str, float]:
    """Return the currently effective dynamic unrevivable coefficients."""

    _ensure_loaded()
    with _lock:
        result = dict(DEFAULT_SETTINGS)
        if _universal_settings:
            result.update(_universal_settings)
        if _session_settings:
            result.update(_session_settings)
        return result


def apply_session_settings(settings: Mapping[str, float]) -> Dict[str, float]:
    """Apply non-persisted overrides for the current Python session."""

    _ensure_loaded()
    with _lock:
        base = _universal_settings or DEFAULT_SETTINGS
        merged = _coerce_values(settings, base)
        global _session_settings
        _session_settings = dict(merged)
        return dict(_session_settings)


def save_universal_settings(settings: Mapping[str, float]) -> Dict[str, float]:
    """Persist overrides to disk and apply them for the current session."""

    merged = _coerce_values(settings, DEFAULT_SETTINGS)
    with _lock:
        _SETTINGS_FILE.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
        global _universal_settings, _session_settings
        _universal_settings = dict(merged)
        _session_settings = dict(merged)
        return dict(merged)


def clear_session_overrides() -> None:
    """Clear non-persisted overrides without touching saved settings."""

    with _lock:
        global _session_settings
        _session_settings = None


def reset_to_defaults() -> Dict[str, float]:
    """Remove persisted settings and clear any in-memory overrides."""

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
    "DEFAULT_SETTINGS",
    "DynamicConfigError",
    "apply_session_settings",
    "clear_session_overrides",
    "get_settings",
    "reset_to_defaults",
    "save_universal_settings",
]
