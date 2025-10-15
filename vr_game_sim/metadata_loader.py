"""Utilities for loading descriptive metadata used by exports."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Dict, Optional


_DESCRIPTIONS_DIR = os.path.join(os.path.dirname(__file__), "Descriptions")


@lru_cache(maxsize=1)
def _load_raw_skill_descriptions() -> Dict[str, str]:
    """Return a mapping of lower-cased skill names to description text."""

    descriptions: Dict[str, str] = {}

    def _normalise(text: str) -> str:
        cleaned = text.replace("\r", " ")
        cleaned = cleaned.replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    # Parse hero skill descriptions. The file contains JavaScript objects with
    # repeated ``name``/``descr`` pairs (e.g. ``skillonename`` and
    # ``skillonedescr``). We match entries using a shared prefix to capture the
    # associated description.
    hero_path = os.path.join(_DESCRIPTIONS_DIR, "heroesskillsandtalents.js")
    if os.path.exists(hero_path):
        with open(hero_path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        for block in re.findall(r"\{([^{}]*)\}", content, flags=re.DOTALL):
            for match in re.finditer(
                r"(\w+?)name\s*:\s*\"([^\"]+)\"[\s\S]*?\1descr\s*:\s*\"([^\"]+)\"",
                block,
            ):
                skill_name = match.group(2)
                description = _normalise(match.group(3))
                if skill_name:
                    descriptions.setdefault(skill_name.lower(), description)

    # Parse the general skills list. This file is almost JSON but with single
    # quotes. We replace them before loading so the data can be processed using
    # :mod:`json`.
    skills_path = os.path.join(_DESCRIPTIONS_DIR, "skills.js")
    if os.path.exists(skills_path):
        with open(skills_path, "r", encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()
        for match in re.finditer(
            r"name:\s*'([^']+)'[\s\S]*?description:\s*'([^']+)'",
            raw,
        ):
            name, descr = match.groups()
            descriptions.setdefault(name.lower(), _normalise(descr))

    return descriptions


@lru_cache(maxsize=1)
def _skill_id_to_name() -> Dict[str, str]:
    from .skill_definitions import SKILL_REGISTRY_GLOBAL

    mapping: Dict[str, str] = {}
    for sid, definition in SKILL_REGISTRY_GLOBAL.items():
        name = definition.get("name") if isinstance(definition, dict) else None
        if isinstance(name, str) and name:
            mapping[sid] = name
    return mapping


_FALLBACK_DESCRIPTIONS = {
    "base_rage": "Generates rage over time, enabling rage skills during a battle.",
    "basic_attack": "Standard troop attack that deals damage to the current target.",
    "counter_attack": "Triggered counter strike in response to enemy attacks.",
}


def get_skill_description(skill_id: Optional[str], skill_name: Optional[str] = None) -> Optional[str]:
    """Return a description for ``skill_id`` or ``skill_name`` if available."""

    descriptions = _load_raw_skill_descriptions()

    if skill_id:
        canonical_name = _skill_id_to_name().get(skill_id)
        if canonical_name:
            description = descriptions.get(canonical_name.lower())
            if description:
                return description
        fallback = _FALLBACK_DESCRIPTIONS.get(skill_id)
        if fallback:
            return fallback

    if skill_name:
        description = descriptions.get(skill_name.lower())
        if description:
            return description

    if skill_name and skill_name.lower() in _FALLBACK_DESCRIPTIONS:
        return _FALLBACK_DESCRIPTIONS[skill_name.lower()]

    return None
