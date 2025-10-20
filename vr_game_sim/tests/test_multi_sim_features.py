from __future__ import annotations

import json
from pathlib import Path

import pytest

from vr_game_sim.gui_main import multi_sim_pair_indices
from vr_game_sim.main import run_additional_simulations


SETUP_PATH = Path(__file__).resolve().parent.parent / "setups" / "1v1" / "CHECK.json"
if SETUP_PATH.exists():
    SETUP_DATA = json.loads(SETUP_PATH.read_text(encoding="utf-8"))
else:  # pragma: no cover - environment guard
    pytest.skip("Fixture setup file missing; skip histogram override test", allow_module_level=True)


def test_histogram_directory_override(tmp_path: Path) -> None:
    hist_dir = tmp_path / "hist"

    run_additional_simulations(
        SETUP_DATA,
        runs=1,
        generate_histograms=True,
        verbose=False,
        num_workers=1,
        histogram_dir=str(hist_dir),
    )

    png_files = list(hist_dir.glob("*.png"))
    assert png_files, "Expected histogram files in override directory"


@pytest.mark.parametrize("count, expected", [(3, 3), (4, 6)])
def test_multi_sim_pair_indices(count: int, expected: int) -> None:
    configs = [{"army_name": f"Army {idx}"} for idx in range(count)]
    pairs = multi_sim_pair_indices(configs)
    assert len(pairs) == expected
    assert all(len(pair) == 2 for pair in pairs)
