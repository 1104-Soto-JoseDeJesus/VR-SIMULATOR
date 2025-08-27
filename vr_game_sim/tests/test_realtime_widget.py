import os
import math

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtCore, QtWidgets

from vr_game_sim.realtime_battle_widget import RealTimeBattleWidget


def _sample_config():
    return {
        "army_name": "Army",
        "unit_type": "pikemen",
        "tier": 5,
        "count": 100,
        "atk_mod": 0,
        "def_mod": 0,
        "hp_mod": 0,
        "unrevivable_ratio": 0.5,
        "heroes": [
            {
                "hero_name_or_preset": "Artur",
                "talent_ids": [],
                "base_skill_ids": [],
                "plugin_skill_ids": [],
            },
            {
                "hero_name_or_preset": "Bjorn",
                "talent_ids": [],
                "base_skill_ids": [],
                "plugin_skill_ids": [],
            },
        ],
    }


def test_save_and_load(tmp_path):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    army_file = tmp_path / "armies.json"
    widget = RealTimeBattleWidget(army_file=army_file)
    widget._add_army_from_config(_sample_config(), team=1)
    widget._save_armies()
    assert army_file.exists()
    widget._refresh_battlefield()
    assert not widget.armies
    widget._load_armies()
    assert len(widget.armies) == 1
    item = widget.armies[0]["item"]
    height = item.main_item.pixmap().height()
    assert item.health_fg.rect().height() == height
    item.set_troop_count(50)
    assert item.health_fg.rect().height() == height / 2


def test_attack_order_and_retaliation():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget = RealTimeBattleWidget()
    widget.attack_radius = 10

    # Add attacker (team 1) and defender (team 2)
    widget._add_army_from_config(_sample_config(), team=1, pos=QtCore.QPointF(0, 0))
    widget._add_army_from_config(_sample_config(), team=2, pos=QtCore.QPointF(5, 0))

    attacker = widget.armies[0]
    defender = widget.armies[1]

    # Drag attacker near defender and commit drop
    attacker["item"].setPos(QtCore.QPointF(6, 0))
    widget.handle_army_drop(attacker["item"])

    # Attacker should snap to 2 units away and target the defender
    assert math.isclose(attacker["item"].pos().x(), 7.0, rel_tol=1e-5)
    assert attacker["target"] is defender
    # Defender had no target so should now target the attacker
    assert defender["target"] is attacker

    # Give defender a different target and attack again; it should keep its target
    widget._add_army_from_config(_sample_config(), team=1, pos=QtCore.QPointF(100, 0))
    other = widget.armies[2]
    defender["target"] = other
    attacker["item"].setPos(QtCore.QPointF(6, 0))
    widget.handle_army_drop(attacker["item"])
    assert defender["target"] is other

    # Defender can re-target by dragging near the attacker
    defender["item"].setPos(attacker["item"].pos() + QtCore.QPointF(1, 0))
    widget.handle_army_drop(defender["item"])
    assert defender["target"] is attacker


def test_global_timer_and_join_wait():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget = RealTimeBattleWidget()

    widget._add_army_from_config(_sample_config(), team=1)
    widget.advance_time(1)

    # Army joining at second 1 should wait until second 2 before acting
    widget._add_army_from_config(_sample_config(), team=1)
    assert widget.current_second == 1
    assert widget.armies[1]["next_action_second"] == 2


def test_aggregate_damage_and_idle_reset():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget = RealTimeBattleWidget()

    # Two attackers and one defender
    widget._add_army_from_config(_sample_config(), team=1)
    widget._add_army_from_config(_sample_config(), team=1)
    widget._add_army_from_config(_sample_config(), team=2)

    widget.advance_time(1)

    # Both attackers act in the same second against the defender
    assert widget.queue_damage(0, 2, 10)
    assert widget.queue_damage(1, 2, 10)

    widget.advance_time(1)

    defender = widget.armies[2]
    assert defender["current_troops"] == _sample_config()["count"] - 20
    # Each attacker advanced their own round counter once
    assert widget.armies[0]["own_round"] == 1
    assert widget.armies[1]["own_round"] == 1

    # No further actions; after two more seconds counters reset
    widget.advance_time(2)
    assert widget.armies[0]["own_round"] == 0
    assert widget.armies[1]["own_round"] == 0
    assert widget.armies[0]["rage"] == 0
    assert widget.armies[1]["rage"] == 0

