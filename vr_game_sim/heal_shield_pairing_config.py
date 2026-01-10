"""Configuration for heal and shield multipliers based on unit type pairings.

This module manages multiplicative adjustments to heal and shield values based on
the unit type pairing (e.g., pike vs infantry, infantry vs archer). These multipliers
are applied after all other boosts and reductions.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import threading
from typing import Dict, Mapping

UNIT_TYPES: tuple[str, ...] = ("pikemen", "archers", "infantry")
EFFECT_TYPES: tuple[str, ...] = ("heal", "shield")


def _make_default_settings() -> Dict[str, float]:
    """Create default heal/shield pairing multipliers."""
    defaults: Dict[str, float] = {}
    
    # Heals
    defaults["pikemen_vs_pikemen_heal"] = 1.0
    defaults["infantry_vs_infantry_heal"] = 1.0
    defaults["archers_vs_archers_heal"] = 1.0
    defaults["pikemen_vs_infantry_heal"] = 0.803
    defaults["infantry_vs_pikemen_heal"] = 1.243
    defaults["pikemen_vs_archers_heal"] = 0.82
    defaults["archers_vs_pikemen_heal"] = 1.21
    defaults["infantry_vs_archers_heal"] = 1.19
    defaults["archers_vs_infantry_heal"] = 0.84
    
    # Shields
    defaults["pikemen_vs_pikemen_shield"] = 1.161
    defaults["infantry_vs_infantry_shield"] = 0.886
    defaults["archers_vs_archers_shield"] = 1.0
    defaults["pikemen_vs_infantry_shield"] = 0.932
    defaults["infantry_vs_pikemen_shield"] = 1.103
    defaults["pikemen_vs_archers_shield"] = 0.955
    defaults["archers_vs_pikemen_shield"] = 1.218
    defaults["infantry_vs_archers_shield"] = 1.055
    defaults["archers_vs_infantry_shield"] = 0.843
    
    return defaults


DEFAULT_SETTINGS: Dict[str, float] = _make_default_settings()

_SETTINGS_FILE = Path(__file__).with_name("heal_shield_pairing_settings.json")

_lock = threading.RLock()
_universal_settings: Dict[str, float] | None = None
_session_settings: Dict[str, float] | None = None


class PairingConfigError(ValueError):
    """Raised when invalid values are supplied for the configuration."""


def _validate_key(key: str) -> None:
    """Validate that a key is in the correct format."""
    parts = key.split("_vs_")
    if len(parts) != 2:
        raise PairingConfigError(f"Invalid key format: {key}")
    
    triggering_part, rest = parts
    if triggering_part not in UNIT_TYPES:
        raise PairingConfigError(f"Unknown unit type in key: {key}")
    
    opponent_and_effect = rest.rsplit("_", 1)
    if len(opponent_and_effect) != 2:
        raise PairingConfigError(f"Invalid key format: {key}")
    
    opponent_type, effect_type = opponent_and_effect
    if opponent_type not in UNIT_TYPES:
        raise PairingConfigError(f"Unknown opponent type in key: {key}")
    if effect_type not in EFFECT_TYPES:
        raise PairingConfigError(f"Unknown effect type in key: {key}")


def _validate_keys(settings: Mapping[str, float]) -> None:
    """Validate all keys in the settings dictionary."""
    for key in settings:
        if key not in DEFAULT_SETTINGS:
            _validate_key(key)  # Will raise if invalid
            # If validation passes but key not in defaults, add it
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
    """Return the currently effective heal/shield pairing multipliers."""
    _ensure_loaded()
    with _lock:
        result = dict(DEFAULT_SETTINGS)
        if _universal_settings:
            result.update(_universal_settings)
        if _session_settings:
            result.update(_session_settings)
        return result


def get_multiplier(triggering_unit_type: str, opponent_unit_type: str, effect_type: str) -> float:
    """Get the multiplier for a specific pairing.
    
    Args:
        triggering_unit_type: Unit type of the army triggering the effect
        opponent_unit_type: Unit type of the opponent army
        effect_type: Either "heal" or "shield"
    
    Returns:
        The multiplier value, or 1.0 if not found
    """
    settings = get_settings()
    key = f"{triggering_unit_type}_vs_{opponent_unit_type}_{effect_type}"
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
    "EFFECT_TYPES",
    "DEFAULT_SETTINGS",
    "PairingConfigError",
    "apply_session_settings",
    "clear_session_overrides",
    "get_settings",
    "get_multiplier",
    "reset_to_defaults",
    "save_universal_settings",
]
