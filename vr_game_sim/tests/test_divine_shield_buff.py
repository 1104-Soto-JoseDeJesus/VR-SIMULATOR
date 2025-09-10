from vr_game_sim.hero_definition import Hero
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.constants import EFFECT_NAME_DIVINE_SHIELD_STRENGTH


def test_divine_shield_passive_buff_applies_once():
    hero = Hero("Tester", [], [], ["plugin_divine_shield"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    skill_def = SKILL_REGISTRY_GLOBAL["plugin_divine_shield"]

    # Trigger the skill once and activate its effects
    happened, _ = skill_def["logic_handler"](army, enemy, skill_def, None, sim)
    army.activate_queued_effects()
    assert happened

    buffs = [e for e in army.active_effects if e.name == EFFECT_NAME_DIVINE_SHIELD_STRENGTH]
    assert len(buffs) == 1
    assert buffs[0].magnitude == 0.20
    assert buffs[0].duration == -1

    # Trigger again to ensure the passive does not stack
    skill_def["logic_handler"](army, enemy, skill_def, None, sim)
    army.activate_queued_effects()
    buffs = [e for e in army.active_effects if e.name == EFFECT_NAME_DIVINE_SHIELD_STRENGTH]
    assert len(buffs) == 1
