import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit


class DummyArmyEntry:
    def __init__(self, army):
        self.army = army


class DummySimulator:
    def __init__(self, engine):
        self.parent_engine = engine
        self.events = []

    def _log_skill_trigger(self, *args, **kwargs):
        self.events.append((args, kwargs))


def test_kill_credit_matches_available_troops():
    defender = Army("Defender", Unit("pikemen", 5, initial_count=1))
    attacker_a = Army("AttackerA", Unit("archers", 5, initial_count=10))
    attacker_b = Army("AttackerB", Unit("archers", 5, initial_count=10))

    engine = type("DummyEngine", (), {})()
    engine._armies = {
        "AttackerA": DummyArmyEntry(attacker_a),
        "AttackerB": DummyArmyEntry(attacker_b),
    }

    simulator = DummySimulator(engine)
    defender.register_simulator(simulator)

    hp_per_troop = defender.unit.effective_hp_per_troop([])
    defender.pending_hp_damage_this_round = hp_per_troop * 10
    defender.damage_contributors_this_round = {
        "AttackerA": hp_per_troop * 6,
        "AttackerB": hp_per_troop * 4,
    }
    defender.damage_contributors_by_skill_this_round = {
        "AttackerA": {"skill_a": hp_per_troop * 6},
        "AttackerB": {"skill_b": hp_per_troop * 4},
    }

    defender.commit_pending_healing_and_damage()

    assert defender.current_troop_count == 0
    troops_removed = defender.unit.initial_count - defender.current_troop_count
    total_credited_kills = (
        attacker_a.kills_dealt_this_round + attacker_b.kills_dealt_this_round
    )
    assert total_credited_kills == pytest.approx(troops_removed)
