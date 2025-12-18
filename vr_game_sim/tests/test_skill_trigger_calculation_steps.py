from vr_game_sim.game_simulator import GameSimulator


class DummyArmy:
    def __init__(self, name: str):
        self.name = name


def test_auto_calculation_steps_include_damage_and_shield_details():
    simulator = GameSimulator.__new__(GameSimulator)
    simulator.round_skill_triggers_log = {"Tester": []}

    tester = DummyArmy("Tester")

    simulator._log_skill_trigger(
        tester,
        "Blazing Strike",
        "Deals damage and grants a shield.",
        {
            "damage_done_hp": 123.45,
            "shield_hp_gained": 55.5,
            "absorbed_hp": 10.25,
        },
    )

    log_entry = simulator.round_skill_triggers_log["Tester"][0]
    steps = log_entry.get("calculation_steps") or []

    expected_labels = {
        "Damage dealt": 123.45,
        "Shield gained": 55.5,
        "Damage absorbed": 10.25,
    }

    assert {step.get("label") for step in steps} >= set(expected_labels.keys())
    for step in steps:
        label = step.get("label")
        if label in expected_labels:
            assert step.get("value") == expected_labels[label]
            assert step.get("note")
