import json

import pytest

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim import troop_scalar_config


def test_troop_scalar_cache_behavior():
    troop_scalar_config.set_session_multiplier(1.0)
    GameSimulator.troop_scalar.cache_clear()
    first = GameSimulator.troop_scalar(5000)
    hits_before = GameSimulator.troop_scalar.cache_info().hits
    second = GameSimulator.troop_scalar(5000)
    hits_after = GameSimulator.troop_scalar.cache_info().hits
    assert first == second
    assert hits_after == hits_before + 1


def test_troop_scalar_extended_range():
    troop_scalar_config.set_session_multiplier(1.0)
    scalar = GameSimulator.troop_scalar(500000)
    assert scalar == (0.20528 * 500000) + 68452


def test_troop_scalar_multiplier_scales_and_persists(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    config_dir = tmp_path / "troop-scalar"
    config_dir.mkdir()
    config_path = config_dir / "multiplier.json"
    monkeypatch.setattr(troop_scalar_config, "_SETTINGS_PATH", config_path)

    troop_scalar_config.set_session_multiplier(1.0)
    GameSimulator.troop_scalar.cache_clear()
    baseline = GameSimulator.troop_scalar(1000)

    scaled_value = troop_scalar_config.set_session_multiplier(1.5)
    assert scaled_value == pytest.approx(1.5)
    boosted = GameSimulator.troop_scalar(1000)
    assert boosted == pytest.approx(baseline * 1.5)

    saved = troop_scalar_config.save_multiplier(2.25)
    assert saved == pytest.approx(2.25)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data["multiplier"] == pytest.approx(2.25)

    troop_scalar_config.set_session_multiplier(0.5)
    reloaded = troop_scalar_config._load_multiplier_from_disk()
    assert reloaded == pytest.approx(2.25)

    troop_scalar_config.set_session_multiplier(1.0)
