"""Configuration for shield consumption multipliers based on unit type pairings.

This module manages multiplicative adjustments to damage taken by shields based on
the unit type pairing (attacker vs defender). The multiplier applies only to the
shield portion of damage; HP overflow is unchanged.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import threading
from typing import Dict, Mapping

UNIT_TYPES: tuple[str, ...] = ("pikemen", "archers", "infantry")
_KEY_SUFFIX = "shield_consumption"


def _make_default_settings() -> Dict[str, float]:
    """Create default shield consumption multipliers (15% extra damage to shield)."""
    defaults: Dict[str, float] = {}
    for attacker in UNIT_TYPES:
        for defender in UNIT_TYPES:
            key = f"{attacker}_vs_{defender}_{_KEY_SUFFIX}"
            defaults[key] = 1.15
    return defaults


DEFAULT_SETTINGS: Dict[str, float] = _make_default_settings()

_SETTINGS_FILE = Path(__file__).with_name("shield_consumption_settings.json")

_lock = threading.RLock()
_universal_settings: Dict[str, float] | None = None
_session_settings: Dict[str, float] | None = None


class PairingConfigError(ValueError):
    """Raised when invalid values are supplied for the configuration."""


def _validate_key(key: str) -> None:
    """Validate that a key is in the correct format."""
    if not key.endswith("_" + _KEY_SUFFIX):
        raise PairingConfigError(f"Invalid key format: {key}")
    rest = key[: -(len(_KEY_SUFFIX) + 1)]
    parts = rest.split("_vs_")
    if len(parts) != 2:
        raise PairingConfigError(f"Invalid key format: {key}")
    attacker_part, defender_part = parts
    if attacker_part not in UNIT_TYPES:
        raise PairingConfigError(f"Unknown unit type in key: {key}")
    if defender_part not in UNIT_TYPES:
        raise PairingConfigError(f"Unknown opponent type in key: {key}")


def _validate_keys(settings: Mapping[str, float]) -> None:
    """Validate all keys in the settings dictionary."""
    for key in settings:
        if key not in DEFAULT_SETTINGS:
            _validate_key(key)
        else:
            _validate_key(key)


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
            raise PairingConfigError(
                f"Setting '{key}' must be a real number"
            ) from exc
        if not math.isfinite(numeric):
            raise PairingConfigError(f"Setting '{key}' must be finite")
        if numeric < 0.0:
            raise PairingConfigError(f"Setting '{key}' cannot be negative")
        merged[key] = numeric

    return merged


def _load_universal_settings() -> None:
    """Load persisted settings from disk."""
    global _universal_settings
    if not _SETTINGS_FILE.exists():
        _universal_settings = None
        return
    try:
        data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("settings must be stored as an object")
        merged = _coerce_values(data, DEFAULT_SETTINGS)
    except (OSError, json.JSONDecodeError, PairingConfigError, ValueError):
        _universal_settings = None
        return
    _universal_settings = merged


def _ensure_loaded() -> None:
    """Ensure settings are loaded from disk if available."""
    with _lock:
        if _universal_settings is None and _SETTINGS_FILE.exists():
            _load_universal_settings()


def get_settings() -> Dict[str, float]:
    """Return the currently effective shield consumption multipliers."""
    _ensure_loaded()
    with _lock:
        result = dict(DEFAULT_SETTINGS)
        if _universal_settings:
            result.update(_universal_settings)
        if _session_settings:
            result.update(_session_settings)
        return result


def get_multiplier(triggering_unit_type: str, opponent_unit_type: str) -> float:
    """Get the shield consumption multiplier for a specific pairing.

    Args:
        triggering_unit_type: Unit type of the attacker (dealing damage)
        opponent_unit_type: Unit type of the defender (whose shield is hit)

    Returns:
        The multiplier value (e.g. 1.15 = 15% extra damage to shield), or 1.0 if not found
    """
    settings = get_settings()
    key = f"{triggering_unit_type}_vs_{opponent_unit_type}_{_KEY_SUFFIX}"
    return settings.get(key, 1.0)


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
    "DEFAULT_SETTINGS",
    "PairingConfigError",
    "apply_session_settings",
    "clear_session_overrides",
    "get_settings",
    "get_multiplier",
    "reset_to_defaults",
    "save_universal_settings",
]
