from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


def test_unrevivable_troops_limit_healing():
    army = Army("A", Unit("pikemen", 5, initial_count=100))
    hp_per_troop = army.unit.effective_hp_per_troop([])
    # Deal damage equivalent to 20 troops
    army.pending_hp_damage_this_round = hp_per_troop * 20
    army.commit_pending_healing_and_damage()
    assert army.current_troop_count == 80
    assert army.unrevivable_troops == 10
    # Clear damage and attempt to heal 20 troops; only 10 should be healed
    army.pending_hp_damage_this_round = 0
    army.pending_hp_healing_this_round = hp_per_troop * 20
    army.commit_pending_healing_and_damage()
    assert army.current_troop_count == 90
