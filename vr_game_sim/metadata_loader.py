"""Utilities for loading descriptive metadata used by exports."""

from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from typing import Dict, Optional

from .enums import SkillTriggerType, SkillType


_DESCRIPTIONS_DIR = os.path.join(os.path.dirname(__file__), "Descriptions")


def _canonicalise_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = re.sub(r"[\'`’]", "", ascii_text.lower())
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


@lru_cache(maxsize=1)
def _load_raw_skill_descriptions() -> Dict[str, str]:
    """Return a mapping of lower-cased skill names to description text."""

    descriptions: Dict[str, str] = {}

    def _store_description(name: str, description: str) -> None:
        if not name or not description:
            return
        lowered = name.lower()
        descriptions.setdefault(lowered, description)
        canonical = _canonicalise_name(name)
        if canonical and canonical != lowered:
            descriptions.setdefault(canonical, description)

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
                    _store_description(skill_name, description)

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
            _store_description(name, _normalise(descr))

    jewel_path = os.path.join(_DESCRIPTIONS_DIR, "JewelSkills.txt")
    if os.path.exists(jewel_path):
        current_rarity: Optional[str] = None

        rarity_pattern = re.compile(r"^\s*([A-Za-z]+)\s+level\s*-", re.IGNORECASE)

        with open(jewel_path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                rarity_match = rarity_pattern.match(line)
                if rarity_match:
                    current_rarity = rarity_match.group(1).strip().title()
                    continue

                match = re.match(r"\s*\"?([^\"]+)\"?\s*:\s*(.+)", line)
                if match:
                    name, descr = match.groups()
                    description = _normalise(descr)
                    _store_description(name, description)
                    if current_rarity:
                        _store_description(f"{name} ({current_rarity})", description)

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


def _generate_fallback_description(skill_id: Optional[str], skill_name: Optional[str]) -> Optional[str]:
    if not skill_id:
        return None

    from .skill_definitions import SKILL_REGISTRY_GLOBAL

    definition = SKILL_REGISTRY_GLOBAL.get(skill_id)
    if not isinstance(definition, dict):
        return None

    display_name = definition.get("name") or skill_name or skill_id.replace("_", " ")

    def _format_type(value: Optional[SkillType | str]) -> Optional[str]:
        if isinstance(value, SkillType):
            return value.name.replace("_", " ").title()
        if isinstance(value, str) and value:
            return value.replace("_", " ").title()
        return None

    def _format_trigger(value: Optional[SkillTriggerType | str]) -> Optional[str]:
        if isinstance(value, SkillTriggerType):
            return value.name.replace("_", " ").lower()
        if isinstance(value, str) and value:
            return value.replace("_", " ").lower()
        return None

    fragments: list[str] = []
    skill_type_text = _format_type(definition.get("type"))
    if skill_type_text:
        fragments.append(f"{skill_type_text} skill")

    trigger_text = _format_trigger(definition.get("trigger"))
    if trigger_text:
        fragments.append(f"triggered on {trigger_text}")

    trigger_chance = definition.get("trigger_chance")
    if isinstance(trigger_chance, (int, float)):
        if trigger_chance >= 1:
            fragments.append("guaranteed activation")
        else:
            fragments.append(f"{trigger_chance * 100:.0f}% activation chance")

    target = definition.get("target")
    if isinstance(target, str) and target:
        fragments.append(f"targeting {target.lower()}")

    if not fragments:
        return f"{display_name} is a combat skill. Detailed description coming soon."

    description = f"{display_name} is a " + fragments[0]
    for fragment in fragments[1:]:
        description += f", {fragment}"
    description += ". Detailed description coming soon."
    return description


_FALLBACK_DESCRIPTIONS = {
    "base_rage": "Generates rage over time, enabling rage skills during a battle.",
    "basic_attack": "Standard troop attack that deals damage to the current target.",
    "counter_attack": "Triggered counter strike in response to enemy attacks.",
    "talent_chiefs_might": (
        "On basic attacks there is a chance to inflict a bleed on the target, dealing"
        " damage over time."
    ),
    "chief's might": (
        "On basic attacks there is a chance to inflict a bleed on the target, dealing"
        " damage over time."
    ),
}


def get_skill_description(skill_id: Optional[str], skill_name: Optional[str] = None) -> Optional[str]:
    """Return a description for ``skill_id`` or ``skill_name`` if available."""

    descriptions = _load_raw_skill_descriptions()

    def _lookup(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        lowered = name.lower()
        for key in {lowered, _canonicalise_name(name)}:
            if not key:
                continue
            description = descriptions.get(key)
            if description:
                return description
        return None

    if skill_id:
        canonical_name = _skill_id_to_name().get(skill_id)
        description = _lookup(canonical_name)
        if description:
            return description
        fallback = _FALLBACK_DESCRIPTIONS.get(skill_id)
        if fallback:
            return fallback

    description = _lookup(skill_name)
    if description:
        return description

    if skill_name and skill_name.lower() in _FALLBACK_DESCRIPTIONS:
        return _FALLBACK_DESCRIPTIONS[skill_name.lower()]

    generated = _generate_fallback_description(skill_id, skill_name)
    if generated:
        return generated

    return None
