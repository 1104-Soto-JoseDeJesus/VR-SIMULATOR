"""Session and persistent configuration for the troop scalar multiplier."""
from __future__ import annotations

import json
import math
import os
import threading
from pathlib import Path
from typing import Any

__all__ = [
    "get_multiplier",
    "set_session_multiplier",
    "save_multiplier",
    "reset_to_default",
]

_LOCK = threading.RLock()
_DEFAULT_MULTIPLIER = 1.0
_ENV_PATH = "VR_GAME_SIM_TROOP_SCALAR_PATH"
_SETTINGS_PATH = Path(
    os.environ.get(_ENV_PATH) or Path(__file__).with_name("troop_scalar_multiplier.json")
)
_current_multiplier: float = _DEFAULT_MULTIPLIER


def _validate_multiplier(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError("Troop scalar multiplier must be a real number") from exc
    if not math.isfinite(number):
        raise ValueError("Troop scalar multiplier must be finite")
    if number < 0:
        raise ValueError("Troop scalar multiplier must be non-negative")
    return number


def _load_multiplier_from_disk() -> float:
    if not _SETTINGS_PATH.exists():
        return _DEFAULT_MULTIPLIER
    try:
        data = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_MULTIPLIER
    value = data.get("multiplier") if isinstance(data, dict) else None
    try:
        return _validate_multiplier(value)
    except ValueError:
        return _DEFAULT_MULTIPLIER


def _write_multiplier(value: float) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"multiplier": value}
    _SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _clear_game_simulator_cache() -> None:
    import sys

    module = sys.modules.get("vr_game_sim.game_simulator")
    GameSimulator = getattr(module, "GameSimulator", None)
    if GameSimulator is None:
        return
    try:
        GameSimulator.troop_scalar.cache_clear()
    except AttributeError:  # pragma: no cover - defensive
        pass


with _LOCK:
    _current_multiplier = _load_multiplier_from_disk()


def get_multiplier() -> float:
    """Return the active troop scalar multiplier."""
    with _LOCK:
        return _current_multiplier


def set_session_multiplier(multiplier: float) -> float:
    """Update the in-memory troop scalar multiplier for the current session."""
    value = _validate_multiplier(multiplier)
    with _LOCK:
        global _current_multiplier
        _current_multiplier = value
    _clear_game_simulator_cache()
    return value


def save_multiplier(multiplier: float | None = None) -> float:
    """Persist ``multiplier`` (or the current value) to disk and return it."""
    if multiplier is not None:
        value = set_session_multiplier(multiplier)
    else:
        value = get_multiplier()
    with _LOCK:
        _write_multiplier(value)
    _clear_game_simulator_cache()
    return value


def reset_to_default() -> float:
    """Restore the multiplier to its default value (both session and disk)."""
    default = set_session_multiplier(_DEFAULT_MULTIPLIER)
    with _LOCK:
        _write_multiplier(default)
    _clear_game_simulator_cache()
    return default

