import uuid
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType
from vr_game_sim.constants import EFFECT_NAME_SILENCE_DEBUFF


def make_army_with_rage_skill(name="Army"):
    hero = Hero("Tester", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=10)
    return Army(name, unit, heroes=[hero])


def test_rage_skill_cancels_when_insufficient_rage():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2)
    sim.round = 1

    army1.current_rage = 900
    army1.hero1_rage_skill_queued_this_round = True

    sim._execute_rage_skills(army1, army2)

    assert not army1.hero1_rage_skill_queued_this_round
    assert army1.current_rage == 900


def test_no_base_rage_when_skill_cast():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)
    sim.round = 1

    army1.current_rage = 1000
    army1.hero1_rage_skill_queued_this_round = True
    sim._execute_rage_skills(army1, army2)
    sim._apply_base_rage_gain()

    assert army1.current_rage == 0
    assert not army1.base_rage_awarded_this_round


def test_base_rage_awarded_when_skill_canceled():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)
    sim.round = 1

    army1.current_rage = 900
    army1.hero1_rage_skill_queued_this_round = True
    sim._execute_rage_skills(army1, army2)
    sim._apply_base_rage_gain()

    assert army1.current_rage == 1000
    assert army1.base_rage_awarded_this_round


def test_base_rage_blocked_when_silenced():
    army1 = make_army_with_rage_skill("A1")
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)
    sim.round = 1

    army1.current_rage = 1000
    army1.hero1_rage_skill_queued_this_round = True
    silence = EffectInstance(uuid.uuid4(), "s", EffectType.DEBUFF, 1,
                             config={"prevents_rage_skill_cast": True},
                             name=EFFECT_NAME_SILENCE_DEBUFF)
    army1.active_effects.append(silence)

    sim._execute_rage_skills(army1, army2)
    sim._apply_base_rage_gain()

    assert army1.current_rage == 1000
    assert not army1.base_rage_awarded_this_round


def test_base_rage_granted_when_hero2_silenced():
    hero1 = Hero("H1", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    hero2 = Hero("H2", [], ["base_skill_snakes_frenzy"], [], SKILL_REGISTRY_GLOBAL)
    unit = Unit("pikemen", 5, initial_count=10)
    army1 = Army("A1", unit, heroes=[hero1, hero2])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])

    sim = GameSimulator(army1, army2)
    sim.round = 1

    army1.current_rage = 1000
    army1.hero2_rage_skill_primed_for_round = sim.round
    silence = EffectInstance(uuid.uuid4(), "s", EffectType.DEBUFF, 1,
                             config={"prevents_rage_skill_cast": True},
                             name=EFFECT_NAME_SILENCE_DEBUFF)
    army1.active_effects.append(silence)

    sim._execute_rage_skills(army1, army2, is_hero2_delayed_trigger=True)
    sim._apply_base_rage_gain()

    assert army1.current_rage == 1100
    assert army1.base_rage_awarded_this_round
