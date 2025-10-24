import os
import re
import time

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def gui_main():
    return pytest.importorskip("vr_game_sim.gui_main", exc_type=ImportError)


def test_counterattack_event_present(gui_main):
    from vr_game_sim.main import create_armies_from_data
    from vr_game_sim.report_builder import ReportBuilder
    from vr_game_sim.game_simulator import GameSimulator

    setup_entries = [
        {
            "army_name": "Blue Team",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 100,
            "atk_mod": 0.0,
            "def_mod": 0.0,
            "hp_mod": 0.0,
            "bonus_stats": {},
            "heroes": [],
            "gem_skills": {},
        },
        {
            "army_name": "Red Team",
            "unit_type": "archers",
            "tier": 5,
            "count": 100,
            "atk_mod": 0.0,
            "def_mod": 0.0,
            "hp_mod": 0.0,
            "bonus_stats": {},
            "heroes": [],
            "gem_skills": {},
        },
    ]

    armies = create_armies_from_data(setup_entries)
    report_builder = ReportBuilder(use_color=False)
    sim = GameSimulator(armies[0], armies[1], report_builder, track_stats=True)
    sim.simulate_battle()
    rounds = report_builder.get_rounds()
    army_histories = [
        {
            "name": army.name,
            "troops": [int(round(float(val))) for val in army.troop_count_history],
            "unrevivable": [int(round(float(val))) for val in army.unrevivable_history],
        }
        for army in armies
    ]

    log_rounds = gui_main.build_battle_log_rounds(rounds, army_histories)
    assert log_rounds, "battle log rounds should not be empty"

    has_counter = any(
        isinstance(entry, dict)
        and entry.get("type") == "counterattack"
        for rnd in log_rounds
        for entry in rnd.get("events", [])
    )
    assert has_counter, "expected at least one counterattack event"


def test_sample_export_excludes_analytics_terms(tmp_path, monkeypatch, gui_main):
    try:
        from PyQt6 import QtWidgets
    except ImportError:
        pytest.skip("PyQt6 not available")

    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    battle_log_rounds = [
        {
            "round": 1,
            "blue_troops_after": 199795,
            "red_troops_after": 579037,
            "blue_losses": -293,
            "red_losses": -1969,
            "events": [
                {
                    "type": "basic_attack",
                    "subject": {
                        "label": "Our party",
                        "alignment": "ally",
                        "troops_after": 198362,
                    },
                    "target": {"label": "Enemy", "alignment": "enemy"},
                    "units": 1964,
                },
                {
                    "type": "counterattack",
                    "attacker": {"label": "Enemy", "alignment": "enemy"},
                    "target": {
                        "label": "Our party",
                        "alignment": "ally",
                        "troops_after": 198086,
                    },
                    "units": 276,
                },
            ],
        }
    ]

    payload = {
        "report_text": "Simulation complete",
        "rounds": [],
        "summary": [],
        "win_rate": 1.0,
        "runs": 1,
        "best_match": None,
        "setup": [],
        "histograms": {},
        "generated_at": time.time(),
        "army_names": ["Blue Team", "Red Team"],
        "battle_log_rounds": battle_log_rounds,
        "sample_battle": {"battle_log_rounds": battle_log_rounds},
    }

    window = gui_main.MainWindow()
    window._last_simulation_payload = payload

    save_path = tmp_path / "sample_only_battle_log.html"
    monkeypatch.setattr(
        gui_main.QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(save_path), "HTML Files (*.html)"),
    )
    monkeypatch.setattr(gui_main.QtWidgets.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(gui_main.QtWidgets.QMessageBox, "critical", lambda *a, **k: None)

    window.export_summary_with_sample_html()

    assert save_path.exists()
    html_content = save_path.read_text(encoding="utf-8").lower()
    for term in [
        "unrevivable",
        "commit damage",
        "damage commit",
        "contributors",
        "contribution",
    ]:
        assert term not in html_content

    window.close()


def test_basic_attack_line_matches_template(gui_main):
    timestamp = time.time()
    rounds = [
        {
            "round": 1,
            "blue_troops_after": 199795,
            "red_troops_after": 579037,
            "blue_losses": -293,
            "red_losses": -1969,
            "events": [
                {
                    "type": "basic_attack",
                    "subject": {
                        "label": "Our party",
                        "alignment": "ally",
                        "troops_after": 198362,
                    },
                    "target": {"label": "Enemy", "alignment": "enemy"},
                    "units": 1964,
                }
            ],
        }
    ]

    html_markup = gui_main.build_battle_log_markup(
        rounds,
        ["Blue Team", "Red Team"],
        timestamp,
        "X728 Y616",
    )
    text_only = re.sub(r"<[^>]+>", "", html_markup)
    assert (
        "[Our party](198,362) launched a basic attack on [Enemy]. [Enemy] lost 1,964 units."
        in text_only
    )
