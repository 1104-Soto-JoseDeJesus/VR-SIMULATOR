"""Logic handlers for jewel skills."""

from __future__ import annotations

import random

from typing import Dict, Any, Optional, Tuple, List

from ..enums import EffectType, DoTType
from ..skill_system import SkillDefinition, ArmyRef, GameSimulatorRef
from ..constants import (
    EFFECT_NAME_DELAYED_RAGE_GAIN,
    EFFECT_NAME_PENDING_HEIMDALL_PURIFY,
    EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
    EFFECT_NAME_HEIMDALL_STEALTH_EVASION,
    EFFECT_NAME_HEIMDALL_RETRIBUTION,
)


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
    """Apply a stat modifying effect on a specific round for jewel skills."""

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
    base_effect_name = config.get("effect_name", skill_def.get("name", skill_id))
    base_activate_next = bool(config.get("activate_next_round", True))
    base_is_dispellable = bool(config.get("is_dispellable", True))
    raw_duration = config.get("duration_rounds")

    # Build the collection of stat modifications this skill should apply.
    effect_configs: List[Dict[str, Any]] = [
        {
            "stat_to_mod": stat_to_mod,
            "magnitude": float(config.get("magnitude", 0.0)),
            "effect_name": base_effect_name,
            "config_filter": config.get("config_filter"),
            "activate_next_round": base_activate_next,
            "is_dispellable": base_is_dispellable,
            "duration_rounds": raw_duration,
        }
    ]

    additional_mods = config.get("additional_stat_mods") or []
    if isinstance(additional_mods, dict):
        additional_mods = [additional_mods]
    for extra in additional_mods:
        if not isinstance(extra, dict):
            continue
        extra_stat = extra.get("stat_to_mod")
        if not extra_stat:
            continue
        effect_configs.append(
            {
                "stat_to_mod": extra_stat,
                "magnitude": float(extra.get("magnitude", 0.0)),
                "effect_name": extra.get("effect_name", base_effect_name),
                "config_filter": extra.get("config_filter"),
                "activate_next_round": bool(
                    extra.get("activate_next_round", base_activate_next)
                ),
                "is_dispellable": bool(
                    extra.get("is_dispellable", base_is_dispellable)
                ),
                "duration_rounds": extra.get("duration_rounds", raw_duration),
            }
        )

    # Avoid applying duplicate effects if this handler runs multiple times in the same round.
    existing_effect_names = set()
    for effect_list in (
        getattr(triggering_army, "active_effects", []),
        getattr(triggering_army, "upcoming_effects", []),
        getattr(triggering_army, "effects_to_activate_next_round", []),
    ):
        for effect in effect_list:
            if effect.source_skill_id == skill_id:
                existing_effect_names.add(effect.name)

    created_effects: List[Tuple[Any, Optional[int], bool]] = []
    for effect_config in effect_configs:
        effect_name = effect_config["effect_name"]
        if effect_name in existing_effect_names:
            continue

        effect_raw_duration = effect_config.get("duration_rounds")
        if effect_raw_duration is None:
            duration_rounds = None
            duration_value = -1
        else:
            duration_rounds = int(round(float(effect_raw_duration)))
            duration_value = max(0, duration_rounds - 1)

        effect_data: Dict[str, Any] = {
            "effect_type": EffectType.STAT_MOD,
            "name": effect_name,
            "stat_to_mod": effect_config["stat_to_mod"],
            "magnitude": effect_config["magnitude"],
            "duration": duration_value,
            "activate_next_round": effect_config["activate_next_round"],
            "is_dispellable": effect_config["is_dispellable"],
        }
        if effect_config.get("config_filter"):
            effect_data["config_filter"] = effect_config["config_filter"]

        created_effect = triggering_army._create_and_add_single_effect(
            effect_data,
            skill_id,
            triggering_army,
            triggering_army,
            opponent_army,
        )
        if not created_effect:
            continue

        created_effects.append(
            (created_effect, duration_rounds, effect_config["activate_next_round"])
        )

    if not created_effects:
        return False, []

    log_entries: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    for created_effect, duration_rounds, activate_next in created_effects:
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
        log_entries.append(
            (
                f"Applies {created_effect.get_functionality_description()} {duration_text}.",
                None,
            )
        )

    return True, log_entries


