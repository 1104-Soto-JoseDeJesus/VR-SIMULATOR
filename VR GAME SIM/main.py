# === File: main.py (with Save/Load Setup Feature) ===
import math
import random
import json
import os
from typing import List, Optional, Dict, Any
import contextlib
import io
import matplotlib.pyplot as plt

from enums import SkillType
from unit_definition import Unit as UnitClass
from hero_definition import Hero, HERO_PRESETS
from army_composition import Army
from game_simulator import GameSimulator
from interactive_setup import (
    input_choice_numbered, input_int, input_float, setup_hero_interactive
)
from skill_definitions import SKILL_REGISTRY_GLOBAL

# --- Configuration for Save/Load ---
SETUPS_DIR = "setups"
LAST_SETUP_FILENAME = os.path.join(SETUPS_DIR, "_last_run_setup.json")
HISTOGRAM_DIR = "histograms"


def ensure_setups_dir():
    """Ensures the setups directory exists."""
    if not os.path.exists(SETUPS_DIR):
        os.makedirs(SETUPS_DIR)


def ensure_histogram_dir():
    """Ensures the histogram output directory exists."""
    if not os.path.exists(HISTOGRAM_DIR):
        os.makedirs(HISTOGRAM_DIR)


def save_setup_to_file(setup_data: List[Dict[str, Any]], filename: str):
    """Saves the army setup data to a JSON file."""
    ensure_setups_dir()
    filepath = os.path.join(SETUPS_DIR, filename)
    try:
        with open(filepath, 'w') as f:
            json.dump(setup_data, f, indent=4)
        print(f"Setup saved to {filepath}")
        # Also save as the last run setup
        with open(LAST_SETUP_FILENAME, 'w') as f_last:
            json.dump(setup_data, f_last, indent=4)
    except IOError as e:
        print(f"Error saving setup: {e}")


