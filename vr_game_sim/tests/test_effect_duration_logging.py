from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero, HERO_PRESETS
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL


def make_army(name: str, hero: Hero | None = None) -> Army:
    unit = Unit("archers", 5, initial_count=1000)
    heroes = [hero] if hero else []
    return Army(name, unit, heroes=heroes)


def test_battle_preparation_applies_and_counts_down():
    builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(report_builder=builder)

    preset = HERO_PRESETS["harald"]
    harald = Hero("Harald", preset["talents"], preset["base_skills"], preset["plugin_skills"], SKILL_REGISTRY_GLOBAL)
    atk = make_army("A", harald)
    dfd = make_army("B")

    engine.add_army(atk, "red", speed=0)
    engine.add_army(dfd, "blue", speed=0)
    engine.tick(0.3)
    engine.engage("A", "B")
    engine.tick(0.7)  # start engagement at t=1
    for _ in range(4):
        engine.tick(1.0)

    rounds = builder.get_rounds()[("A", "B")]
    assert len(rounds) >= 3

    round2 = rounds[1]
    round3 = rounds[2]

    # Battle Preparation should appear in the round it triggers (round 2)
    line_r2 = next((l for l in round2["active_effects"] if "Battle Preparation Attack Buff" in l), None)
    assert line_r2 and "Dur: 30 rounds" in line_r2

    # Duration should decrease in the following round
    line_r3 = next((l for l in round3["active_effects"] if "Battle Preparation Attack Buff" in l), None)
    assert line_r3 and "Dur: 29 rounds" in line_r3
