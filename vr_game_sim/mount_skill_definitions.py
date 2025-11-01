"""Utility for loading mount skill definitions from metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .enums import (
    EffectType,
    PluginSkillLabel,
    SkillTriggerType,
    SkillType,
    StatType,
)
from .skill_logic.mount_skill_handlers import (
    handle_mount_command_skill,
    handle_mount_cooperation_skill,
    handle_mount_reactive_skill,
)
from .skill_system import SkillDefinition

_DATA_PATH = Path(__file__).with_name("Descriptions").joinpath("MountSkillsBehaviors.json")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower())
    slug = re.sub(r"_{2,}", "_", slug).strip("_")
    return slug


def _extract_passive_effect(skill_id: str, description: str) -> List[Dict[str, Any]]:
    passive_effects: List[Dict[str, Any]] = []
    match = re.search(
        r"passive:\s*\+(\d+(?:\.\d+)?)%\s*(command|cooperation|counterattack) skill critical rate",
        description,
        flags=re.IGNORECASE,
    )
    if not match:
        return passive_effects

    magnitude = float(match.group(1)) / 100.0
    category = match.group(2).lower()
    stat_map = {
        "command": StatType.COMMAND_SKILL_CRIT_RATE,
        "cooperation": StatType.COOPERATION_SKILL_CRIT_RATE,
        "counterattack": StatType.REACTIVE_SKILL_CRIT_RATE,
    }
    stat = stat_map.get(category)
    if not stat:
        return passive_effects

    passive_effects.append(
        {
            "effect_type": EffectType.STAT_MOD,
            "name": f"{skill_id}_passive_{stat.value}",
            "stat_to_mod": stat,
            "magnitude": magnitude,
            "duration": -1,
        }
    )
    return passive_effects


def _extract_interval(description: str) -> Tuple[int, int]:
    match = re.search(r"every\s+(\d+)s", description, flags=re.IGNORECASE)
    if not match:
        return 0, 0
    seconds = int(match.group(1))
    if seconds <= 0:
        return seconds, 0
    rounds = max(1, int(round(seconds / 3)))
    return seconds, rounds


def _extract_limit(description: str) -> Tuple[int, int]:
    match = re.search(
        r"limit:\s*triggers? up to\s*(\d+)\s*times?(?:\s*per\s*target)?", description, flags=re.IGNORECASE
    )
    if not match:
        return 0, 0
    count = int(match.group(1))
    if count <= 0:
        return 0, 0
    return count, 0


def _extract_numbers(description: str, pattern: str) -> List[float]:
    return [float(num) for num in re.findall(pattern, description, flags=re.IGNORECASE)]


def _extract_rage(description: str) -> float:
    match = re.search(r"(recover|restore|gain)\s+(\d+)\s+rage", description, flags=re.IGNORECASE)
    if not match:
        return 0.0
    return float(match.group(2))


def _create_effect(
    *,
    skill_id: str,
    stat: StatType,
    magnitude_pct: float,
    duration_seconds: int,
    target: str,
    name_hint: str,
) -> Dict[str, Any]:
    magnitude = magnitude_pct / 100.0
    duration_rounds = max(0, int(round(duration_seconds / 3)))
    if duration_rounds > 0:
        duration_value = max(0, duration_rounds - 1)
    else:
        duration_value = duration_rounds
    effect_name = f"{skill_id}_{name_hint}_{stat.value}"
    return {
        "effect_type": EffectType.STAT_MOD,
        "name": effect_name,
        "stat_to_mod": stat,
        "magnitude": magnitude,
        "duration": duration_value,
        "target": target,
        "duration_rounds": duration_rounds,
    }


def _extract_buffs(skill_id: str, description: str) -> List[Dict[str, Any]]:
    effects: List[Dict[str, Any]] = []
    lower = description.lower()
    seen: set[Tuple[str, str, float, int]] = set()

    patterns = [
        (r"increase your total damage by (\d+)% for (\d+)s", StatType.GENERAL_DAMAGE_MODIFIER, "SELF", "total_damage"),
        (r"increase your damage by (\d+)% for (\d+)s", StatType.GENERAL_DAMAGE_MODIFIER, "SELF", "damage"),
        (
            r"increase your counterattack damage by (\d+)% for (\d+)s",
            StatType.COUNTER_DAMAGE_ADJUST,
            "SELF",
            "counter_damage",
        ),
        (
            r"increase your burning damage by (\d+)% for (\d+)s",
            StatType.BURN_DAMAGE_BOOST,
            "SELF",
            "burn_damage",
        ),
        (
            r"increase your poison damage by (\d+)% for (\d+)s",
            StatType.POISON_DAMAGE_BOOST,
            "SELF",
            "poison_damage",
        ),
        (
            r"increase the target's damage received by (\d+)% for (\d+)s",
            StatType.DAMAGE_TAKEN_MULTIPLIER,
            "ENEMY",
            "target_damage_taken",
        ),
        (
            r"reduce your damage taken by (\d+)% for (\d+)s",
            StatType.DAMAGE_TAKEN_MULTIPLIER,
            "SELF",
            "damage_taken",
        ),
        (
            r"reduces damage taken by (\d+)% for (\d+)s",
            StatType.DAMAGE_TAKEN_MULTIPLIER,
            "SELF",
            "damage_taken",
        ),
        (
            r"increase your damage reduction by (\d+)% for (\d+)s",
            StatType.DAMAGE_TAKEN_MULTIPLIER,
            "SELF",
            "damage_reduction",
        ),
        (
            r"increase your total damage by (\d+)% for (\d+) seconds",
            StatType.GENERAL_DAMAGE_MODIFIER,
            "SELF",
            "total_damage",
        ),
    ]

    for pattern, stat, target, hint in patterns:
        for match in re.finditer(pattern, lower):
            magnitude_pct = float(match.group(1))
            duration_seconds = int(match.group(2))
            key = (stat.value, target, magnitude_pct, duration_seconds)
            if key in seen:
                continue
            seen.add(key)
            effect = _create_effect(
                skill_id=skill_id,
                stat=stat,
                magnitude_pct=magnitude_pct,
                duration_seconds=duration_seconds,
                target=target,
                name_hint=hint,
            )
            effects.append(effect)

    return effects


def _split_effects_by_target(effects: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    self_effects: List[Dict[str, Any]] = []
    enemy_effects: List[Dict[str, Any]] = []
    for effect in effects:
        target = effect.pop("target", "SELF")
        if target == "ENEMY":
            enemy_effects.append(effect)
        else:
            self_effects.append(effect)
    return self_effects, enemy_effects


def _build_skill_definition(entry: Dict[str, Any]) -> SkillDefinition:
    name = entry.get("name", "Unknown Mount Skill")
    mount_type = str(entry.get("type", "command")).lower().strip()
    skill_id = f"mount_{mount_type}_{_slugify(name)}"
    description = entry.get("description", "")

    trigger = SkillTriggerType.CHANCE_PER_ROUND
    logic_handler = handle_mount_command_skill
    label = PluginSkillLabel.COMMAND
    additional_triggers: List[SkillTriggerType] = []

    if mount_type == "reactive":
        trigger = SkillTriggerType.ON_HIT_BY_BASIC_ATTACK
        logic_handler = handle_mount_reactive_skill
        label = PluginSkillLabel.REACTIVE
        additional_triggers = [SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE]
    elif mount_type == "cooperation":
        trigger = SkillTriggerType.ON_BASIC_ATTACK
        logic_handler = handle_mount_cooperation_skill
        label = PluginSkillLabel.COOPERATION

    interval_seconds, interval_rounds = _extract_interval(description)
    limit_per_round, _ = _extract_limit(description)
    damage_factors = _extract_numbers(description, r"damage factor\s*(\d+)")
    heal_factors = _extract_numbers(description, r"heal factor\s*(\d+)")
    rage_gain = _extract_rage(description)
    passive_effects = _extract_passive_effect(skill_id, description)
    buff_effects = _extract_buffs(skill_id, description)
    self_effects, enemy_effects = _split_effects_by_target(buff_effects)

    config: Dict[str, Any] = {
        "troop_types": entry.get("troop_types", []),
        "slot": entry.get("slot"),
        "mount_type": mount_type,
        "description": description,
        "damage_factors": damage_factors,
        "heal_factors": heal_factors,
        "rage_gain": rage_gain,
        "self_effects": self_effects,
        "enemy_effects": enemy_effects,
    }

    if interval_seconds:
        config["interval_seconds"] = interval_seconds
    if interval_rounds:
        config["interval_rounds"] = interval_rounds
        config["cooldown_rounds"] = interval_rounds

    if additional_triggers:
        config["additional_triggers"] = additional_triggers

    if limit_per_round:
        config["max_triggers_per_round"] = limit_per_round

    config.setdefault("reactive_sources", [])
    if mount_type == "reactive" and not config["reactive_sources"]:
        config["reactive_sources"] = [
            SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
            SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE,
        ]

    skill_def: SkillDefinition = {
        "id": skill_id,
        "name": name,
        "type": SkillType.MOUNT_SKILL,
        "trigger": trigger,
        "trigger_chance": 1.0,
        "target": "ENEMY",
        "logic_handler": logic_handler,
        "labels": [label],
        "config": config,
    }

    if passive_effects:
        skill_def["effects_to_apply"] = passive_effects

    return skill_def


def _load_mount_entries() -> List[Dict[str, Any]]:
    if not _DATA_PATH.exists():
        return []
    try:
        with _DATA_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    return []


def _build_mount_registry() -> Dict[str, SkillDefinition]:
    registry: Dict[str, SkillDefinition] = {}
    for entry in _load_mount_entries():
        skill_def = _build_skill_definition(entry)
        registry[skill_def["id"]] = skill_def
    return registry


MOUNT_SKILL_DEFINITIONS: Dict[str, SkillDefinition] = _build_mount_registry()

