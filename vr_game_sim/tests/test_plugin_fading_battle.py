import random

from vr_game_sim.army_composition import Army
from vr_game_sim.enums import SkillTriggerType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.unit_definition import Unit


def _army_with_fading_battle(mode="standard"):
    hero = Hero(
        "Tester",
        ["dummy_talent_empty", "dummy_talent_empty", "dummy_talent_empty"],
        [],
        ["plugin_fading_battle"],
        SKILL_REGISTRY_GLOBAL,
    )
    army = Army("Atk", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("Def", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, mode=mode)
    return army, enemy, sim


def test_fading_battle_hits_only_primary_in_duel(monkeypatch):
    army, enemy, sim = _army_with_fading_battle()
    recorded = []

    def fake_calc(source, target, factor, **kwargs):
        recorded.append(target.name)
        return 0, 0, 0, 0, []

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    sim._process_skill_triggers(army, enemy, SkillTriggerType.ON_BASIC_ATTACK)
    assert recorded == [enemy.name]


def test_fading_battle_splashes_to_additional_enemies(monkeypatch):
    army, enemy, sim = _army_with_fading_battle(mode="battlefield")
    extras = [Army(f"Def{i}", Unit("archers", 5, initial_count=10), heroes=[]) for i in range(2, 5)]
    for extra in extras:
        extra.register_simulator(sim)

    class DummyEngine:
        def get_engaged_enemies(self, name):
            return [enemy] + extras

    sim.parent_engine = DummyEngine()

    recorded = []

    def fake_calc(source, target, factor, **kwargs):
        recorded.append(target.name)
        return 0, 0, 0, 0, []

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    monkeypatch.setattr(random, "sample", lambda seq, k: list(seq)[:k])

    sim._process_skill_triggers(army, enemy, SkillTriggerType.ON_BASIC_ATTACK)
    assert enemy.name in recorded
    assert len(recorded) == 3
    assert set(recorded[1:]).issubset({extra.name for extra in extras})
