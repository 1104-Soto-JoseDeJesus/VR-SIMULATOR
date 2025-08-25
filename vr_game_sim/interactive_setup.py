# === File: interactive_setup.py ===
from typing import List, Optional, Dict, Tuple, Any

from .enums import SkillType
from .unit_definition import Unit
from .hero_definition import Hero, HERO_PRESETS  # HERO_PRESETS is imported here
from .skill_system import SkillDefinition


def input_choice_numbered(prompt: str, choices_ordered: List[str], default: Optional[str] = None) -> str:
    print(prompt)
    indexed_choices: Dict[int, str] = {i + 1: choice for i, choice in enumerate(choices_ordered)}
    default_num_display = ""
    default_selection_value = default

    if default:
        try:
            default_idx = choices_ordered.index(default) + 1
            default_num_display = f" (default: {default_idx} - '{default}')"
        except ValueError:
            default_num_display = f" (default: '{default}')"  # Should not happen if default is in choices

    for i, choice_text in indexed_choices.items():
        print(f"  [{i}] {choice_text}")
    prompt_text = f"Enter your choice by number{default_num_display}: "

    while True:
        user_input_str = input(prompt_text).strip()
        if not user_input_str and default_selection_value is not None:
            return default_selection_value
        try:
            choice_num = int(user_input_str)
            if choice_num in indexed_choices:
                return indexed_choices[choice_num]
            else:
                print(f"Invalid number. Please select from 1 to {len(choices_ordered)}.")
        except ValueError:
            # Allow direct string input matching default if default is not in choices_ordered (e.g. free text default)
            if default and user_input_str == default:
                return default
            print("Invalid input. Please enter a number or press Enter for default.")


def input_multi_choice_numbered(prompt: str, option_pairs: List[Tuple[str, str]]) -> List[str]:
    """Allows the user to select multiple options presented in a numbered list.

    `option_pairs` should be a list of tuples where the first element is the
    value to return and the second is the text displayed to the user. Returns
    the list of selected values. An empty return list means no selection.
    """
    print(prompt)
    for idx, (_, display) in enumerate(option_pairs, start=1):
        print(f"  [{idx}] {display}")

    while True:
        raw = input("Enter numbers separated by commas (leave blank for none): ").strip()
        if not raw:
            return []
        try:
            nums = [int(val.strip()) for val in raw.split(',') if val.strip()]
        except ValueError:
            print("Invalid input. Please enter numbers only.")
            continue
        if all(1 <= n <= len(option_pairs) for n in nums):
            return [option_pairs[n - 1][0] for n in nums]
        print(f"Invalid selection. Choose numbers between 1 and {len(option_pairs)}.")


def input_int(prompt: str, min_val: Optional[int] = None, max_val: Optional[int] = None,
              default: Optional[int] = None) -> int:
    prompt_text = prompt
    if default is not None: prompt_text += f" (default: {default})"
    prompt_text += ": "
    while True:
        try:
            val_str = input(prompt_text).strip()
            if not val_str and default is not None: return default
            val = int(val_str)
            if (min_val is None or val >= min_val) and (max_val is None or val <= max_val): return val
            error_parts = []
            if min_val is not None: error_parts.append(f"greater than or equal to {min_val}")
            if max_val is not None: error_parts.append(f"less than or equal to {max_val}")
            print(f"Value must be {' and '.join(error_parts)}.")
        except ValueError:
            print("Invalid input. Please enter a whole number.")


def input_float(prompt: str, default: Optional[float] = None) -> float:
    prompt_text = prompt
    if default is not None: prompt_text += f" (default: {default})"
    prompt_text += " (e.g., 0.1 for +10%): "
    while True:
        try:
            val_str = input(prompt_text).strip()
            if not val_str and default is not None: return default
            return float(val_str)
        except ValueError:
            print("Invalid input. Please enter a decimal number (e.g., 0.05).")


def prompt_grid_position(used_positions: set[Tuple[int, int]]) -> Tuple[int, int]:
    """Prompt the user for a grid position within the 2x4 arena.

    The arena has four columns (0-3) and two rows (0-1). Ensures the chosen slot
    is not already occupied.
    """
    while True:
        col = input_int("  Enter column (0-3)", 0, 3)
        row = input_int("  Enter row (0-1)", 0, 1)
        pos = (col, row)
        if pos not in used_positions:
            used_positions.add(pos)
            return pos
        print("  Slot already occupied. Choose another.")


