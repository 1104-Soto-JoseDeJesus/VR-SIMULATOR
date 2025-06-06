import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from game_simulator import GameSimulator


def test_troop_scalar_cache_behavior():
    GameSimulator.troop_scalar.cache_clear()
    first = GameSimulator.troop_scalar(5000)
    hits_before = GameSimulator.troop_scalar.cache_info().hits
    second = GameSimulator.troop_scalar(5000)
    hits_after = GameSimulator.troop_scalar.cache_info().hits
    assert first == second
    assert hits_after == hits_before + 1
