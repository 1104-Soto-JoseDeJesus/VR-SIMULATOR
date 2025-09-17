import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def test_dynamic_unrevivable_ratio_uses_damage_share():
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

    army.damage_inflicted_this_round = {enemy.name: damage_to_enemy}
    enemy.damage_inflicted_this_round = {army.name: damage_to_army}

    army.commit_pending_healing_and_damage()
    enemy.commit_pending_healing_and_damage()

    assert army.unrevivable_troops == 24
    assert enemy.unrevivable_troops == 8
    assert army._last_dynamic_unrevivable_ratio == pytest.approx(0.6)
    assert enemy._last_dynamic_unrevivable_ratio == pytest.approx(0.4)
