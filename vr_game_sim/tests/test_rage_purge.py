from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.game_simulator import GameSimulator


def test_rage_purge_deals_damage_and_consumes_rage():
    hero = Hero('Tester', [], [], ['plugin_rage_purge'], SKILL_REGISTRY_GLOBAL)
    army = Army('A', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    enemy = Army('E', Unit('archers', 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)

    army.current_rage = 150
    skill_def = SKILL_REGISTRY_GLOBAL['plugin_rage_purge']

    happened, _ = skill_def['logic_handler'](army, enemy, skill_def, None, sim)

    assert happened
    assert army.current_rage == 50
    assert enemy.pending_hp_damage_this_round > 0

