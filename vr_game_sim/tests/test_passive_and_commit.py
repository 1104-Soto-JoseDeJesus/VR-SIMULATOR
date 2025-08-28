from vr_game_sim.battlefield_engine import BattlefieldEngine
from vr_game_sim.battlefield_report_builder import BattlefieldReportBuilder
from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit
from vr_game_sim.hero_definition import Hero, HERO_PRESETS
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.report_builder import ReportBuilder


def make_army_with_laird(name: str) -> Army:
    preset = HERO_PRESETS['laird']
    hero = Hero(
        'laird',
        preset['talents'],
        preset['base_skills'],
        preset['plugin_skills'],
        SKILL_REGISTRY_GLOBAL,
    )
    unit = Unit('pikemen', 5, initial_count=1000)
    return Army(name, unit, heroes=[hero])


def test_passive_effects_and_commit_logged_same_round():
    builder = BattlefieldReportBuilder()
    engine = BattlefieldEngine(report_builder=builder)
    atk = make_army_with_laird('A')
    dfd = Army('B', Unit('archers', 5, initial_count=1000))
    engine.add_army(atk, 'red')
    engine.add_army(dfd, 'blue')
    engine.engage('A', 'B')
    engine.tick(1.1)
    rounds = builder.get_rounds()[('A', 'B')]
    assert len(rounds) == 1
    round1 = rounds[0]
    assert any('Holy Shield Boost' in line for line in round1['active_effects'])
    assert any(tr['skill_name'] == 'Damage Commitment' for tr in round1['skill_triggers']['A'])


def test_simulator_commit_logged_same_round():
    atk = Army('A', Unit('pikemen', 5, initial_count=1000))
    dfd = Army('B', Unit('archers', 5, initial_count=1000))
    rb = ReportBuilder(use_color=False)
    sim = GameSimulator(atk, dfd, rb)
    sim.simulate_battle()
    rounds = rb.get_rounds()
    round1 = rounds[0]
    assert any(tr['skill_name'] == 'Damage Commitment' for tr in round1['skill_triggers']['A'])
