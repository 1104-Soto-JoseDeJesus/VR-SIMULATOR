from __future__ import annotations

"""Definitions and helpers for hero gear items."""

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from .enums import StatType


@dataclass(frozen=True, slots=True)
class GearEffect:
    """Represents a single stat modifier granted by a gear item."""

    stat: StatType
    magnitude: float
    description: str


@dataclass(frozen=True, slots=True)
class GearDefinition:
    """Static data describing a piece of hero gear."""

    id: str
    name: str
    rarity: str
    slot: str
    icon_path: str
    effects: tuple[GearEffect, ...]

    def effect_descriptions(self) -> tuple[str, ...]:
        """Return human-readable descriptions for each effect."""

        return tuple(effect.description for effect in self.effects)


_MODULE_DIR = os.path.dirname(__file__)
_ICON_DIR = os.path.join(_MODULE_DIR, "Gear Icons")

GEAR_SLOT_ORDER: list[tuple[str, str]] = [
    ("head", "Head"),
    ("weapon", "Weapon"),
    ("chest", "Chest"),
    ("boots", "Boots"),
]

VALID_GEAR_SLOTS = {slot for slot, _ in GEAR_SLOT_ORDER}

_SLOT_ALIASES: Dict[str, str] = {
    "head": "head",
    "helm": "head",
    "helmet": "head",
    "headgear": "head",
    "weapon": "weapon",
    "mainhand": "weapon",
    "hand": "weapon",
    "blade": "weapon",
    "axe": "weapon",
    "chest": "chest",
    "armor": "chest",
    "armour": "chest",
    "body": "chest",
    "breastplate": "chest",
    "boots": "boots",
    "boot": "boots",
    "feet": "boots",
    "foot": "boots",
    "greaves": "boots",
}


def normalize_gear_slot(value: Any) -> str | None:
    """Normalise a potential gear slot label to the canonical slot string."""

    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None

    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    if text in _SLOT_ALIASES:
        return _SLOT_ALIASES[text]

    simplified = re.sub(r"[^a-z]", "", text)
    return _SLOT_ALIASES.get(simplified)


RARITY_BACKGROUNDS: Dict[str, str] = {
    "Legendary": os.path.join(_ICON_DIR, "Legendary.png"),
    "Epic": os.path.join(_ICON_DIR, "Epic.png"),
}


def _icon_path(filename: str) -> str:
    return os.path.join(_ICON_DIR, filename)


def _canonicalise_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-z0-9]+", " ", ascii_text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


