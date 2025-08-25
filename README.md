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

To launch the graphical interface use:

```bash
python -m vr_game_sim.gui_main
```

Within the GUI you can configure armies, run simulations and view the generated
histogram figures. Use the **Export Figures** button to save these images to a
directory of your choice.
The adjacent **Export Summary Image** button saves a single PNG containing the
army preview along with all histograms.

You will be prompted to create a new setup or load a saved one from the
`vr_game_sim/setups` directory. Setups can be saved as JSON files for later use.

## Multi-army battlefield

Besides the traditional duel simulator, the project now offers a
grid-based battlefield where more than two armies can manoeuvre and clash.

Use the simple text interface to experiment with movement and combat:

```bash
python -m vr_game_sim.multi_cli
```

Commands allow armies to move across the map, advance rounds and display the
current field state. When two armies meet on the same tile the existing 1v1
combat simulator resolves the engagement.

Within the graphical interface a dedicated **Battlefield** tab renders a larger
grid that stretches to fill the tab so every tile is visible without scrolling.
Armies can be moved by dragging their markers to new tiles and clicking a
marker selects that army in the controls below. Double‑clicking a marker opens a
dedicated configuration dialog for that battlefield army so changes do not
affect the duel tab. If two armies are ordered to march toward the same
destination, they immediately clash to decide which one advances. Use the
"Reset from Setup" button to load a fresh copy of the armies defined in the
**Army Setup** tab and step the simulation round by round.

### Non-interactive mode

You can bypass the interactive prompts by providing the `--setup` option with a
path to a JSON setup file:

```bash
python -m vr_game_sim.main --setup path/to/setup.json
```

The simulator will load the file, run the battle once and then run additional
silent simulations for statistics. Both the command line interface and the GUI
now default to using all available CPU cores for these extra runs. If you call
`run_additional_simulations` directly, pass the `num_workers` argument to
control how many worker processes are spawned.

## Running tests

From the repository root run:

```bash
pytest
```

This will execute the unit tests located in `vr_game_sim/tests`.

## Image layout metadata

`StarredImageLabel` uses a small JSON sidecar file to customise how stars are
positioned over an image.  Place a file next to the image with the same base
name and a `.json` extension containing optional keys:

```json
{
  "max_stars": 6,
  "star_vertical_ratio": 0.88,
  "star_side_margin_ratio": 0.04
}
```

Ratios are expressed as fractions of the full image dimensions.  They control
the number of stars, how far from the top the star strip begins and any
horizontal padding around the stars.

For visual tuning, launch the GUI and choose **Debug → Star Overlay Tuner**.
Load a hero or plugin image, adjust the ratios and offsets in the dialog and
click **Save Layout** to write a JSON sidecar next to the image.
