"""Tests covering interactive CLI recommendation integration."""

from __future__ import annotations

import copy
from typing import Any, Dict, List

import pytest

from vr_game_sim.interactive_setup import setup_hero_interactive
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.hero_definition import HERO_PRESETS


@pytest.fixture
def locked_sigurd() -> Dict[str, Any]:
    preset = HERO_PRESETS["sigurd"]
    return {
        "hero_name_or_preset": "Sigurd",
        "talent_ids": list(preset.get("talents", [])),
        "base_skill_ids": list(preset.get("base_skills", [])),
        "plugin_skill_ids": list(preset.get("plugin_skills", [])),
    }


def test_cli_recommendation_with_locked_slot(monkeypatch: pytest.MonkeyPatch, locked_sigurd: Dict[str, Any]) -> None:
    """Recommendations should respect existing heroes and fill the remaining slot."""

    recommendation_queue: List[Dict[str, Any]] = []
    own_setup = {
        "army_name": "Army",
        "unit_type": "pikemen",
        "tier": 5,
        "count": 40000,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "heroes": [copy.deepcopy(locked_sigurd)],
        "bonus_stats": {"hp_boost": 0.18},
        "use_dynamic_unrevivable_ratio": True,
        "blocked_heroes": ["leif"],
        "blocked_plugin_skills": ["plugin_battle_hymn"],
    }
    opponent_setup = copy.deepcopy(own_setup)

    yvette_preset = HERO_PRESETS["yvette"]
    recommended_config = {
        "heroes": [copy.deepcopy(locked_sigurd), {
            "hero_name_or_preset": "Yvette",
            "talent_ids": list(yvette_preset.get("talents", [])),
            "base_skill_ids": list(yvette_preset.get("base_skills", [])),
            "plugin_skill_ids": list(yvette_preset.get("plugin_skills", [])),
        }],
        "bonus_stats": copy.deepcopy(own_setup["bonus_stats"]),
        "use_dynamic_unrevivable_ratio": own_setup["use_dynamic_unrevivable_ratio"],
        "blocked_heroes": copy.deepcopy(own_setup["blocked_heroes"]),
        "blocked_plugin_skills": copy.deepcopy(own_setup["blocked_plugin_skills"]),
    }

    def fake_recommend_build_for_matchup(
        own: Dict[str, Any],
        opponent: Dict[str, Any],
        skill_registry: Dict[str, Any],
        *,
        runs: int = 60,
    ) -> Dict[str, Any]:
        assert own["heroes"] == own_setup["heroes"]
        assert own.get("blocked_heroes") == own_setup["blocked_heroes"]
        assert own.get("blocked_plugin_skills") == own_setup["blocked_plugin_skills"]
        return {
            "config": copy.deepcopy(recommended_config),
            "win_rate": 0.9,
            "runs": runs,
            "metadata": {"seed": 42},
            "evaluated_candidates": 1,
        }

    monkeypatch.setattr(
        "vr_game_sim.interactive_setup.recommend_build_for_matchup",
        fake_recommend_build_for_matchup,
    )
    monkeypatch.setattr("builtins.input", lambda _: "y")

    hero_obj = setup_hero_interactive(
        2,
        own_setup["army_name"],
        SKILL_REGISTRY_GLOBAL,
        recommendation_queue=recommendation_queue,
        own_setup=own_setup,
        opponent_setup=opponent_setup,
        recommendation_runs=10,
    )

    assert hero_obj is not None
    assert hero_obj.name == "Yvette"
    assert recommendation_queue == []
    assert own_setup["bonus_stats"] == {"hp_boost": 0.18}
