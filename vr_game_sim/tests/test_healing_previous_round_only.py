import pytest
from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.game_simulator import GameSimulator


def test_healing_ignores_current_round_losses():
    """Healing in the same round as damage should not revive newly lost troops."""
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    army.register_simulator(sim)
    enemy.register_simulator(sim)

    hp_per_troop = army.unit.effective_hp_per_troop(army.active_effects)
    army.pending_hp_damage_this_round = hp_per_troop * 3  # enough to kill 3 troops
    army.pending_hp_healing_this_round = hp_per_troop * 2  # attempt to heal 2 troops

    starting_count = army.current_troop_count
    army.commit_pending_healing_and_damage()

    # Healing should not revive any of the troops lost this round
    assert army.current_troop_count == starting_count - 3
