"""Utilities for recommending army builds based on simulated matchups."""

from __future__ import annotations

import copy
import itertools
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .enums import SkillType
from .hero_definition import HERO_PRESETS
from .skill_system import SkillDefinition

MAX_PLUGIN_POOL = 8


def _normalise_plugin_list(plugins: Sequence[str]) -> List[str]:
    """Return a list of plugin ids trimmed of trailing empty slots."""

    cleaned = [sid for sid in plugins if sid]
    return cleaned


def _plugin_candidates(
    skill_registry: Dict[str, SkillDefinition],
    blocked_plugins: Optional[Sequence[str]] = None,
) -> List[str]:
    """Return a deterministic list of plugin skill ids to consider."""

    blocked_set = {pid for pid in blocked_plugins or [] if pid}
    candidates = [
        sid
        for sid, skill in skill_registry.items()
        if skill.get("type") == SkillType.PLUGIN_SKILL and sid not in blocked_set
    ]
    candidates.sort()
    return candidates[:MAX_PLUGIN_POOL]


def _build_plugin_variants(
    preset_plugins: Sequence[str],
    plugin_pool: Sequence[str],
    blocked_plugins: Optional[Sequence[str]] = None,
) -> List[Tuple[str, str]]:
    """Create plugin slot combinations to evaluate for a hero.

    Variants include the preset configuration as well as permutations of one or
    two plugins taken from ``plugin_pool``.  The returned tuples always contain
    exactly two entries representing the two plugin slots (empty strings denote
    unused slots).
    """

    blocked_set = {pid for pid in blocked_plugins or [] if pid}

    preset_pair = tuple((list(preset_plugins) + ["", ""])[:2])
    variants: set[Tuple[str, str]] = {("", "")}
    if not any(pid in blocked_set for pid in preset_pair if pid):
        variants.add(preset_pair)

    available_plugins = []
    for plugin_id in plugin_pool:
        if plugin_id in blocked_set:
            continue
        available_plugins.append(plugin_id)
        variants.add((plugin_id, ""))
        variants.add((plugin_id, plugin_id))

    for first_id, second_id in itertools.combinations(available_plugins, 2):
        variants.add((first_id, second_id))

    return sorted(variants)


def _hero_variants(
    hero_key: str,
    plugin_pool: Sequence[str],
    *,
    blocked_plugins: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """Return candidate hero configurations for a given preset hero."""

    preset = HERO_PRESETS.get(hero_key)
    if not preset:
        return []

    talents = list(preset.get("talents", []))
    base_skills = list(preset.get("base_skills", []))
    plugin_variants = _build_plugin_variants(
        preset.get("plugin_skills", []), plugin_pool, blocked_plugins
    )

    configs: list[dict[str, Any]] = []
    for plugins in plugin_variants:
        cfg = {
            "hero_name_or_preset": hero_key.capitalize(),
            "talent_ids": talents,
            "base_skill_ids": base_skills,
            "plugin_skill_ids": _normalise_plugin_list(plugins),
        }
        if blocked_plugins and any(pid in blocked_plugins for pid in cfg["plugin_skill_ids"]):
            continue
        configs.append(cfg)
    return configs


def _unique_candidate_key(heroes: Sequence[Dict[str, Any]]) -> Tuple:
    """Return a hashable representation for deduplicating hero sets."""

    canonical: list[tuple] = []
    for hero_cfg in heroes:
        canonical.append(
            (
                hero_cfg.get("hero_name_or_preset", ""),
                tuple(hero_cfg.get("talent_ids", [])),
                tuple(hero_cfg.get("base_skill_ids", [])),
                tuple(hero_cfg.get("plugin_skill_ids", [])),
            )
        )
    return tuple(canonical)


def recommend_build_for_matchup(
    own_setup: Dict[str, Any],
    opponent_setup: Dict[str, Any],
    skill_registry: Dict[str, SkillDefinition],
    *,
    runs: int = 60,
) -> Optional[Dict[str, Any]]:
    """Return the highest win-rate hero configuration for ``own_setup``.

    The helper evaluates combinations of hero presets and plugin skill
    selections pulled from ``HERO_PRESETS`` and ``skill_registry``.  Each
    candidate is simulated against ``opponent_setup`` using
    :func:`run_additional_simulations`.  The candidate yielding the highest win
    rate for the first army is returned along with metadata describing the
    evaluation process.
    """

    if not own_setup or not opponent_setup:
        return None

    base_setup = copy.deepcopy(own_setup)
    existing_heroes_raw = base_setup.get("heroes") or []
    locked_heroes: list[dict[str, Any]] = []
    for hero_cfg in existing_heroes_raw:
        if not hero_cfg:
            continue
        locked_heroes.append(copy.deepcopy(hero_cfg))
    base_setup["heroes"] = locked_heroes

    blocked_heroes = {
        str(name).lower()
        for name in base_setup.get("blocked_heroes", [])
        if isinstance(name, str) and name
    }
    blocked_plugins = {
        str(pid)
        for pid in base_setup.get("blocked_plugin_skills", [])
        if isinstance(pid, str) and pid
    }

    blocked_plugins_list = tuple(sorted(blocked_plugins))

    plugin_pool = _plugin_candidates(skill_registry, blocked_plugins_list)

    hero_keys = sorted(HERO_PRESETS.keys())
    hero_variants_map: dict[str, list[dict[str, Any]]] = {}
    for hero_key in hero_keys:
        if hero_key in blocked_heroes:
            continue
        hero_variants_map[hero_key] = _hero_variants(
            hero_key, plugin_pool, blocked_plugins=blocked_plugins_list
        )

    target_slots = max(len(locked_heroes), 2)
    open_slots = max(0, target_slots - len(locked_heroes))

    variant_options: list[Optional[dict[str, Any]]] = [None]
    for hero_key in hero_keys:
        variant_options.extend(hero_variants_map.get(hero_key, []))

    evaluated = 0
    best_win_rate = float("-inf")
    best_config: Optional[dict[str, Any]] = None
    best_metadata: Optional[dict[str, Any]] = None

    seen: set[Tuple] = set()

    opponent_cfg = copy.deepcopy(opponent_setup)

    from .main import run_additional_simulations  # Local import to avoid circular dependency

    if open_slots:
        combinations_iter = itertools.combinations_with_replacement(
            variant_options, open_slots
        )
    else:
        combinations_iter = [()]

    for combo in combinations_iter:
        heroes: list[dict[str, Any]] = [copy.deepcopy(hero) for hero in locked_heroes]
        for variant in combo:
            if variant:
                heroes.append(copy.deepcopy(variant))

        key = _unique_candidate_key(heroes)
        if key in seen:
            continue
        seen.add(key)

        candidate_setup = copy.deepcopy(base_setup)
        candidate_setup["heroes"] = heroes

        try:
            win_rate, metadata = run_additional_simulations(
                [candidate_setup, opponent_cfg],
                runs=runs,
                generate_histograms=False,
                verbose=False,
                num_workers=1,
            )
        except Exception:  # pragma: no cover - bubbled up to caller
            continue

        evaluated += 1
        if win_rate > best_win_rate:
            best_win_rate = win_rate
            best_config = candidate_setup
            best_metadata = metadata or {}

    if best_config is None:
        return None

    result = {
        "config": best_config,
        "win_rate": best_win_rate,
        "metadata": best_metadata or {},
        "evaluated_candidates": evaluated,
        "runs": runs,
    }
    return result

