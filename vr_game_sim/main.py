# === File: main.py (with Save/Load Setup Feature) ===
import math
import random
import json
import os
import argparse
import sys
from typing import List, Optional, Dict, Any, Callable
import contextlib
import io
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
import matplotlib
from matplotlib.ticker import MaxNLocator
import numpy as np

# Use a non-interactive backend so matplotlib doesn't block the script when
# generating figures. This avoids hangs after the battle summary prints.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Explicitly disable interactive mode and clear any existing figures.
plt.ioff()
plt.close("all")
# Use the default matplotlib style globally. Specific figures can
# override this using ``plt.style.context`` when needed.
plt.style.use("default")

from vr_game_sim.enums import SkillType
from vr_game_sim.unit_definition import Unit as UnitClass
from vr_game_sim.hero_definition import Hero, HERO_PRESETS
from vr_game_sim.army_composition import Army
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.interactive_setup import (
    input_choice_numbered,
    input_int,
    input_float,
    setup_hero_interactive,
    input_multi_choice_numbered,
)
from vr_game_sim.skill_definitions import (
    SKILL_REGISTRY_GLOBAL,
    build_skill_registry_with_overrides,
)

# --- Configuration for Save/Load ---
# Resolve asset directories relative to this file so the package works even
# when the current working directory is outside the project root.  Previously
# the code relied on ``os.getcwd()`` which caused lookup failures (and crashes
# on some platforms) when running ``python -m vr_game_sim.main`` from another
# directory.  Using absolute paths ensures setups and histogram outputs are
# written to the package's folders regardless of where the process starts.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETUPS_DIR = os.path.join(BASE_DIR, "setups")
HISTOGRAM_DIR = os.path.join(BASE_DIR, "histograms")
LAST_SETUP_FILENAME = os.path.join(SETUPS_DIR, "_last_run_setup.json")
# Default size for generated histogram images (width, height in inches)
# Reduced size so the four histogram images can be displayed together in a
# 2x2 layout without exceeding a typical screen resolution.
HISTOGRAM_FIGSIZE = (2.5, 1.5)
# Higher DPI improves clarity without affecting the displayed size of the figure
HISTOGRAM_DPI = 1000
# Bin count for histograms to improve bar visibility
HISTOGRAM_BINS = 60
# Font size for titles and labels inside histogram figures
HISTOGRAM_FONT_SIZE = 4
# Font size for axis tick numbers inside histogram figures
HISTOGRAM_TICK_FONT_SIZE = 3
# Approximate number of tick marks on each axis
HISTOGRAM_TICK_COUNT = 8
# Background color for generated figures (matches Army Preview)
HISTOGRAM_BG_COLOR = "#353535"
HISTOGRAM_TEXT_COLOR = "#ffffff"
# Line width for gridlines inside histogram figures
HISTOGRAM_GRIDLINE_WIDTH = 0.5


def ensure_setups_dir():
    """Ensures the setups directory exists."""
    if not os.path.exists(SETUPS_DIR):
        os.makedirs(SETUPS_DIR)


def ensure_histogram_dir():
    """Ensures the histogram output directory exists."""
    if not os.path.exists(HISTOGRAM_DIR):
        os.makedirs(HISTOGRAM_DIR)


