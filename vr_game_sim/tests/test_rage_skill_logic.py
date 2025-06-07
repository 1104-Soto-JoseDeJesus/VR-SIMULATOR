import pytest

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL


def make_army_with_rage_skill(name="Army"):
    hero = Hero("Tester", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=10)
    return Army(name, unit, heroes=[hero])


def test_rage_skill_cancels_when_insufficient_rage():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2)
    sim.round = 2  # simulate entering round 2

    army1.current_rage = 900
    army1.hero1_rage_skill_queued_this_round = True

    sim._execute_rage_skills(army1, army2)

    assert not army1.hero1_rage_skill_queued_this_round
    assert army1.current_rage == 900


def test_base_rage_blocked_when_skill_queued():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2)
    army1.reset_for_new_battle()
    army2.reset_for_new_battle()
    sim.round = 2

    army1.hero1_rage_skill_queued_this_round = True
    sim._apply_base_rage_gain()

    assert army1.current_rage == 0
    assert not army1.base_rage_awarded_this_round


def test_no_subtract_when_base_rage_prevented():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2)
    army1.reset_for_new_battle()
    army2.reset_for_new_battle()
    sim.round = 2

    army1.current_rage = 1000
    army1.hero1_rage_skill_queued_this_round = True
    sim._apply_base_rage_gain()
    sim._execute_rage_skills(army1, army2)

    if army1.hero1_rage_skill_used_round == sim.round and army1.base_rage_awarded_this_round:
        army1.current_rage = max(0, army1.current_rage - 100)

    assert army1.current_rage == 0
