"""Utilities for loading descriptive metadata used by exports."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from functools import lru_cache
from typing import Dict, Iterable, Optional

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

    def _store_description(name: str, description: str, context: Optional[str] = None) -> None:
        if not name or not description:
            return
        lowered = name.lower().strip()
        canonical = _canonicalise_name(name)

        keys: list[str] = []
        context_key = context.lower().strip() if isinstance(context, str) else None
        if context_key:
            if lowered:
                keys.append(f"{context_key}:{lowered}")
            if canonical and canonical != lowered:
                keys.append(f"{context_key}:{canonical}")

        if lowered:
            keys.append(lowered)
        if canonical and canonical != lowered:
            keys.append(canonical)

        for key in keys:
            if key and key not in descriptions:
                descriptions[key] = description

    def _normalise(text: str) -> str:
        cleaned = text.replace("\r", " ")
        cleaned = cleaned.replace("\n", " ")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    # Parse hero skill descriptions. Prefer the simplified JSON export but fall
    # back to the historical JavaScript file if necessary.
    hero_json_path = os.path.join(_DESCRIPTIONS_DIR, "heroes_skills_talents_simple.json")
    hero_entries = None
    if os.path.exists(hero_json_path):
        try:
            with open(hero_json_path, "r", encoding="utf-8") as fh:
                hero_entries = json.load(fh)
        except (OSError, json.JSONDecodeError):
            hero_entries = None

    if isinstance(hero_entries, list):
        for entry in hero_entries:
            skills = entry.get("skills") if isinstance(entry, dict) else None
            for skill in skills or ():
                if not isinstance(skill, dict):
                    continue
                name = skill.get("name")
                description = skill.get("description")
                if isinstance(name, str) and isinstance(description, str):
                    _store_description(name, _normalise(description), context="skill")

            talents = entry.get("talents") if isinstance(entry, dict) else None
            for talent in talents or ():
                if not isinstance(talent, dict):
                    continue
                name = talent.get("name")
                description = talent.get("description")
                if isinstance(name, str) and isinstance(description, str):
                    _store_description(name, _normalise(description), context="talent")
    else:
        hero_path = os.path.join(_DESCRIPTIONS_DIR, "heroesskillsandtalents.js")
        if os.path.exists(hero_path):
            with open(hero_path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            for block in re.findall(r"\{([^{}]*)\}", content, flags=re.DOTALL):
                for match in re.finditer(
                    r"(\w+?)name\s*:\s*\"([^\"]+)\"[\s\S]*?\1descr\s*:\s*\"([^\"]+)\"",
                    block,
                ):
                    prefix, skill_name, descr_text = match.groups()
                    description = _normalise(descr_text)
                    if skill_name:
                        context = "talent" if prefix.startswith("talent") else "skill"
                        _store_description(skill_name, description, context=context)

    skills_json_path = os.path.join(_DESCRIPTIONS_DIR, "skills_simple.json")
    skills_entries = None
    if os.path.exists(skills_json_path):
        try:
            with open(skills_json_path, "r", encoding="utf-8") as fh:
                skills_entries = json.load(fh)
        except (OSError, json.JSONDecodeError):
            skills_entries = None

    if isinstance(skills_entries, list):
        for entry in skills_entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            description = entry.get("description")
            if isinstance(name, str) and isinstance(description, str):
                _store_description(name, _normalise(description), context="skill")
    else:
        # Parse the historical JavaScript export which used single quotes and
        # therefore required manual extraction.
        skills_path = os.path.join(_DESCRIPTIONS_DIR, "skills.js")
        if os.path.exists(skills_path):
            with open(skills_path, "r", encoding="utf-8", errors="ignore") as fh:
                raw = fh.read()
            for match in re.finditer(
                r"name:\s*'([^']+)'[\s\S]*?description:\s*'([^']+)'",
                raw,
            ):
                name, descr = match.groups()
                _store_description(name, _normalise(descr), context="skill")

    mount_json_path = os.path.join(_DESCRIPTIONS_DIR, "mountskills_simple.json")
    mount_entries = None
    if os.path.exists(mount_json_path):
        try:
            with open(mount_json_path, "r", encoding="utf-8") as fh:
                mount_entries = json.load(fh)
        except (OSError, json.JSONDecodeError):
            mount_entries = None

    if isinstance(mount_entries, list):
        for entry in mount_entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            description = entry.get("description")
            if isinstance(name, str) and isinstance(description, str):
                _store_description(name, _normalise(description), context="mount")
    else:
        mount_path = os.path.join(_DESCRIPTIONS_DIR, "mountskills.js")
        if os.path.exists(mount_path):
            with open(mount_path, "r", encoding="utf-8", errors="ignore") as fh:
                raw = fh.read()
            for match in re.finditer(
                r"name:\s*\"([^\"]+)\"[\s\S]*?description:\s*\"([^\"]+)\"",
                raw,
            ):
                name, descr = match.groups()
                _store_description(name, _normalise(descr), context="mount")

    jewel_path = os.path.join(_DESCRIPTIONS_DIR, "JewelSkills.txt")
    if os.path.exists(jewel_path):
        current_rarity: Optional[str] = None

        rarity_pattern = re.compile(r"^\s*([A-Za-z]+)\s+level\s*-", re.IGNORECASE)
        rarity_name_pattern = re.compile(
            r"^\s*([A-Za-z]+)\s+\"([^\"]+)\"\s*:\s*(.+)",
            re.IGNORECASE,
        )
        name_pattern = re.compile(r"^\s*\"([^\"]+)\"\s*:\s*(.+)")

        with open(jewel_path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                rarity_match = rarity_pattern.match(line)
                if rarity_match:
                    current_rarity = rarity_match.group(1).strip().title()
                    continue

                rarity_name_match = rarity_name_pattern.match(line)
                if rarity_name_match:
                    rarity_text, name, descr = rarity_name_match.groups()
                    rarity = rarity_text.strip().title()
                    description = _normalise(descr)
                    _store_description(name, description, context="jewel")
                    _store_description(f"{name} ({rarity})", description, context="jewel")
                    current_rarity = rarity
                    continue

                match = name_pattern.match(line)
                if match:
                    name, descr = match.groups()
                    description = _normalise(descr)
                    _store_description(name, description, context="jewel")
                    if current_rarity:
                        _store_description(
                            f"{name} ({current_rarity})",
                            description,
                            context="jewel",
                        )

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
    "plugin_helas_curse": (
        "Every few rounds Hela's Curse ignites the enemy with burn damage and can also"
        " strip their defenses, reducing their base defense for a short duration."
    ),
    "hela's curse": (
        "Every few rounds Hela's Curse ignites the enemy with burn damage and can also"
        " strip their defenses, reducing their base defense for a short duration."
    ),
}


def get_skill_description(skill_id: Optional[str], skill_name: Optional[str] = None) -> Optional[str]:
    """Return a description for ``skill_id`` or ``skill_name`` if available."""

    descriptions = _load_raw_skill_descriptions()

    def _lookup(name: Optional[str], contexts: Iterable[str] = ()) -> Optional[str]:
        if not name:
            return None
        lowered = name.lower().strip()
        canonical = _canonicalise_name(name)

        ordered_keys: list[str] = []
        for context in contexts:
            context_key = context.lower().strip() if isinstance(context, str) else ""
            if not context_key:
                continue
            if lowered:
                ordered_keys.append(f"{context_key}:{lowered}")
            if canonical and canonical != lowered:
                ordered_keys.append(f"{context_key}:{canonical}")

        if lowered:
            ordered_keys.append(lowered)
        if canonical and canonical != lowered:
            ordered_keys.append(canonical)

        for key in ordered_keys:
            if not key:
                continue
            description = descriptions.get(key)
            if description:
                return description
        return None

    contexts: list[str] = []
    definition = None
    if skill_id:
        from .skill_definitions import SKILL_REGISTRY_GLOBAL

        definition = SKILL_REGISTRY_GLOBAL.get(skill_id)
        skill_type_value = definition.get("type") if isinstance(definition, dict) else None

        def _add_context(value: str) -> None:
            lowered = value.strip().lower()
            if lowered and lowered not in contexts:
                contexts.append(lowered)

        type_text: Optional[str]
        if isinstance(skill_type_value, SkillType):
            type_text = skill_type_value.name.lower()
        elif isinstance(skill_type_value, str):
            type_text = skill_type_value.lower()
        else:
            type_text = None

        if not type_text and skill_id.startswith("talent_"):
            type_text = "talent"
        elif not type_text and skill_id.startswith("plugin_"):
            type_text = "plugin"

        if type_text == "talent":
            _add_context("talent")
            _add_context("skill")
        elif type_text in {"plugin", "plugin_skill"}:
            _add_context("plugin")
            _add_context("skill")
        elif type_text in {"mount", "mount_skill"}:
            _add_context("mount")
            _add_context("skill")
        else:
            _add_context("skill")

        canonical_name = _skill_id_to_name().get(skill_id)
        description = _lookup(canonical_name, contexts)
        if description:
            return description
        fallback = _FALLBACK_DESCRIPTIONS.get(skill_id)
        if fallback:
            return fallback

    description = _lookup(skill_name, contexts)
    if description:
        return description

    if skill_name and skill_name.lower() in _FALLBACK_DESCRIPTIONS:
        return _FALLBACK_DESCRIPTIONS[skill_name.lower()]

    generated = _generate_fallback_description(skill_id, skill_name)
    if generated:
        return generated

    return None
