from vr_game_sim.report_builder import ReportBuilder


def test_report_builder_filters_skill_actions():
    rb = ReportBuilder(use_color=False)
    rb.emit_round(
        1,
        combat_actions=[
            {
                "attacker_name": "A",
                "defender_name": "D",
                "action_type": "Basic Attack",
                "damage_potential_hp": 10,
                "absorbed_hp": 0,
                "final_hp_damage": 10,
                "potential_kills": 0,
            },
            {
                "attacker_name": "A",
                "defender_name": "D",
                "action_type": "Fireball",
                "damage_potential_hp": 20,
                "absorbed_hp": 0,
                "final_hp_damage": 20,
                "potential_kills": 0,
            },
        ],
        skill_triggers={
            "A": [
                {
                    "skill_name": "Fireball",
                    "effect_description": "Burns",
                    "damage_done_hp": 20,
                }
            ]
        },
        active_effects=None,
    )

    rounds = rb.get_rounds()
    assert len(rounds[0]["combat_actions"]) == 1
    assert rounds[0]["combat_actions"][0]["action_type"] == "Basic Attack"
