from vr_game_sim.army_composition import Army
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_logic.base_skill_handlers import handle_base_skill_berserk_fury


def test_berserk_fury_increases_rage_gain():
    hero = Hero("Hobert", [], ["base_skill_berserk_fury"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=1000)
    army = Army("A", unit, heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=1000), heroes=[])
    sim = GameSimulator(army, enemy)

    # Simulate troop loss to trigger one stack (6% loss -> 1 stack)
    army.current_troop_count = 940
    skill_def = SKILL_REGISTRY_GLOBAL["base_skill_berserk_fury"]
    handle_base_skill_berserk_fury(army, enemy, skill_def, None, sim)
    army.activate_queued_effects()

    gained = army.add_rage(100)
    assert gained == 103
    assert army.current_rage == 103

    gained = army.add_rage(75)
    assert gained == 77
    assert army.current_rage == 180
