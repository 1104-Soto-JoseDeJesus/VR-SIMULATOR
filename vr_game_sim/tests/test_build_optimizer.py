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
    ) -> BasicSimulationResult:
        hero = sim_setup[0]["heroes"][0]
        assert hero["plugin_skill_ids"][0] == "plugin_existing"
        calls.append(copy.deepcopy(hero["plugin_skill_ids"]))
        if progress_callback:
            progress_callback(runs, runs)
        return BasicSimulationResult(0, 0)

    monkeypatch.setattr(
        "vr_game_sim.main.run_simulations_basic",
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
            "heroes": [],
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
    ) -> BasicSimulationResult:
        heroes = sim_setup[0]["heroes"]
        assert all(hero["hero_name_or_preset"].lower() != "alpha" for hero in heroes)
        assert all(
            "plugin_blocked" not in hero.get("plugin_skill_ids", []) for hero in heroes
        )
        if progress_callback:
            progress_callback(runs, runs)
        return BasicSimulationResult(runs, 0)

    monkeypatch.setattr(
        "vr_game_sim.main.run_simulations_basic",
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
    ) -> BasicSimulationResult:
        nonlocal evaluations
        evaluations += 1
        if progress_callback:
            progress_callback(runs, runs)
        return BasicSimulationResult(evaluations, 0)

    monkeypatch.setattr(
        "vr_game_sim.main.run_simulations_basic",
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
    ) -> BasicSimulationResult:
        nonlocal called
        called += 1
        assert sim_setup[0]["heroes"], "expected hero configuration"
        if progress_callback:
            progress_callback(runs, runs)
        return BasicSimulationResult(runs, 0)

    def fail_if_called(*_: Any, **__: Any) -> None:
        raise AssertionError("fast helper should handle simulations")

    monkeypatch.setattr("vr_game_sim.main.run_simulations_basic", fake_basic, raising=False)
    monkeypatch.setattr("vr_game_sim.main._run_single_battle", fail_if_called, raising=False)

    build_optimizer.recommend_army1_build(setup, runs=2, num_workers=1)
    assert called > 0