def _smooth_counts(counts: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """Return counts smoothed by a Gaussian kernel."""
    if counts.size == 0:
        return counts
    kernel_size = int(6 * sigma + 1)
    x = np.linspace(-3 * sigma, 3 * sigma, kernel_size)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    return np.convolve(counts, kernel, mode="same")


def save_setup_to_file(setup_data: List[Dict[str, Any]], filename: str):
    """Saves the army setup data to a JSON file."""
    ensure_setups_dir()
    filepath = os.path.join(SETUPS_DIR, filename)
    try:
        with open(filepath, "w") as f:
            json.dump(setup_data, f, indent=4)
        print(f"Setup saved to {filepath}")
        # Also save as the last run setup
        with open(LAST_SETUP_FILENAME, "w") as f_last:
            json.dump(setup_data, f_last, indent=4)
    except IOError as e:
        print(f"Error saving setup: {e}")


def load_setup_from_file(filename: str) -> Optional[List[Dict[str, Any]]]:
    """Loads army setup data from a JSON file. Accepts absolute or relative path."""
    filepath = filename
    if not os.path.isabs(filename):
        filepath = os.path.join(SETUPS_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Error: Setup file {filepath} not found.")
        return None
    try:
        with open(filepath, "r") as f:
            setup_data = json.load(f)
        print(f"Setup loaded from {filepath}")
        return setup_data
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading setup: {e}")
        return None


def list_saved_setups() -> List[str]:
    """Lists available .json setup files in the setups directory, excluding internal ones."""
    ensure_setups_dir()
    try:
        files = [
            f
            for f in os.listdir(SETUPS_DIR)
            if f.endswith(".json") and f != os.path.basename(LAST_SETUP_FILENAME)
        ]
        return sorted(files)
    except OSError:
        return []


def create_armies_from_data(loaded_data: List[Dict[str, Any]]) -> List[Army]:
    """Creates Army objects from loaded setup data."""
    armies: List[Army] = []
    # Collect all overrides so ``GameSimulator`` can use a registry with the
    # tweaked values when looking up skills by id (e.g. for rage skills).
    combined_overrides: Dict[str, Dict[str, Any]] = {}

    for army_config in loaded_data:
        unit = UnitClass(
            army_config["unit_type"],
            army_config["tier"],
            initial_count=army_config["count"],
            initial_atk_modifier=army_config["atk_mod"],
            initial_def_modifier=army_config["def_mod"],
            initial_hp_modifier=army_config["hp_mod"],
        )
        heroes_list: List[Hero] = []
        for hero_conf in army_config.get("heroes", []):
            overrides = hero_conf.get("skill_overrides")
            if overrides:
                # Merge into ``combined_overrides`` – last hero wins if the same
                # skill id is tweaked multiple times.
                for sid, params in overrides.items():
                    combined_overrides[sid] = params
            registry = (
                build_skill_registry_with_overrides(overrides)
                if overrides
                else SKILL_REGISTRY_GLOBAL
            )
            hero = Hero(
                name=hero_conf["hero_name_or_preset"],
                talent_ids=hero_conf["talent_ids"],
                base_skill_ids=hero_conf["base_skill_ids"],
                plugin_skill_ids=hero_conf["plugin_skill_ids"],
                skill_registry=registry,
            )
            heroes_list.append(hero)

        # Create Army instance. The simulator instance will be injected later by GameSimulator.
        army_obj = Army(
            army_config["army_name"],
            unit,
            heroes_list,
            army_config.get("unrevivable_ratio", 0.5),
        )
        armies.append(army_obj)

    # Ensure ``GameSimulator`` uses a registry with any overrides applied.
    if combined_overrides:
        GameSimulator.SKILL_REGISTRY_GLOBAL = build_skill_registry_with_overrides(combined_overrides)
    else:
        GameSimulator.SKILL_REGISTRY_GLOBAL = SKILL_REGISTRY_GLOBAL

    return armies


def _run_single_battle(
    setup_data: List[Dict[str, Any]],
    seed: int | None = None,
    return_report: bool = False,
) -> tuple:
    """Helper to run a single battle.

    Parameters
    ----------
    setup_data: List[Dict[str, Any]]
        Serialized army setup.
    seed: int | None
        When provided, ``random.seed`` is set before creating the simulator to
        ensure deterministic results.
    return_report: bool
        If ``True`` the full battle report text is returned as the final element
        in the tuple. ``GameSimulator`` is instantiated with ``track_stats`` set
        to ``True`` so that the report contains damage/heal/shield/rage figures.

    Returns
    -------
    tuple
        ``(own, enemy, rounds, diff, winner[, report_text])``
    """
    if seed is not None:
        random.seed(seed)

    armies = create_armies_from_data(setup_data)
    sim = GameSimulator(armies[0], armies[1], track_stats=return_report)
    with contextlib.redirect_stdout(io.StringIO()):
        sim.simulate_battle()
    winner = 0
    if sim.army1.current_troop_count > 0 and sim.army2.current_troop_count <= 0:
        winner = 1
    elif sim.army2.current_troop_count > 0 and sim.army1.current_troop_count <= 0:
        winner = 2
    own = sim.army1.current_troop_count
    enemy = sim.army2.current_troop_count
    diff = own - enemy
    result = (own, enemy, sim.round, diff, winner)
    if return_report:
        report_text = sim.report_builder.get_report_text()
        return (*result, report_text)
    return result


def run_additional_simulations(
    setup_data: List[Dict[str, Any]],
    runs: int = 300,
    *,
    generate_histograms: bool = True,
    verbose: bool = True,
    num_workers: int = 1,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> float:
    """Runs extra simulations and computes summary statistics.

    In addition to the aggregate statistics, a representative battle whose
    outcome is closest to the average troop difference is replayed with tracked
    stats and its report printed.  If ``num_workers`` is greater than 1,
    simulations are spread across multiple processes. ``progress_callback`` can
    be used to report completion status as ``(completed, total)``. The function
    returns the win rate for Army 1 as a float between 0 and 1."""
    # Ensure any previous figures are closed before starting the additional runs
    plt.close("all")

    own_remaining: List[float] = []
    enemy_remaining: List[float] = []
    rounds_taken: List[int] = []
    diff_results: List[float] = []
    winners: List[int] = []  # 1 -> army1, 2 -> army2, 0 -> draw

    army1_name = (
        setup_data[0].get("army_name", "Army 1") if len(setup_data) > 0 else "Army 1"
    )
    army2_name = (
        setup_data[1].get("army_name", "Army 2") if len(setup_data) > 1 else "Army 2"
    )
    battle_results: List[tuple] = []
    seeds = [random.randrange(1 << 30) for _ in range(runs)]

    worker_inputs = [setup_data] * runs
    if num_workers > 1:
        with ProcessPoolExecutor(
            max_workers=num_workers, mp_context=multiprocessing.get_context("spawn")
        ) as ex:
            results_iter = ex.map(_run_single_battle, worker_inputs, seeds)
            completed = 0
            for own, enemy, r_taken, diff, winner in results_iter:
                own_remaining.append(own)
                enemy_remaining.append(enemy)
                rounds_taken.append(r_taken)
                diff_results.append(diff)
                winners.append(winner)
                battle_results.append((own, enemy))
                completed += 1
                if progress_callback:
                    progress_callback(completed, runs)
    else:
        for i, seed_val in enumerate(seeds):
            own, enemy, r_taken, diff, winner = _run_single_battle(setup_data, seed=seed_val)
            own_remaining.append(own)
            enemy_remaining.append(enemy)
            rounds_taken.append(r_taken)
            diff_results.append(diff)
            winners.append(winner)
            battle_results.append((own, enemy))
            if progress_callback:
                progress_callback(i + 1, runs)

    avg_own = sum(own_remaining) / len(own_remaining) if own_remaining else 0
    avg_enemy = (
        sum(enemy_remaining) / len(enemy_remaining) if enemy_remaining else 0
    )
    best_idx = (
        min(
            range(runs),
            key=lambda i: (own_remaining[i] - avg_own) ** 2
            + (enemy_remaining[i] - avg_enemy) ** 2,
        )
        if own_remaining and enemy_remaining
        else 0
    )
    if own_remaining and enemy_remaining:
        _, _, _, _, _, report_text = _run_single_battle(
            setup_data, seed=seeds[best_idx], return_report=True
        )
        print(report_text)

    if generate_histograms:
        ensure_histogram_dir()

        avg_rounds = sum(rounds_taken) / len(rounds_taken) if rounds_taken else 0

        with plt.style.context("ggplot"):
            fig, ax = plt.subplots(figsize=HISTOGRAM_FIGSIZE, dpi=HISTOGRAM_DPI)
            fig.patch.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.hist(
                own_remaining,
                bins=HISTOGRAM_BINS,
                color="green",
                edgecolor="black",
            )
            counts, bins_ = np.histogram(own_remaining, bins=HISTOGRAM_BINS)
            centers = (bins_[:-1] + bins_[1:]) / 2
            smooth = _smooth_counts(counts)
            ax.plot(centers, smooth, color="yellow", linewidth=0.5)
            ax.axvline(avg_own, color="white", linestyle="dashed", linewidth=1)
            ax.set_title(
                f"{army1_name} Remaining Troops",
                fontsize=HISTOGRAM_FONT_SIZE,
                color=HISTOGRAM_TEXT_COLOR,
            )
            ax.set_xlabel("Troops", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.set_ylabel("Frequency", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.tick_params(axis="both", labelsize=HISTOGRAM_TICK_FONT_SIZE, colors=HISTOGRAM_TEXT_COLOR)
            ax.grid(linewidth=HISTOGRAM_GRIDLINE_WIDTH)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            fig.tight_layout()
            fig.savefig(
                os.path.join(HISTOGRAM_DIR, "own_remaining_troops.png"),
                dpi=HISTOGRAM_DPI,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

        with plt.style.context("ggplot"):
            fig, ax = plt.subplots(figsize=HISTOGRAM_FIGSIZE, dpi=HISTOGRAM_DPI)
            fig.patch.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.hist(
                enemy_remaining,
                bins=HISTOGRAM_BINS,
                color="red",
                edgecolor="black",
            )
            counts, bins_ = np.histogram(enemy_remaining, bins=HISTOGRAM_BINS)
            centers = (bins_[:-1] + bins_[1:]) / 2
            smooth = _smooth_counts(counts)
            ax.plot(centers, smooth, color="yellow", linewidth=0.5)
            ax.axvline(avg_enemy, color="white", linestyle="dashed", linewidth=1)
            ax.set_title(
                f"{army2_name} Remaining Troops",
                fontsize=HISTOGRAM_FONT_SIZE,
                color=HISTOGRAM_TEXT_COLOR,
            )
            ax.set_xlabel("Troops", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.set_ylabel("Frequency", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.tick_params(axis="both", labelsize=HISTOGRAM_TICK_FONT_SIZE, colors=HISTOGRAM_TEXT_COLOR)
            ax.grid(linewidth=HISTOGRAM_GRIDLINE_WIDTH)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            fig.tight_layout()
            fig.savefig(
                os.path.join(HISTOGRAM_DIR, "enemy_remaining_troops.png"),
                dpi=HISTOGRAM_DPI,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

        with plt.style.context("ggplot"):
            fig, ax = plt.subplots(figsize=HISTOGRAM_FIGSIZE, dpi=HISTOGRAM_DPI)
            fig.patch.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.hist(
                rounds_taken,
                bins=HISTOGRAM_BINS,
                color="lightgreen",
                edgecolor="black",
            )
            counts, bins_ = np.histogram(rounds_taken, bins=HISTOGRAM_BINS)
            centers = (bins_[:-1] + bins_[1:]) / 2
            smooth = _smooth_counts(counts)
            ax.plot(centers, smooth, color="yellow", linewidth=0.5)
            ax.axvline(avg_rounds, color="white", linestyle="dashed", linewidth=1)
            ax.set_title(
                "Rounds to Battle End",
                fontsize=HISTOGRAM_FONT_SIZE,
                color=HISTOGRAM_TEXT_COLOR,
            )
            ax.set_xlabel("Rounds", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.set_ylabel("Frequency", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.tick_params(axis="both", labelsize=HISTOGRAM_TICK_FONT_SIZE, colors=HISTOGRAM_TEXT_COLOR)
            ax.grid(linewidth=HISTOGRAM_GRIDLINE_WIDTH)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            fig.tight_layout()
            fig.savefig(
                os.path.join(HISTOGRAM_DIR, "rounds_to_battle_end.png"),
                dpi=HISTOGRAM_DPI,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

        # Histogram of troop count difference
        with plt.style.context("ggplot"):
            fig, ax = plt.subplots(figsize=HISTOGRAM_FIGSIZE, dpi=HISTOGRAM_DPI)
            fig.patch.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.hist(
                diff_results,
                bins=HISTOGRAM_BINS,
                color="orange",
                edgecolor="black",
            )
            counts, bins_ = np.histogram(diff_results, bins=HISTOGRAM_BINS)
            centers = (bins_[:-1] + bins_[1:]) / 2
            smooth = _smooth_counts(counts)
            ax.plot(centers, smooth, color="yellow", linewidth=0.5)
            ax.axvline(0, color="white", linestyle="dashed", linewidth=1)
            ax.set_title(
                "Difference in Surviving Troops",
                fontsize=HISTOGRAM_FONT_SIZE,
                color=HISTOGRAM_TEXT_COLOR,
            )
            ax.set_xlabel("Own - Enemy", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.set_ylabel("Frequency", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.tick_params(axis="both", labelsize=HISTOGRAM_TICK_FONT_SIZE, colors=HISTOGRAM_TEXT_COLOR)
            ax.grid(linewidth=HISTOGRAM_GRIDLINE_WIDTH)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            fig.tight_layout()
            fig.savefig(
                os.path.join(HISTOGRAM_DIR, "troop_difference.png"),
                dpi=HISTOGRAM_DPI,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

        # Scatter plot of difference vs rounds
        with plt.style.context("ggplot"):
            fig, ax = plt.subplots(figsize=HISTOGRAM_FIGSIZE, dpi=HISTOGRAM_DPI)
            fig.patch.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.set_facecolor(HISTOGRAM_BG_COLOR)
            colors = ["green" if d >= 0 else "red" for d in diff_results]
            ax.scatter(rounds_taken, diff_results, c=colors, s=2, edgecolors="none")
            ax.set_title(
                "Diff vs Rounds",
                fontsize=HISTOGRAM_FONT_SIZE,
                color=HISTOGRAM_TEXT_COLOR,
            )
            ax.set_xlabel("Rounds", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.set_ylabel("Own - Enemy", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.tick_params(axis="both", labelsize=HISTOGRAM_TICK_FONT_SIZE, colors=HISTOGRAM_TEXT_COLOR)
            ax.grid(linewidth=HISTOGRAM_GRIDLINE_WIDTH)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            fig.tight_layout()
            fig.savefig(
                os.path.join(HISTOGRAM_DIR, "diff_vs_rounds.png"),
                dpi=HISTOGRAM_DPI,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

        # Cumulative distribution of rounds
        with plt.style.context("ggplot"):
            fig, ax = plt.subplots(figsize=HISTOGRAM_FIGSIZE, dpi=HISTOGRAM_DPI)
            fig.patch.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.set_facecolor(HISTOGRAM_BG_COLOR)
            sorted_rounds = np.sort(rounds_taken)
            cdf = np.arange(1, len(sorted_rounds) + 1) / len(sorted_rounds)
            ax.plot(sorted_rounds, cdf, color="cyan", linewidth=1)
            ax.set_title(
                "CDF of Rounds",
                fontsize=HISTOGRAM_FONT_SIZE,
                color=HISTOGRAM_TEXT_COLOR,
            )
            ax.set_xlabel("Rounds", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.set_ylabel("Probability", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.tick_params(axis="both", labelsize=HISTOGRAM_TICK_FONT_SIZE, colors=HISTOGRAM_TEXT_COLOR)
            ax.grid(linewidth=HISTOGRAM_GRIDLINE_WIDTH)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            fig.tight_layout()
            fig.savefig(
                os.path.join(HISTOGRAM_DIR, "rounds_cdf.png"),
                dpi=HISTOGRAM_DPI,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

        # Rolling statistics line plot
        with plt.style.context("ggplot"):
            fig, ax = plt.subplots(figsize=HISTOGRAM_FIGSIZE, dpi=HISTOGRAM_DPI)
            fig.patch.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.set_facecolor(HISTOGRAM_BG_COLOR)
            x = np.arange(1, len(own_remaining) + 1)
            own_avg = np.cumsum(own_remaining) / x
            enemy_avg = np.cumsum(enemy_remaining) / x
            win_avg = np.cumsum([1 if w == 1 else 0 for w in winners]) / x
            ax.plot(x, own_avg, label="Own", linewidth=0.5, color="green")
            ax.plot(x, enemy_avg, label="Enemy", linewidth=0.5, color="red")
            ax2 = ax.twinx()
            ax2.plot(x, win_avg, label="Win rate", linewidth=0.5, color="white")
            ax.set_title(
                "Rolling Averages",
                fontsize=HISTOGRAM_FONT_SIZE,
                color=HISTOGRAM_TEXT_COLOR,
            )
            ax.set_xlabel("Runs", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax.set_ylabel("Avg Troops", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            ax2.set_ylabel("Win Rate", fontsize=HISTOGRAM_FONT_SIZE, color=HISTOGRAM_TEXT_COLOR)
            for axis in (ax, ax2):
                axis.tick_params(axis="both", labelsize=HISTOGRAM_TICK_FONT_SIZE, colors=HISTOGRAM_TEXT_COLOR)
                axis.grid(linewidth=HISTOGRAM_GRIDLINE_WIDTH)
                axis.xaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
                axis.yaxis.set_major_locator(MaxNLocator(nbins=HISTOGRAM_TICK_COUNT))
            fig.tight_layout()
            fig.savefig(
                os.path.join(HISTOGRAM_DIR, "rolling_stats.png"),
                dpi=HISTOGRAM_DPI,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

    # Pie chart for win percentages
    wins_army1 = winners.count(1)
    wins_army2 = winners.count(2)
    if generate_histograms and wins_army1 + wins_army2 > 0:
        with plt.style.context("default"):
            fig, ax = plt.subplots(figsize=HISTOGRAM_FIGSIZE, dpi=HISTOGRAM_DPI)
            fig.patch.set_facecolor(HISTOGRAM_BG_COLOR)
            ax.set_facecolor(HISTOGRAM_BG_COLOR)
            wedges, texts, autotexts = ax.pie(
                [wins_army1, wins_army2],
                labels=[army1_name, army2_name],
                autopct="%.1f%%",
                colors=["green", "red"],
                startangle=90,
                textprops={"fontsize": HISTOGRAM_FONT_SIZE, "color": HISTOGRAM_TEXT_COLOR},
            )
            for text in texts + autotexts:
                text.set_color(HISTOGRAM_TEXT_COLOR)
            ax.set_title(
                "Victory Distribution",
                fontsize=HISTOGRAM_FONT_SIZE,
                color=HISTOGRAM_TEXT_COLOR,
            )
            ax.axis("equal")
            fig.tight_layout()
            fig.savefig(
                os.path.join(HISTOGRAM_DIR, "victory_distribution.png"),
                dpi=HISTOGRAM_DPI,
                bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)

    if generate_histograms:
        # Ensure no figures remain open in case others were created
        plt.close("all")

    # Determine battle closest to average outcome
    if verbose and diff_results:
        closest_idx = best_idx
        closest_own, closest_enemy = battle_results[closest_idx]
        winner_text = "Draw"
        if winners[closest_idx] == 1:
            winner_text = army1_name
        elif winners[closest_idx] == 2:
            winner_text = army2_name
        print(
            f"Battle closest to average outcome: #{closest_idx + 1} -> Winner: {winner_text}; {army1_name}: {closest_own:.0f} troops, {army2_name}: {closest_enemy:.0f} troops"
        )

    # Final cleanup to ensure matplotlib does not keep figures open
    plt.close("all")
    return wins_army1 / runs


def run_interactive_setup() -> List[Army]:
    """Runs the full interactive setup for two armies."""
    armies_setup_interactive: List[Army] = []
    ordered_unit_types = sorted(list(UnitClass.ALLOWED_TYPES))

    for i in range(1, 3):
        print(f"\n--- Army {i} Setup ---")
        army_name = input(f"Army {i} Name (default: Army {i}): ").strip() or f"Army {i}"
        unit_type_str = input_choice_numbered(
            "Select Unit type", ordered_unit_types, default="pikemen"
        )
        tier = input_int(
            "Tier",
            min_val=min(UnitClass.ALLOWED_TIERS),
            max_val=max(UnitClass.ALLOWED_TIERS),
            default=5,
        )
        count = input_int("Troop count", min_val=1, default=100000)
        print(
            f"  Enter initial stat modifiers for {unit_type_str} T{tier} (as decimals, e.g., 0.1 for +10%):"
        )
        atk_mod = input_float(
            "  Initial Attack Modifier", default=0.0
        )  # Changed default to float
        def_mod = input_float(
            "  Initial Defense Modifier", default=0.0
        )  # Changed default to float
        hp_mod = input_float(
            "  Initial HP Modifier", default=0.0
        )  # Changed default to float

        current_unit_obj = UnitClass(
            unit_type_str,
            tier,
            initial_count=count,
            initial_atk_modifier=atk_mod,
            initial_def_modifier=def_mod,
            initial_hp_modifier=hp_mod,
        )
        current_heroes_list: List[Hero] = []
        max_heroes_per_army = 2  # As per existing logic

        for hero_num in range(1, max_heroes_per_army + 1):
            add_hero_prompt = (
                f"  Add Hero {hero_num} to {army_name}? (yes/no, default: yes): "
            )
            add_hero_choice = input(add_hero_prompt).strip().lower() or "yes"

            if add_hero_choice == "yes":
                hero_obj = setup_hero_interactive(
                    hero_num, army_name, SKILL_REGISTRY_GLOBAL
                )
                if hero_obj:
                    current_heroes_list.append(hero_obj)
                    skill_names_for_log = [
                        s["name"]
                        for s in hero_obj.skills
                        if s["id"] != "dummy_talent_empty" and s["id"] != ""
                    ]
                    print(
                        f"    Added {hero_obj.name} to {army_name} with skills: {skill_names_for_log}."
                    )
            else:
                break

        army_instance = Army(army_name, current_unit_obj, current_heroes_list)
        armies_setup_interactive.append(army_instance)
        print(
            f"--- {army_name} (T{current_unit_obj.tier} {current_unit_obj.unit_type} x{current_unit_obj.initial_count}) setup complete. ---"
        )
    return armies_setup_interactive


def get_setup_data_for_saving(armies: List[Army]) -> List[Dict[str, Any]]:
    """Prepares the data from Army objects for saving."""
    save_data_list: List[Dict[str, Any]] = []
    for army_obj in armies:
        army_config = {
            "army_name": army_obj.name,
            "unit_type": army_obj.unit.unit_type,
            "tier": army_obj.unit.tier,
            "count": army_obj.unit.initial_count,
            "atk_mod": army_obj.unit.atk_multiplier,
            "def_mod": army_obj.unit.def_multiplier,
            "hp_mod": army_obj.unit.hp_multiplier,
            "heroes": [],
        }
        for hero_obj in army_obj.heroes:
            hero_config = {
                "hero_name_or_preset": hero_obj.name,  # This is the name used/entered during setup
                "talent_ids": hero_obj.talent_ids,
                "base_skill_ids": hero_obj.base_skill_ids,
                "plugin_skill_ids": hero_obj.plugin_skill_ids,
            }
            army_config["heroes"].append(hero_config)
        save_data_list.append(army_config)
    return save_data_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run battle simulation")
    parser.add_argument(
        "--setup",
        help="Path to JSON setup file to load and run non-interactively",
    )
    args = parser.parse_args()

    print("=== Battle Simulator ===")
    ensure_setups_dir()
    if args.setup:
        loaded = load_setup_from_file(args.setup)
        if not loaded:
            sys.exit(1)
        run_additional_simulations(loaded, num_workers=os.cpu_count())
        plt.close("all")
        sys.exit(0)

    armies_to_simulate: List[Army] = []

    action_prompt = "Choose action: (N)ew setup, (L)oad setup, (R)un last setup (if available), (Q)uit: "
    chosen_action = ""

    # Check if last run setup exists for the (R) option
    can_run_last = os.path.exists(LAST_SETUP_FILENAME)
    if not can_run_last:
        action_prompt = "Choose action: (N)ew setup, (L)oad setup, (Q)uit: "

    while not armies_to_simulate or len(armies_to_simulate) != 2:
        chosen_action = input(action_prompt).strip().upper()

        if chosen_action == "Q":
            print("Exiting simulator.")
            sys.exit(0)

        elif chosen_action == "N":
            armies_to_simulate = run_interactive_setup()
            if len(armies_to_simulate) == 2:
                save_choice = input("Save this setup? (y/N): ").strip().lower()
                if save_choice == "y":
                    file_name_base = input(
                        "Enter filename for setup (e.g., my_test_setup, .json will be added): "
                    ).strip()
                    if file_name_base:
                        save_setup_to_file(
                            get_setup_data_for_saving(armies_to_simulate),
                            f"{file_name_base}.json",
                        )
                    else:
                        print(
                            "No filename entered, setup not saved by custom name (but saved as last run)."
                        )
                        # Still save as last run even if no custom name
                        save_setup_to_file(
                            get_setup_data_for_saving(armies_to_simulate),
                            os.path.basename(LAST_SETUP_FILENAME),
                        )

                else:  # If not saving with custom name, still save as last run
                    save_setup_to_file(
                        get_setup_data_for_saving(armies_to_simulate),
                        os.path.basename(LAST_SETUP_FILENAME),
                    )

        elif chosen_action == "L":
            saved_files = list_saved_setups()
            if not saved_files:
                print("No saved setups found. Please create a new setup first.")
                continue  # Go back to action prompt

            print("\nAvailable setups:")
            for idx, fname in enumerate(saved_files):
                print(f"  [{idx + 1}] {fname}")

            file_choice_idx_str = input(
                f"Enter number of setup to load (1-{len(saved_files)}): "
            ).strip()
            try:
                file_choice_idx = int(file_choice_idx_str) - 1
                if 0 <= file_choice_idx < len(saved_files):
                    selected_file = saved_files[file_choice_idx]
                    loaded_data_list = load_setup_from_file(selected_file)
                    if loaded_data_list:
                        armies_to_simulate = create_armies_from_data(loaded_data_list)
                        # Save this loaded setup as the "last run" setup as well
                        save_setup_to_file(
                            loaded_data_list, os.path.basename(LAST_SETUP_FILENAME)
                        )

                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif chosen_action == "R" and can_run_last:
            print("Loading last run setup...")
            loaded_data_list = load_setup_from_file(
                os.path.basename(LAST_SETUP_FILENAME)
            )
            if loaded_data_list:
                armies_to_simulate = create_armies_from_data(loaded_data_list)
            else:
                print("Could not load last setup. Please create a new one.")

        elif chosen_action == "R" and not can_run_last:
            print("No last setup available to run.")

        else:
            print("Invalid action. Please choose N, L, R (if available), or Q.")

        if len(armies_to_simulate) != 2 and chosen_action not in ["Q"]:
            print("Setup was not completed or loaded correctly. Please try again.")
            armies_to_simulate = []  # Reset to ensure loop continues if setup failed

    if armies_to_simulate and len(armies_to_simulate) == 2:
        setup_snapshot = get_setup_data_for_saving(armies_to_simulate)
        run_additional_simulations(setup_snapshot, num_workers=os.cpu_count())
        plt.close("all")
        sys.exit(0)
    elif chosen_action != "Q":  # If not quitting and setup failed
        print("Could not set up two armies. Exiting.")
