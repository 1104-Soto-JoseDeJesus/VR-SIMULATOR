import copy
from typing import Any

import pytest

from vr_game_sim import build_optimizer
from vr_game_sim.enums import SkillType


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
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_existing": _plugin_def("plugin_existing"),
            "plugin_new": _plugin_def("plugin_new"),
        },
        raising=False,
    )

    calls: list[list[str]] = []

    def fake_run_additional(sim_setup: list[dict[str, Any]], **_: Any) -> tuple[float, None]:
        hero = sim_setup[0]["heroes"][0]
        assert hero["plugin_skill_ids"][0] == "plugin_existing"
        calls.append(copy.deepcopy(hero["plugin_skill_ids"]))
        return 0.5, None

    monkeypatch.setattr(
        "vr_game_sim.main.run_additional_simulations",
        fake_run_additional,
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
        },
        raising=False,
    )
    monkeypatch.setattr(
        build_optimizer,
        "SKILL_REGISTRY_GLOBAL",
        {
            "plugin_allowed": _plugin_def("plugin_allowed"),
            "plugin_blocked": _plugin_def("plugin_blocked"),
        },
        raising=False,
    )

    def fake_run_additional(sim_setup: list[dict[str, Any]], **_: Any) -> tuple[float, None]:
        heroes = sim_setup[0]["heroes"]
        assert all(hero["hero_name_or_preset"].lower() != "alpha" for hero in heroes)
        assert all(
            "plugin_blocked" not in hero.get("plugin_skill_ids", []) for hero in heroes
        )
        return 0.6, None

    monkeypatch.setattr(
        "vr_game_sim.main.run_additional_simulations",
        fake_run_additional,
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
        },
        raising=False,
    )

    evaluations = 0

    def fake_run_additional(_: list[dict[str, Any]], **__: Any) -> tuple[float, None]:
        nonlocal evaluations
        evaluations += 1
        return 0.1 * evaluations, None

    monkeypatch.setattr(
        "vr_game_sim.main.run_additional_simulations",
        fake_run_additional,
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