_RAW_GEAR_DATA: list[dict[str, Any]] = [
    {
        "id": "gear_immolated_axe_legendary",
        "name": "Immolated Axe",
        "rarity": "Legendary",
        "slot": "weapon",
        "icon": "Immolated-Axe.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.10,
                "Basic attack damage increase 10% (+0.1 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.0675,
                "Counterattack damage increase 6.75% (+0.0675 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_blazing_helmet_legendary",
        "name": "Blazing Helmet",
        "rarity": "Legendary",
        "slot": "head",
        "icon": "Blazing-Helmet.png",
        "effects": [
            (
                StatType.GENERAL_DAMAGE_MODIFIER,
                0.0325,
                "Overall damage increase 3.25% (+0.0325 to all applicable damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_inferno_armor_legendary",
        "name": "Inferno Armor",
        "rarity": "Legendary",
        "slot": "chest",
        "icon": "Inferno-Armor.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.10,
                "Basic attack damage increase 10% (+0.1 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.0675,
                "Counterattack damage increase 6.75% (+0.0675 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_ferocious_boots_legendary",
        "name": "Ferocious Boots",
        "rarity": "Legendary",
        "slot": "boots",
        "icon": "Ferocious-Boots.png",
        "effects": [
            (
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                -0.05,
                "Overall damage received decrease 5% (reduces own damage received, -0.05 to applicable incoming damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_gleaming_longbow_legendary",
        "name": "Gleaming Longbow",
        "rarity": "Legendary",
        "slot": "weapon",
        "icon": "Gleaming-Longbow.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.0675,
                "Basic attack damage increase 6.75% (+0.0675 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.10,
                "Counterattack damage increase 10% (+0.1 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_divine_crown_legendary",
        "name": "Divine Crown",
        "rarity": "Legendary",
        "slot": "head",
        "icon": "Divine-Crown.png",
        "effects": [
            (
                StatType.GENERAL_DAMAGE_MODIFIER,
                0.05,
                "Overall damage increase 5% (+0.05 to all applicable damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_verdant_armor_legendary",
        "name": "Verdant Armor",
        "rarity": "Legendary",
        "slot": "chest",
        "icon": "Verdant-Armor.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.10,
                "Basic attack damage increase 10% (+0.1 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.0675,
                "Counterattack damage increase 6.75% (+0.0675 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_thicket_boots_legendary",
        "name": "Thicket Boots",
        "rarity": "Legendary",
        "slot": "boots",
        "icon": "Thicket-Boots.png",
        "effects": [
            (
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                -0.0325,
                "Overall damage received decrease 3.25% (reduces own damage received, -0.0325 to applicable incoming damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_marine_halberd_legendary",
        "name": "Marine Halberd",
        "rarity": "Legendary",
        "slot": "weapon",
        "icon": "Marine-Halberd.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.0675,
                "Basic attack damage increase 6.75% (+0.0675 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.10,
                "Counterattack damage increase 10% (+0.1 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_abyssal_crown_legendary",
        "name": "Abyssal Crown",
        "rarity": "Legendary",
        "slot": "head",
        "icon": "Abyssal-Crown.png",
        "effects": [
            (
                StatType.GENERAL_DAMAGE_MODIFIER,
                0.0325,
                "Overall damage increase 3.25% (+0.0325 to all applicable damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_bylgjas_armor_legendary",
        "name": "Bylgja's Armor",
        "rarity": "Legendary",
        "slot": "chest",
        "icon": "Bylgjas-Armor.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.0675,
                "Basic attack damage increase 6.75% (+0.0675 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.10,
                "Counterattack damage increase 10% (+0.1 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_tsunami_plated_boots_legendary",
        "name": "Tsunami Plated Boots",
        "rarity": "Legendary",
        "slot": "boots",
        "icon": "Tsunami-Plated-Boots.png",
        "effects": [
            (
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                -0.05,
                "Overall damage received decrease 5% (reduces own damage received, -0.05 to applicable incoming damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_immolated_axe_epic",
        "name": "Immolated Axe",
        "rarity": "Epic",
        "slot": "weapon",
        "icon": "Immolated-Axe.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.04,
                "Basic attack damage increase 4% (+0.04 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.0275,
                "Counterattack damage increase 2.75% (+0.0275 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_blazing_helmet_epic",
        "name": "Blazing Helmet",
        "rarity": "Epic",
        "slot": "head",
        "icon": "Blazing-Helmet.png",
        "effects": [
            (
                StatType.GENERAL_DAMAGE_MODIFIER,
                0.0125,
                "Overall damage increase 1.25% (+0.0125 to all applicable damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_inferno_armor_epic",
        "name": "Inferno Armor",
        "rarity": "Epic",
        "slot": "chest",
        "icon": "Inferno-Armor.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.04,
                "Basic attack damage increase 4% (+0.04 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.0275,
                "Counterattack damage increase 2.75% (+0.0275 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_ferocious_boots_epic",
        "name": "Ferocious Boots",
        "rarity": "Epic",
        "slot": "boots",
        "icon": "Ferocious-Boots.png",
        "effects": [
            (
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                -0.02,
                "Overall damage received decrease 2% (reduces own damage received, -0.02 to applicable incoming damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_gleaming_longbow_epic",
        "name": "Gleaming Longbow",
        "rarity": "Epic",
        "slot": "weapon",
        "icon": "Gleaming-Longbow.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.0275,
                "Basic attack damage increase 2.75% (+0.0275 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.04,
                "Counterattack damage increase 4% (+0.04 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_divine_crown_epic",
        "name": "Divine Crown",
        "rarity": "Epic",
        "slot": "head",
        "icon": "Divine-Crown.png",
        "effects": [
            (
                StatType.GENERAL_DAMAGE_MODIFIER,
                0.02,
                "Overall damage increase 2% (+0.02 to all applicable damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_verdant_armor_epic",
        "name": "Verdant Armor",
        "rarity": "Epic",
        "slot": "chest",
        "icon": "Verdant-Armor.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.04,
                "Basic attack damage increase 4% (+0.04 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.0275,
                "Counterattack damage increase 2.75% (+0.0275 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_thicket_boots_epic",
        "name": "Thicket Boots",
        "rarity": "Epic",
        "slot": "boots",
        "icon": "Thicket-Boots.png",
        "effects": [
            (
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                -0.0125,
                "Overall damage received decrease 1.25% (reduces own damage received, -0.0125 to applicable incoming damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_marine_halberd_epic",
        "name": "Marine Halberd",
        "rarity": "Epic",
        "slot": "weapon",
        "icon": "Marine-Halberd.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.0275,
                "Basic attack damage increase 2.75% (+0.0275 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.04,
                "Counterattack damage increase 4% (+0.04 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_abyssal_crown_epic",
        "name": "Abyssal Crown",
        "rarity": "Epic",
        "slot": "head",
        "icon": "Abyssal-Crown.png",
        "effects": [
            (
                StatType.GENERAL_DAMAGE_MODIFIER,
                0.0125,
                "Overall damage increase 1.25% (+0.0125 to all applicable damage multipliers except DoTs)",
            ),
        ],
    },
    {
        "id": "gear_bylgjas_armor_epic",
        "name": "Bylgja's Armor",
        "rarity": "Epic",
        "slot": "chest",
        "icon": "Bylgjas-Armor.png",
        "effects": [
            (
                StatType.BASIC_DAMAGE_ADJUST,
                0.0275,
                "Basic attack damage increase 2.75% (+0.0275 to basic attack damage multiplier)",
            ),
            (
                StatType.COUNTER_DAMAGE_ADJUST,
                0.04,
                "Counterattack damage increase 4% (+0.04 to counterattack damage multiplier)",
            ),
        ],
    },
    {
        "id": "gear_tsunami_plated_boots_epic",
        "name": "Tsunami Plated Boots",
        "rarity": "Epic",
        "slot": "boots",
        "icon": "Tsunami-Plated-Boots.png",
        "effects": [
            (
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                -0.02,
                "Overall damage received decrease 2% (reduces own damage received, -0.02 to applicable incoming damage multipliers except DoTs)",
            ),
        ],
    },
]


GEAR_REGISTRY: Dict[str, GearDefinition] = {}
_GEAR_ALIAS_TO_ID: Dict[str, str] = {}

_NAME_COUNTS: Dict[str, int] = {}
for entry in _RAW_GEAR_DATA:
    key = _canonicalise_name(entry["name"])
    _NAME_COUNTS[key] = _NAME_COUNTS.get(key, 0) + 1


def _register_aliases(gear: GearDefinition, *aliases: Iterable[str]) -> None:
    for alias_group in aliases:
        for alias in alias_group:
            canonical = _canonicalise_name(alias)
            if canonical and canonical not in _GEAR_ALIAS_TO_ID:
                _GEAR_ALIAS_TO_ID[canonical] = gear.id


for entry in _RAW_GEAR_DATA:
    effects = tuple(GearEffect(stat=stat, magnitude=magnitude, description=description) for stat, magnitude, description in entry["effects"])
    gear_def = GearDefinition(
        id=entry["id"],
        name=entry["name"],
        rarity=entry["rarity"].title(),
        slot=entry["slot"],
        icon_path=_icon_path(entry["icon"]),
        effects=effects,
    )
    GEAR_REGISTRY[gear_def.id] = gear_def

    alias_sets = [
        {gear_def.id, f"{gear_def.rarity} {gear_def.name}", f"{gear_def.name} {gear_def.rarity}", f"{gear_def.rarity} - {gear_def.name}", f"{gear_def.name} ({gear_def.rarity})"},
    ]
    name_key = _canonicalise_name(gear_def.name)
    if _NAME_COUNTS.get(name_key, 0) == 1:
        alias_sets.append({gear_def.name})
    _register_aliases(gear_def, *alias_sets)


def normalize_gear_id(value: Any) -> str:
    """Normalise ``value`` into a canonical gear identifier if possible."""

    if value is None:
        return ""
    if isinstance(value, GearDefinition):
        return value.id
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        if text in GEAR_REGISTRY:
            return text
        lowered = text.lower()
        for gear_id in GEAR_REGISTRY:
            if lowered == gear_id.lower():
                return gear_id
        canonical = _canonicalise_name(text)
        mapped = _GEAR_ALIAS_TO_ID.get(canonical)
        return mapped or ""
    if isinstance(value, dict):
        for key in ("id", "gear_id", "gear", "name"):
            if key in value:
                normalized = normalize_gear_id(value.get(key))
                if normalized:
                    return normalized
        for item in value.values():
            normalized = normalize_gear_id(item)
            if normalized:
                return normalized
        return ""
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = normalize_gear_id(item)
            if normalized:
                return normalized
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return normalize_gear_id(str(value))
    if isinstance(value, bool):
        return ""
    return normalize_gear_id(str(value))


def resolve_gear(value: Any) -> Optional[GearDefinition]:
    """Return the :class:`GearDefinition` represented by ``value`` if found."""

    if isinstance(value, GearDefinition):
        return value
    gear_id = normalize_gear_id(value)
    if gear_id and gear_id in GEAR_REGISTRY:
        return GEAR_REGISTRY[gear_id]
    if isinstance(value, str):
        canonical = _canonicalise_name(value)
        mapped = _GEAR_ALIAS_TO_ID.get(canonical)
        if mapped:
            return GEAR_REGISTRY.get(mapped)
    return None


__all__ = [
    "GearDefinition",
    "GearEffect",
    "GEAR_REGISTRY",
    "GEAR_SLOT_ORDER",
    "RARITY_BACKGROUNDS",
    "VALID_GEAR_SLOTS",
    "normalize_gear_id",
    "normalize_gear_slot",
    "resolve_gear",
]

