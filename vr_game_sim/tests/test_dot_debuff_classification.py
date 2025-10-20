import copy
import random
import uuid

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.effect_system import EffectInstance
from vr_game_sim.enums import EffectType, DoTType
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.skill_logic.base_skill_handlers import handle_base_skill_zeal
from vr_game_sim.skill_logic.talent_handlers import handle_talent_fearless_pursuit


def _basic_armies():
    army1 = Army("A1", Unit("pikemen", 5, initial_count=10), heroes=[])
    army2 = Army("A2", Unit("archers", 5, initial_count=10), heroes=[])
    sim = GameSimulator(army1, army2)
    return army1, army2, sim


def test_poison_dot_cleansed_as_debuff(monkeypatch):
    army1, army2, sim = _basic_armies()
    poison = EffectInstance(
        uuid.uuid4(),
        "s",
        EffectType.DAMAGE_OVER_TIME,
        1,
        config={"dot_type": DoTType.POISON},
    )
    army1.active_effects.append(poison)
    skill_def = copy.deepcopy(SKILL_REGISTRY_GLOBAL["base_skill_zeal"])
    skill_def["config"]["debuff_removal_chance"] = 1.0
    skill_def["config"]["damage_chance"] = 0.0
    monkeypatch.setattr(random, "random", lambda: 0.0)
    handle_base_skill_zeal(army1, army2, skill_def, None, sim)
    assert poison not in army1.active_effects


def test_dot_counts_as_debuff_for_condition(monkeypatch):
    army1, army2, sim = _basic_armies()
    bleed = EffectInstance(
        uuid.uuid4(),
        "s",
        EffectType.DAMAGE_OVER_TIME,
        1,
        config={"dot_type": DoTType.BLEED},
    )
    army2.active_effects.append(bleed)
    skill_def = copy.deepcopy(SKILL_REGISTRY_GLOBAL["talent_fearless_pursuit"])
    skill_def["config"]["damage_factor"] = 100
    skill_def["config"]["alt_damage_factor"] = 200
    recorded = {}

    def fake_calc(trig, opp, factor, **kwargs):
        recorded["factor"] = factor
        return 0, 0, 0, 0

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    handle_talent_fearless_pursuit(army1, army2, skill_def, None, sim)
    assert recorded.get("factor") == 200


def test_no_debuff_uses_base_damage(monkeypatch):
    army1, army2, sim = _basic_armies()
    skill_def = copy.deepcopy(SKILL_REGISTRY_GLOBAL["talent_fearless_pursuit"])
    skill_def["config"]["damage_factor"] = 150
    skill_def["config"]["alt_damage_factor"] = 325
    recorded = {}

    def fake_calc(trig, opp, factor, **kwargs):
        recorded["factor"] = factor
        return 0, 0, 0, 0

    monkeypatch.setattr(sim, "_calculate_generic_skill_damage", fake_calc)
    monkeypatch.setattr(random, "random", lambda: 0.0)
    handle_talent_fearless_pursuit(army1, army2, skill_def, None, sim)
    assert recorded.get("factor") == 150
