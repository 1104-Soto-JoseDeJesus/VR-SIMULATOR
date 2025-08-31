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
)
from vr_game_sim.game_simulator import GameSimulator


def test_sacred_blade_hits_indirect_attackers(monkeypatch):
    hero = Hero('Laird', [], ['base_skill_sacred_blade'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    direct = Army('E1', Unit('archers', 5, initial_count=10), heroes=[])
    extras = [Army(f'E{i}', Unit('archers', 5, initial_count=10), heroes=[]) for i in range(2,5)]
    sim = GameSimulator(army, direct, mode='battlefield')
    for a in [direct] + extras:
        a.register_simulator(sim)
    class DummyEngine:
        def get_engaged_enemies(self, name):
            return [direct] + extras
    sim.parent_engine = DummyEngine()
    monkeypatch.setattr(random, 'sample', lambda pop, k: pop[:k])
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_sacred_blade']
    handle_rage_sacred_blade(army, direct, skill_def, {}, sim)
    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round > 0
    assert extras[1].pending_hp_damage_this_round > 0
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
                army.name: SimpleNamespace(position=(0.0, 0.0)),
                direct.name: SimpleNamespace(position=(1.0, 0.0)),
                extras[0].name: SimpleNamespace(position=(0.5, 0.5)),
                extras[1].name: SimpleNamespace(position=(0.5, -0.5)),
                extras[2].name: SimpleNamespace(position=(-1.0, 0.0)),
            }
        def get_engaged_enemies(self, name):
            return [direct] + extras
    sim.parent_engine = DummyEngine()
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_paralyzing_terror']
    handle_rage_skill_paralyzing_terror(army, direct, skill_def, {}, sim)
    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round > 0
    assert extras[1].pending_hp_damage_this_round > 0
    assert extras[2].pending_hp_damage_this_round == 0


def test_incineration_hits_indirect_attackers(monkeypatch):
    hero = Hero('Artur', [], ['base_skill_incineration'], [], SKILL_REGISTRY_GLOBAL)
    army = Army('H', Unit('pikemen', 5, initial_count=10), heroes=[hero])
    direct = Army('E1', Unit('archers', 5, initial_count=10), heroes=[])
    extras = [Army(f'E{i}', Unit('archers', 5, initial_count=10), heroes=[]) for i in range(2,5)]
    sim = GameSimulator(army, direct, mode='battlefield')
    for a in [direct] + extras:
        a.register_simulator(sim)
    class DummyEngine:
        def get_engaged_enemies(self, name):
            return [direct] + extras
    sim.parent_engine = DummyEngine()
    monkeypatch.setattr(random, 'sample', lambda pop, k: pop[:k])
    skill_def = SKILL_REGISTRY_GLOBAL['base_skill_incineration']
    handle_rage_incineration(army, direct, skill_def, {}, sim)
    assert direct.pending_hp_damage_this_round > 0
    assert extras[0].pending_hp_damage_this_round > 0
    assert extras[1].pending_hp_damage_this_round > 0
    assert extras[2].pending_hp_damage_this_round == 0
