"""Tests for Field Damage Comparison (_run_fdc_pair)."""

import pytest

pytest.importorskip("PyQt6")
from vr_game_sim.main import _run_fdc_pair


def _minimal_cfg(name: str, unit_type: str, count: int) -> dict:
    return {
        "army_name": name,
        "unit_type": unit_type,
        "tier": 5,
        "count": count,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "unrevivable_ratio": 0.5,
        "heroes": [],
    }


def test_fdc_pair_fresh_dummy_per_slot():
    attacker = _minimal_cfg("Attacker", "archers", 80)
    dummy = _minimal_cfg("Dummy", "infantry", 40)

    red1, blue1 = _run_fdc_pair(
        attacker,
        dummy,
        slot_index=1,
        seed=12345,
        max_rounds=4,
    )
    red2, blue2 = _run_fdc_pair(
        attacker,
        dummy,
        slot_index=2,
        seed=12345,
        max_rounds=4,
    )

    assert red1["team"] == "red"
    assert blue1["team"] == "blue"
    assert red2["team"] == "red"
    assert blue2["team"] == "blue"

    # Same template → same reported initial; each duel uses a fresh dummy copy.
    assert blue1["initial"] == blue2["initial"] == 40
    assert red1["initial"] == red2["initial"] == 80

    assert "FDC #1" in red1["name"]
    assert "FDC dummy #1" in blue1["name"]
    assert "FDC #2" in red2["name"]
    assert "FDC dummy #2" in blue2["name"]
