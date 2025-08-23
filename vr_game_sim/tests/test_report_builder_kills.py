from vr_game_sim.report_builder import ReportBuilder


def test_skill_kills_displayed_in_report():
    rb = ReportBuilder(use_color=False)
    skill_triggers = {
        "Army1": [
            {
                "skill_name": "Fireball",
                "effect_description": "Burns enemy",
                "damage_done_hp": 100,
                "potential_kills": 3,
            }
        ]
    }
    rb.emit_round(1, [], skill_triggers)
    report_text = rb.get_report_text()
    assert "Kills 3" in report_text
