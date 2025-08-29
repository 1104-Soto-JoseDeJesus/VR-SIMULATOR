import random

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL


def _start_round(sim: GameSimulator) -> None:
    sim.round += 1
    sim.army1.rage_added_this_round = 0.0
    sim.army2.rage_added_this_round = 0.0
    sim.army1.shield_hp_gained_this_round = 0.0
    sim.army2.shield_hp_gained_this_round = 0.0
    sim.army1.pending_hp_damage_this_round = 0.0
    sim.army1.pending_hp_healing_this_round = 0.0
    sim.army2.pending_hp_damage_this_round = 0.0
    sim.army2.pending_hp_healing_this_round = 0.0
    sim.round_combat_actions_log.clear()
    sim.round_skill_triggers_log = {sim.army1.name: [], sim.army2.name: []}
    for army in (sim.army1, sim.army2):
        army.triggered_skills_this_round.clear()
        army.healing_hymn_triggered_this_round = False
        army.base_rage_awarded_this_round = False


def test_healing_hymn_resets_each_round_simulator(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero = Hero("H", [], [], ["talent_healing_hymn"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army, enemy, track_stats=False)

    _start_round(sim)
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    dmg_first = enemy.pending_hp_damage_this_round
    assert dmg_first > 0
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert enemy.pending_hp_damage_this_round == dmg_first

    _start_round(sim)
    assert not army.healing_hymn_triggered_this_round
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert enemy.pending_hp_damage_this_round > 0


def test_healing_hymn_resets_each_round_battlefield_engine(monkeypatch):
    monkeypatch.setattr(random, "random", lambda: 0.0)
    hero = Hero("H", [], [], ["talent_healing_hymn"], SKILL_REGISTRY_GLOBAL)
    army = Army("A", Unit("pikemen", 5, initial_count=10), heroes=[hero])
    enemy = Army("E", Unit("archers", 5, initial_count=10), heroes=[])

    engine = BattlefieldEngine()
    monkeypatch.setattr(GameSimulator, "_calculate_and_log_attack", lambda self, a, b, is_counter=False: (0, 0, 0, 0))
    engine.add_army(army, "T1")
    engine.add_army(enemy, "T2")
    engine.engage("A", "E")
    engine.tick(1.0)

    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    dmg_first = enemy.pending_hp_damage_this_round
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert enemy.pending_hp_damage_this_round == dmg_first
    assert dmg_first > 0
    assert army.healing_hymn_triggered_this_round

    engine.tick(1.0)
    assert not army.healing_hymn_triggered_this_round
    army.calculate_and_add_pending_healing(1000.0, army, enemy)
    assert army.healing_hymn_triggered_this_round