def _opponent_for_calc(
    opponent_army: ArmyRef,
    event_data: Optional[Dict[str, Any]],
) -> Optional[ArmyRef]:
    """Return the opponent army reference best suited for calculations."""

    if event_data:
        for key in ("actual_opponent_for_calc", "opponent_for_shield_calc"):
            ref = event_data.get(key)
            if ref is not None:
                return ref
    return opponent_army


def _army_has_fewer_troops(triggering_army: ArmyRef, opponent_army: Optional[ArmyRef]) -> bool:
    """Return ``True`` when ``triggering_army`` has fewer troops than ``opponent_army``."""

    if not opponent_army:
        return False
    return triggering_army.current_troop_count < opponent_army.current_troop_count


def _army_below_remaining_pct(triggering_army: ArmyRef, pct: Optional[float]) -> bool:
    """Return ``True`` when the army's remaining troops are below ``pct`` of original."""

    if pct is None:
        return True
    try:
        threshold = float(pct)
    except (TypeError, ValueError):
        return True
    if threshold <= 0:
        return True
    original = getattr(triggering_army.unit, "initial_count", 0)
    if original <= 0:
        return False
    return triggering_army.current_troop_count < original * threshold


def _apply_composite_combat_effects(
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_def: SkillDefinition,
    event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    """Apply the mixed damage/heal/dot effects configured for a jewel skill."""

    config = skill_def.get("config", {}) or {}
    skill_id = skill_def.get("id", "")
    effect_label = config.get("effect_name", skill_def.get("name", skill_id))
    log_entries: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    an_effect_happened = False

    target_for_calc = _opponent_for_calc(opponent_army, event_data)
    current_round = _get_army_round(triggering_army, simulator)

    damage_factor = float(config.get("damage_factor", 0.0))
    if (
        damage_factor > 0
        and opponent_army
        and opponent_army.current_troop_count > 0
        and simulator
    ):
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(  # type: ignore[attr-defined]
            triggering_army,
            target_for_calc or opponent_army,
            damage_factor,
            source_skill_def=skill_def,
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_entries.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {
                    "damage_done_hp": round(raw_logged_damage),
                    "absorbed_hp": round(absorbed),
                    "potential_kills": kills,
                    "calculation_steps": calc_steps,
                },
            )
        )

    heal_factor = float(config.get("heal_factor", 0.0))
    if heal_factor > 0 and triggering_army and triggering_army.current_troop_count > 0:
        heal_target_for_calc = target_for_calc or opponent_army
        if heal_target_for_calc:
            healed_amount = triggering_army.calculate_and_add_pending_healing(
                heal_factor,
                triggering_army,
                heal_target_for_calc,
                source_skill_id=skill_id,
            )
            if healed_amount > 0:
                an_effect_happened = True
                log_entries.append(
                    (
                        f"Heals self for {healed_amount:.0f} HP (Factor: {heal_factor}).",
                        None,
                    )
                )

    rage_gain = float(config.get("rage_gain", 0.0))
    if rage_gain > 0:
        effect_data = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_DELAYED_RAGE_GAIN,
            "duration": 0,
            "config": {"rage_amount": float(rage_gain)},
            "activate_next_round": True,
        }
        created = triggering_army._create_and_add_single_effect(
            effect_data,
            skill_id,
            triggering_army,
            triggering_army,
            opponent_army,
        )
        if created:
            an_effect_happened = True
            log_entries.append((f"Gains {rage_gain:.0f} rage next round.", None))

    dot_mapping = {
        "burn": DoTType.BURN,
        "poison": DoTType.POISON,
        "bleed": DoTType.BLEED,
        "lacerate": DoTType.LACERATE,
    }
    for dot_key, dot_type in dot_mapping.items():
        factor = float(config.get(f"{dot_key}_factor", 0.0))
        if factor <= 0 or not opponent_army or opponent_army.current_troop_count <= 0:
            continue
        duration = config.get(f"{dot_key}_duration", 0)
        duration_int = int(round(float(duration))) if duration is not None else 0
        effect_name = config.get(
            f"{dot_key}_effect_name",
            f"{effect_label} • {dot_key.title()}",
        )
        dot_effect = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": effect_name,
            "dot_type": dot_type,
            "status_effect_factor": factor,
            "duration": duration_int,
            "activate_next_round": True,
        }
        created_dot = opponent_army._create_and_add_single_effect(
            dot_effect,
            skill_id,
            triggering_army,
            opponent_army,
            triggering_army,
        )
        if created_dot:
            an_effect_happened = True
            log_entries.append(
                (
                    f"Inflicts '{effect_name}' on {opponent_army.name} (Factor: {factor}) "
                    f"for {duration_int + 1} rounds (starting next round).",
                    None,
                )
            )

    shield_factor = float(config.get("shield_factor", 0.0))
    if shield_factor > 0 and triggering_army.current_troop_count > 0:
        shield_duration = int(round(float(config.get("shield_duration", 0))))
        shield_effect_name = config.get(
            "shield_effect_name",
            f"{effect_label} Shield",
        )
        shield_data = {
            "effect_type": EffectType.SHIELD,
            "name": shield_effect_name,
            "duration": shield_duration,
            "magnitude_calc_type": "dynamic_shield_resistance_v1",
            "shield_factor": shield_factor,
            "activate_next_round": True,
        }
        created_shield = triggering_army._create_and_add_single_effect(
            shield_data,
            skill_id,
            triggering_army,
            triggering_army,
            target_for_calc or opponent_army,
        )
        if created_shield:
            an_effect_happened = True
            estimated = 0.0
            if simulator and (target_for_calc or opponent_army):
                estimated = simulator._calculate_shield_magnitude_for_logging(  # type: ignore[attr-defined]
                    triggering_army,
                    target_for_calc or opponent_army,
                    shield_factor,
                )
            log_entries.append(
                (
                    f"Gains '{shield_effect_name}' for {shield_duration + 1} rounds (starting next round)."
                    + (f" Estimated shield: {estimated:.0f} HP." if estimated > 0 else ""),
                    None,
                )
            )

    # Self stat modifiers (e.g., temporary damage reduction buffs)
    stat_mods = config.get("self_stat_mods") or []
    if isinstance(stat_mods, dict):
        stat_mods = [stat_mods]
    for mod in stat_mods:
        stat_to_mod = mod.get("stat_to_mod")
        if not stat_to_mod:
            continue
        magnitude = float(mod.get("magnitude", 0.0))
        effect_name = mod.get("effect_name", effect_label)
        activate_next = bool(mod.get("activate_next_round", True))
        duration_rounds_raw = mod.get("duration_rounds")
        if duration_rounds_raw is None:
            duration_rounds = None
            duration_value = -1
        else:
            duration_rounds = int(round(float(duration_rounds_raw)))
            duration_value = max(0, duration_rounds - 1)
        effect_data: Dict[str, Any] = {
            "effect_type": EffectType.STAT_MOD,
            "name": effect_name,
            "stat_to_mod": stat_to_mod,
            "magnitude": magnitude,
            "duration": duration_value,
            "activate_next_round": activate_next,
        }
        if mod.get("config_filter"):
            effect_data["config_filter"] = mod["config_filter"]
        if mod.get("is_dispellable") is not None:
            effect_data["is_dispellable"] = bool(mod.get("is_dispellable"))
        created_effect = triggering_army._create_and_add_single_effect(
            effect_data,
            skill_id,
            triggering_army,
            triggering_army,
            opponent_army,
        )
        if created_effect:
            an_effect_happened = True
            start_round = current_round + (1 if activate_next else 0)
            if duration_rounds is None:
                duration_text = f"starting round {start_round} until removed"
            elif duration_rounds <= 0:
                duration_text = f"in round {start_round}"
            else:
                end_round = start_round + max(0, duration_rounds - 1)
                duration_text = f"for {duration_rounds} rounds (R{start_round}-R{end_round})"
            log_entries.append(
                (
                    f"Applies {created_effect.get_functionality_description()} {duration_text}.",
                    None,
                )
            )

    # Custom effects applied to self (e.g., evasion, retribution)
    custom_effects = config.get("self_custom_effects") or []
    if isinstance(custom_effects, dict):
        custom_effects = [custom_effects]
    for custom in custom_effects:
        effect_type = custom.get("effect_type", EffectType.CUSTOM_SKILL_EFFECT)
        effect_name = custom.get("name", effect_label)
        if not effect_name:
            continue
        activate_next = bool(custom.get("activate_next_round", True))
        duration_rounds_raw = custom.get("duration_rounds")
        if duration_rounds_raw is None:
            duration_rounds = None
            duration_value = -1
        else:
            duration_rounds = int(round(float(duration_rounds_raw)))
            duration_value = max(0, duration_rounds - 1)
        effect_data = {
            "effect_type": effect_type,
            "name": effect_name,
            "duration": duration_value,
            "activate_next_round": activate_next,
            "config": custom.get("config", {}).copy(),
        }
        if custom.get("magnitude") is not None:
            effect_data["magnitude"] = float(custom.get("magnitude"))
        if custom.get("is_dispellable") is not None:
            effect_data["config"]["is_dispellable"] = bool(custom.get("is_dispellable"))
        created_custom = triggering_army._create_and_add_single_effect(
            effect_data,
            skill_id,
            triggering_army,
            triggering_army,
            opponent_army,
        )
        if created_custom:
            an_effect_happened = True
            start_round = current_round + (1 if activate_next else 0)
            if duration_rounds is None:
                duration_text = f"starting round {start_round} until removed"
            elif duration_rounds <= 0:
                duration_text = f"in round {start_round}"
            else:
                end_round = start_round + max(0, duration_rounds - 1)
                duration_text = f"for {duration_rounds} rounds (R{start_round}-R{end_round})"
            log_entries.append(
                (
                    f"Gains '{effect_name}' {duration_text}.",
                    None,
                )
            )

    # Schedule random cleanses or dispels when requested
    cleanse_count = int(round(float(config.get("self_cleanse_count", 0))))
    if cleanse_count > 0:
        eligible_debuffs = [
            eff
            for eff in triggering_army.active_effects
            if (
                eff.effect_type == EffectType.DEBUFF
                or (
                    eff.effect_type == EffectType.DAMAGE_OVER_TIME
                    and eff.config.get("dot_type")
                    in {DoTType.BLEED, DoTType.POISON, DoTType.BURN, DoTType.LACERATE}
                )
                or eff.config.get("prevents_counterattack")
                or eff.config.get("prevents_basic_attack")
                or eff.config.get("prevents_rage_skill_cast")
                or (eff.effect_type == EffectType.STAT_MOD and eff.is_harmful_for_target())
                or (eff.effect_type == EffectType.CUSTOM_SKILL_EFFECT and eff.is_harmful_for_target())
            )
        ]
        if eligible_debuffs:
            selected = random.sample(
                eligible_debuffs,
                k=min(len(eligible_debuffs), cleanse_count),
            )
            debuff_ids = [eff.id for eff in selected]
            debuff_names = [eff.name or f"Unnamed Debuff ({str(eff.id)[:4]})" for eff in selected]
            pending_cleanse = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_PENDING_HEIMDALL_PURIFY,
                "duration": 0,
                "config": {
                    "debuff_ids_to_remove": debuff_ids,
                    "debuff_names_removed_log": debuff_names,
                },
                "activate_next_round": True,
            }
            created_cleanse = triggering_army._create_and_add_single_effect(
                pending_cleanse,
                skill_id,
                triggering_army,
                triggering_army,
                opponent_army,
            )
            if created_cleanse:
                an_effect_happened = True
                log_entries.append(
                    (
                        f"Schedules self-cleanse for {len(selected)} debuff(s) next round.",
                        None,
                    )
                )
        else:
            log_entries.append(("Attempted self-cleanse, but no active debuffs found.", None))

    dispel_count = int(round(float(config.get("enemy_dispel_count", 0))))
    if dispel_count > 0 and opponent_army:
        eligible_buffs = [
            eff
            for eff in opponent_army.active_effects
            if eff.is_dispellable_buff_candidate()
        ]
        if eligible_buffs:
            selected = random.sample(
                eligible_buffs,
                k=min(len(eligible_buffs), dispel_count),
            )
            buff_ids = [eff.id for eff in selected]
            buff_names = [eff.name or f"Buff ID ...{str(eff.id)[-4:]}" for eff in selected]
            pending_dispel = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
                "duration": 0,
                "config": {
                    "buff_ids_to_remove": buff_ids,
                    "targeted_buff_names_initial_log": buff_names,
                },
                "activate_next_round": True,
            }
            created_dispel = opponent_army._create_and_add_single_effect(
                pending_dispel,
                skill_id,
                triggering_army,
                opponent_army,
                triggering_army,
            )
            if created_dispel:
                an_effect_happened = True
                log_entries.append(
                    (
                        f"Schedules enemy buff dispel for {len(selected)} effect(s) next round.",
                        None,
                    )
                )
        else:
            log_entries.append(("Attempted buff dispel, but no dispellable buffs found.", None))

    return an_effect_happened, log_entries


