from types import SimpleNamespace

import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def test_dynamic_unrevivable_ratio_weights_combat_and_skill_kills():
    army = Army(
        "Army1",
        Unit("pikemen", 5, initial_count=100),
        use_dynamic_unrevivable_ratio=True,
    )
    enemy = Army(
        "Army2",
        Unit("archers", 5, initial_count=100),
        use_dynamic_unrevivable_ratio=True,
    )

    hp_a = army.unit.effective_hp_per_troop([])
    hp_b = enemy.unit.effective_hp_per_troop([])

    damage_to_army = hp_a * 40  # Army loses 40 troops worth of HP
    damage_to_enemy = hp_b * 20  # Enemy loses 20 troops worth of HP

    army.pending_hp_damage_this_round = damage_to_army
    enemy.pending_hp_damage_this_round = damage_to_enemy

    army.damage_contributors_this_round = {enemy.name: damage_to_army}
    enemy.damage_contributors_this_round = {army.name: damage_to_enemy}

    army.damage_contributors_by_skill_this_round = {
        enemy.name: {
            "basic_attack": hp_a * 10,
            "skill_fireball": hp_a * 30,
        }
    }
    enemy.damage_contributors_by_skill_this_round = {
        army.name: {
            "basic_attack": damage_to_enemy,
        }
    }

    army.commit_pending_healing_and_damage()
    enemy.commit_pending_healing_and_damage()

    assert army.unrevivable_troops == 27
    assert enemy.unrevivable_troops == 9
    assert army._last_dynamic_unrevivable_ratio == pytest.approx(0.6791666667, rel=1e-6)
    assert enemy._last_dynamic_unrevivable_ratio == pytest.approx(0.4333333333, rel=1e-6)


def test_dynamic_unrevivable_ratio_skill_heavy_damage():
    army = Army(
        "Army1",
        Unit("pikemen", 5, initial_count=100),
        use_dynamic_unrevivable_ratio=True,
    )
    enemy = Army(
        "Army2",
        Unit("archers", 5, initial_count=100),
        use_dynamic_unrevivable_ratio=True,
    )

    hp_a = army.unit.effective_hp_per_troop([])

    damage_to_army = hp_a * 10
    army.pending_hp_damage_this_round = damage_to_army
    army.damage_contributors_this_round = {enemy.name: damage_to_army}
    army.damage_contributors_by_skill_this_round = {
        enemy.name: {
            "skill_fireball": damage_to_army,
        }
    }

    army.commit_pending_healing_and_damage()

    assert army.unrevivable_troops == 8
    assert army._last_dynamic_unrevivable_ratio == pytest.approx(0.8)


def test_arena_indirect_attack_uses_per_attacker_ratios():
    target = Army(
        "Target",
        Unit("pikemen", 5, initial_count=100),
        use_dynamic_unrevivable_ratio=True,
    )
    direct = Army(
        "Direct",
        Unit("archers", 5, initial_count=100),
        use_dynamic_unrevivable_ratio=True,
    )
    indirect = Army(
        "Indirect",
        Unit("infantry", 5, initial_count=100),
        use_dynamic_unrevivable_ratio=True,
    )

    engine = SimpleNamespace(
        _armies={
            target.name: SimpleNamespace(direct_target=direct.name),
            direct.name: SimpleNamespace(direct_target=target.name),
            indirect.name: SimpleNamespace(direct_target=target.name),
        }
    )
    target.simulator = SimpleNamespace(mode="arena", parent_engine=engine)

    hp = target.unit.effective_hp_per_troop([])
    total_kills = 30
    target.pending_hp_damage_this_round = hp * total_kills
    target.damage_contributors_this_round = {
        direct.name: hp * 15,
        indirect.name: hp * 15,
    }
    target.damage_contributors_by_skill_this_round = {
        direct.name: {
            "basic_attack": hp * 10,
            "skill_fireball": hp * 5,
        },
        indirect.name: {
            "basic_attack": hp * 2,
            "skill_chain": hp * 13,
        },
    }

    hp_direct = direct.unit.effective_hp_per_troop([])
    hp_indirect = indirect.unit.effective_hp_per_troop([])

    direct.pending_hp_damage_this_round = hp_direct * 10
    direct.damage_contributors_this_round = {
        target.name: hp_direct * 10,
    }
    direct.damage_contributors_by_skill_this_round = {
        target.name: {
            "basic_attack": hp_direct * 6,
            "skill_storm": hp_direct * 4,
        }
    }

    indirect.pending_hp_damage_this_round = hp_indirect * 5
    indirect.damage_contributors_this_round = {
        target.name: hp_indirect * 5,
    }
    indirect.damage_contributors_by_skill_this_round = {
        target.name: {
            "basic_attack": hp_indirect * 3,
            "skill_chain": hp_indirect * 2,
        }
    }

    target.commit_pending_healing_and_damage()

    direct_ratio = target._calculate_dynamic_unrevivable_ratio(10.0, 5.0, 6.0, 4.0)
    indirect_ratio = target._calculate_dynamic_unrevivable_ratio(2.0, 13.0, 3.0, 2.0)
    expected_unrevivable = (
        10.0 * direct_ratio[0]
        + 5.0 * direct_ratio[1]
        + 2.0 * indirect_ratio[0]
        + 13.0 * indirect_ratio[1]
    )
    expected_increase = round(expected_unrevivable)
    assert expected_increase == 17
    assert target.unrevivable_troops == expected_increase
    total_kills = 30.0
    expected_effective_ratio = expected_unrevivable / total_kills
    assert target._last_dynamic_unrevivable_ratio == pytest.approx(
        expected_effective_ratio
    )
