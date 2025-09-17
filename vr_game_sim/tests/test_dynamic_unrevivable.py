from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator


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