def load_setup_from_file(filename: str) -> Optional[List[Dict[str, Any]]]:
    """Loads army setup data from a JSON file."""
    filepath = os.path.join(SETUPS_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Error: Setup file {filepath} not found.")
        return None
    try:
        with open(filepath, 'r') as f:
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
        files = [f for f in os.listdir(SETUPS_DIR) if
                 f.endswith(".json") and f != os.path.basename(LAST_SETUP_FILENAME)]
        return sorted(files)
    except OSError:
        return []


def create_armies_from_data(loaded_data: List[Dict[str, Any]]) -> List[Army]:
    """Creates Army objects from loaded setup data."""
    armies: List[Army] = []
    for army_config in loaded_data:
        unit = UnitClass(
            army_config["unit_type"],
            army_config["tier"],
            army_config["count"],
            initial_atk_modifier=army_config["atk_mod"],
            initial_def_modifier=army_config["def_mod"],
            initial_hp_modifier=army_config["hp_mod"]
        )
        heroes_list: List[Hero] = []
        for hero_conf in army_config.get("heroes", []):
            # Hero constructor takes skill IDs and registry
            hero = Hero(
                name=hero_conf["hero_name_or_preset"],
                talent_ids=hero_conf["talent_ids"],
                base_skill_ids=hero_conf["base_skill_ids"],
                plugin_skill_ids=hero_conf["plugin_skill_ids"],
                skill_registry=SKILL_REGISTRY_GLOBAL
            )
            heroes_list.append(hero)

        # Create Army instance. The simulator instance will be injected later by GameSimulator.
        army_obj = Army(army_config["army_name"], unit, heroes_list)
        armies.append(army_obj)
    return armies


def run_additional_simulations(setup_data: List[Dict[str, Any]], runs: int = 200) -> None:
    """Runs extra simulations silently, generates histograms, and computes summary statistics."""
    own_remaining: List[float] = []
    enemy_remaining: List[float] = []
    rounds_taken: List[int] = []
    diff_results: List[float] = []
    winners: List[int] = []  # 1 -> army1, 2 -> army2, 0 -> draw

    army1_name = setup_data[0].get("army_name", "Army 1") if len(setup_data) > 0 else "Army 1"
    army2_name = setup_data[1].get("army_name", "Army 2") if len(setup_data) > 1 else "Army 2"
    battle_results: List[tuple] = []

    for _ in range(runs):
        armies = create_armies_from_data(setup_data)
        sim = GameSimulator(armies[0], armies[1])
        with contextlib.redirect_stdout(io.StringIO()):
            sim.simulate_battle()
        own_remaining.append(sim.army1.current_troop_count)
        enemy_remaining.append(sim.army2.current_troop_count)
        rounds_taken.append(sim.round)
        diff_results.append(sim.army1.current_troop_count - sim.army2.current_troop_count)
        if sim.army1.current_troop_count > 0 and sim.army2.current_troop_count <= 0:
            winners.append(1)
        elif sim.army2.current_troop_count > 0 and sim.army1.current_troop_count <= 0:
            winners.append(2)
        else:
            winners.append(0)
        battle_results.append((sim.army1.current_troop_count, sim.army2.current_troop_count))

    ensure_histogram_dir()

    plt.figure()
    plt.hist(own_remaining, bins='auto', color='blue', alpha=0.7)
    plt.title(f'{army1_name} Remaining Troops')
    plt.xlabel('Troops')
    plt.ylabel('Frequency')
    plt.savefig(os.path.join(HISTOGRAM_DIR, 'own_remaining_troops.png'))
    plt.close()

    plt.figure()
    plt.hist(enemy_remaining, bins='auto', color='red', alpha=0.7)
    plt.title(f'{army2_name} Remaining Troops')
    plt.xlabel('Troops')
    plt.ylabel('Frequency')
    plt.savefig(os.path.join(HISTOGRAM_DIR, 'enemy_remaining_troops.png'))
    plt.close()

    plt.figure()
    plt.hist(rounds_taken, bins='auto', color='green', alpha=0.7)
    plt.title('Rounds to Battle End')
    plt.xlabel('Rounds')
    plt.ylabel('Frequency')
    plt.savefig(os.path.join(HISTOGRAM_DIR, 'rounds_to_battle_end.png'))
    plt.close()

    # Pie chart for win percentages
    wins_army1 = winners.count(1)
    wins_army2 = winners.count(2)
    if wins_army1 + wins_army2 > 0:
        plt.figure()
        plt.pie([wins_army1, wins_army2], labels=[army1_name, army2_name], autopct='%1.1f%%', startangle=90)
        plt.title('Victory Distribution')
        plt.axis('equal')
        plt.savefig(os.path.join(HISTOGRAM_DIR, 'victory_distribution.png'))
        plt.close()

    # Determine battle closest to average outcome
    if diff_results:
        avg_diff = sum(diff_results) / len(diff_results)
        closest_idx = min(range(len(diff_results)), key=lambda i: abs(diff_results[i] - avg_diff))
        closest_own, closest_enemy = battle_results[closest_idx]
        winner_text = 'Draw'
        if winners[closest_idx] == 1:
            winner_text = army1_name
        elif winners[closest_idx] == 2:
            winner_text = army2_name
        print(f"Battle closest to average outcome: #{closest_idx + 1} -> Winner: {winner_text}; {army1_name}: {closest_own:.0f} troops, {army2_name}: {closest_enemy:.0f} troops")


def run_interactive_setup() -> List[Army]:
    """Runs the full interactive setup for two armies."""
    armies_setup_interactive: List[Army] = []
    ordered_unit_types = sorted(list(UnitClass.ALLOWED_TYPES))

    for i in range(1, 3):
        print(f"\n--- Army {i} Setup ---")
        army_name = input(f"Army {i} Name (default: Army {i}): ").strip() or f"Army {i}"
        unit_type_str = input_choice_numbered("Select Unit type", ordered_unit_types, default='pikemen')
        tier = input_int("Tier", min_val=min(UnitClass.ALLOWED_TIERS), max_val=max(UnitClass.ALLOWED_TIERS), default=5)
        count = input_int("Troop count", min_val=1, default=100000)
        print(f"  Enter initial stat modifiers for {unit_type_str} T{tier} (as decimals, e.g., 0.1 for +10%):")
        atk_mod = input_float("  Initial Attack Modifier", default=0.0)  # Changed default to float
        def_mod = input_float("  Initial Defense Modifier", default=0.0)  # Changed default to float
        hp_mod = input_float("  Initial HP Modifier", default=0.0)  # Changed default to float

        current_unit_obj = UnitClass(unit_type_str, tier, count,
                                     initial_atk_modifier=atk_mod,
                                     initial_def_modifier=def_mod,
                                     initial_hp_modifier=hp_mod)
        current_heroes_list: List[Hero] = []
        max_heroes_per_army = 2  # As per existing logic

        for hero_num in range(1, max_heroes_per_army + 1):
            add_hero_prompt = f"  Add Hero {hero_num} to {army_name}? (yes/no, default: yes): "
            add_hero_choice = input(add_hero_prompt).strip().lower() or 'yes'

            if add_hero_choice == 'yes':
                hero_obj = setup_hero_interactive(hero_num, army_name, SKILL_REGISTRY_GLOBAL)
                if hero_obj:
                    current_heroes_list.append(hero_obj)
                    skill_names_for_log = [s['name'] for s in hero_obj.skills if
                                           s['id'] != 'dummy_talent_empty' and s['id'] != '']
                    print(f"    Added {hero_obj.name} to {army_name} with skills: {skill_names_for_log}.")
            else:
                break

        army_instance = Army(army_name, current_unit_obj, current_heroes_list)
        armies_setup_interactive.append(army_instance)
        print(
            f"--- {army_name} (T{current_unit_obj.tier} {current_unit_obj.unit_type} x{current_unit_obj.initial_count}) setup complete. ---")
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
            "heroes": []
        }
        for hero_obj in army_obj.heroes:
            hero_config = {
                "hero_name_or_preset": hero_obj.name,  # This is the name used/entered during setup
                "talent_ids": hero_obj.talent_ids,
                "base_skill_ids": hero_obj.base_skill_ids,
                "plugin_skill_ids": hero_obj.plugin_skill_ids
            }
            army_config["heroes"].append(hero_config)
        save_data_list.append(army_config)
    return save_data_list


