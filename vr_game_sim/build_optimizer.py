"""Army build optimisation helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import copy
import os
import threading
from itertools import combinations, product
from typing import Any, Optional

from .enums import SkillType
from .hero_definition import HERO_PRESETS
from .skill_definitions import SKILL_REGISTRY_GLOBAL


def _normalise_entries(values: Iterable[str] | None) -> list[str]:
    """Return a cleaned list of lowercase strings from ``values``."""

    entries: list[str] = []
    if not values:
        return entries
    for value in values:
        if not value:
            continue
        for part in str(value).split(","):
            item = part.strip()
            if item:
                entries.append(item.lower())
    return entries


def _collect_hero_candidates(setup_data: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build a mapping of candidate hero configurations by lowercase name."""

    candidates: dict[str, dict[str, Any]] = {}
    for army in setup_data:
        for hero_cfg in army.get("heroes", []):
            name = hero_cfg.get("hero_name_or_preset")
            if not name:
                continue
            candidates[name.lower()] = copy.deepcopy(hero_cfg)

    for name, preset in HERO_PRESETS.items():
        if name in candidates:
            continue
        candidates[name] = {
            "hero_name_or_preset": name.capitalize(),
            "talent_ids": list(preset.get("talents", [])),
            "base_skill_ids": list(preset.get("base_skills", [])),
            "plugin_skill_ids": list(preset.get("plugin_skills", [])),
        }
    return candidates


def _collect_plugin_candidates(blocked_plugins: set[str]) -> list[str]:
    """Return plugin skill ids that are not blocked."""

    candidates: list[str] = []
    for skill_id, definition in SKILL_REGISTRY_GLOBAL.items():
        if definition.get("type") != SkillType.PLUGIN_SKILL:
            continue
        if skill_id.lower() in blocked_plugins:
            continue
        candidates.append(skill_id)
    candidates.sort()
    return candidates


