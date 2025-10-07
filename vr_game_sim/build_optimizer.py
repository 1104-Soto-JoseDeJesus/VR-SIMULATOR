"""Army build optimisation helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import copy
import os
import threading
from itertools import combinations_with_replacement, product
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
        plugins = [pid for pid in hero.get("plugin_skill_ids", []) if pid]
        if len(plugins) < 2:
            plugin_gaps = True
        hero["plugin_skill_ids"] = plugins[:2]

    if not has_empty_slot and not plugin_gaps:
        raise ValueError("Army 1 already has both heroes and plugins assigned")

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
        options = [copy.deepcopy(cfg) for cfg in hero_candidates.values()]
        if not options:
            raise ValueError("No admissible heroes remain for empty slots")
        slot_candidates.append(options)

    def _prepare_plugin_option_sets(
        hero_assignment: list[dict[str, Any]],
    ) -> list[list[list[str]]] | None:
        plugin_option_sets: list[list[list[str]]] = []
        for hero_cfg in hero_assignment:
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("cancelled")

            plugins = [pid for pid in hero_cfg.get("plugin_skill_ids", []) if pid][:2]
            if blocked_plugin_set and any(pid.lower() in blocked_plugin_set for pid in plugins):
                return None

            needed = 2 - len(plugins)
            if needed <= 0:
                plugin_option_sets.append([list(plugins)])
                continue

            if not plugin_candidates:
                raise ValueError("No plugin skills available to fill empty slots")

            options: list[list[str]] = []
            for combo in combinations_with_replacement(plugin_candidates, needed):
                option = list(plugins) + list(combo)
                option = option[:2]
                if blocked_plugin_set and any(
                    pid.lower() in blocked_plugin_set for pid in option
                ):
                    continue
                options.append(option)

            if not options:
                return None

            plugin_option_sets.append(options)

        return plugin_option_sets

    def _estimate_candidate_total() -> int:
        total = 0
        for hero_choice in product(*slot_candidates):
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("cancelled")

            hero_assignment = [copy.deepcopy(hero) for hero in hero_choice]
            plugin_option_sets = _prepare_plugin_option_sets(hero_assignment)
            if not plugin_option_sets:
                continue

            combos = 1
            for options in plugin_option_sets:
                combos *= len(options)
            total += combos

        return total

    seen_keys: set[tuple[tuple[str, tuple[str, ...]], ...]] = set()

    def _iter_candidate_setups() -> Iterable[tuple[dict[str, Any], ...]]:
        for hero_choice in product(*slot_candidates):
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("cancelled")

            hero_assignment = [copy.deepcopy(hero) for hero in hero_choice]
            plugin_option_sets = _prepare_plugin_option_sets(hero_assignment)
            if not plugin_option_sets:
                continue

            for plugin_choice in product(*plugin_option_sets):
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError("cancelled")

                populated: list[dict[str, Any]] = []
                for hero_cfg, plugin_ids in zip(hero_assignment, plugin_choice):
                    hero_copy = copy.deepcopy(hero_cfg)
                    hero_copy["plugin_skill_ids"] = list(plugin_ids)
                    populated.append(hero_copy)

                key = tuple(
                    (
                        hero_cfg.get("hero_name_or_preset", "").lower(),
                        tuple(sorted(
                            pid for pid in hero_cfg.get("plugin_skill_ids", []) if pid
                        )),
                    )
                    for hero_cfg in populated
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                yield tuple(populated)

    estimated_total = _estimate_candidate_total()

    candidates_iter = _iter_candidate_setups()
    total_candidates = 0

    from .main import run_additional_simulations

    best_setup: list[dict[str, Any]] | None = None
    best_win_rate = -1.0
    for idx, hero_tuple in enumerate(candidates_iter, start=1):
        total_candidates = idx
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("cancelled")

        candidate_setup = copy.deepcopy(base_setup)
        candidate_setup[0]["heroes"] = [copy.deepcopy(hero_cfg) for hero_cfg in hero_tuple]

        win_rate, _ = run_additional_simulations(
            candidate_setup,
            runs=runs,
            verbose=False,
            generate_histograms=False,
            num_workers=num_workers,
        )

        if progress_callback:
            progress_callback(idx, max(estimated_total, idx))

        if win_rate > best_win_rate:
            best_win_rate = win_rate
            best_setup = candidate_setup

    if total_candidates == 0:
        raise ValueError("No valid hero/plugin combinations found for recommendation")

    if best_setup is None:
        raise ValueError("No winning configuration identified")

    if progress_callback and total_candidates != max(estimated_total, total_candidates):
        progress_callback(total_candidates, total_candidates)

    info = {
        "win_rate": best_win_rate,
        "evaluations": total_candidates,
        "runs": runs,
        "num_workers": num_workers,
        "heroes": copy.deepcopy(best_setup[0].get("heroes", [])),
    }
    return best_setup, info