def setup_simple_army(army_name: str) -> Dict[str, Any]:
    """Minimal interactive setup for an army without heroes."""
    unit_type = input_choice_numbered("  Unit type", ["infantry", "archers", "pikemen"], "infantry")
    tier = input_int("  Tier", 1, 10, 5)
    count = input_int("  Troop count", 1)
    atk = input_float("  Attack modifier", 0.0)
    defense = input_float("  Defense modifier", 0.0)
    hp = input_float("  HP modifier", 0.0)
    return {
        "army_name": army_name,
        "unit_type": unit_type,
        "tier": tier,
        "count": count,
        "atk_mod": atk,
        "def_mod": defense,
        "hp_mod": hp,
        "heroes": [],
    }


def setup_armies_arena_interactive(side_label: str, march_count: int) -> List[Dict[str, Any]]:
    """Interactive helper to build multiple marches for arena mode."""
    marches: List[Dict[str, Any]] = []
    used: set[Tuple[int, int]] = set()
    for i in range(march_count):
        print(f"\nConfiguring {side_label} march {i + 1}")
        name = input(f"  Enter march name (default: {side_label}_{i + 1}): ").strip() or f"{side_label}_{i + 1}"
        army_conf = setup_simple_army(name)
        pos = prompt_grid_position(used)
        army_conf["grid_pos"] = list(pos)
        marches.append(army_conf)
    return marches


def _select_skill_interactive(
        prompt_message: str,
        skill_type_filter: SkillType,
        current_skill_id: Optional[str],
        is_talent_slot: bool,
        skill_registry: Dict[str, SkillDefinition]
) -> str:
    print(prompt_message)
    candidate_skills_map: Dict[int, Tuple[str, str]] = {}
    display_idx = 1

    none_option_id = "dummy_talent_empty" if is_talent_slot else ""
    # Ensure dummy_talent_empty is in skill_registry for its name, or provide a fallback
    default_none_name = "Empty Talent Slot" if is_talent_slot else "None / Empty Slot"
    none_option_name = skill_registry.get("dummy_talent_empty", {}).get("name",
                                                                        default_none_name) if is_talent_slot else "None / Empty Slot"

    candidate_skills_map[display_idx] = (none_option_id, none_option_name)
    display_idx += 1

    available_skills = []
    for s_id, s_def in skill_registry.items():
        if s_def.get('type') == skill_type_filter:
            # Don't list the dummy talent among selectable options if it's a talent slot, it's covered by "None"
            if is_talent_slot and s_id == "dummy_talent_empty":
                continue
            available_skills.append((s_id, s_def.get("name", s_id)))  # Use ID as fallback name
    available_skills.sort(key=lambda x: x[1])  # Sort by name

    for s_id, s_name in available_skills:
        # Ensure no duplicates if a skill ID somehow matches none_option_id but isn't the dummy for talents
        if s_id not in [val[0] for val in candidate_skills_map.values()]:
            candidate_skills_map[display_idx] = (s_id, s_name)
            display_idx += 1

    print("Available options:")
    default_choice_num_display = None
    final_default_skill_id_for_prompt = current_skill_id if current_skill_id is not None else none_option_id

    for num, (s_id, s_name) in candidate_skills_map.items():
        id_display = f"(ID: {s_id})" if s_id and s_id != "dummy_talent_empty" and s_id != "" else ""
        print(f"  [{num}] {s_name} {id_display}")
        if s_id == final_default_skill_id_for_prompt:
            default_choice_num_display = num

    prompt_text_final = "Enter selection by number"
    if default_choice_num_display is not None and default_choice_num_display in candidate_skills_map:
        default_name_for_prompt = candidate_skills_map[default_choice_num_display][1]
        prompt_text_final += f" (default: {default_choice_num_display} - '{default_name_for_prompt}')"
    prompt_text_final += ": "

    while True:
        user_input_str = input(prompt_text_final).strip()
        if not user_input_str and final_default_skill_id_for_prompt is not None:
            # Ensure the default ID being returned is valid, especially for "None" options
            if final_default_skill_id_for_prompt == "" and is_talent_slot:  # Should be dummy_talent_empty for talents
                return "dummy_talent_empty"
            return final_default_skill_id_for_prompt

        try:
            choice_num = int(user_input_str)
            if choice_num in candidate_skills_map:
                selected_id = candidate_skills_map[choice_num][0]
                # Ensure correct "None" ID for talents
                if selected_id == "" and is_talent_slot:
                    return "dummy_talent_empty"
                return selected_id
            else:
                print(f"Invalid number. Please select from 1 to {len(candidate_skills_map)}.")
        except ValueError:
            print("Invalid input. Please enter a number or press Enter for default.")


