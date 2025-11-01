"""Logic handlers for mount skills."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..enums import EffectType
from ..skill_system import SkillDefinition

ArmyRef = "Army"
GameSimulatorRef = "GameSimulator"


def _apply_effects(
    *,
    source_army: ArmyRef,
    target_army: ArmyRef,
    opponent_for_calc: ArmyRef,
    skill_id: str,
    effects: List[Dict[str, Any]] | None,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    if not effects:
        return False, []

    triggered = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []

    for effect in effects:
        effect_data = effect.copy()
        created = source_army._create_and_add_single_effect(
            effect_data,
            source_skill_id=skill_id,
            owner_army=source_army,
            target_army=target_army,
            opponent_of_owner_for_calc=opponent_for_calc,
        )
        if created:
            triggered = True
            if created.effect_type == EffectType.STAT_MOD:
                desc = created.get_functionality_description()
            else:
                desc = created.name or "Effect applied"
            logs.append((f"Applies effect: {desc} for {created.duration + 1} round(s).", None))
    return triggered, logs


def _apply_damage_events(
    *,
    triggering_army: ArmyRef,
    calc_target: ArmyRef,
    application_target: ArmyRef,
    simulator: GameSimulatorRef,
    skill_def: SkillDefinition,
    damage_factors: List[float],
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    triggered = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []

    for factor in damage_factors:
        if not factor:
            continue
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army,
            calc_target,
            factor,
            source_skill_def=skill_def,
            damage_application_target=application_target,
        )
        if hp_damage > 0:
            application_target.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            triggered = True
        logs.append(
            (
                f"Deals direct damage (Factor {factor:.0f}).",
                {
                    "damage_done_hp": round(raw_logged_damage),
                    "absorbed_hp": round(absorbed),
                    "potential_kills": kills,
                },
            )
        )
    return triggered, logs


def _apply_heals(
    *,
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_id: str,
    heal_factors: List[float],
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    triggered = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []

    for heal_factor in heal_factors:
        if not heal_factor:
            continue
        healed_amount = triggering_army.calculate_and_add_pending_healing(
            heal_factor,
            healer_army=triggering_army,
            opponent_of_healer=opponent_army,
            source_skill_id=skill_id,
        )
        if healed_amount > 0:
            triggered = True
        logs.append((f"Heals for factor {heal_factor:.0f} (result {healed_amount:.0f} HP).", None))
    return triggered, logs


def _apply_rage_gain(
    *,
    triggering_army: ArmyRef,
    target_army: ArmyRef,
    rage_amount: float,
    skill_id: str,
    mount_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    if rage_amount <= 0:
        return False, []
    metadata = mount_metadata or {}
    rage_to_award = float(rage_amount)
    if metadata:
        slot_identifier: Any = metadata.get("slot")
        if slot_identifier is None:
            slot_identifier = triggering_army.get_mount_slot_key(metadata)
        target_name = target_army.name if target_army else triggering_army.name
        key = (str(slot_identifier), target_name)
        existing = triggering_army.mount_rage_grants_this_round.get(key)
        if existing is not None:
            if existing >= rage_amount - 1e-9:
                return False, []
            rage_to_award = rage_amount - existing
        triggering_army.mount_rage_grants_this_round[key] = max(
            existing or 0.0, float(rage_amount)
        )

    if rage_to_award <= 0:
        return False, []

    gained = target_army.add_rage(rage_to_award, source_skill_id=skill_id)
    if gained <= 0:
        return False, []
    return True, [(f"Grants {gained:.0f} Rage.", None)]


def _apply_passive_effects_once(
    *,
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_def: SkillDefinition,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    passive_effects = skill_def.get("effects_to_apply")
    if not passive_effects:
        return False, []

    passive_key = triggering_army.get_skill_trigger_key(skill_def)
    if passive_key in triggering_army.mount_passives_applied:
        return False, []

    triggered, logs = _apply_effects(
        source_army=triggering_army,
        target_army=triggering_army,
        opponent_for_calc=opponent_army,
        skill_id=skill_def["id"],
        effects=passive_effects,
    )

    if triggered:
        triggering_army.mount_passives_applied.add(passive_key)

    return triggered, logs


def handle_mount_command_skill(
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_def: SkillDefinition,
    event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    config = skill_def.get("config", {})
    calc_target = opponent_army
    if event_data and event_data.get("actual_opponent_for_calc"):
        calc_target = event_data["actual_opponent_for_calc"]

    mount_metadata = config.get("mount_metadata") or {}

    damage_factors = [float(x) for x in config.get("damage_factors", []) if x]
    heal_factors = [float(x) for x in config.get("heal_factors", []) if x]
    self_effects = config.get("self_effects") or []
    enemy_effects = config.get("enemy_effects") or []
    rage_gain = float(config.get("rage_gain", 0.0))

    triggered = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []

    dmg_triggered, dmg_logs = _apply_damage_events(
        triggering_army=triggering_army,
        calc_target=calc_target,
        application_target=opponent_army,
        simulator=simulator,
        skill_def=skill_def,
        damage_factors=damage_factors,
    )
    if dmg_triggered:
        triggered = True
    logs.extend(dmg_logs)

    heal_triggered, heal_logs = _apply_heals(
        triggering_army=triggering_army,
        opponent_army=opponent_army,
        skill_id=skill_def["id"],
        heal_factors=heal_factors,
    )
    if heal_triggered:
        triggered = True
    logs.extend(heal_logs)

    self_triggered, self_logs = _apply_effects(
        source_army=triggering_army,
        target_army=triggering_army,
        opponent_for_calc=opponent_army,
        skill_id=skill_def["id"],
        effects=self_effects,
    )
    if self_triggered:
        triggered = True
    logs.extend(self_logs)

    enemy_triggered, enemy_logs = _apply_effects(
        source_army=triggering_army,
        target_army=opponent_army,
        opponent_for_calc=opponent_army,
        skill_id=skill_def["id"],
        effects=enemy_effects,
    )
    if enemy_triggered:
        triggered = True
    logs.extend(enemy_logs)

    rage_triggered, rage_logs = _apply_rage_gain(
        triggering_army=triggering_army,
        target_army=triggering_army,
        rage_amount=rage_gain,
        skill_id=skill_def["id"],
        mount_metadata=mount_metadata,
    )
    if rage_triggered:
        triggered = True
    logs.extend(rage_logs)

    passive_triggered, passive_logs = _apply_passive_effects_once(
        triggering_army=triggering_army,
        opponent_army=opponent_army,
        skill_def=skill_def,
    )
    if passive_triggered:
        triggered = True
    logs.extend(passive_logs)

    return triggered, logs


def handle_mount_cooperation_skill(
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_def: SkillDefinition,
    event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    config = skill_def.get("config", {})
    calc_target = opponent_army
    if event_data and event_data.get("actual_opponent_for_calc"):
        calc_target = event_data["actual_opponent_for_calc"]

    mount_metadata = config.get("mount_metadata") or {}

    damage_factors = [float(x) for x in config.get("damage_factors", []) if x]
    heal_factors = [float(x) for x in config.get("heal_factors", []) if x]
    self_effects = config.get("self_effects") or []
    enemy_effects = config.get("enemy_effects") or []
    rage_gain = float(config.get("rage_gain", 0.0))

    triggered = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []

    dmg_triggered, dmg_logs = _apply_damage_events(
        triggering_army=triggering_army,
        calc_target=calc_target,
        application_target=opponent_army,
        simulator=simulator,
        skill_def=skill_def,
        damage_factors=damage_factors,
    )
    if dmg_triggered:
        triggered = True
    logs.extend(dmg_logs)

    heal_triggered, heal_logs = _apply_heals(
        triggering_army=triggering_army,
        opponent_army=opponent_army,
        skill_id=skill_def["id"],
        heal_factors=heal_factors,
    )
    if heal_triggered:
        triggered = True
    logs.extend(heal_logs)

    self_triggered, self_logs = _apply_effects(
        source_army=triggering_army,
        target_army=triggering_army,
        opponent_for_calc=opponent_army,
        skill_id=skill_def["id"],
        effects=self_effects,
    )
    if self_triggered:
        triggered = True
    logs.extend(self_logs)

    enemy_triggered, enemy_logs = _apply_effects(
        source_army=triggering_army,
        target_army=opponent_army,
        opponent_for_calc=opponent_army,
        skill_id=skill_def["id"],
        effects=enemy_effects,
    )
    if enemy_triggered:
        triggered = True
    logs.extend(enemy_logs)

    rage_triggered, rage_logs = _apply_rage_gain(
        triggering_army=triggering_army,
        target_army=triggering_army,
        rage_amount=rage_gain,
        skill_id=skill_def["id"],
        mount_metadata=mount_metadata,
    )
    if rage_triggered:
        triggered = True
    logs.extend(rage_logs)

    passive_triggered, passive_logs = _apply_passive_effects_once(
        triggering_army=triggering_army,
        opponent_army=opponent_army,
        skill_def=skill_def,
    )
    if passive_triggered:
        triggered = True
    logs.extend(passive_logs)

    return triggered, logs


def handle_mount_reactive_skill(
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_def: SkillDefinition,
    event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    config = skill_def.get("config", {})
    calc_target = opponent_army
    if event_data and event_data.get("actual_opponent_for_calc"):
        calc_target = event_data["actual_opponent_for_calc"]

    trigger_type = event_data.get("trigger_type") if isinstance(event_data, dict) else None
    allowed_sources = config.get("reactive_sources") or []
    if allowed_sources and trigger_type not in allowed_sources:
        return False, []

    mount_metadata = config.get("mount_metadata") or {}

    damage_factors = [float(x) for x in config.get("damage_factors", []) if x]
    heal_factors = [float(x) for x in config.get("heal_factors", []) if x]
    self_effects = config.get("self_effects") or []
    enemy_effects = config.get("enemy_effects") or []
    rage_gain = float(config.get("rage_gain", 0.0))

    triggered = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []

    dmg_triggered, dmg_logs = _apply_damage_events(
        triggering_army=triggering_army,
        calc_target=calc_target,
        application_target=opponent_army,
        simulator=simulator,
        skill_def=skill_def,
        damage_factors=damage_factors,
    )
    if dmg_triggered:
        triggered = True
    logs.extend(dmg_logs)

    heal_triggered, heal_logs = _apply_heals(
        triggering_army=triggering_army,
        opponent_army=opponent_army,
        skill_id=skill_def["id"],
        heal_factors=heal_factors,
    )
    if heal_triggered:
        triggered = True
    logs.extend(heal_logs)

    self_triggered, self_logs = _apply_effects(
        source_army=triggering_army,
        target_army=triggering_army,
        opponent_for_calc=opponent_army,
        skill_id=skill_def["id"],
        effects=self_effects,
    )
    if self_triggered:
        triggered = True
    logs.extend(self_logs)

    enemy_triggered, enemy_logs = _apply_effects(
        source_army=triggering_army,
        target_army=opponent_army,
        opponent_for_calc=opponent_army,
        skill_id=skill_def["id"],
        effects=enemy_effects,
    )
    if enemy_triggered:
        triggered = True
    logs.extend(enemy_logs)

    rage_triggered, rage_logs = _apply_rage_gain(
        triggering_army=triggering_army,
        target_army=triggering_army,
        rage_amount=rage_gain,
        skill_id=skill_def["id"],
        mount_metadata=mount_metadata,
    )
    if rage_triggered:
        triggered = True
    logs.extend(rage_logs)

    passive_triggered, passive_logs = _apply_passive_effects_once(
        triggering_army=triggering_army,
        opponent_army=opponent_army,
        skill_def=skill_def,
    )
    if passive_triggered:
        triggered = True
    logs.extend(passive_logs)

    return triggered, logs
