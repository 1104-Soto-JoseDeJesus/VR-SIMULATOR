"""
Contains generic or utility skill handlers that can be reused by multiple skills.
"""
from typing import Tuple, List, Optional, Dict, Any

# Use string forward references for type hints to avoid circular imports
ArmyRef = "Army"
GameSimulatorRef = "GameSimulator"
SkillDefinition = Dict[str, Any] # from ..skill_system
EffectInstance = "EffectInstance" # from ..effect_system
# No direct need for enums here unless a utility handler becomes very complex

def handle_generic_single_damage_skill(
    triggering_army: ArmyRef, opponent_army: ArmyRef,
    skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    damage_factor = skill_config.get("damage_factor", 0.0)

    if damage_factor > 0:
        calc_target = opponent_army
        if event_data and event_data.get('actual_opponent_for_calc'):
            calc_target = event_data['actual_opponent_for_calc']

        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army,
            calc_target,
            damage_factor,
            source_skill_def=skill_def,
            damage_application_target=opponent_army,
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage to {opponent_army.name}.",
                {
                    "damage_done_hp": round(raw_logged_damage),
                    "absorbed_hp": round(absorbed),
                    "potential_kills": kills,
                    "calculation_steps": calc_steps,
                },
            )
        )
    return an_effect_happened, log_details

def handle_generic_heal_skill(
    triggering_army: ArmyRef, opponent_army: ArmyRef, # opponent_army is context for heal calc
    skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    heal_factor = skill_config.get("heal_factor", 0.0)
    target_army_for_heal = triggering_army # Default: heal self

    if heal_factor > 0:
        healed_amount = target_army_for_heal.calculate_and_add_pending_healing(
            heal_factor,
            healer_army=triggering_army,
            opponent_of_healer=opponent_army,
            skill_heal_adjustment_magnitude=0.0,  # Assuming generic heal doesn't have its own direct adjustment
            source_skill_id=skill_id,
        )
        if healed_amount > 0:
            an_effect_happened = True
            log_details.append((f"Calculated potential healing for {target_army_for_heal.name} (Factor: {heal_factor}), amount: {healed_amount:.0f} HP.", None))
    return an_effect_happened, log_details