def recommend_army1_build(
    setup_data: list[dict[str, Any]],
    *,
    blocked_heroes: Iterable[str] | None = None,
    blocked_plugins: Iterable[str] | None = None,
    runs: int | None = None,
    num_workers: int | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
    cancel_event: Optional[threading.Event] = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Recommend a hero/plugin configuration for Army 1.

    Parameters
    ----------
    setup_data:
        Current battle configuration. The structure matches the JSON saved by
        :func:`vr_game_sim.main.get_setup_data_for_saving`.
    blocked_heroes:
        Optional iterable of hero names to exclude (case-insensitive).
    blocked_plugins:
        Optional iterable of plugin skill ids to exclude (case-insensitive).
    runs:
        Number of simulations per candidate. Defaults to the standard
        "Additional Runs" value of 300.
    num_workers:
        Process count supplied to :func:`run_additional_simulations`. Defaults
        to ``os.cpu_count()``.
    progress_callback:
        Invoked after each evaluated candidate with ``(completed, total)``.
    cancel_event:
        When supplied and set, stops the search early by raising
        ``RuntimeError('cancelled')``.

    Returns
    -------
    tuple
        ``(setup, info)`` where ``setup`` mirrors the input with Army 1 heroes
        updated and ``info`` includes the projected win rate.

    Raises
    ------
    ValueError
        If Army 1 already has both hero slots filled with fully populated
        plugins or if no valid candidate combination exists.
    RuntimeError
        Propagated when ``cancel_event`` is set during evaluation.
    """

    if not setup_data:
        raise ValueError("Setup must contain at least one army")

    army1_original = setup_data[0]
    base_setup = copy.deepcopy(setup_data)
    army1 = base_setup[0]

    heroes = [copy.deepcopy(hero) for hero in army1.get("heroes", [])[:2]]
    while len(heroes) < 2:
        heroes.append(None)

    has_empty_slot = any(hero is None for hero in heroes)
    plugin_gaps = False
    for hero in heroes:
        if not hero:
            continue
        seen_plugin_ids: set[str] = set()
        plugins: list[str] = []
        for pid in hero.get("plugin_skill_ids", []):
            if not pid:
                continue
            pid_lower = pid.lower()
            if pid_lower in seen_plugin_ids:
                continue
            seen_plugin_ids.add(pid_lower)
            plugins.append(pid)
        plugins = plugins[:2]
        if len(plugins) < 2:
            plugin_gaps = True
        hero["plugin_skill_ids"] = plugins[:2]

    if not has_empty_slot and not plugin_gaps:
        raise ValueError("Army 1 already has both heroes and plugins assigned")

    existing_hero_names_lower = {
        hero.get("hero_name_or_preset", "").strip().lower()
        for hero in heroes
        if hero and hero.get("hero_name_or_preset")
    }

    blocked_hero_set = set(_normalise_entries(blocked_heroes))
    blocked_plugin_set = set(_normalise_entries(blocked_plugins))

    hero_candidates = _collect_hero_candidates(setup_data)
    for blocked in blocked_hero_set:
        hero_candidates.pop(blocked, None)

    runs = runs or 300
    if runs <= 0:
        raise ValueError("Runs must be a positive integer")
    num_workers = num_workers or (os.cpu_count() or 1)
    if num_workers <= 0:
        raise ValueError("Worker count must be a positive integer")

    plugin_candidates = _collect_plugin_candidates(blocked_plugin_set)

    slot_candidates: list[list[dict[str, Any]]] = []
    for hero in heroes:
        if hero is not None:
            slot_candidates.append([hero])
            continue
        options = [
            copy.deepcopy(cfg)
            for name, cfg in hero_candidates.items()
            if name not in existing_hero_names_lower
        ]
        if not options:
            raise ValueError("No admissible heroes remain for empty slots")
        slot_candidates.append(options)

    unique_candidates: list[tuple[dict[str, Any], ...]] = []
    seen_keys: set[tuple[tuple[str, tuple[str, ...]], ...]] = set()

    for hero_choice in product(*slot_candidates):
        hero_assignment = [copy.deepcopy(hero) for hero in hero_choice]

        seen_hero_names: set[str] = set()
        duplicate_hero = False
        for hero_cfg in hero_assignment:
            if not hero_cfg:
                continue
            name = hero_cfg.get("hero_name_or_preset", "")
            if not name:
                continue
            name_key = name.strip().lower()
            if name_key in seen_hero_names:
                duplicate_hero = True
                break
            seen_hero_names.add(name_key)
        if duplicate_hero:
            continue

        plugin_option_sets: list[list[list[str]]] = []
        assignment_invalid = False
        for hero_cfg in hero_assignment:
            seen_plugin_ids: set[str] = set()
            plugins: list[str] = []
            for pid in hero_cfg.get("plugin_skill_ids", []):
                if not pid:
                    continue
                pid_lower = pid.lower()
                if pid_lower in seen_plugin_ids:
                    continue
                seen_plugin_ids.add(pid_lower)
                plugins.append(pid)
            plugins = plugins[:2]
            needed = 2 - len(plugins)
            if needed < 0:
                needed = 0
            if needed == 0:
                plugin_option_sets.append([plugins])
                continue
            if not plugin_candidates:
                raise ValueError("No plugin skills available to fill empty slots")
            available_candidates = [
                pid
                for pid in plugin_candidates
                if pid.lower() not in seen_plugin_ids
            ]
            if len(available_candidates) < needed:
                assignment_invalid = True
                break
            options: list[list[str]] = []
            for combo in combinations(available_candidates, needed):
                option = plugins + list(combo)
                options.append(option)
            plugin_option_sets.append(options)
        if assignment_invalid:
            continue

        for plugin_choice in product(*plugin_option_sets):
            populated: list[dict[str, Any]] = []
            invalid = False
            used_plugin_ids: set[str] = set()
            for hero_cfg, plugin_ids in zip(hero_assignment, plugin_choice):
                if blocked_plugin_set and any(
                    pid.lower() in blocked_plugin_set for pid in plugin_ids
                ):
                    invalid = True
                    break
                for pid in plugin_ids:
                    pid_lower = pid.lower()
                    if pid_lower in used_plugin_ids:
                        invalid = True
                        break
                    used_plugin_ids.add(pid_lower)
                if invalid:
                    break
                hero_copy = copy.deepcopy(hero_cfg)
                hero_copy["plugin_skill_ids"] = list(plugin_ids)
                populated.append(hero_copy)
            if invalid:
                continue

            key = tuple(
                (
                    hero_cfg.get("hero_name_or_preset", "").lower(),
                    tuple(sorted(pid for pid in hero_cfg.get("plugin_skill_ids", []) if pid)),
                )
                for hero_cfg in populated
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_candidates.append(tuple(populated))

    if not unique_candidates:
        raise ValueError("No valid hero/plugin combinations found for recommendation")

    from .main import run_simulations_basic_with_cutoff

    best_setup: list[dict[str, Any]] | None = None
    best_win_rate = -1.0
    for idx, hero_tuple in enumerate(unique_candidates, start=1):
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("cancelled")

        candidate_setup = copy.deepcopy(base_setup)
        candidate_setup[0]["heroes"] = [copy.deepcopy(hero_cfg) for hero_cfg in hero_tuple]

        completed_runs = 0
        wins_army1 = 0

        def _should_stop(
            completed: int, total: int, result
        ) -> bool:
            if total <= 0:
                return False
            remaining = total - completed
            wins_so_far = result.wins_army1
            best_case = (wins_so_far + remaining) / total
            return best_case <= best_win_rate

        for completed_runs, aggregate_result in run_simulations_basic_with_cutoff(
            candidate_setup,
            runs,
            num_workers=num_workers,
            progress_callback=None,
            should_stop=_should_stop,
        ):
            wins_army1 = aggregate_result.wins_army1

        if progress_callback:
            progress_callback(idx, len(unique_candidates))

        win_rate = wins_army1 / runs if runs else 0.0

        if completed_runs < runs:
            continue

        if win_rate > best_win_rate:
            best_win_rate = win_rate
            best_setup = candidate_setup

    if best_setup is None:
        raise ValueError("No winning configuration identified")

    info = {
        "win_rate": best_win_rate,
        "evaluations": len(unique_candidates),
        "runs": runs,
        "num_workers": num_workers,
        "heroes": copy.deepcopy(best_setup[0].get("heroes", [])),
    }
    return best_setup, info

