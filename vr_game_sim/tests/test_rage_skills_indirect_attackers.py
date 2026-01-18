import random
from types import SimpleNamespace

from vr_game_sim.unit_definition import Unit
from vr_game_sim.army_composition import Army
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.skill_logic.rage_skill_handlers import (
    handle_rage_sacred_blade,
    handle_rage_skill_paralyzing_terror,
    handle_rage_incineration,
    handle_rage_all_kill,
)
from vr_game_sim.game_simulator import GameSimulator


def test_sacred_blade_does_not_hit_indirect_attackers(monkeypatch):
    hero = Hero('Laird', [], ['base_skill_sacred_blade'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    direct = Army('E1', Unit('archers', 5, initial_count=10), heroes=[])
    extras = [Army(f'E{i}', Unit('archers', 5, initial_count=10), heroes=[]) for i in range(2,5)]
    sim = GameSimulator(army, direct, mode='battlefield')
    for a in [direct] + extras:
        a.register_simulator(sim)
    class DummyEngine:
        def get_direct_attackers(self, name):
            return [direct]
    sim.parent_engine = DummyEngine()
    monkeypatch.setattr(random, 'sample', lambda pop, k: pop[:k])
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_sacred_blade']
    handle_rage_sacred_blade(army, direct, skill_def, {}, sim)
    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round == 0
    assert extras[1].pending_hp_damage_this_round == 0
    assert extras[2].pending_hp_damage_this_round == 0


def test_paralyzing_terror_respects_angle():
    hero = Hero('Wooder', [], ['base_skill_paralyzing_terror'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    direct = Army('E1', Unit('archers', 5, initial_count=10), heroes=[])
    extras = [
        Army('E2', Unit('archers', 5, initial_count=10), heroes=[]),
        Army('E3', Unit('archers', 5, initial_count=10), heroes=[]),
        Army('E4', Unit('archers', 5, initial_count=10), heroes=[]),
    ]
    sim = GameSimulator(army, direct, mode='battlefield')
    for a in [direct] + extras:
        a.register_simulator(sim)
    class DummyEngine:
        def __init__(self):
            self._armies = {
                army.name: SimpleNamespace(position=(0.0, 0.0), army=army, direct_target=None),
                direct.name: SimpleNamespace(position=(1.0, 0.0), army=direct, direct_target=army.name),
                extras[0].name: SimpleNamespace(position=(0.5, 0.5), army=extras[0], direct_target=army.name),
                extras[1].name: SimpleNamespace(position=(0.5, -0.5), army=extras[1], direct_target=army.name),
                extras[2].name: SimpleNamespace(position=(-1.0, 0.0), army=extras[2], direct_target=None),
            }
        def get_direct_attackers(self, name):
            return [ctx.army for ctx in self._armies.values() if ctx.direct_target == name]
    sim.parent_engine = DummyEngine()
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_paralyzing_terror']
    handle_rage_skill_paralyzing_terror(army, direct, skill_def, {}, sim)
    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round > 0
    assert extras[1].pending_hp_damage_this_round > 0
    assert extras[2].pending_hp_damage_this_round == 0


def test_all_kill_respects_angle():
    hero = Hero('Ivor', [], ['rage_skill_all_kill'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    direct = Army('E1', Unit('archers', 5, initial_count=10), heroes=[])
    extras = [
        Army('E2', Unit('archers', 5, initial_count=10), heroes=[]),
        Army('E3', Unit('archers', 5, initial_count=10), heroes=[]),
        Army('E4', Unit('archers', 5, initial_count=10), heroes=[]),
    ]
    sim = GameSimulator(army, direct, mode='battlefield')
    for a in [direct] + extras:
        a.register_simulator(sim)
    class DummyEngine:
        def __init__(self):
            self._armies = {
                army.name: SimpleNamespace(position=(0.0, 0.0), army=army, direct_target=None),
                direct.name: SimpleNamespace(position=(1.0, 0.0), army=direct, direct_target=army.name),
                extras[0].name: SimpleNamespace(position=(0.5, 0.5), army=extras[0], direct_target=army.name),
                extras[1].name: SimpleNamespace(position=(0.5, -0.5), army=extras[1], direct_target=army.name),
                extras[2].name: SimpleNamespace(position=(-1.0, 0.0), army=extras[2], direct_target=army.name),
            }
        def get_direct_attackers(self, name):
            return [ctx.army for ctx in self._armies.values() if ctx.direct_target == name]
    sim.parent_engine = DummyEngine()
    skill_def = SKILL_REGISTRY_GLOBAL['rage_skill_all_kill']
    handle_rage_all_kill(army, direct, skill_def, {}, sim)
    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round > 0
    assert extras[1].pending_hp_damage_this_round > 0
    assert extras[2].pending_hp_damage_this_round == 0


def test_incineration_does_not_hit_indirect_attackers(monkeypatch):
    hero = Hero('Artur', [], ['base_skill_incineration'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    direct = Army('E1', Unit('archers', 5, initial_count=10), heroes=[])
    extras = [Army(f'E{i}', Unit('archers', 5, initial_count=10), heroes=[]) for i in range(2,5)]
    sim = GameSimulator(army, direct, mode='battlefield')
    for a in [direct] + extras:
        a.register_simulator(sim)
    class DummyEngine:
        def get_direct_attackers(self, name):
            return [direct]
    sim.parent_engine = DummyEngine()
    monkeypatch.setattr(random, 'sample', lambda pop, k: pop[:k])
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_incineration']
    handle_rage_incineration(army, direct, skill_def, {}, sim)
    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round == 0
    assert extras[1].pending_hp_damage_this_round == 0
    assert extras[2].pending_hp_damage_this_round == 0


def test_indomitable_spirit_hits_extra_attackers_in_battlefield():
    hero = Hero("Rolfe", [], ["base_skill_indomitable_spirit"], [], SKILL_REGISTRY_GLOBAL)
    army = Army("H", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    direct = Army("E1", Unit("archers", 5, initial_count=10), heroes=[])
    extras = [
        Army("E2", Unit("archers", 5, initial_count=10), heroes=[]),
        Army("E3", Unit("archers", 5, initial_count=10), heroes=[]),
    ]
    sim = GameSimulator(army, direct, mode="battlefield")
    for a in [direct] + extras:
        a.register_simulator(sim)

    class DummyEngine:
        def get_direct_attackers(self, name):
            return [direct] + extras

    sim.parent_engine = DummyEngine()
    army.current_rage = 1000
    army.hero1_rage_skill_queued_this_round = True

    sim._execute_rage_skills(army, direct)

    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round > 0
    assert extras[1].pending_hp_damage_this_round > 0


def test_indomitable_spirit_single_target_in_standard_mode():
    hero = Hero("Rolfe", [], ["base_skill_indomitable_spirit"], [], SKILL_REGISTRY_GLOBAL)
    army = Army("H", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    direct = Army("E1", Unit("archers", 5, initial_count=10), heroes=[])
    extras = [
        Army("E2", Unit("archers", 5, initial_count=10), heroes=[]),
        Army("E3", Unit("archers", 5, initial_count=10), heroes=[]),
    ]
    sim = GameSimulator(army, direct, mode="standard")
    for a in [direct] + extras:
        a.register_simulator(sim)

    class DummyEngine:
        def get_direct_attackers(self, name):
            return [direct] + extras

    sim.parent_engine = DummyEngine()
    army.current_rage = 1000
    army.hero1_rage_skill_queued_this_round = True

    sim._execute_rage_skills(army, direct)

    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round == 0
    assert extras[1].pending_hp_damage_this_round == 0
