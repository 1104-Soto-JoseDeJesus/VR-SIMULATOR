from vr_game_sim.game_simulator import GameSimulator


def test_troop_scalar_cache_behavior():
    GameSimulator.troop_scalar.cache_clear()
    first = GameSimulator.troop_scalar(5000)
    hits_before = GameSimulator.troop_scalar.cache_info().hits
    second = GameSimulator.troop_scalar(5000)
    hits_after = GameSimulator.troop_scalar.cache_info().hits
    assert first == second
    assert hits_after == hits_before + 1