def setup_hero_interactive(hero_index: int, army_name_for_hero_setup: str,
                           skill_registry: Dict[str, SkillDefinition]) -> Optional[Hero]:
    print(f"\n  --- Hero {hero_index} Setup for {army_name_for_hero_setup} ---")

    # MODIFICATION: Present preset choices by number with option for custom entry
    preset_names_sorted = sorted([name.capitalize() for name in HERO_PRESETS.keys()])
    preset_options = preset_names_sorted + ["Custom"]
    chosen_preset = input_choice_numbered(
        f"  Select hero preset for Hero {hero_index} or choose 'Custom' to enter a name",
        preset_options,
        default="Custom",
    )

    if chosen_preset == "Custom":
        hero_name_input = input(
            f"  Enter custom name for Hero {hero_index} (leave blank to cancel): "
        ).strip()
        if not hero_name_input:
            return None
    else:
        hero_name_input = chosen_preset

    hero_key = hero_name_input.lower()
    is_preset_hero = hero_key in HERO_PRESETS

    talents = ["dummy_talent_empty"] * 3  # Default to dummy talent ID for empty talent slots
    base_skills = ["", ""]  # Default to empty string for empty base/plugin slots
    plugin_skills = ["", ""]

    if is_preset_hero:
        print(f"    Using preset for {hero_name_input.capitalize()}.")
        preset = HERO_PRESETS[hero_key]
        # Ensure talents list is exactly 3 items, padding with dummy_talent_empty if preset has fewer
        talents = (preset.get('talents', []) + ["dummy_talent_empty"] * 3)[:3]
        # Ensure base_skills and plugin_skills lists are exactly 2 items, padding with "" if fewer
        base_skills = (preset.get('base_skills', []) + ["", ""] * 2)[:2]
        plugin_skills = (preset.get('plugin_skills', []) + ["", ""] * 2)[:2]

        print("    Preset Talents (fixed):")
        for i, talent_id in enumerate(talents):
            talent_name = skill_registry.get(talent_id, {}).get("name", "Unknown Talent") if talent_id else "Empty Slot"
            print(f"      Slot {i + 1}: {talent_name} (ID: {talent_id or 'N/A'})")
        print("    Preset Base Skills (fixed):")
        for i, bs_id in enumerate(base_skills):
            name = skill_registry.get(bs_id, {}).get("name", "Empty Slot") if bs_id else "Empty Slot"
            print(f"      Slot {i + 1}: {name} (ID: {bs_id or 'N/A'})")
        # Plugin skills for preset heroes are typically empty or fixed, so just list them.
        # If you want them to be customizable even for presets, this part needs adjustment.
        print("    Preset Plugin Skills (fixed):")
        for i, ps_id in enumerate(plugin_skills):
            name = skill_registry.get(ps_id, {}).get("name", "Empty Slot") if ps_id else "Empty Slot"
            print(f"      Slot {i + 1}: {name} (ID: {ps_id or 'N/A'})")

    else:  # Custom hero setup
        print(f"    Custom hero setup for '{hero_name_input}'.")
        print("    --- Talents (3 required) ---")
        for i in range(3):
            talents[i] = _select_skill_interactive(
                f"    Talent Slot {i + 1}", SkillType.TALENT, talents[i], True, skill_registry)
        print("    --- Base Skills (max 2) ---")
        for i in range(2):
            base_skills[i] = _select_skill_interactive(
                f"    Base Skill Slot {i + 1}", SkillType.BASE_SKILL, base_skills[i], False, skill_registry)

    # Always allow plugin skill selection for both preset (if you want to override) and custom heroes.
    # If presets should have fixed plugins, this part could be conditional.
    # For now, let's assume plugins are always customizable.
    print(f"    --- Plugin Skills for {hero_name_input.capitalize()} (Hero {hero_index}) (max 2) ---")
    for i in range(2):
        plugin_skills[i] = _select_skill_interactive(
            f"    Plugin Skill Slot {i + 1}", SkillType.PLUGIN_SKILL, plugin_skills[i], False, skill_registry)

    # Filter out empty strings before creating the Hero object, but ensure talents always has 3 (using dummy_talent_empty)
    final_talents = [t_id if t_id else "dummy_talent_empty" for t_id in talents]
    final_base_skills = [bs_id for bs_id in base_skills if bs_id and bs_id.lower() not in ["none", "blank"]]
    final_plugin_skills = [ps_id for ps_id in plugin_skills if ps_id and ps_id.lower() not in ["none", "blank"]]

    return Hero(hero_name_input.capitalize(), final_talents, final_base_skills, final_plugin_skills, skill_registry)

