import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim import dynamic_unrevivable_config
from vr_game_sim.main import run_additional_simulations


def _create_dynamic_armies():
    unit_a = Unit("pikemen", 5, initial_count=100)
    unit_b = Unit("archers", 5, initial_count=100)
    army_a = Army(
        "Alpha",
        unit_a,
        unrevivable_ratio=0.3,
        use_dynamic_unrevivable_ratio=True,
    )
    army_b = Army(
        "Bravo",
        unit_b,
        unrevivable_ratio=0.3,
        use_dynamic_unrevivable_ratio=True,
    )
    sim = GameSimulator(army_a, army_b, track_stats=False)
    return army_a, army_b, sim


@pytest.fixture(autouse=True)
def reset_dynamic_config(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    settings_path = tmp_path_factory.mktemp("dyncfg") / "dynamic_unrevivable_settings.json"
    monkeypatch.setattr(dynamic_unrevivable_config, "_SETTINGS_FILE", settings_path)
    dynamic_unrevivable_config.reset_to_defaults()
    yield
    dynamic_unrevivable_config.reset_to_defaults()


def test_dynamic_unrevivable_mutual():
    army_a, army_b, sim = _create_dynamic_armies()
    army_a.clear_dynamic_unrevivable_tracking()
    army_b.clear_dynamic_unrevivable_tracking()
    hp_a = army_a.unit.effective_hp_per_troop([])
    hp_b = army_b.unit.effective_hp_per_troop([])

    # Army A loses 10 combat and 20 skill troops to army B
    army_a.pending_hp_damage_this_round = hp_a * 30
    army_a.damage_contributors_this_round = {army_b.name: hp_a * 30}
    army_a.damage_contributors_by_skill_this_round = {
        army_b.name: {
            "basic_attack": hp_a * 10,
            "skill_burst": hp_a * 20,
        }
    }

    # Army B loses 8 combat and 2 skill troops to army A
    army_b.pending_hp_damage_this_round = hp_b * 10
    army_b.damage_contributors_this_round = {army_a.name: hp_b * 10}
    army_b.damage_contributors_by_skill_this_round = {
        army_a.name: {
            "basic_attack": hp_b * 8,
            "skill_slash": hp_b * 2,
        }
    }

    army_a.commit_pending_healing_and_damage()
    army_b.commit_pending_healing_and_damage()
    sim.apply_unrevivable_post_commit(mutual_engagement=True)

    assert army_a.unrevivable_troops == 19
    assert army_b.unrevivable_troops == 4


def test_dynamic_unrevivable_mutual_override_changes_result():
    dynamic_unrevivable_config.apply_session_settings(
        {
            "pikemen_combat_base": 0.5,
            "pikemen_combat_bonus_multiplier": 0.5,
            "pikemen_skill_base": 0.5,
            "pikemen_skill_bonus_multiplier": 0.5,
            "pikemen_non_mutual_base": 0.5,
            "pikemen_non_mutual_bonus_multiplier": 0.5,
            "archers_combat_base": 0.5,
            "archers_combat_bonus_multiplier": 0.5,
            "archers_skill_base": 0.5,
            "archers_skill_bonus_multiplier": 0.5,
            "archers_non_mutual_base": 0.5,
            "archers_non_mutual_bonus_multiplier": 0.5,
        }
    )
    army_a, army_b, sim = _create_dynamic_armies()
    army_a.clear_dynamic_unrevivable_tracking()
    army_b.clear_dynamic_unrevivable_tracking()
    hp_a = army_a.unit.effective_hp_per_troop([])
    hp_b = army_b.unit.effective_hp_per_troop([])

    army_a.pending_hp_damage_this_round = hp_a * 30
    army_a.damage_contributors_this_round = {army_b.name: hp_a * 30}
    army_a.damage_contributors_by_skill_this_round = {
        army_b.name: {
            "basic_attack": hp_a * 10,
            "skill_burst": hp_a * 20,
        }
    }

    army_b.pending_hp_damage_this_round = hp_b * 10
    army_b.damage_contributors_this_round = {army_a.name: hp_b * 10}
    army_b.damage_contributors_by_skill_this_round = {
        army_a.name: {
            "basic_attack": hp_b * 8,
            "skill_slash": hp_b * 2,
        }
    }

    army_a.commit_pending_healing_and_damage()
    army_b.commit_pending_healing_and_damage()
    sim.apply_unrevivable_post_commit(mutual_engagement=True)

    assert army_a.unrevivable_troops == 27
    assert army_b.unrevivable_troops == 7


def test_dynamic_unrevivable_mutual_troop_multiplier_changes_result():
    dynamic_unrevivable_config.apply_session_settings(
        {
            "archers_combat_base": 0.0,
            "archers_combat_bonus_multiplier": 0.0,
            "archers_skill_base": 0.0,
            "archers_skill_bonus_multiplier": 0.0,
            "archers_non_mutual_base": 0.0,
            "archers_non_mutual_bonus_multiplier": 0.0,
            "pikemen_combat_base": 0.4,
            "pikemen_combat_bonus_multiplier": 0.7,
            "pikemen_skill_base": 0.4,
            "pikemen_skill_bonus_multiplier": 0.7,
            "pikemen_non_mutual_base": 0.4,
            "pikemen_non_mutual_bonus_multiplier": 0.7,
        }
    )
    army_a, army_b, sim = _create_dynamic_armies()
    army_a.clear_dynamic_unrevivable_tracking()
    army_b.clear_dynamic_unrevivable_tracking()
    hp_a = army_a.unit.effective_hp_per_troop([])
    hp_b = army_b.unit.effective_hp_per_troop([])

    army_a.pending_hp_damage_this_round = hp_a * 30
    army_a.damage_contributors_this_round = {army_b.name: hp_a * 30}
    army_a.damage_contributors_by_skill_this_round = {
        army_b.name: {
            "basic_attack": hp_a * 10,
            "skill_burst": hp_a * 20,
        }
    }

    army_b.pending_hp_damage_this_round = hp_b * 10
    army_b.damage_contributors_this_round = {army_a.name: hp_b * 10}
    army_b.damage_contributors_by_skill_this_round = {
        army_a.name: {
            "basic_attack": hp_b * 8,
            "skill_slash": hp_b * 2,
        }
    }

    army_a.commit_pending_healing_and_damage()
    army_b.commit_pending_healing_and_damage()
    sim.apply_unrevivable_post_commit(mutual_engagement=True)

    assert army_a.unrevivable_troops == 0
    assert army_b.unrevivable_troops == 7


def test_dynamic_unrevivable_non_mutual():
    army_a, army_b, sim = _create_dynamic_armies()
    army_a.clear_dynamic_unrevivable_tracking()
    army_b.clear_dynamic_unrevivable_tracking()
    hp_a = army_a.unit.effective_hp_per_troop([])
    hp_b = army_b.unit.effective_hp_per_troop([])

    # Army A loses 5 combat and 5 skill troops
    army_a.pending_hp_damage_this_round = hp_a * 10
    army_a.damage_contributors_this_round = {army_b.name: hp_a * 10}
    army_a.damage_contributors_by_skill_this_round = {
        army_b.name: {
            "basic_attack": hp_a * 5,
            "skill_burst": hp_a * 5,
        }
    }

    # Army B loses 6 combat troops
    army_b.pending_hp_damage_this_round = hp_b * 6
    army_b.damage_contributors_this_round = {army_a.name: hp_b * 6}
    army_b.damage_contributors_by_skill_this_round = {
        army_a.name: {
            "basic_attack": hp_b * 6,
        }
    }

    army_a.commit_pending_healing_and_damage()
    army_b.commit_pending_healing_and_damage()
    sim.apply_unrevivable_post_commit(mutual_engagement=False)

    assert army_a.unrevivable_troops == 5
    assert army_b.unrevivable_troops == 3


def test_dynamic_unrevivable_non_mutual_override_changes_result():
    dynamic_unrevivable_config.apply_session_settings(
        {
            "pikemen_combat_base": 0.5,
            "pikemen_combat_bonus_multiplier": 0.5,
            "pikemen_skill_base": 0.5,
            "pikemen_skill_bonus_multiplier": 0.5,
            "pikemen_non_mutual_base": 0.5,
            "pikemen_non_mutual_bonus_multiplier": 0.5,
            "archers_combat_base": 0.5,
            "archers_combat_bonus_multiplier": 0.5,
            "archers_skill_base": 0.5,
            "archers_skill_bonus_multiplier": 0.5,
            "archers_non_mutual_base": 0.5,
            "archers_non_mutual_bonus_multiplier": 0.5,
        }
    )
    army_a, army_b, sim = _create_dynamic_armies()
    army_a.clear_dynamic_unrevivable_tracking()
    army_b.clear_dynamic_unrevivable_tracking()
    hp_a = army_a.unit.effective_hp_per_troop([])
    hp_b = army_b.unit.effective_hp_per_troop([])

    army_a.pending_hp_damage_this_round = hp_a * 10
    army_a.damage_contributors_this_round = {army_b.name: hp_a * 10}
    army_a.damage_contributors_by_skill_this_round = {
        army_b.name: {
            "basic_attack": hp_a * 5,
            "skill_burst": hp_a * 5,
        }
    }

    army_b.pending_hp_damage_this_round = hp_b * 6
    army_b.damage_contributors_this_round = {army_a.name: hp_b * 6}
    army_b.damage_contributors_by_skill_this_round = {
        army_a.name: {
            "basic_attack": hp_b * 6,
        }
    }

    army_a.commit_pending_healing_and_damage()
    army_b.commit_pending_healing_and_damage()
    sim.apply_unrevivable_post_commit(mutual_engagement=False)

    assert army_a.unrevivable_troops == 7
    assert army_b.unrevivable_troops == 5


def test_run_additional_simulations_propagates_dynamic_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    override = {
        "pikemen_combat_base": 0.42,
        "pikemen_combat_bonus_multiplier": 0.12,
        "pikemen_skill_base": 0.37,
        "pikemen_skill_bonus_multiplier": 0.88,
        "pikemen_non_mutual_base": 0.15,
        "pikemen_non_mutual_bonus_multiplier": 0.73,
        "archers_combat_base": 0.18,
        "archers_combat_bonus_multiplier": 0.56,
        "archers_skill_base": 0.27,
        "archers_skill_bonus_multiplier": 0.63,
        "archers_non_mutual_base": 0.31,
        "archers_non_mutual_bonus_multiplier": 0.44,
    }
    dynamic_unrevivable_config.apply_session_settings(override)

    captured: list[dict | None] = []

    def fake_run_single_battle(
        setup: list[dict],
        seed: int | None = None,
        dynamic_settings: dict | None = None,
        return_report: bool = False,
    ):
        captured.append(dynamic_settings)
        base_result = (0, 0, 1, 0, 0, 0, 0)
        if return_report:
            return (*base_result, "report")
        return base_result

    class DummyExecutor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def map(self, fn, *iterables):
            for args in zip(*iterables):
                yield fn(*args)

    monkeypatch.setattr("vr_game_sim.main._run_single_battle", fake_run_single_battle)
    monkeypatch.setattr("vr_game_sim.main.ProcessPoolExecutor", DummyExecutor)

    setup_data = [
        {
            "army_name": "Alpha",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 100,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
            "use_dynamic_unrevivable_ratio": True,
        },
        {
            "army_name": "Bravo",
            "unit_type": "archers",
            "tier": 5,
            "count": 100,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
            "use_dynamic_unrevivable_ratio": True,
        },
    ]

    captured.clear()
    _, best_match = run_additional_simulations(
        setup_data,
        runs=2,
        generate_histograms=False,
        verbose=False,
        num_workers=1,
    )
    assert captured and all(isinstance(item, dict) for item in captured)
    expected_settings = dynamic_unrevivable_config.get_settings()
    for entry in captured:
        assert entry == expected_settings
    assert best_match and best_match.get("dynamic_settings") == expected_settings

    captured.clear()
    _, best_match = run_additional_simulations(
        setup_data,
        runs=2,
        generate_histograms=False,
        verbose=False,
        num_workers=2,
    )
    assert len(captured) == 2
    for entry in captured:
        assert entry == expected_settings
    assert best_match and best_match.get("dynamic_settings") == expected_settings
