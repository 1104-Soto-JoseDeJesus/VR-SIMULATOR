"""Snapshot regression test for the in-game log HTML renderer."""

import os

from vr_game_sim.ingame_log.html_renderer import HtmlRenderer
from vr_game_sim.ingame_log.log_adapter import LogAdapter
from vr_game_sim.ingame_log.log_events import LogEvent
from vr_game_sim.ingame_log.number_format import NumberFormat


def test_ingame_log_snapshot():
    assets_dir = os.path.join(os.path.dirname(__file__), "..", "ingame_log")
    renderer = HtmlRenderer(assets_dir=assets_dir, number_format=NumberFormat(thousands=False))
    adapter = LogAdapter(renderer)

    adapter.push(LogEvent(type="ROUND_START", round=1))
    adapter.push(
        LogEvent(
            type="BASIC_ATTACK",
            round=1,
            attacker_name="Army A",
            defender_name="Army B",
            damage=1234.9,
            kills=7,
        )
    )
    adapter.push(
        LogEvent(
            type="COUNTER_ATTACK",
            round=1,
            attacker_name="Army B",
            defender_name="Army A",
            damage=321,
        )
    )
    adapter.push(LogEvent(type="ROUND_END", round=1))
    adapter.push(LogEvent(type="BATTLE_END", winner="Army A", rounds_total=1))

    out = adapter.render_html().strip()
    snapshot_path = os.path.join(os.path.dirname(__file__), "snapshots", "ingame_log.html")
    with open(snapshot_path, "r", encoding="utf-8") as handle:
        expected = handle.read().strip()
    assert out == expected
