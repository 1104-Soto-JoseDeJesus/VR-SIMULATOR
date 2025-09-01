from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.skill_logic.plugin_skill_handlers import handle_plugin_hymn_of_life


def _start_round(sim: GameSimulator) -> None:
    sim.round += 1
    sim.army1.pending_hp_damage_this_round = 0.0
    sim.army1.pending_hp_healing_this_round = 0.0
    sim.army2.pending_hp_damage_this_round = 0.0
    sim.army2.pending_hp_healing_this_round = 0.0
    for army in (sim.army1, sim.army2):
        if army.effects_to_activate_next_round:
            army.upcoming_effects.extend(army.effects_to_activate_next_round)
            army.effects_to_activate_next_round.clear()
        army.activate_queued_effects()
        army.decrement_effect_durations()
    for army, opponent in ((sim.army1, sim.army2), (sim.army2, sim.army1)):
        army.activate_queued_effects()
        army.process_periodic_effects("start_of_round", opponent=opponent)
        army.activate_queued_effects()


def test_hymn_of_life_heals_once_per_round():
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, track_stats=False)

    skill_def = SKILL_REGISTRY_GLOBAL["plugin_hymn_of_life"]
    handle_plugin_hymn_of_life(army, enemy, skill_def, None, sim)

    # Effect is scheduled; process two rounds verifying single heal per round
    for _ in range(2):
        _start_round(sim)
        heal_at_start = army.pending_hp_healing_this_round
        assert heal_at_start > 0
        army.process_periodic_effects("end_of_round", opponent=enemy)
        assert army.pending_hp_healing_this_round == heal_at_start
        army.commit_pending_healing_and_damage()

    _start_round(sim)
    # Effect should have expired after two rounds
    assert army.pending_hp_healing_this_round == 0
