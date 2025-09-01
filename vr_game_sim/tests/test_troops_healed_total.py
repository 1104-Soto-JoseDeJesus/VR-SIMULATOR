import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator


def test_troops_healed_total_tracks_healed_troops():
    army = Army("A", Unit("pikemen", 5, initial_count=10), unrevivable_ratio=0.0)
    enemy = Army("E", Unit("archers", 5, initial_count=10))
    GameSimulator(army, enemy, track_stats=False)

    hp_per_troop = army.unit.effective_hp_per_troop(army.active_effects)
    # Inflict losses so there are troops to heal
    army.pending_hp_damage_this_round = hp_per_troop * 5
    army.commit_pending_healing_and_damage()

    healed_hp = army.calculate_and_add_pending_healing(1000.0, army, enemy)
    army.commit_pending_healing_and_damage()
    expected_troops = min(5, healed_hp / hp_per_troop)

    assert army.troops_healed_total == pytest.approx(expected_troops)
