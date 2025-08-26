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
battlefield where more than two armies can manoeuvre and clash using smooth
float-based movement rather than snapping to hexes.

Use the simple text interface to experiment with movement and combat:

```bash
python -m vr_game_sim.multi_cli
```

Commands allow armies to move across the map, advance rounds and display the
current field state. Attempting to enter a tile occupied by another army
triggers the existing 1v1 combat simulator while both forces remain in
adjacent positions.

Within the graphical interface a dedicated **Battlefield** tab renders a full‑window map without scrollbars.
Each army is represented by its main hero portrait with a smaller secondary hero icon tucked into the bottom‑right; armies without
heroes fall back to a simple initial letter. Armies march toward dragged destinations using NavMesh waypoints updated ten times per
second for smooth, accurate movement and battles resolve in real time – a 30‑round duel occupies the armies for 30 seconds with their
troop bars ticking down each second. Each marker shows a white vertical bar along the left side indicating remaining troops that rises or falls as losses and reinforcements occur. Double‑click a marker to open a dedicated configuration
dialog for that battlefield army so changes do not affect the duel tab. Use the mouse wheel to
zoom the map. Dragging an army onto an occupied tile triggers combat but
the units remain on adjacent cells while the duel resolves. Portrait overlays no longer block dragging,
so armies remain movable even when heroes are assigned. Armies can be added via an **Add Army**
button with up to five per team, letting larger forces clash. When two or more armies march on the
same foe only one is treated as the direct target and trades basic attacks, counterattacks and
skills; additional attackers only draw counterstrikes and reactive effects. Conflicts now cycle through
all armies on a tile so several attackers can converge on a single defender. Armies never turn on
members of their own team, and when several march on one target they automatically fan out to empty
adjacent cells instead of stacking in the same spot. If that direct target falls the army automatically
retargets another of its attackers. A companion **Battlefield Reports** tab lists the battle log for each
army. A **Reset from Setup** button reloads a fresh copy of the armies defined in the **Army Setup** tab.

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
