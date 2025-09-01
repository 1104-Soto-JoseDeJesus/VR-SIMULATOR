from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.constants import (
    EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST,
    EFFECT_NAME_FATAL_BLEEDING_DOT,
)
from vr_game_sim.enums import EffectType, DoTType


def make_army(name: str, hero: Hero | None = None) -> Army:
    unit = Unit("pikemen", 5, initial_count=1000)
    heroes = [hero] if hero else []
    return Army(name, unit, heroes=heroes)


def test_timed_buff_activation_and_global_decrement():
    builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(builder)

    hero = Hero("Blesser", [], ["base_skill_vital_blessing"], [], SKILL_REGISTRY_GLOBAL)
    dfd = make_army("D", hero)
    atk1 = make_army("A1")
    atk2 = make_army("A2")

    dfd.current_rage = 1000  # rage skill will cast next round

    engine.add_army(atk1, "red", position=(0, 0), speed=0)
    engine.add_army(atk2, "red", position=(4, 0), speed=0)
    engine.add_army(dfd, "blue", position=(2, 0), speed=0)

    engine.engage("A1", "D")
    engine.engage("A2", "D")

    for _ in range(4):
        engine.tick(1.0)

    rounds = builder.get_rounds()
    r_a1 = rounds[("A1", "D")]
    r_a2 = rounds[("A2", "D")]

    assert not any(
        EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST in line for line in r_a1[0]["active_effects"]
    )
    assert not any(
        EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST in line for line in r_a2[0]["active_effects"]
    )

    # Effect activates one round after the rage skill casts
    assert not any(
        EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST in line for line in r_a1[1]["active_effects"]
    )
    assert not any(
        EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST in line for line in r_a2[1]["active_effects"]
    )

    line_a1_r3 = next(
        (
            l
            for l in r_a1[2]["active_effects"]
            if EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST in l
        ),
        None,
    )
    line_a2_r3 = next(
        (
            l
            for l in r_a2[2]["active_effects"]
            if EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST in l
        ),
        None,
    )
    assert line_a1_r3 and "Dur: 5 rounds" in line_a1_r3
    assert line_a2_r3 and "Dur: 5 rounds" in line_a2_r3

    line_a1_r4 = next(
        (
            l
            for l in r_a1[3]["active_effects"]
            if EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST in l
        ),
        None,
    )
    line_a2_r4 = next(
        (
            l
            for l in r_a2[3]["active_effects"]
            if EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST in l
        ),
        None,
    )
    assert line_a1_r4 and "Dur: 4 rounds" in line_a1_r4
    assert line_a2_r4 and "Dur: 4 rounds" in line_a2_r4


def test_end_of_round_dot_applies_once():
    builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(builder)

    atk1 = make_army("A1")
    atk2 = make_army("A2")
    dfd = make_army("D")

    engine.add_army(atk1, "red", position=(0, 0), speed=0)
    engine.add_army(atk2, "red", position=(4, 0), speed=0)
    engine.add_army(dfd, "blue", position=(2, 0), speed=0)

    engine.engage("A1", "D")
    engine.engage("A2", "D")

    engine.tick(1.0)

    dot_data = {
        "effect_type": EffectType.DAMAGE_OVER_TIME,
        "name": EFFECT_NAME_FATAL_BLEEDING_DOT,
        "dot_type": DoTType.BLEED,
        "status_effect_factor": 100,
        "duration": 2,
        "activate_next_round": True,
    }
    atk1._create_and_add_single_effect(dot_data, "test_skill", atk1, dfd, dfd)

    engine.tick(1.0)
    bleed = [e for e in dfd.active_effects if e.name == EFFECT_NAME_FATAL_BLEEDING_DOT]
    assert len(bleed) == 1 and bleed[0].duration == 2

    rounds = builder.get_rounds()
    line_a1_r2 = next(
        (
            l
            for l in rounds[("A1", "D")][1]["active_effects"]
            if EFFECT_NAME_FATAL_BLEEDING_DOT in l
        ),
        None,
    )
    line_a2_r2 = next(
        (
            l
            for l in rounds[("A2", "D")][1]["active_effects"]
            if EFFECT_NAME_FATAL_BLEEDING_DOT in l
        ),
        None,
    )
    assert line_a1_r2 and "Dur: 3 rounds" in line_a1_r2
    assert line_a2_r2 and "Dur: 3 rounds" in line_a2_r2

    trig_pair1 = rounds[("A1", "D")][1]["skill_triggers"].get("D", [])
    trig_pair2 = rounds[("A2", "D")][1]["skill_triggers"].get("D", [])
    dot_logs = [
        tr
        for tr in (trig_pair1 + trig_pair2)
        if "damage (pending)" in tr.get("effect_description", "")
        and "BLEED" in tr.get("effect_description", "").upper()
    ]
    assert len(dot_logs) == 1

    engine.tick(1.0)
    bleed = [e for e in dfd.active_effects if e.name == EFFECT_NAME_FATAL_BLEEDING_DOT]
    assert len(bleed) == 1 and bleed[0].duration == 1
    line_a1_r3 = next(
        (
            l
            for l in builder.get_rounds()[("A1", "D")][2]["active_effects"]
            if EFFECT_NAME_FATAL_BLEEDING_DOT in l
        ),
        None,
    )
    line_a2_r3 = next(
        (
            l
            for l in builder.get_rounds()[("A2", "D")][2]["active_effects"]
            if EFFECT_NAME_FATAL_BLEEDING_DOT in l
        ),
        None,
    )
    assert line_a1_r3 and "Dur: 2 rounds" in line_a1_r3
    assert line_a2_r3 and "Dur: 2 rounds" in line_a2_r3
