import dataclasses

import vr_game_sim.battlefield as bf_module
from vr_game_sim.battlefield import Battlefield


@dataclasses.dataclass
class DummyArmy:
    name: str
    hp: int


class DummyGameSimulator:
    def __init__(self, attacker: DummyArmy, defender: DummyArmy):
        self.attacker = attacker
        self.defender = defender
        self.rounds = 0
        self.reactive_calls = 0

    def simulate_round(self):
        self.rounds += 1
        if self.defender.hp > 0:
            self.defender.hp -= 1
        return {"round": self.rounds, "attacker": self.attacker.name, "defender_hp": self.defender.hp}

    def simulate_reactive_round(self):
        self.reactive_calls += 1
        return {"reactive": self.reactive_calls}


def test_battlefield_tracks_direct_and_indirect(monkeypatch):
    monkeypatch.setattr(bf_module, "GameSimulator", DummyGameSimulator)

    defender = DummyArmy("Def", hp=5)
    atk1 = DummyArmy("Atk1", hp=5)
    atk2 = DummyArmy("Atk2", hp=5)

    bf = Battlefield()
    bf.add_army(defender, team="B")
    bf.add_army(atk1, team="A")
    bf.add_army(atk2, team="A")

    bf.register_engagement("Atk1", "Def")
    bf.register_engagement("Atk2", "Def")

    bf.tick()

    # Only the direct attacker deals damage.
    assert defender.hp == 4
    assert bf.current_time == 1
    assert bf.direct_targets["Def"] == "Atk1"
    assert bf.indirect_attackers["Def"] == {"Atk2"}
    assert bf.engagements[("Atk1", "Def")].rounds == 1
    assert bf.engagements[("Atk2", "Def")].reactive_calls == 1
    assert len(bf.get_combat_report("Atk1", "Def")) == 1
    assert len(bf.get_combat_report("Atk2", "Def")) == 1
    assert bf.get_local_round("Def") == 1
    assert bf.get_local_round("Atk1") == 1
    assert bf.get_local_round("Atk2") == 1


def test_battlefield_remove_army_cleans_engagements(monkeypatch):
    monkeypatch.setattr(bf_module, "GameSimulator", DummyGameSimulator)

    defender = DummyArmy("Def", hp=5)
    atk1 = DummyArmy("Atk1", hp=5)

    bf = Battlefield()
    bf.add_army(defender, team="B")
    bf.add_army(atk1, team="A")
    bf.register_engagement("Atk1", "Def")

    bf.tick()
    bf.remove_army("Atk1")

    assert "Atk1" not in bf.armies
    assert not bf.engagements


def test_local_round_resets_after_inactivity(monkeypatch):
    """Armies that have not fought for 2 seconds reset their local round."""
    monkeypatch.setattr(bf_module, "GameSimulator", DummyGameSimulator)

    defender = DummyArmy("Def", hp=5)
    atk = DummyArmy("Atk", hp=5)

    bf = Battlefield()
    bf.add_army(defender, team="B")
    bf.add_army(atk, team="A")

    bf.register_engagement("Atk", "Def")
    bf.tick()  # time = 1, both armies engaged

    assert bf.get_local_round("Atk") == 1

    # Remove the engagement and let two seconds pass with no combat.
    bf.engagements.clear()
    bf._engagement_start_time.clear()
    bf.tick()  # time = 2
    bf.tick()  # time = 3 triggers local round reset

    assert bf.get_local_round("Atk") == 0

    # Re-engage and ensure the first action happens on the next tick boundary.
    bf.register_engagement("Atk", "Def")
    # No round should have happened yet
    assert bf.get_local_round("Atk") == 0
    bf.tick()  # time = 4, first round after re-engaging
    assert bf.get_local_round("Atk") == 1
    assert bf.current_time == 4


def test_reactive_skills_gated_once(monkeypatch):
    monkeypatch.setattr(bf_module, "GameSimulator", DummyGameSimulator)

    defender = DummyArmy("Def", hp=5)
    atk1 = DummyArmy("Atk1", hp=5)
    atk2 = DummyArmy("Atk2", hp=5)
    atk3 = DummyArmy("Atk3", hp=5)

    bf = Battlefield()
    bf.add_army(defender, team="B")
    bf.add_army(atk1, team="A")
    bf.add_army(atk2, team="A")
    bf.add_army(atk3, team="A")

    bf.register_engagement("Atk1", "Def")
    bf.register_engagement("Atk2", "Def")
    bf.register_engagement("Atk3", "Def")

    bf.tick()

    reactive_sum = (bf.engagements[("Atk2", "Def")].reactive_calls +
                    bf.engagements[("Atk3", "Def")].reactive_calls)
    assert reactive_sum == 1
    assert defender.hp == 4