def handle_gem_skill_lower_troop_periodic_composite(
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_def: SkillDefinition,
    event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    """Handle periodic composite effects that require the army to be outnumbered."""

    if not opponent_army or opponent_army.current_troop_count <= 0:
        return False, []

    config = skill_def.get("config", {}) or {}
    interval = int(round(float(config.get("trigger_interval", 0))))
    if interval <= 0:
        return False, []

    current_round = _get_army_round(triggering_army, simulator)
    if current_round <= 0:
        return False, []

    start_round = int(round(float(config.get("start_round", interval))))
    if current_round < start_round:
        return False, []
    if (current_round - start_round) % interval != 0:
        return False, []

    if config.get("require_lower_troops", False) and not _army_has_fewer_troops(triggering_army, opponent_army):
        return False, []

    if not _army_below_remaining_pct(
        triggering_army, config.get("require_remaining_pct_below")
    ):
        return False, []

    return _apply_composite_combat_effects(
        triggering_army,
        opponent_army,
        skill_def,
        event_data,
        simulator,
    )


def handle_gem_skill_lower_troop_attack_composite(
    triggering_army: ArmyRef,
    opponent_army: ArmyRef,
    skill_def: SkillDefinition,
    event_data: Optional[Dict[str, Any]],
    simulator: GameSimulatorRef,
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    """Handle basic/counter triggered composite effects that require fewer troops."""

    if not opponent_army or opponent_army.current_troop_count <= 0:
        return False, []

    config = skill_def.get("config", {}) or {}
    if config.get("require_lower_troops", False) and not _army_has_fewer_troops(triggering_army, opponent_army):
        return False, []

    if not _army_below_remaining_pct(
        triggering_army, config.get("require_remaining_pct_below")
    ):
        return False, []

    return _apply_composite_combat_effects(
        triggering_army,
        opponent_army,
        skill_def,
        event_data,
        simulator,
    )

