"""Logic handlers for gem skills."""

from __future__ import annotations

from typing import Dict, Any, Optional, Tuple, List

from ..enums import EffectType
from ..skill_system import SkillDefinition, ArmyRef, GameSimulatorRef


def _get_army_round(army: ArmyRef, simulator: GameSimulatorRef) -> int:
    """Return the current round for ``army`` with simulator fallback."""

    if hasattr(army, "army_round"):
        return army.army_round
    return simulator.round if simulator else 0


def _matches_unit(unit_type: Optional[str], requirement: Any) -> bool:
    """Return ``True`` when ``unit_type`` satisfies ``requirement``."""

    if requirement in (None, "", []):
        return True
    if unit_type is None:
        return False
    if isinstance(requirement, (list, tuple, set)):
        return any(_matches_unit(unit_type, item) for item in requirement)
    return unit_type.lower() == str(requirement).lower()


def handle_gem_skill_delayed_stat_mod(
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_def: SkillDefinition,
    event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    """Apply a stat modifying effect on a specific round for gem skills."""

    config = skill_def.get("config", {}) or {}
    current_round = _get_army_round(triggering_army, simulator)
    trigger_round = int(config.get("trigger_round", 1))
    if current_round != trigger_round:
        return False, []

    if not _matches_unit(getattr(triggering_army.unit, "unit_type", None), config.get("require_own_unit")):
        return False, []

    enemy_requirement = config.get("require_enemy_unit")
    if enemy_requirement:
        enemy_unit_type = getattr(opponent_army.unit, "unit_type", None) if opponent_army else None
        if not _matches_unit(enemy_unit_type, enemy_requirement):
            return False, []

    stat_to_mod = config.get("stat_to_mod")
    if not stat_to_mod:
        return False, []

    skill_id = skill_def["id"]
    effect_name = config.get("effect_name", skill_def.get("name", skill_id))

    # Avoid applying duplicate effects if this handler runs multiple times in the same round.
    for effect_list in (
        getattr(triggering_army, "active_effects", []),
        getattr(triggering_army, "upcoming_effects", []),
        getattr(triggering_army, "effects_to_activate_next_round", []),
    ):
        for effect in effect_list:
            if effect.source_skill_id == skill_id and effect.name == effect_name:
                return False, []

    raw_duration = config.get("duration_rounds")
    duration_rounds: Optional[int]
    if raw_duration is None:
        duration_rounds = None
        duration_value = -1
    else:
        duration_rounds = int(round(float(raw_duration)))
        duration_value = max(0, duration_rounds - 1)

    effect_data: Dict[str, Any] = {
        "effect_type": EffectType.STAT_MOD,
        "name": effect_name,
        "stat_to_mod": stat_to_mod,
        "magnitude": float(config.get("magnitude", 0.0)),
        "duration": duration_value,
        "activate_next_round": bool(config.get("activate_next_round", True)),
        "is_dispellable": bool(config.get("is_dispellable", True)),
    }
    if config.get("config_filter"):
        effect_data["config_filter"] = config["config_filter"]

    created_effect = triggering_army._create_and_add_single_effect(
        effect_data,
        skill_id,
        triggering_army,
        triggering_army,
        opponent_army,
    )
    if not created_effect:
        return False, []

    activate_next = bool(config.get("activate_next_round", True))
    start_round = current_round + (1 if activate_next else 0)
    if duration_rounds is None:
        duration_text = f"starting round {start_round} until removed"
    else:
        end_round = start_round + max(0, duration_rounds - 1)
        duration_text = (
            f"for {duration_rounds} rounds (R{start_round}-R{end_round})"
            if duration_rounds > 0
            else f"in round {start_round}"
        )

    log_message = (
        f"Applies {created_effect.get_functionality_description()} {duration_text}."
    )
    return True, [(log_message, None)]

