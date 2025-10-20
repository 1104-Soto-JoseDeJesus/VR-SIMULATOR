import random

from vr_game_sim.army_composition import Army
from vr_game_sim.enums import SkillTriggerType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit


def _army_with_sacred_counter():
    hero = Hero(
        "Tester",
        ["talent_sacred_counter", "dummy_talent_empty", "dummy_talent_empty"],
        [],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    army = Army("Atk", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("Def", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy)
    return army, enemy, sim


def test_sacred_counter_does_not_trigger_on_own_attack(monkeypatch):
    army, enemy, sim = _army_with_sacred_counter()
    recorded = []

    def fake_calc(source, target, factor, **kwargs):
        recorded.append((target.name, factor))
        return 0, 0, 0, 0

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    sim._process_skill_triggers(army, enemy, SkillTriggerType.ON_BASIC_ATTACK)
    assert recorded == []


def test_sacred_counter_triggers_when_hit(monkeypatch):
    army, enemy, sim = _army_with_sacred_counter()
    recorded = []

    def fake_calc(source, target, factor, **kwargs):
        recorded.append((target.name, factor))
        return 0, 0, 0, 0

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    sim._process_skill_triggers(army, enemy, SkillTriggerType.ON_HIT_BY_BASIC_ATTACK)
    assert recorded == [(enemy.name, SKILL_REGISTRY_GLOBAL["talent_sacred_counter"]["config"]["damage_factor"])]