if __name__ == "__main__":
    print("=== Battle Simulator ===")
    ensure_setups_dir()
    armies_to_simulate: List[Army] = []

    action_prompt = "Choose action: (N)ew setup, (L)oad setup, (R)un last setup (if available), (Q)uit: "
    chosen_action = ""

    # Check if last run setup exists for the (R) option
    can_run_last = os.path.exists(LAST_SETUP_FILENAME)
    if not can_run_last:
        action_prompt = "Choose action: (N)ew setup, (L)oad setup, (Q)uit: "

    while not armies_to_simulate or len(armies_to_simulate) != 2:
        chosen_action = input(action_prompt).strip().upper()

        if chosen_action == 'Q':
            print("Exiting simulator.")
            exit()

        elif chosen_action == 'N':
            armies_to_simulate = run_interactive_setup()
            if len(armies_to_simulate) == 2:
                save_choice = input("Save this setup? (y/N): ").strip().lower()
                if save_choice == 'y':
                    file_name_base = input(
                        "Enter filename for setup (e.g., my_test_setup, .json will be added): ").strip()
                    if file_name_base:
                        save_setup_to_file(get_setup_data_for_saving(armies_to_simulate), f"{file_name_base}.json")
                    else:
                        print("No filename entered, setup not saved by custom name (but saved as last run).")
                        # Still save as last run even if no custom name
                        save_setup_to_file(get_setup_data_for_saving(armies_to_simulate),
                                           os.path.basename(LAST_SETUP_FILENAME))

                else:  # If not saving with custom name, still save as last run
                    save_setup_to_file(get_setup_data_for_saving(armies_to_simulate),
                                       os.path.basename(LAST_SETUP_FILENAME))

        elif chosen_action == 'L':
            saved_files = list_saved_setups()
            if not saved_files:
                print("No saved setups found. Please create a new setup first.")
                continue  # Go back to action prompt

            print("\nAvailable setups:")
            for idx, fname in enumerate(saved_files):
                print(f"  [{idx + 1}] {fname}")

            file_choice_idx_str = input(f"Enter number of setup to load (1-{len(saved_files)}): ").strip()
            try:
                file_choice_idx = int(file_choice_idx_str) - 1
                if 0 <= file_choice_idx < len(saved_files):
                    selected_file = saved_files[file_choice_idx]
                    loaded_data_list = load_setup_from_file(selected_file)
                    if loaded_data_list:
                        armies_to_simulate = create_armies_from_data(loaded_data_list)
                        # Save this loaded setup as the "last run" setup as well
                        save_setup_to_file(loaded_data_list, os.path.basename(LAST_SETUP_FILENAME))

                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif chosen_action == 'R' and can_run_last:
            print("Loading last run setup...")
            loaded_data_list = load_setup_from_file(os.path.basename(LAST_SETUP_FILENAME))
            if loaded_data_list:
                armies_to_simulate = create_armies_from_data(loaded_data_list)
            else:
                print("Could not load last setup. Please create a new one.")

        elif chosen_action == 'R' and not can_run_last:
            print("No last setup available to run.")

        else:
            print("Invalid action. Please choose N, L, R (if available), or Q.")

        if len(armies_to_simulate) != 2 and chosen_action not in ['Q']:
            print("Setup was not completed or loaded correctly. Please try again.")
            armies_to_simulate = []  # Reset to ensure loop continues if setup failed

    if armies_to_simulate and len(armies_to_simulate) == 2:
        # The GameSimulator constructor will inject the simulator instance into each Army
        setup_snapshot = get_setup_data_for_saving(armies_to_simulate)
        sim = GameSimulator(armies_to_simulate[0], armies_to_simulate[1])
        sim.simulate_battle()

        run_additional_simulations(setup_snapshot)
    elif chosen_action != 'Q':  # If not quitting and setup failed
        print("Could not set up two armies. Exiting.")

