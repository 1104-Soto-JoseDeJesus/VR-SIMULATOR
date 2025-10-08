import copy
from typing import Any

import pytest

from vr_game_sim import build_optimizer
from vr_game_sim.enums import SkillType
from vr_game_sim.main import BasicSimulationResult


def _plugin_def(skill_id: str) -> dict[str, Any]:
    return {"id": skill_id, "type": SkillType.PLUGIN_SKILL}


def test_recommendation_preserves_existing_plugins(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = [
        {
            "army_name": "Army 1",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 1,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [
                {
                    "hero_name_or_preset": "Alpha",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_existing"],
                }
            ],
        },
        {"army_name": "Army 2", "heroes": []},
    ]

    monkeypatch.setattr(
        build_optimizer,
        "HERO_PRESETS",
        {
            "alpha": {"talents": [], "base_skills": [], "plugin_skills": []},
            "beta": {"talents": [], "base_skills": [], "plugin_skills": []},
            "gamma": {"talents": [], "base_skills": [], "plugin_skills": []},
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_existing": _plugin_def("plugin_existing"),
            "plugin_new": _plugin_def("plugin_new"),
            "plugin_extra_a": _plugin_def("plugin_extra_a"),
            "plugin_extra_b": _plugin_def("plugin_extra_b"),
        },
        raising=False,
    )

    calls: list[list[str]] = []

    def fake_run_basic(
        sim_setup: list[dict[str, Any]],
        runs: int,
        *,
        num_workers: int = 1,
        progress_callback: Any | None = None,
        should_stop: Any | None = None,
    ):
        hero = sim_setup[0]["heroes"][0]
        assert hero["plugin_skill_ids"][0] == "plugin_existing"
        calls.append(copy.deepcopy(hero["plugin_skill_ids"]))
        for completed in range(1, runs + 1):
            if progress_callback:
                progress_callback(completed, runs)
            result = BasicSimulationResult(0, 0)
            stop = should_stop(completed, runs, result) if should_stop else False
            yield completed, result
            if stop:
                break

    monkeypatch.setattr(
        "vr_game_sim.main.run_simulations_basic_with_cutoff",
        fake_run_basic,
        raising=False,
    )

    build_optimizer.recommend_army1_build(setup, runs=1, num_workers=1)
    assert calls, "expected at least one simulation"


def test_block_lists_skip_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = [
        {
            "army_name": "Army 1",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 1,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [
                {
                    "hero_name_or_preset": "Existing",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_existing_a", "plugin_existing_b"],
                }
            ],
        },
        {"army_name": "Army 2", "heroes": []},
    ]

    monkeypatch.setattr(
        build_optimizer,
        "HERO_PRESETS",
        {
            "alpha": {"talents": [], "base_skills": [], "plugin_skills": []},
            "beta": {"talents": [], "base_skills": [], "plugin_skills": []},
            "gamma": {"talents": [], "base_skills": [], "plugin_skills": []},
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_allowed": _plugin_def("plugin_allowed"),
            "plugin_blocked": _plugin_def("plugin_blocked"),
            "plugin_extra_a": _plugin_def("plugin_extra_a"),
            "plugin_extra_b": _plugin_def("plugin_extra_b"),
            "plugin_extra_c": _plugin_def("plugin_extra_c"),
            "plugin_extra_d": _plugin_def("plugin_extra_d"),
        },
        raising=False,
    )

    def fake_run_basic(
        sim_setup: list[dict[str, Any]],
        runs: int,
        *,
        num_workers: int = 1,
        progress_callback: Any | None = None,
        should_stop: Any | None = None,
    ):
        heroes = sim_setup[0]["heroes"]
        assert all(hero["hero_name_or_preset"].lower() != "alpha" for hero in heroes)
        assert all(
            "plugin_blocked" not in hero.get("plugin_skill_ids", []) for hero in heroes
        )
        for completed in range(1, runs + 1):
            if progress_callback:
                progress_callback(completed, runs)
            result = BasicSimulationResult(runs, 0)
            stop = should_stop(completed, runs, result) if should_stop else False
            yield completed, result
            if stop:
                break

    monkeypatch.setattr(
        "vr_game_sim.main.run_simulations_basic_with_cutoff",
        fake_run_basic,
        raising=False,
    )

    build_optimizer.recommend_army1_build(
        setup,
        blocked_heroes=["alpha"],
        blocked_plugins=["plugin_blocked"],
        runs=1,
        num_workers=1,
    )


def test_plugin_permutations_evaluated_once(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = [
        {
            "army_name": "Army 1",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 1,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [
                {
                    "hero_name_or_preset": "Alpha",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": [],
                },
                {
                    "hero_name_or_preset": "Beta",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_existing", "plugin_other"],
                },
            ],
        },
        {"army_name": "Army 2", "heroes": []},
    ]

    monkeypatch.setattr(
        build_optimizer,
        "HERO_PRESETS",
        {
            "alpha": {"talents": [], "base_skills": [], "plugin_skills": []},
            "beta": {"talents": [], "base_skills": [], "plugin_skills": []},
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_x": _plugin_def("plugin_x"),
            "plugin_y": _plugin_def("plugin_y"),
            "plugin_z": _plugin_def("plugin_z"),
        },
        raising=False,
    )

    evaluations = 0

    def fake_run_basic(
        _: list[dict[str, Any]],
        runs: int,
        *,
        num_workers: int = 1,
        progress_callback: Any | None = None,
        should_stop: Any | None = None,
    ):
        nonlocal evaluations
        evaluations += 1
        for completed in range(1, runs + 1):
            if progress_callback:
                progress_callback(completed, runs)
            result = BasicSimulationResult(evaluations, 0)
            stop = should_stop(completed, runs, result) if should_stop else False
            yield completed, result
            if stop:
                break

    monkeypatch.setattr(
        "vr_game_sim.main.run_simulations_basic_with_cutoff",
        fake_run_basic,
        raising=False,
    )

    build_optimizer.recommend_army1_build(setup, runs=1, num_workers=1)
    assert evaluations == 3


def test_recommendation_requires_empty_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = [
        {
            "army_name": "Army 1",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 1,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [
                {
                    "hero_name_or_preset": "Alpha",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_existing", "plugin_other"],
                },
                {
                    "hero_name_or_preset": "Beta",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_existing", "plugin_other"],
                },
            ],
        },
        {"army_name": "Army 2", "heroes": []},
    ]

    monkeypatch.setattr(
        build_optimizer,
        "HERO_PRESETS",
        {
            "alpha": {"talents": [], "base_skills": [], "plugin_skills": []},
            "beta": {"talents": [], "base_skills": [], "plugin_skills": []},
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_existing": _plugin_def("plugin_existing"),
            "plugin_other": _plugin_def("plugin_other"),
        },
        raising=False,
    )

    with pytest.raises(ValueError):
        build_optimizer.recommend_army1_build(setup, runs=1, num_workers=1)


def test_recommendation_uses_basic_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = [
        {
            "army_name": "Army 1",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 1,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [
                {
                    "hero_name_or_preset": "Alpha",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_existing"],
                },
                {
                    "hero_name_or_preset": "Beta",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": [],
                },
            ],
        },
        {"army_name": "Army 2", "heroes": []},
    ]

    monkeypatch.setattr(
        build_optimizer,
        "HERO_PRESETS",
        {
            "alpha": {"talents": [], "base_skills": [], "plugin_skills": ["plugin_existing"]},
            "beta": {"talents": [], "base_skills": [], "plugin_skills": []},
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_existing": _plugin_def("plugin_existing"),
            "plugin_x": _plugin_def("plugin_x"),
            "plugin_y": _plugin_def("plugin_y"),
            "plugin_z": _plugin_def("plugin_z"),
        },
        raising=False,
    )

    called = 0

    def fake_basic(
        sim_setup: list[dict[str, Any]],
        runs: int,
        *,
        num_workers: int = 1,
        progress_callback: Any | None = None,
        should_stop: Any | None = None,
    ):
        nonlocal called
        called += 1
        assert sim_setup[0]["heroes"], "expected hero configuration"
        for completed in range(1, runs + 1):
            if progress_callback:
                progress_callback(completed, runs)
            result = BasicSimulationResult(runs, 0)
            stop = should_stop(completed, runs, result) if should_stop else False
            yield completed, result
            if stop:
                break

    def fail_if_called(*_: Any, **__: Any) -> None:
        raise AssertionError("slow helper should not run")

    monkeypatch.setattr("vr_game_sim.main.run_simulations_basic_with_cutoff", fake_basic, raising=False)
    monkeypatch.setattr("vr_game_sim.main.run_additional_simulations", fail_if_called, raising=False)

    build_optimizer.recommend_army1_build(setup, runs=2, num_workers=1)
    assert called > 0


def test_candidate_with_low_best_case_stops_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setup = [
        {
            "army_name": "Army 1",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 1,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [
                {
                    "hero_name_or_preset": "Existing",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_existing_a", "plugin_existing_b"],
                }
            ],
        },
        {"army_name": "Army 2", "heroes": []},
    ]

    monkeypatch.setattr(
        build_optimizer,
        "HERO_PRESETS",
        {
            "existing": {
                "talents": [],
                "base_skills": [],
                "plugin_skills": ["plugin_existing_a", "plugin_existing_b"],
            },
            "alpha": {
                "talents": [],
                "base_skills": [],
                "plugin_skills": ["plugin_a1", "plugin_a2"],
            },
            "beta": {
                "talents": [],
                "base_skills": [],
                "plugin_skills": ["plugin_b1", "plugin_b2"],
            },
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_existing_a": _plugin_def("plugin_existing_a"),
            "plugin_existing_b": _plugin_def("plugin_existing_b"),
            "plugin_a1": _plugin_def("plugin_a1"),
            "plugin_a2": _plugin_def("plugin_a2"),
            "plugin_b1": _plugin_def("plugin_b1"),
            "plugin_b2": _plugin_def("plugin_b2"),
        },
        raising=False,
    )

    outcomes = {
        "Alpha": [1, 1, 0, 1],  # 3 wins from 4 simulations -> 0.75 win rate
        "Beta": [2, 2, 2, 2],  # Always loses so best case never exceeds incumbent
    }
    history: dict[str, list[int]] = {}

    def fake_helper(
        sim_setup: list[dict[str, Any]],
        runs: int,
        *,
        num_workers: int = 1,
        progress_callback: Any | None = None,
        should_stop: Any | None = None,
    ):
        hero_name = sim_setup[0]["heroes"][1]["hero_name_or_preset"]
        outcome_sequence = outcomes[hero_name]
        assert runs == len(outcome_sequence)
        wins = 0
        draws = 0
        hero_history = history.setdefault(hero_name, [])
        for completed, winner in enumerate(outcome_sequence, start=1):
            if winner == 1:
                wins += 1
            elif winner == 0:
                draws += 1
            result = BasicSimulationResult(wins, draws)
            hero_history.append(completed)
            if progress_callback:
                progress_callback(completed, runs)
            stop = should_stop(completed, runs, result) if should_stop else False
            yield completed, result
            if stop:
                break

    monkeypatch.setattr(
        "vr_game_sim.main.run_simulations_basic_with_cutoff",
        fake_helper,
        raising=False,
    )

    candidate_progress: list[tuple[int, int]] = []

    best_setup, info = build_optimizer.recommend_army1_build(
        setup,
        runs=4,
        num_workers=1,
        progress_callback=lambda completed, total: candidate_progress.append((completed, total)),
    )

    assert best_setup[0]["heroes"][1]["hero_name_or_preset"] == "Alpha"
    assert info["win_rate"] == pytest.approx(0.75)
    assert history["Alpha"] == [1, 2, 3, 4]
    assert history["Beta"] == [1]
    assert candidate_progress == [(1, 2), (2, 2)]


def test_preferred_candidate_runs_first(monkeypatch: pytest.MonkeyPatch) -> None:
    setup = [
        {
            "army_name": "Army 1",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 1,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [
                {
                    "hero_name_or_preset": "Gamma",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_lock_a", "plugin_lock_b"],
                }
            ],
            "optimizer_guess_slots": [0],
            "optimizer_preferred_assignment": [
                {
                    "slot_index": 0,
                    "hero_name_or_preset": "Alpha",
                    "talent_ids": [],
                    "base_skill_ids": [],
                    "plugin_skill_ids": ["plugin_guess_a", "plugin_guess_b"],
                }
            ],
        },
        {"army_name": "Army 2", "heroes": []},
    ]

    monkeypatch.setattr(
        build_optimizer,
        "HERO_PRESETS",
        {
            "alpha": {
                "talents": [],
                "base_skills": [],
                "plugin_skills": ["plugin_guess_a", "plugin_guess_b"],
            },
            "beta": {
                "talents": [],
                "base_skills": [],
                "plugin_skills": ["plugin_alt_a", "plugin_alt_b"],
            },
            "gamma": {
                "talents": [],
                "base_skills": [],
                "plugin_skills": ["plugin_lock_a", "plugin_lock_b"],
            },
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_guess_a": _plugin_def("plugin_guess_a"),
            "plugin_guess_b": _plugin_def("plugin_guess_b"),
            "plugin_alt_a": _plugin_def("plugin_alt_a"),
            "plugin_alt_b": _plugin_def("plugin_alt_b"),
            "plugin_lock_a": _plugin_def("plugin_lock_a"),
            "plugin_lock_b": _plugin_def("plugin_lock_b"),
        },
        raising=False,
    )

    calls: list[tuple[str, ...]] = []
    stop_flags: list[tuple[tuple[str, ...], int, bool]] = []

    def fake_run_basic(
        sim_setup: list[dict[str, Any]],
        runs: int,
        *,
        num_workers: int = 1,
        progress_callback: Any | None = None,
        should_stop: Any | None = None,
    ):
        hero_names = tuple(
            hero.get("hero_name_or_preset", "") for hero in sim_setup[0].get("heroes", [])
        )
        calls.append(hero_names)
        for completed in range(1, runs + 1):
            if progress_callback:
                progress_callback(completed, runs)
            wins = completed if hero_names and hero_names[0] == "Alpha" else 0
            result = BasicSimulationResult(wins, 0)
            stop = should_stop(completed, runs, result) if should_stop else False
            stop_flags.append((hero_names, completed, stop))
            yield completed, result
            if stop:
                break

    monkeypatch.setattr(
        "vr_game_sim.main.run_simulations_basic_with_cutoff",
        fake_run_basic,
        raising=False,
    )

    best_setup, info = build_optimizer.recommend_army1_build(
        setup,
        runs=3,
        num_workers=1,
    )

    assert calls, "expected simulations to run"
    assert calls[0] == ("Alpha", "Gamma")
    assert any("Beta" in names for names in calls)
    assert any(
        "Beta" in names and stop for names, _, stop in stop_flags
    ), "expected beta candidate to stop early"
    assert best_setup[0]["heroes"][0]["hero_name_or_preset"] == "Alpha"
