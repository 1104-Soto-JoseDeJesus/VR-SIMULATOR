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
from typing import Dict, Iterable, Mapping


UNIT_TYPES: tuple[str, ...] = ("pikemen", "archers", "infantry")
TYPE_SPECIFIC_FIELDS: tuple[str, ...] = (
    "combat_base",
    "combat_bonus_multiplier",
    "skill_base",
    "skill_bonus_multiplier",
    "non_mutual_base",
    "non_mutual_bonus_multiplier",
)


def _build_legacy_expansions() -> Dict[str, tuple[str, ...]]:
    expansions: Dict[str, tuple[str, ...]] = {}
    for field in TYPE_SPECIFIC_FIELDS:
        key = field
        expansions[key] = tuple(f"{unit_type}_{field}" for unit_type in UNIT_TYPES)
    return expansions


LEGACY_KEY_EXPANSIONS = _build_legacy_expansions()
_TYPE_MULTIPLIER_KEYS = {f"{unit_type}_multiplier" for unit_type in UNIT_TYPES}


def _make_default_settings() -> Dict[str, float]:
    defaults: Dict[str, float] = {}
    for unit_type in UNIT_TYPES:
        defaults.update(
            {
                f"{unit_type}_combat_base": 0.2,
                f"{unit_type}_combat_bonus_multiplier": 0.35,
                f"{unit_type}_skill_base": 0.2,
                f"{unit_type}_skill_bonus_multiplier": 0.60,
                f"{unit_type}_non_mutual_base": 0.2,
                f"{unit_type}_non_mutual_bonus_multiplier": 0.60,
            }
        )
    return defaults


DEFAULT_SETTINGS: Dict[str, float] = _make_default_settings()

_SETTINGS_FILE = Path(__file__).with_name("dynamic_unrevivable_settings.json")

_lock = threading.RLock()
_universal_settings: Dict[str, float] | None = None
_session_settings: Dict[str, float] | None = None


class DynamicConfigError(ValueError):
    """Raised when invalid values are supplied for the configuration."""


def _validate_keys(settings: Iterable[str]) -> None:
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

    expanded_overrides: Dict[str, float] = {}
    multiplier_adjustments: Dict[str, float] = {}
    for key, value in overrides.items():
        if key in _TYPE_MULTIPLIER_KEYS:
            multiplier_adjustments[key] = value
            continue
        expansion = LEGACY_KEY_EXPANSIONS.get(key)
        if expansion:
            for new_key in expansion:
                expanded_overrides[new_key] = value
        else:
            expanded_overrides[key] = value

    _validate_keys(expanded_overrides)

    merged = dict(base)
    for key, value in expanded_overrides.items():
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

    for key, value in multiplier_adjustments.items():
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
        unit_type = key.split("_", 1)[0]
        for field in TYPE_SPECIFIC_FIELDS:
            merged_key = f"{unit_type}_{field}"
            merged[merged_key] = merged[merged_key] * numeric
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


def get_type_settings(unit_type: str, settings: Mapping[str, float] | None = None) -> Dict[str, float]:
    """Return the coefficients relevant for the provided ``unit_type`` attacker."""

    normalized = (unit_type or "").lower()
    if normalized not in UNIT_TYPES:
        normalized = UNIT_TYPES[0]
    active = settings or get_settings()
    return {
        field: active[f"{normalized}_{field}"]
        for field in TYPE_SPECIFIC_FIELDS
    }


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
    "UNIT_TYPES",
    "TYPE_SPECIFIC_FIELDS",
    "DEFAULT_SETTINGS",
    "DynamicConfigError",
    "apply_session_settings",
    "clear_session_overrides",
    "get_settings",
    "get_type_settings",
    "reset_to_defaults",
    "save_universal_settings",
]
