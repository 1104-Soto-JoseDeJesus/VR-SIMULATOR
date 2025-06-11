# VR Battle Simulator

This project contains a simplified VR battle simulator. The code lives inside the
`vr_game_sim` package.

## Requirements

* Python 3.10+
* [matplotlib](https://matplotlib.org)
* [tabulate](https://pypi.org/project/tabulate/)
* [pytest](https://pytest.org) (for running tests)
* [colorama](https://pypi.org/project/colorama) (for colored output)

Install dependencies with:

```bash
pip install -r requirements.txt
```

A minimal `requirements.txt` could contain:

```
matplotlib
tabulate
pytest
colorama
```

## Running the simulator

Execute the simulator interactively:

```bash
python -m vr_game_sim.main
```

You will be prompted to create a new setup or load a saved one from the
`vr_game_sim/setups` directory. Setups can be saved as JSON files for later use.

### Non-interactive mode

You can bypass the interactive prompts by providing the `--setup` option with a
path to a JSON setup file:

```bash
python -m vr_game_sim.main --setup path/to/setup.json
```

The simulator will load the file, run the battle once and then run additional
silent simulations for statistics.

To utilize multiple CPU cores during these extra runs, call
`run_additional_simulations` with the `num_workers` argument greater than 1.

## Running tests

From the repository root run:

```bash
pytest
```

This will execute the unit tests located in `vr_game_sim/tests`.
