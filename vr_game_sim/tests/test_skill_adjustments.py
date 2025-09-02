import random
from types import SimpleNamespace

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.skill_logic.rage_skill_handlers import (
    handle_rage_inspiring_dance,
    handle_rage_skill_heavenly_descent,
    handle_rage_vital_blessing,
)
from vr_game_sim.constants import EFFECT_NAME_INSPIRING_DANCE_BASIC_BUFF
from vr_game_sim.game_simulator import GameSimulator


def test_inspiring_dance_buffs_allies(monkeypatch):
    hero = Hero("Gregory", [], ["base_skill_inspiring_dance"], [], SKILL_REGISTRY_GLOBAL)
    army = Army("A0", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E0", Unit("archers", 5, initial_count=10), heroes=[])
    allies = [Army(f"A{i}", Unit("pikemen", 5, initial_count=10), heroes=[]) for i in range(1,7)]
    sim = GameSimulator(army, enemy, mode="battlefield")
    for a in [army, enemy] + allies:
        a.register_simulator(sim)
    engine = SimpleNamespace(_armies={})
    engine._armies[army.name] = SimpleNamespace(army=army, team="T1", position=(0.0, 0.0))
    engine._armies[enemy.name] = SimpleNamespace(army=enemy, team="T2", position=(100.0, 0.0))
    for i, ally in enumerate(allies, 1):
        engine._armies[ally.name] = SimpleNamespace(army=ally, team="T1", position=(10.0 * i, 0.0))
    sim.parent_engine = engine
    monkeypatch.setattr(random, "sample", lambda pop, k: pop[:k])
    skill_def = SKILL_REGISTRY_GLOBAL["base_skill_inspiring_dance"]
    handle_rage_inspiring_dance(army, enemy, skill_def, {}, sim)
    buffed = [any(e.name == EFFECT_NAME_INSPIRING_DANCE_BASIC_BUFF for e in ally.effects_to_activate_next_round) for ally in allies]
    assert buffed[:5] == [True] * 5
    assert buffed[5] is False


def test_heavenly_descent_only_hits_direct_attackers():
    hero = Hero("Jens", [], ["base_skill_heavenly_descent"], [], SKILL_REGISTRY_GLOBAL)
    army = Army("H", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    direct = Army("E0", Unit("archers", 5, initial_count=10), heroes=[])
    extras = [Army(f"E{i}", Unit("archers", 5, initial_count=10), heroes=[]) for i in range(1,6)]
    sim = GameSimulator(army, direct, mode="battlefield")
    for a in [army, direct] + extras:
        a.register_simulator(sim)
    engine = SimpleNamespace(_armies={})
    engine._armies[army.name] = SimpleNamespace(army=army, team="T1", position=(0.0, 0.0), direct_target=None)
    engine._armies[direct.name] = SimpleNamespace(army=direct, team="T2", position=(50.0, 0.0), direct_target=army.name)
    for i, extra in enumerate(extras, 1):
        engine._armies[extra.name] = SimpleNamespace(army=extra, team="T2", position=(10.0 * i, 0.0), direct_target=None)
    sim.parent_engine = engine
    skill_def = SKILL_REGISTRY_GLOBAL["base_skill_heavenly_descent"]
    handle_rage_skill_heavenly_descent(army, direct, skill_def, {}, sim)
    dmg = [e.pending_hp_damage_this_round for e in extras]
    assert direct.pending_hp_damage_this_round > 0
    assert all(d == 0 for d in dmg)


def test_vital_blessing_heals_allies(monkeypatch):
    hero = Hero("Yvette", [], ["base_skill_vital_blessing"], [], SKILL_REGISTRY_GLOBAL)
    army = Army("Y0", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E0", Unit("archers", 5, initial_count=10), heroes=[])
    allies = [Army(f"Y{i}", Unit("pikemen", 5, initial_count=10), heroes=[]) for i in range(1,6)]
    sim = GameSimulator(army, enemy, mode="battlefield")
    for a in [army, enemy] + allies:
        a.register_simulator(sim)
    engine = SimpleNamespace(_armies={})
    engine._armies[army.name] = SimpleNamespace(army=army, team="T1", position=(0.0, 0.0))
    engine._armies[enemy.name] = SimpleNamespace(army=enemy, team="T2", position=(100.0, 0.0))
    for i, ally in enumerate(allies, 1):
        engine._armies[ally.name] = SimpleNamespace(army=ally, team="T1", position=(10.0 * i, 0.0))
    sim.parent_engine = engine
    monkeypatch.setattr(random, "sample", lambda pop, k: pop[:k])
    skill_def = SKILL_REGISTRY_GLOBAL["base_skill_vital_blessing"]
    handle_rage_vital_blessing(army, enemy, skill_def, {}, sim)
    heals = [a.pending_hp_healing_this_round for a in allies]
    assert all(h > 0 for h in heals[:4])
    assert heals[4] == 0
