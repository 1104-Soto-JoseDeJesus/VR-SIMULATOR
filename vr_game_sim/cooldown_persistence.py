from __future__ import annotations

import json
import os
from typing import Any, Dict


DEFAULTS_PATH = os.path.join(os.path.dirname(__file__), "cooldown_defaults.json")


def _default_payload() -> Dict[str, Any]:
    """Return the built-in fallback structure for cooldown defaults."""
    return {
        "global": {"cooldowns_enabled": True},
        "categories": {
            "hero": True,
            "plugin": False,
            "gem": True,
            "mount": True,
        },
        "skills": {},
    }


def load_cooldown_defaults(path: str | None = None) -> Dict[str, Any]:
    """Load persisted cooldown defaults from ``path`` or the standard location.

    Any missing sections are filled with sensible defaults so callers can rely
    on the returned dictionary containing the keys ``global``, ``categories``
    and ``skills``.
    """
    filename = path or DEFAULTS_PATH
    data: Dict[str, Any] = {}
    try:
        with open(filename, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
            if isinstance(loaded, dict):
                data.update(loaded)
    except OSError:
        # Absence of a config file is expected on first run.
        pass
    except json.JSONDecodeError:
        # Corrupt config – ignore and fall back to defaults.
        pass

    defaults = _default_payload()
    # Merge user data over defaults while preserving structure.
    global_cfg = defaults["global"]
    global_cfg.update(
        {k: bool(v) for k, v in (data.get("global") or {}).items() if isinstance(v, (bool, int))}
    )

    cat_cfg = defaults["categories"]
    cat_cfg.update(
        {k: bool(v) for k, v in (data.get("categories") or {}).items() if isinstance(v, (bool, int))}
    )

    skills_cfg: Dict[str, bool] = {}
    for sid, flag in (data.get("skills") or {}).items():
        try:
            skills_cfg[str(sid)] = bool(flag)
        except Exception:
            continue
    defaults["skills"] = skills_cfg
    return defaults


def save_cooldown_defaults(payload: Dict[str, Any], path: str | None = None) -> None:
    """Persist ``payload`` to ``path`` or the standard location.

    The function is intentionally forgiving – any failure simply results in the
    settings not being written rather than raising an exception in the GUI.
    """
    filename = path or DEFAULTS_PATH
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    safe_payload = _default_payload()

    # Merge provided values into the safe template.
    provided_global = payload.get("global") or {}
    provided_categories = payload.get("categories") or {}
    provided_skills = payload.get("skills") or {}

    for key, value in provided_global.items():
        if isinstance(value, (bool, int)):
            safe_payload["global"][key] = bool(value)
    for key, value in provided_categories.items():
        if isinstance(value, (bool, int)):
            safe_payload["categories"][key] = bool(value)

    skills_cfg: Dict[str, bool] = {}
    if isinstance(provided_skills, dict):
        for sid, flag in provided_skills.items():
            try:
                skills_cfg[str(sid)] = bool(flag)
            except Exception:
                continue
    safe_payload["skills"] = skills_cfg

    try:
        with open(filename, "w", encoding="utf-8") as fh:
            json.dump(safe_payload, fh, indent=2, sort_keys=True)
    except OSError:
        # Ignore write errors – they should not interrupt the GUI workflow.
        return


