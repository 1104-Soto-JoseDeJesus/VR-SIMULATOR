from vr_game_sim.main import run_multi_battle


def test_multi_battle_runs():
    setup = [
        {
            "army_name": "A1",
            "unit_type": "infantry",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
        {
            "army_name": "A2",
            "unit_type": "archers",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
        {
            "army_name": "A3",
            "unit_type": "pikemen",
            "tier": 5,
            "count": 50,
            "atk_mod": 0,
            "def_mod": 0,
            "hp_mod": 0,
            "heroes": [],
        },
    ]
    armies = run_multi_battle(setup, max_rounds=50, seed=1)
    assert len(armies) >= 1
    assert any(a.current_troop_count < a.unit.initial_count for a in armies)
