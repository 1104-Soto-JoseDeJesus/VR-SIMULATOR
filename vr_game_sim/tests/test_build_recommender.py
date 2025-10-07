"""Tests for the build recommendation helper."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

import pytest

from vr_game_sim.build_recommender import recommend_build_for_matchup
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL


@pytest.fixture
def base_setup() -> Dict[str, Any]:
    return {
        "army_name": "Test Army",
        "unit_type": "pikemen",
        "tier": 5,
        "count": 50000,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "heroes": [],
    }


def test_recommend_build_selects_highest_win_rate(monkeypatch: pytest.MonkeyPatch, base_setup: Dict[str, Any]) -> None:
    """The recommender should return the configuration with the top win rate."""

    recorded: List[Tuple[str, ...]] = []

    def fake_run(setup_data: List[Dict[str, Any]], runs: int, **_: Any) -> tuple[float, Dict[str, Any]]:
        own = setup_data[0]
        heroes = tuple(
            hero.get("hero_name_or_preset", "").lower()
            for hero in own.get("heroes", [])
        )
        recorded.append(heroes)
        if heroes == ("sigurd", "yvette"):
            return 0.85, {"seed": 1234}
        if heroes == ("sigurd",):
            return 0.8, {"seed": 2222}
        return 0.1, {"seed": 9999}

    monkeypatch.setattr(
        "vr_game_sim.main.run_additional_simulations",
        fake_run,
    )

    own_setup = copy.deepcopy(base_setup)
    opponent_setup = copy.deepcopy(base_setup)

    result = recommend_build_for_matchup(
        own_setup,
        opponent_setup,
        SKILL_REGISTRY_GLOBAL,
        runs=5,
    )

    assert result is not None
    config = result["config"]
    hero_names = [h.get("hero_name_or_preset", "").lower() for h in config.get("heroes", [])]
    assert hero_names == ["sigurd", "yvette"]
    assert pytest.approx(result["win_rate"], rel=1e-6) == 0.85
    assert result["metadata"]["seed"] == 1234
    assert ("sigurd", "yvette") in recorded


def test_recommend_build_preserves_locked_hero(monkeypatch: pytest.MonkeyPatch, base_setup: Dict[str, Any]) -> None:
    """Locked heroes must be preserved while filling only open slots."""

    locked_hero = {
        "hero_name_or_preset": "Sigurd",
        "talent_ids": ["locked-talent-1", "locked-talent-2"],
        "base_skill_ids": ["locked-base-1"],
        "plugin_skill_ids": ["locked-plugin"],
        "skill_overrides": {"base": "override"},
    }

    def fake_run(setup_data: List[Dict[str, Any]], runs: int, **_: Any) -> tuple[float, Dict[str, Any]]:
        own = setup_data[0]
        heroes = own.get("heroes", [])
        assert heroes
        assert heroes[0] == locked_hero
        if len(heroes) == 1:
            return 0.2, {"seed": 1111}
        second = heroes[1].get("hero_name_or_preset", "").lower()
        if second == "yvette":
            return 0.95, {"seed": 2222}
        return 0.1, {"seed": 3333}

    monkeypatch.setattr(
        "vr_game_sim.main.run_additional_simulations",
        fake_run,
    )

    own_setup = copy.deepcopy(base_setup)
    own_setup["heroes"] = [copy.deepcopy(locked_hero)]
    own_setup["bonus_stats"] = {"hp_boost": 0.12}
    own_setup["use_dynamic_unrevivable_ratio"] = True
    opponent_setup = copy.deepcopy(base_setup)

    result = recommend_build_for_matchup(
        own_setup,
        opponent_setup,
        SKILL_REGISTRY_GLOBAL,
        runs=5,
    )

    assert result is not None
    config = result["config"]
    assert config["heroes"][0] == locked_hero
    assert config["heroes"][1]["hero_name_or_preset"].lower() == "yvette"
    assert config.get("bonus_stats") == own_setup["bonus_stats"]
    assert config.get("use_dynamic_unrevivable_ratio") is True
    assert pytest.approx(result["win_rate"], rel=1e-6) == 0.95


def test_recommend_build_respects_blocked_heroes(
    monkeypatch: pytest.MonkeyPatch, base_setup: Dict[str, Any]
) -> None:
    """Candidates using blocked hero presets should not be evaluated."""

    recorded: list[tuple[str, ...]] = []
    blocked_hero = "sigurd"

    def fake_run(setup_data: List[Dict[str, Any]], runs: int, **_: Any) -> tuple[float, Dict[str, Any]]:
        own = setup_data[0]
        heroes = tuple(hero.get("hero_name_or_preset", "").lower() for hero in own.get("heroes", []))
        assert blocked_hero not in heroes
        recorded.append(heroes)
        if heroes == ("yvette",):
            return 0.9, {"seed": 5555}
        return 0.2, {"seed": 1111}

    monkeypatch.setattr(
        "vr_game_sim.main.run_additional_simulations",
        fake_run,
    )

    own_setup = copy.deepcopy(base_setup)
    own_setup["blocked_heroes"] = [blocked_hero]
    opponent_setup = copy.deepcopy(base_setup)

    result = recommend_build_for_matchup(
        own_setup,
        opponent_setup,
        SKILL_REGISTRY_GLOBAL,
        runs=5,
    )

    assert result is not None
    hero_names = [h.get("hero_name_or_preset", "").lower() for h in result["config"].get("heroes", [])]
    assert blocked_hero not in hero_names
    assert hero_names == ["yvette"]
    assert any(recorded)


def test_recommend_build_respects_blocked_plugins(
    monkeypatch: pytest.MonkeyPatch, base_setup: Dict[str, Any]
) -> None:
    """Plugin skill exclusions should be honoured during enumeration."""

    blocked_plugin = "plugin_blessed_negation"
    saw_non_empty = {"value": False}

    def fake_run(setup_data: List[Dict[str, Any]], runs: int, **_: Any) -> tuple[float, Dict[str, Any]]:
        own = setup_data[0]
        for hero in own.get("heroes", []):
            plugins = tuple(hero.get("plugin_skill_ids", []))
            if plugins:
                saw_non_empty["value"] = True
            assert blocked_plugin not in plugins
        # Reward any setup that equips at least one plugin
        has_plugin = any(hero.get("plugin_skill_ids") for hero in own.get("heroes", []))
        return (0.85 if has_plugin else 0.1, {"seed": 7777})

    monkeypatch.setattr(
        "vr_game_sim.main.run_additional_simulations",
        fake_run,
    )

    own_setup = copy.deepcopy(base_setup)
    own_setup["blocked_plugin_skills"] = [blocked_plugin]
    opponent_setup = copy.deepcopy(base_setup)

    result = recommend_build_for_matchup(
        own_setup,
        opponent_setup,
        SKILL_REGISTRY_GLOBAL,
        runs=5,
    )

    assert result is not None
    assert saw_non_empty["value"] is True
    for hero in result["config"].get("heroes", []):
        assert blocked_plugin not in hero.get("plugin_skill_ids", [])
