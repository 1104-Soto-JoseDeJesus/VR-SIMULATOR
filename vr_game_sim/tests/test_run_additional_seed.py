import json
from pathlib import Path

import pytest

from vr_game_sim.main import _run_single_battle, run_additional_simulations
from vr_game_sim import troop_scalar_config


SEED_SEQUENCE = [
    288545018,
    135520872,
    547756574,
    253228484,
    1063938749,
    965274705,
    1014138928,
    815217483,
]
RUNS = len(SEED_SEQUENCE)
SETUP_PATH = (
    Path(__file__).resolve().parent.parent / "setups" / "1v1" / "CHECK.json"
)
SETUP_DATA = json.loads(SETUP_PATH.read_text(encoding="utf-8"))
troop_scalar_config.set_session_multiplier(1.0)
RESULTS = [_run_single_battle(SETUP_DATA, seed=s) for s in SEED_SEQUENCE]


def _patch_randrange(monkeypatch: pytest.MonkeyPatch, seeds: list[int]) -> None:
    iterator = iter(seeds)

    def fake_randrange(start: int, stop: int | None = None, step: int = 1) -> int:
        if stop is None:
            stop = start
            start = 0
        try:
            return next(iterator)
        except StopIteration as exc:  # pragma: no cover - defensive
            raise AssertionError("run_additional_simulations requested more seeds than provided") from exc

    monkeypatch.setattr("vr_game_sim.main.random.randrange", fake_randrange)


def _expected_best_index(winner: int, target: int) -> int:
    candidates: list[tuple[int, float]] = []
    for idx, (_, _, _, _, actual_winner, _, _) in enumerate(RESULTS[:RUNS]):
        if actual_winner != winner:
            continue
        remaining = RESULTS[idx][0] if winner == 1 else RESULTS[idx][1]
        candidates.append((idx, abs(float(remaining) - target)))
    assert candidates, "Expected at least one matching winner in the deterministic seed list"
    return min(candidates, key=lambda item: (item[1], item[0]))[0]


def test_seed_selection_prefers_army1(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_randrange(monkeypatch, SEED_SEQUENCE.copy())
    target_remaining = 50_000
    expected_idx = _expected_best_index(1, target_remaining)
    expected_win_rate = sum(
        1 for _, _, _, _, winner, _, _ in RESULTS[:RUNS] if winner == 1
    ) / RUNS

    win_rate, best_match = run_additional_simulations(
        SETUP_DATA,
        runs=RUNS,
        generate_histograms=False,
        verbose=False,
        num_workers=1,
        target_outcome={"winner": 1, "remaining": target_remaining},
    )

    assert pytest.approx(win_rate) == expected_win_rate
    assert best_match is not None
    assert best_match["winner"] == 1
    assert best_match["seed"] == SEED_SEQUENCE[expected_idx]
    assert best_match["army1_remaining"] == pytest.approx(RESULTS[expected_idx][0])
    assert best_match["army2_remaining"] == pytest.approx(RESULTS[expected_idx][1])
    assert best_match["troop_scalar_multiplier"] == pytest.approx(
        troop_scalar_config.get_multiplier()
    )

    selected_delta = abs(best_match["army1_remaining"] - target_remaining)
    for idx, result in enumerate(RESULTS[:RUNS]):
        if result[4] != 1:
            continue
        assert selected_delta <= abs(result[0] - target_remaining) + 1e-6


def test_seed_selection_prefers_army2(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_randrange(monkeypatch, SEED_SEQUENCE.copy())
    target_remaining = 90_000
    expected_idx = _expected_best_index(2, target_remaining)

    win_rate, best_match = run_additional_simulations(
        SETUP_DATA,
        runs=RUNS,
        generate_histograms=False,
        verbose=False,
        num_workers=1,
        target_outcome={"winner": 2, "remaining": target_remaining},
    )

    assert best_match is not None
    assert best_match["winner"] == 2
    assert best_match["seed"] == SEED_SEQUENCE[expected_idx]
    assert best_match["army1_remaining"] == pytest.approx(RESULTS[expected_idx][0])
    assert best_match["army2_remaining"] == pytest.approx(RESULTS[expected_idx][1])
    assert best_match["troop_scalar_multiplier"] == pytest.approx(
        troop_scalar_config.get_multiplier()
    )

    selected_delta = abs(best_match["army2_remaining"] - target_remaining)
    for idx, result in enumerate(RESULTS[:RUNS]):
        if result[4] != 2:
            continue
        assert selected_delta <= abs(result[1] - target_remaining) + 1e-6


def test_report_summary_includes_unrevivable() -> None:
    _, _, _, _, _, _, _, report_text = _run_single_battle(
        SETUP_DATA, seed=SEED_SEQUENCE[0], return_report=True
    )
    summary_lines = report_text.strip().splitlines()[-2:]
    assert len(summary_lines) == 2
    assert all("Unrevivable" in line for line in summary_lines)


def test_cli_replay_respects_multiplier(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_randrange(monkeypatch, SEED_SEQUENCE.copy())
    custom_multiplier = 1.3
    troop_scalar_config.set_session_multiplier(custom_multiplier)

    _, best_match = run_additional_simulations(
        SETUP_DATA,
        runs=2,
        generate_histograms=False,
        verbose=False,
        num_workers=1,
    )

    assert best_match is not None
    assert best_match["troop_scalar_multiplier"] == pytest.approx(custom_multiplier)

    replay = _run_single_battle(
        SETUP_DATA,
        seed=best_match["seed"],
        dynamic_settings=best_match.get("dynamic_settings"),
        troop_scalar_multiplier=best_match.get("troop_scalar_multiplier"),
    )

    assert replay[0] == pytest.approx(best_match["army1_remaining"])
    assert replay[1] == pytest.approx(best_match["army2_remaining"])

    troop_scalar_config.set_session_multiplier(1.0)
