import random
import uuid
from typing import Tuple, List, Optional, Dict, Any

from ..enums import EffectType, StatType, SkillTriggerType, DoTType
from ..effect_system import EffectInstance
from ..skill_system import SkillDefinition, ArmyRef, GameSimulatorRef
from ..constants import *


def _get_army_round(army: ArmyRef, simulator: GameSimulatorRef) -> int:
    """Return the round counter for ``army``.

    If the army has not yet been assigned its own round counter the
    simulator's global round is used as a fallback (or ``0`` when no
    simulator is available).  This avoids referencing opponent data during
    start-of-round processing.
    """
    if hasattr(army, "army_round"):
        return army.army_round
    return simulator.round if simulator else 0


def _count_effects_by_name(army: ArmyRef, effect_name: str) -> int:
    return sum(1 for eff in army.active_effects if eff.name == effect_name)


def _add_nature_mark_stacks(
    army: ArmyRef, opponent_army: ArmyRef, skill_def: SkillDefinition, count: int
) -> int:
    created = 0
    for _ in range(max(0, count)):
        mark_effect = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_NATURE_MARK,
            "duration": -1,
            "activate_next_round": True,
        }
        if army._create_and_add_single_effect(mark_effect, skill_def["id"], army, army, opponent_army):
            created += 1
    return created


def _remove_all_effects_by_name(army: ArmyRef, effect_name: str) -> int:
    removed = [eff for eff in army.active_effects if eff.name == effect_name]
    for eff in removed:
        if eff in army.active_effects:
            army.active_effects.remove(eff)
    return len(removed)


def _manual_override(event_data: Optional[Dict[str, Any]]) -> bool:
    return bool(event_data and event_data.get("manual_override"))


def _enemy_bleeding(opponent_army: ArmyRef, event_data: Optional[Dict[str, Any]]) -> bool:
    if _manual_override(event_data):
        return True
    return any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BLEED
        for eff in opponent_army.active_effects
    )


def handle_base_skill_planned_attack(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                                     ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {})
    dmg_fctrs = [sk_cfg.get("hit1_damage_factor", 0.0), sk_cfg.get("hit2_damage_factor", 0.0)]
    for i, dmg_fctr in enumerate(dmg_fctrs):
        if dmg_fctr == 0.0:
            continue
        if opp_army.current_troop_count <= 0:
            break
        calc_target = ev_data.get('actual_opponent_for_calc', opp_army) if ev_data else opp_army
        hp_dmg, absrb, kills, raw_log_dmg, calc_steps = sim._calculate_generic_skill_damage(
            trig_army,
            calc_target,
            dmg_fctr,
            source_skill_def=sk_def,
            damage_application_target=opp_army,
        )
        if hp_dmg > 0:
            opp_army.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0:
            eff_hpnd = True
        logs.append(
            (
                f"Hit {i + 1} deals damage to {opp_army.name}.",
                {
                    "damage_done_hp": round(raw_log_dmg),
                    "absorbed_hp": round(absrb),
                    "potential_kills": kills,
                    "calculation_steps": calc_steps,
                },
            )
        )
    return eff_hpnd, logs


def handle_base_skill_flame_guardian(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                                     ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"];
    dmg_fctr = sk_cfg.get("damage_factor", 0.0);
    dmg_dealt = False
    if dmg_fctr > 0:
        calc_target = ev_data.get('actual_opponent_for_calc', opp_army) if ev_data else opp_army
        hp_dmg, absrb, kills, raw_log_dmg, calc_steps = sim._calculate_generic_skill_damage(
            trig_army,
            calc_target,
            dmg_fctr,
            source_skill_def=sk_def,
            damage_application_target=opp_army,
        )
        if hp_dmg > 0:
            opp_army.pending_hp_damage_this_round += hp_dmg
            dmg_dealt = True
        if absrb > 0 and not dmg_dealt:
            dmg_dealt = True
        if hp_dmg > 0 or absrb > 0:
            eff_hpnd = True
        logs.append(
            (
                f"Deals damage to {opp_army.name}.",
                {
                    "damage_done_hp": round(raw_log_dmg),
                    "absorbed_hp": round(absrb),
                    "potential_kills": kills,
                    "calculation_steps": calc_steps,
                },
            )
        )
    if dmg_dealt and random.random() < sk_cfg.get("shield_chance", 0.0):
        sh_fctr_fg = sk_cfg.get("shield_factor", 0.0);
        sh_dur_fg = sk_cfg.get("self_shield_duration", 1);
        sh_name = sk_cfg.get("effect_name", EFFECT_NAME_FLAME_GUARDIAN_SHIELD)
        if sh_fctr_fg > 0:
            sh_data = {"effect_type": EffectType.SHIELD, "name": sh_name, "duration": sh_dur_fg,
                       "magnitude_calc_type": "dynamic_shield_resistance_v1", "shield_factor": sh_fctr_fg,
                       "activate_next_round": True}
            cr_sh = trig_army._create_and_add_single_effect(sh_data, sk_id, trig_army, trig_army, opp_army)
            if cr_sh:
                eff_hpnd = True;
                est_mag = sim._calculate_shield_magnitude_for_logging(trig_army, opp_army,
                                                                      float(sh_fctr_fg)) if sim else cr_sh.magnitude
                logs.append(
                    (f"Gains Shield ({cr_sh.get_functionality_description()}), active for next {sh_dur_fg + 1} round(s). Est. Mag: {est_mag:.0f}",
                     None))
    return eff_hpnd, logs


def handle_base_skill_sanctity_of_life(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                                       ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"]
    if random.random() < sk_cfg.get("heal_chance", 0.0):
        heal_fctr = sk_cfg.get("heal_factor", 0.0)
        if heal_fctr > 0:
            healed_amount = trig_army.calculate_and_add_pending_healing(
                heal_fctr, trig_army, opp_army, source_skill_id=sk_id
            )
            if healed_amount > 0:
                eff_hpnd = True
                logs.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_fctr}).", None))
    is_h1 = (trig_army.heroes and len(trig_army.heroes) > 0 and sk_id in [s["id"] for s in trig_army.heroes[0].skills])
    if is_h1 and len(trig_army.heroes) > 1 and trig_army.hero2_rage_skill_id:
        if random.random() < sk_cfg.get("buff_hero2_chance", 0.0):
            buff_dets = sk_cfg.get("buff_details")
            if buff_dets:
                buff_data_copy = buff_dets.copy()
                cr_buff = trig_army._create_and_add_single_effect(buff_data_copy, sk_id, trig_army, trig_army, opp_army)
                if cr_buff: eff_hpnd = True; logs.append(
                    (f"Buffs Hero #2's rage skill: {cr_buff.get_functionality_description()} for {cr_buff.duration + 1} rounds (starting next round).",
                     None))
    return eff_hpnd, logs


def handle_base_skill_zeal(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                           ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {})
    if random.random() < sk_cfg.get("damage_chance", 0.0):
        dmg_fctr = sk_cfg.get("damage_factor", 0.0)
        if dmg_fctr > 0:
            hp_dmg, absrb, kills, raw_dmg, calc_steps = sim._calculate_generic_skill_damage(
                trig_army,
                opp_army,
                dmg_fctr,
                source_skill_def=sk_def,
            )
            if hp_dmg > 0: opp_army.pending_hp_damage_this_round += hp_dmg
            if hp_dmg > 0 or absrb > 0: eff_hpnd = True
            logs.append((f"Deals damage to {opp_army.name}.",
                         {
                             "damage_done_hp": round(raw_dmg),
                             "absorbed_hp": round(absrb),
                             "potential_kills": kills,
                             "calculation_steps": calc_steps,
                         }))
    if random.random() < sk_cfg.get("debuff_removal_chance", 0.0):
        dbuffs_on_army = [
            eff
            for eff in trig_army.active_effects
            if (
                eff.effect_type == EffectType.DEBUFF
                or (
                    eff.effect_type == EffectType.DAMAGE_OVER_TIME
                    and eff.config.get("dot_type")
                    in [DoTType.BLEED, DoTType.POISON, DoTType.BURN, DoTType.LACERATE]
                )
                or eff.config.get("prevents_counterattack")
                or eff.config.get("prevents_basic_attack")
                or eff.name == EFFECT_NAME_SILENCE_DEBUFF
            )
        ]
        if dbuffs_on_army:
            dbuff_to_rmv = random.choice(dbuffs_on_army);
            trig_army.active_effects.remove(dbuff_to_rmv)
            logs.append((f"Removes debuff: {dbuff_to_rmv.name}.", None));
            eff_hpnd = True
    return eff_hpnd, logs


def handle_base_skill_snake_eyes(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    if not triggering_army.started_round_with_active_shield:
        return False, []

    if random.random() < skill_config.get("damage_chance", 0.0):
        damage_factor = skill_config.get("damage_factor", 0.0)
        if damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                an_effect_happened = True
            log_details.append((
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
            ))

    if random.random() < skill_config.get("debuff_chance", 0.0):
        debuff_duration = skill_config.get("debuff_duration", 1)
        debuff_effect_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_BROKEN_BLADE_DEBUFF,
            "duration": debuff_duration,
            "config": {"prevents_counterattack": True},
            "activate_next_round": True
        }
        created_debuff = opponent_army._create_and_add_single_effect(
            debuff_effect_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
            log_details.append((
                f"Inflicts '{EFFECT_NAME_BROKEN_BLADE_DEBUFF}' on {opponent_army.name} for {created_debuff.duration + 1} rounds (starting next round).",
                None
            ))
    return an_effect_happened, log_details


def handle_base_skill_ready_to_pounce(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    buff_magnitude = skill_config.get("buff_magnitude", 1.0)
    buff_duration = skill_config.get("buff_duration", 1)

    buff_effect_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_READY_TO_POUNCE_BUFF,
        "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST,
        "magnitude": buff_magnitude,
        "duration": buff_duration,
        "activate_next_round": True
    }
    created_buff = triggering_army._create_and_add_single_effect(
        buff_effect_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_buff:
        an_effect_happened = True
        log_details.append((
            f"Gains '{EFFECT_NAME_READY_TO_POUNCE_BUFF}': {created_buff.get_functionality_description()} for {created_buff.duration + 1} rounds (starting next round).",
            None
        ))
    return an_effect_happened, log_details


def handle_base_skill_threatening_blade(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    if triggering_army.current_troop_count > opponent_army.current_troop_count:
        damage_factor = skill_config.get("damage_factor", 0.0)
        if damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor,
                source_skill_def=skill_def
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                an_effect_happened = True
            log_details.append((
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name} (own troops higher).",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
            ))
    else:
        def_buff_magnitude = skill_config.get("defense_buff_magnitude", 0.0)
        def_buff_duration = skill_config.get("defense_buff_duration", 4)

        if def_buff_magnitude > 0:
            buff_effect_data = {
                "effect_type": EffectType.STAT_MOD,
                "name": EFFECT_NAME_THREATENING_BLADE_DEF_BUFF,
                "stat_to_mod": StatType.BASE_DEFENSE_MULTIPLIER,
                "magnitude": def_buff_magnitude,
                "duration": def_buff_duration,
                "activate_next_round": True
            }
            created_buff = triggering_army._create_and_add_single_effect(
                buff_effect_data, skill_id, triggering_army, triggering_army, opponent_army
            )
            if created_buff:
                an_effect_happened = True
                log_details.append((
                    f"Gains '{EFFECT_NAME_THREATENING_BLADE_DEF_BUFF}': {created_buff.get_functionality_description()} for {created_buff.duration + 1} rounds (own troops lower or equal).",
                    None
                ))
    return an_effect_happened, log_details


def handle_base_skill_unyielding_will(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    h2_rage_buff_magnitude = skill_config.get("h2_rage_buff_magnitude", 0.0)
    h2_rage_buff_duration = skill_config.get("h2_rage_buff_duration", 2)
    if h2_rage_buff_magnitude > 0 and triggering_army.hero2_rage_skill_id:
        buff_effect_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_UNYIELDING_WILL_H2_RAGE_BOOST,
            "stat_to_mod": StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER,
            "magnitude": h2_rage_buff_magnitude,
            "duration": h2_rage_buff_duration,
            "activate_next_round": True
        }
        created_buff = triggering_army._create_and_add_single_effect(
            buff_effect_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            an_effect_happened = True
            log_details.append((
                f"Gains '{EFFECT_NAME_UNYIELDING_WILL_H2_RAGE_BOOST}': {created_buff.get_functionality_description()} for {created_buff.duration + 1} rounds (starting next round).",
                None
            ))

    if random.random() < skill_config.get("heal_chance", 0.0):
        heal_factor = skill_config.get("heal_factor", 0.0)
        if heal_factor > 0:
            healed_amount = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
            )
            if healed_amount > 0:
                an_effect_happened = True
                log_details.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_factor}).", None))
    return an_effect_happened, log_details


def handle_base_skill_heart_of_tolerance(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 9)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
        ))

    if random.random() < skill_config.get("rage_reduction_chance", 0.0):
        rage_to_reduce = skill_config.get("rage_reduction_amount", 0)
        if rage_to_reduce > 0 and opponent_army.current_rage > 0:
            actual_reduction = min(opponent_army.current_rage, float(rage_to_reduce))
            effect_data = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_DELAYED_RAGE_REDUCTION,
                "duration": 0,
                "config": {"rage_reduction": actual_reduction},
                "activate_next_round": True,
            }
            created = opponent_army._create_and_add_single_effect(
                effect_data, skill_id, triggering_army, opponent_army, triggering_army
            )
            if created:
                an_effect_happened = True
                log_details.append((f"Reduces {opponent_army.name}'s rage by {actual_reduction:.0f} next round.", None))
    else:
        log_details.append(
            (f"Rage reduction chance ({skill_config.get('rage_reduction_chance', 0.0) * 100:.0f}%) not met.", None))

    return an_effect_happened, log_details


# --- OLENA BASE SKILL HANDLER ---
def handle_base_skill_enchanted_arrow(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        # event_data might contain info about the rage skill cast
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    # This skill triggers ON_OWN_RAGE_SKILL_CAST, so the 35% chance is primary
    # The simulator handles the 35% trigger chance for this handler.

    burn_factor = skill_config.get("burn_factor", 0.0)
    burn_duration = skill_config.get("burn_duration", 1)  # For 2 active rounds (applied next round)

    if burn_factor > 0:
        burn_effect_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_ENCHANTED_ARROW_BURN,
            "dot_type": DoTType.BURN,
            "status_effect_factor": burn_factor,
            "duration": burn_duration,
            "activate_next_round": True
        }
        created_burn = opponent_army._create_and_add_single_effect(
            burn_effect_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_burn:
            an_effect_happened = True
            log_details.append((
                f"Inflicts '{EFFECT_NAME_ENCHANTED_ARROW_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                None
            ))

    return an_effect_happened, log_details


def handle_base_skill_huginns_slingshot(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    base_damage = cfg.get("damage_factor", 0.0)
    burn_damage = cfg.get("burn_damage_factor", base_damage)
    enemy_burned = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BURN
        for eff in opponent_army.active_effects
    )
    chosen_factor = burn_damage if enemy_burned else base_damage

    if chosen_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, chosen_factor, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            happened = True
        condition_note = " (burned target)" if enemy_burned else ""
        logs.append((
            f"Deals damage{condition_note} to {opponent_army.name} (Factor: {chosen_factor}).",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
        ))

    return happened, logs


def handle_base_skill_rapid_fire(  # Verdandi's skill, already exists
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 9)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
        ))

    rage_gain = skill_config.get("rage_gain", 0)
    if rage_gain > 0:
        effect_data = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_DELAYED_RAGE_GAIN,
            "duration": 0,
            "config": {"rage_amount": float(rage_gain)},
            "activate_next_round": True,
        }
        created = triggering_army._create_and_add_single_effect(
            effect_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created:
            an_effect_happened = True
            log_details.append((f"Gains {rage_gain:.0f} rage next round.", None))

    return an_effect_happened, log_details


def handle_base_skill_torment(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 9)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps})
        )

    burn_factor = skill_config.get("burn_factor", 0.0)
    burn_duration = skill_config.get("burn_duration", 2)
    if burn_factor > 0:
        burn_effect_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_TORMENT_BURN,
            "dot_type": DoTType.BURN,
            "status_effect_factor": burn_factor,
            "duration": burn_duration,
            "activate_next_round": True
        }
        created_burn = opponent_army._create_and_add_single_effect(
            burn_effect_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_burn:
            an_effect_happened = True
            log_details.append(
                (f"Inflicts '{EFFECT_NAME_TORMENT_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                 None)
            )

    return an_effect_happened, log_details


# --- Freydis Base Skill Handlers ---
def handle_base_skill_blades_judgment(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 9)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    burn_factor = skill_config.get("burn_factor", 0.0)
    burn_duration = skill_config.get("burn_duration", 2)
    if burn_factor > 0:
        burn_effect_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_BLADES_JUDGMENT_BURN,
            "dot_type": DoTType.BURN,
            "status_effect_factor": burn_factor,
            "duration": burn_duration,
            "activate_next_round": True,
        }
        created_burn = opponent_army._create_and_add_single_effect(
            burn_effect_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_burn:
            an_effect_happened = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_BLADES_JUDGMENT_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details


# --- Gregory Base Skill Handlers ---
def handle_base_skill_drumming_disturbance(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    heal_factor = skill_config.get("heal_factor", 0.0)
    heal_duration = skill_config.get("heal_duration", 2)
    if heal_factor > 0:
        hot_data = {
            "effect_type": EffectType.HEAL_OVER_TIME,
            "name": EFFECT_NAME_DRUMMING_DISTURBANCE_HOT,
            "magnitude": heal_factor,
            "duration": heal_duration,
            "activate_next_round": True,
        }
        created_hot = triggering_army._create_and_add_single_effect(
            hot_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_hot:
            an_effect_happened = True
            log_details.append(
                (f"Applies {created_hot.get_functionality_description()} for {heal_duration + 1} rounds.", None)
            )

    reduction_magnitude = skill_config.get("rage_reduction_mag", -0.1)
    reduction_duration = skill_config.get("rage_reduction_duration", 2)
    for stat_type in [StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER, StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER]:
        debuff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_DRUMMING_DISTURBANCE_RAGE_REDUCTION,
            "stat_to_mod": stat_type,
            "magnitude": reduction_magnitude,
            "duration": reduction_duration,
            "activate_next_round": True,
        }
        created_debuff = opponent_army._create_and_add_single_effect(
            debuff_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
    if an_effect_happened:
        log_details.append(
            (f"Reduces enemy rage skill damage by {abs(reduction_magnitude) * 100:.0f}% for {reduction_duration + 1} rounds.", None)
        )
    return an_effect_happened, log_details


def handle_base_skill_divine_energize(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps})
        )

    vul_mag = skill_config.get("vulnerability_magnitude", 0.0)
    vul_dur = skill_config.get("vulnerability_duration", 2)
    if vul_mag != 0:
        debuff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_DIVINE_ENERGIZE_VULNERABILITY,
            "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER,
            "magnitude": vul_mag,
            "duration": vul_dur,
            "activate_next_round": True,
            "config_filter": {"attack_type": "BASIC"}
        }
        created_debuff = opponent_army._create_and_add_single_effect(
            debuff_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
            log_details.append(
                (f"Inflicts vulnerability: {created_debuff.get_functionality_description()} on {opponent_army.name} for {vul_dur + 1} rounds (starting next round).",
                 None)
            )

    return an_effect_happened, log_details


# --- Rollo Base Skill Handlers ---
def handle_base_skill_tough_choice(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                   skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                   simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if not any(eff.name == EFFECT_NAME_TOUGH_CHOICE_BASIC_BUFF and eff.source_skill_id == skill_def["id"] for eff in triggering_army.active_effects):
        bdata = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_TOUGH_CHOICE_BASIC_BUFF,
                 "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": cfg.get("basic_buff", 0.3),
                 "duration": -1, "activate_next_round": False}
        cdata = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_TOUGH_CHOICE_COUNTER_DEBUFF,
                 "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": cfg.get("counter_debuff", -0.3),
                 "duration": -1, "activate_next_round": False}
        if triggering_army._create_and_add_single_effect(bdata, skill_def["id"], triggering_army, triggering_army, opponent_army):
            happened = True
            logs.append((f"Gains permanent '{EFFECT_NAME_TOUGH_CHOICE_BASIC_BUFF}'.", None))
        if triggering_army._create_and_add_single_effect(cdata, skill_def["id"], triggering_army, triggering_army, opponent_army):
            happened = True
            logs.append((f"Gains permanent '{EFFECT_NAME_TOUGH_CHOICE_COUNTER_DEBUFF}'.", None))
    if any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects):
        if random.random() < cfg.get("heal_chance", 0.0):
            heal_factor = cfg.get("heal_factor", 0.0)
            healed = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_def["id"]
            )
            if healed > 0:
                happened = True
                logs.append((f"Heals for {healed:.0f} HP (Factor: {heal_factor}).", None))
    return happened, logs



def handle_base_skill_flurry(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    skill_id = skill_def["id"]

    damage_factor = cfg.get("damage_factor", 0.0)
    if damage_factor > 0:
        calc_target = event_data.get('actual_opponent_for_calc', opponent_army) if event_data else opponent_army
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, calc_target, damage_factor,
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
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    buff_details = cfg.get("buff_details")
    if buff_details:
        buff_copy = buff_details.copy()
        if "name" not in buff_copy:
            buff_copy["name"] = EFFECT_NAME_FLURRY_REACTIVE_BOOST
        effect_name = buff_copy["name"]
        existing_buff: Optional[EffectInstance] = None
        existing_location: Optional[str] = None

        for eff in triggering_army.active_effects:
            if eff.name == effect_name and eff.source_skill_id == skill_id:
                existing_buff = eff
                existing_location = "active"
                break

        if existing_buff is None:
            for eff in triggering_army.upcoming_effects:
                if eff.name == effect_name and eff.source_skill_id == skill_id:
                    existing_buff = eff
                    existing_location = "upcoming"
                    break

        if existing_buff is None:
            for eff in triggering_army.effects_to_activate_next_round:
                if eff.name == effect_name and eff.source_skill_id == skill_id:
                    existing_buff = eff
                    existing_location = "queued_next_round"
                    break

        if existing_buff:
            refreshed_duration = max(existing_buff.duration, buff_copy.get("duration", existing_buff.duration))
            existing_buff.duration = refreshed_duration
            if "magnitude" in buff_copy:
                existing_buff.magnitude = buff_copy["magnitude"]
            an_effect_happened = True

            if existing_location == "queued_next_round":
                log_details.append(
                    (
                        f"Refreshes Reactive Skill Damage Boost queued for next round: {existing_buff.get_functionality_description()} for {existing_buff.duration + 1} round(s).",
                        None,
                    )
                )
            elif existing_location == "upcoming":
                log_details.append(
                    (
                        f"Refreshes Reactive Skill Damage Boost before activation: {existing_buff.get_functionality_description()} for {existing_buff.duration + 1} round(s).",
                        None,
                    )
                )
            else:
                log_details.append(
                    (
                        f"Refreshes Reactive Skill Damage Boost: {existing_buff.get_functionality_description()} for {existing_buff.duration + 1} round(s).",
                        None,
                    )
                )
        else:
            created_buff = triggering_army._create_and_add_single_effect(
                buff_copy, skill_id, triggering_army, triggering_army, opponent_army
            )
            if created_buff:
                an_effect_happened = True
                log_details.append(
                    (
                        f"Gains Reactive Skill Damage Boost: {created_buff.get_functionality_description()} for {created_buff.duration + 1} round(s) (starting next round).",
                        None,
                    )
                )

    return an_effect_happened, log_details


# --- Lagertha Base Skill Handler ---
def handle_base_skill_shield_breaker(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg = cfg.get("damage_factor", 0.0)
    if dmg > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage (Factor: {dmg}) to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))

    enemy_bleeding = _enemy_bleeding(opponent_army, event_data)
    if enemy_bleeding:
        buff_mag = cfg.get("buff_magnitude", 0.0)
        buff_dur = cfg.get("buff_duration", 1)
        if buff_mag != 0:
            buff_data = {
                "effect_type": EffectType.STAT_MOD,
                "name": EFFECT_NAME_SHIELD_BREAKER_BASIC_BUFF,
                "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
                "magnitude": buff_mag,
                "duration": buff_dur,
                "activate_next_round": True,
            }
            if triggering_army._create_and_add_single_effect(buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army):
                happened = True
                logs.append((f"Gains '{EFFECT_NAME_SHIELD_BREAKER_BASIC_BUFF}' for {buff_dur + 1} rounds (starting next round).", None))
    return happened, logs


# --- Greta Base Skill Handlers ---
def handle_base_skill_broken_blade_charge(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    has_retribution = any(
        eff.effect_type == EffectType.CUSTOM_SKILL_EFFECT and eff.config.get("retribution_rate", 0) > 0
        for eff in triggering_army.active_effects
    )
    if not has_retribution:
        return False, []

    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    if random.random() < cfg.get("shield_chance", 0.0):
        shield_factor = cfg.get("shield_factor", 0.0)
        shield_duration = cfg.get("shield_duration", 1)
        if shield_factor > 0:
            shield_data = {
                "effect_type": EffectType.SHIELD,
                "name": EFFECT_NAME_BROKEN_BLADE_CHARGE_SHIELD,
                "duration": shield_duration,
                "magnitude_calc_type": "dynamic_shield_resistance_v1",
                "shield_factor": shield_factor,
                "activate_next_round": True,
            }
            created_shield = triggering_army._create_and_add_single_effect(
                shield_data, skill_def["id"], triggering_army, triggering_army, opponent_army
            )
            if created_shield:
                happened = True
                est_mag = (
                    simulator._calculate_shield_magnitude_for_logging(triggering_army, opponent_army, float(shield_factor))
                    if simulator
                    else created_shield.magnitude
                )
                logs.append(
                    (
                        f"Gains shield ({created_shield.get_functionality_description()}) for {shield_duration + 1} rounds "
                        f"(starting next round). Est. Mag: {est_mag:.0f}",
                        None,
                    )
                )

    if random.random() < cfg.get("slow_chance", 0.0):
        slow_duration = cfg.get("slow_duration", 1)
        slow_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_SLOW_DEBUFF,
            "duration": slow_duration,
            "activate_next_round": True,
        }
        created_slow = opponent_army._create_and_add_single_effect(
            slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_slow:
            happened = True
            logs.append(
                (
                    f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    enemy_silenced = any(eff.name == EFFECT_NAME_SILENCE_DEBUFF for eff in opponent_army.active_effects)
    if enemy_silenced and random.random() < cfg.get("silence_damage_chance", 0.0):
        damage_factor = cfg.get("silence_damage_factor", 0.0)
        if damage_factor > 0 and simulator:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append(
                (
                    f"Deals bonus damage (Factor: {damage_factor}) to {opponent_army.name} because they are silenced.",
                    {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
                )
            )

    enemy_bleeding = _enemy_bleeding(opponent_army, event_data)
    if enemy_bleeding and random.random() < cfg.get("bleed_heal_chance", 0.0):
        heal_factor = cfg.get("bleed_heal_factor", 0.0)
        if heal_factor > 0:
            healed = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_def["id"]
            )
            if healed > 0:
                happened = True
                logs.append((f"Heals for {healed:.0f} HP (Factor: {heal_factor}) because the enemy is bleeding.", None))

    return happened, logs


def handle_base_skill_winters_coronation(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    bleed_factor = cfg.get("bleed_factor", 0.0)
    bleed_duration = cfg.get("bleed_duration", 1)
    if bleed_factor > 0:
        bleed_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_WINTERS_CORONATION_BLEED,
            "dot_type": DoTType.BLEED,
            "status_effect_factor": bleed_factor,
            "duration": bleed_duration,
            "activate_next_round": True,
        }
        created_bleed = opponent_army._create_and_add_single_effect(
            bleed_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_bleed:
            happened = True
            logs.append(
                (
                    f"Inflicts '{EFFECT_NAME_WINTERS_CORONATION_BLEED}' on {opponent_army.name} (Factor: {bleed_factor}) "
                    f"for {bleed_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    if triggering_army.current_troop_count > opponent_army.current_troop_count:
        slow_duration = cfg.get("slow_duration", 1)
        slow_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_SLOW_DEBUFF,
            "duration": slow_duration,
            "activate_next_round": True,
        }
        created_slow = opponent_army._create_and_add_single_effect(
            slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_slow:
            happened = True
            logs.append(
                (
                    f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_duration + 1} rounds (starting next round).",
                    None,
                )
            )
    elif triggering_army.current_troop_count < opponent_army.current_troop_count:
        shield_factor = cfg.get("shield_factor", 0.0)
        shield_duration = cfg.get("shield_duration", 1)
        if shield_factor > 0:
            shield_data = {
                "effect_type": EffectType.SHIELD,
                "name": EFFECT_NAME_WINTERS_CORONATION_SHIELD,
                "duration": shield_duration,
                "magnitude_calc_type": "dynamic_shield_resistance_v1",
                "shield_factor": shield_factor,
                "activate_next_round": True,
            }
            created_shield = triggering_army._create_and_add_single_effect(
                shield_data, skill_def["id"], triggering_army, triggering_army, opponent_army
            )
            if created_shield:
                happened = True
                est_mag = (
                    simulator._calculate_shield_magnitude_for_logging(triggering_army, opponent_army, float(shield_factor))
                    if simulator
                    else created_shield.magnitude
                )
                logs.append(
                    (
                        f"Gains shield ({created_shield.get_functionality_description()}) for {shield_duration + 1} rounds (starting next round). Est. Mag: {est_mag:.0f}",
                        None,
                    )
                )

        if cfg.get("purify_count", 0) > 0:
            eligible_debuffs = [
                eff
                for eff in triggering_army.active_effects
                if (
                    eff.effect_type == EffectType.DEBUFF
                    or (
                        eff.effect_type == EffectType.DAMAGE_OVER_TIME
                        and eff.config.get("dot_type") in [DoTType.BLEED, DoTType.POISON, DoTType.BURN, DoTType.LACERATE]
                    )
                    or eff.config.get("prevents_counterattack")
                    or eff.config.get("prevents_basic_attack")
                    or eff.config.get("prevents_rage_skill_cast")
                )
            ]
            if eligible_debuffs:
                selected = random.choice(eligible_debuffs)
                pending_cleanse = {
                    "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                    "name": EFFECT_NAME_WINTERS_CORONATION_PURIFY,
                    "duration": 0,
                    "config": {
                        "debuff_ids_to_remove": [selected.id],
                        "debuff_names_removed_log": [selected.name],
                    },
                    "activate_next_round": True,
                }
                if triggering_army._create_and_add_single_effect(
                    pending_cleanse, skill_def["id"], triggering_army, triggering_army, opponent_army
                ):
                    happened = True
                    logs.append((f"Purifies '{selected.name}' next round.", None))
            else:
                logs.append(("No debuffs to purify.", None))

    return happened, logs


def handle_base_skill_nayas_hunting_instinct(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    damage_factor = (
        skill_config.get("boosted_damage_factor", 0.0)
        if triggering_army.started_round_with_active_shield
        else skill_config.get("damage_factor", 0.0)
    )

    if damage_factor > 0 and simulator:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    debuff_duration = skill_config.get("debuff_duration", 0)
    debuff_data = {
        "effect_type": EffectType.DEBUFF,
        "name": EFFECT_NAME_BROKEN_BLADE_DEBUFF,
        "duration": debuff_duration,
        "config": {"prevents_counterattack": True},
        "activate_next_round": True,
    }
    created_debuff = opponent_army._create_and_add_single_effect(
        debuff_data, skill_def["id"], triggering_army, opponent_army, triggering_army
    )
    if created_debuff:
        an_effect_happened = True
        log_details.append(
            (
                f"Inflicts '{EFFECT_NAME_BROKEN_BLADE_DEBUFF}' on {opponent_army.name} for {created_debuff.duration + 1} rounds (starting next round).",
                None,
            )
        )
    return an_effect_happened, log_details


def handle_base_skill_inspiration_arrives(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0 and simulator:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    buff_magnitude = skill_config.get("buff_magnitude", 0.0)
    buff_duration = skill_config.get("buff_duration", 0)
    if buff_magnitude != 0:
        buff_effect_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_INSPIRATION_ARRIVES_COUNTER_BOOST,
            "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST,
            "magnitude": buff_magnitude,
            "duration": buff_duration,
            "activate_next_round": True,
        }
        created_buff = triggering_army._create_and_add_single_effect(
            buff_effect_data, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            an_effect_happened = True
            log_details.append(
                (
                    f"Gains '{EFFECT_NAME_INSPIRATION_ARRIVES_COUNTER_BOOST}' for {created_buff.duration + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details

def handle_rage_bloody_pillage(triggering_army: ArmyRef, opponent_army: ArmyRef,
                               skill_def: SkillDefinition, event_data: Dict[str, Any],
                               simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    dmg_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg_factor = cfg.get("damage_factor", 0.0)
    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False), source_skill_def=skill_def)
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            dmg_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))
    bleed_factor = cfg.get("bleed_factor", 0.0)
    bleed_dur = cfg.get("bleed_duration", 2)
    if bleed_factor > 0:
        bleed_data = {"effect_type": EffectType.DAMAGE_OVER_TIME, "name": EFFECT_NAME_BLOODY_PILLAGE_BLEED,
                      "dot_type": DoTType.BLEED, "status_effect_factor": bleed_factor,
                      "duration": bleed_dur, "activate_next_round": True}
        if opponent_army._create_and_add_single_effect(bleed_data, skill_def["id"], triggering_army, opponent_army, triggering_army):
            happened = True
            dmg_flag = True
            logs.append((f"Inflicts '{EFFECT_NAME_BLOODY_PILLAGE_BLEED}' on {opponent_army.name} (Factor: {bleed_factor}) for {bleed_dur + 1} rounds (starting next round).", None))
    return happened, logs, dmg_flag


# --- Harald Base Skill Handlers ---
def handle_base_skill_fleet_raider(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                   skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                   simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if random.random() < cfg.get("damage_chance", 0.0):
        dmg_factor = cfg.get("damage_factor", 0.0)
        if dmg_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def)
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((f"Deals damage to {opponent_army.name}.",
                         {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))
        buff_mag = cfg.get("buff_magnitude", 0.25)
        buff_dur = cfg.get("buff_duration", 5)
        buff = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_FLEET_RAIDER_BUFF,
                "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": buff_mag,
                "duration": buff_dur, "activate_next_round": True}
        if triggering_army._create_and_add_single_effect(buff, skill_def["id"], triggering_army, triggering_army, opponent_army):
            happened = True
            logs.append((f"Gains '{EFFECT_NAME_FLEET_RAIDER_BUFF}' for {buff_dur + 1} rounds (starting next round).", None))
    return happened, logs


# --- Yulmi Base Skill Handlers ---
def handle_base_skill_plague(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    trigger_interval = cfg.get("trigger_interval", 9)
    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    poison_factor = cfg.get("poison_factor", 0.0)
    poison_duration = cfg.get("poison_duration", 1)
    damage_taken_debuff = cfg.get("damage_taken_debuff", 0.0)
    debuff_duration = cfg.get("debuff_duration", 1)

    if poison_factor > 0:
        poison_effect = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_PLAGUE_POISON,
            "dot_type": DoTType.POISON,
            "status_effect_factor": poison_factor,
            "duration": poison_duration,
            "activate_next_round": True,
        }
        created_poison = opponent_army._create_and_add_single_effect(
            poison_effect, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_poison:
            an_effect_happened = True
            log_details.append(
                (f"Inflicts '{EFFECT_NAME_PLAGUE_POISON}' on {opponent_army.name} (Factor: {poison_factor}) for {poison_duration + 1} rounds (starting next round).",
                 None)
            )

    enemy_poisoned = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.POISON
        for eff in opponent_army.active_effects
    )
    if enemy_poisoned and damage_taken_debuff != 0:
        debuff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_PLAGUE_DAMAGE_TAKEN_DEBUFF,
            "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER,
            "magnitude": damage_taken_debuff,
            "duration": debuff_duration,
            "activate_next_round": True,
        }
        created_debuff = opponent_army._create_and_add_single_effect(
            debuff_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
            log_details.append(
                (f"{opponent_army.name} takes {damage_taken_debuff * 100:.0f}% more damage for {debuff_duration + 1} rounds.", None)
            )

    return an_effect_happened, log_details


# --- Ivor Base Skill Handlers ---
def handle_base_skill_fatal_flying_axe(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                       skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                       simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg = cfg.get("damage_factor", 0.0)
    buffed = cfg.get("buffed_damage_factor", dmg)
    enemy_has_temp_buff = any(
        eff.effect_type not in (EffectType.DEBUFF, EffectType.DAMAGE_OVER_TIME)
        and eff.duration != -1
        for eff in opponent_army.active_effects
    )
    dmg_factor = buffed if enemy_has_temp_buff else dmg
    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def)
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))
    return happened, logs

def handle_rage_raging_smash(triggering_army: ArmyRef, opponent_army: ArmyRef,
                              skill_def: SkillDefinition, event_data: Dict[str, Any], simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    dmg_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg_factor = cfg.get("damage_factor", 0.0)
    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False), source_skill_def=skill_def)
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            dmg_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))
    slow_dur = cfg.get("slow_duration", 4)
    slow_data = {"effect_type": EffectType.DEBUFF, "name": EFFECT_NAME_SLOW_DEBUFF, "duration": slow_dur,
                 "activate_next_round": True, "config": {}}
    if opponent_army._create_and_add_single_effect(slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army):
        happened = True
        dmg_flag = True
        logs.append((f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_dur + 1} rounds (starting next round).", None))
    return happened, logs, dmg_flag


# --- Bjorn Base Skill Handlers ---
def handle_base_skill_crippling_pursuit(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                        simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if random.random() < cfg.get("damage_chance", 0.0):
        dmg_factor = cfg.get("damage_factor", 0.0)
        if dmg_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def)
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((f"Deals damage to {opponent_army.name}.",
                         {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))
        if any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects):
            extra_factor = cfg.get("extra_damage_factor", 0.0)
            if extra_factor > 0:
                hp_damage2, abs2, kills2, raw2, calc_steps2 = simulator._calculate_generic_skill_damage(
                    triggering_army, opponent_army, extra_factor, source_skill_def=skill_def)
                if hp_damage2 > 0:
                    opponent_army.pending_hp_damage_this_round += hp_damage2
                if hp_damage2 > 0 or abs2 > 0:
                    happened = True
                logs.append((f"Deals additional damage to {opponent_army.name} due to slow.",
                             {
                                 "damage_done_hp": round(raw2),
                                 "absorbed_hp": round(abs2),
                                 "potential_kills": kills2,
                                 "calculation_steps": calc_steps2,
                             }))
    return happened, logs


def handle_rage_lethal_fracture(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                skill_def: SkillDefinition, event_data: Dict[str, Any], simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    dmg_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg_factor = cfg.get("damage_factor", 0.0)
    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False), source_skill_def=skill_def)
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            dmg_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))
    slow_dur = cfg.get("slow_duration", 3)
    slow_data = {"effect_type": EffectType.DEBUFF, "name": EFFECT_NAME_SLOW_DEBUFF, "duration": slow_dur,
                 "activate_next_round": True, "config": {}}
    if opponent_army._create_and_add_single_effect(slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army):
        happened = True
        dmg_flag = True
        logs.append((f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_dur + 1} rounds (starting next round).", None))
    atk_buff_mag = cfg.get("attack_buff", 0.15)
    atk_buff_dur = cfg.get("attack_duration", 3)
    buff_data = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_LETHAL_FRACTURE_ATK_BUFF,
                 "stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER, "magnitude": atk_buff_mag,
                 "duration": atk_buff_dur, "activate_next_round": True, "unit_type_condition": "infantry"}
    if triggering_army._create_and_add_single_effect(buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army):
        happened = True
        logs.append((f"Gains '{EFFECT_NAME_LETHAL_FRACTURE_ATK_BUFF}' for {atk_buff_dur + 1} rounds (starting next round).", None))
    return happened, logs, dmg_flag


# --- Hobert Base Skill Handlers ---
def handle_base_skill_berserk_fury(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                   skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                   simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    initial = triggering_army.unit.initial_count
    if initial <= 0:
        return False, []
    lost_ratio = max(0.0, (initial - triggering_army.current_troop_count) / initial)
    stacks_needed = min(5, int(lost_ratio / cfg.get("loss_per_stack", 0.06)))
    existing_stacks = sum(1 for eff in triggering_army.active_effects if eff.name == EFFECT_NAME_BERSERK_FURY_BUFF and eff.source_skill_id == skill_def["id"])
    while existing_stacks < stacks_needed:
        buff = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_BERSERK_FURY_BUFF,
                "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": cfg.get("basic_buff", 0.12),
                "duration": -1, "activate_next_round": False}
        rage_eff = {"effect_type": EffectType.CUSTOM_SKILL_EFFECT, "name": EFFECT_NAME_BERSERK_FURY_RAGE_GAIN,
                    "duration": -1, "config": {"rage_bonus_pct": cfg.get("rage_bonus_pct", 0.03)}}
        if triggering_army._create_and_add_single_effect(buff, skill_def["id"], triggering_army, triggering_army, opponent_army):
            happened = True
            logs.append((f"Gains Berserk Fury stack {existing_stacks + 1}/{stacks_needed}.", None))
        triggering_army._create_and_add_single_effect(rage_eff, skill_def["id"], triggering_army, triggering_army, opponent_army)
        existing_stacks += 1
    return happened, logs


def handle_rage_brutal_blow(triggering_army: ArmyRef, opponent_army: ArmyRef,
                            skill_def: SkillDefinition, event_data: Dict[str, Any], simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    dmg_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg_factor = cfg.get("damage_factor", 0.0)
    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False), source_skill_def=skill_def)
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            dmg_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))
    shield_factor = cfg.get("shield_factor", 0.0)
    shield_dur = cfg.get("shield_duration", 2)
    if shield_factor > 0:
        shield_data = {"effect_type": EffectType.SHIELD, "name": EFFECT_NAME_BRUTAL_BLOW_SHIELD,
                       "duration": shield_dur, "magnitude_calc_type": "dynamic_shield_resistance_v1",
                       "shield_factor": shield_factor, "activate_next_round": True}
        if triggering_army._create_and_add_single_effect(shield_data, skill_def["id"], triggering_army, triggering_army, opponent_army):
            happened = True
            logs.append((f"Gains shield for {shield_dur + 1} rounds (starting next round).", None))
    # schedule buff removal and self cleanse
    if cfg.get("buff_removal_count", 2) > 0:
        opp_buff_ids = [
            eff.id
            for eff in opponent_army.active_effects
            if eff.is_dispellable_buff_candidate()
        ][
            : cfg.get("buff_removal_count", 2)
        ]
        pending = {"effect_type": EffectType.CUSTOM_SKILL_EFFECT, "name": EFFECT_NAME_PENDING_BRUTAL_BLOW_BUFF_REMOVAL,
                   "duration": 0, "config": {"buff_ids_to_remove": opp_buff_ids,
                                            "targeted_buff_names_initial_log": [eff.name for eff in opponent_army.active_effects if eff.id in opp_buff_ids]},
                   "activate_next_round": True}
        opponent_army._create_and_add_single_effect(pending, skill_def["id"], triggering_army, opponent_army, triggering_army)
    if cfg.get("self_cleanse_count", 1) > 0:
        own_debuff_ids = [
            eff.id
            for eff in triggering_army.active_effects
            if (
                eff.effect_type == EffectType.DEBUFF
                or (
                    eff.effect_type == EffectType.DAMAGE_OVER_TIME
                    and eff.config.get("dot_type")
                    in [DoTType.BLEED, DoTType.POISON, DoTType.BURN, DoTType.LACERATE]
                )
                or eff.config.get("prevents_counterattack")
                or eff.config.get("prevents_basic_attack")
                or eff.config.get("prevents_rage_skill_cast")
                or (eff.effect_type == EffectType.STAT_MOD and eff.is_harmful_for_target())
                or (eff.effect_type == EffectType.CUSTOM_SKILL_EFFECT and eff.is_harmful_for_target())
            )
        ][: cfg.get("self_cleanse_count", 1)]
        pending_cleanse = {"effect_type": EffectType.CUSTOM_SKILL_EFFECT, "name": EFFECT_NAME_PENDING_BRUTAL_BLOW_CLEANSE,
                           "duration": 0, "config": {"debuff_ids_to_remove": own_debuff_ids,
                                                    "debuff_names_removed_log": [eff.name for eff in triggering_army.active_effects if eff.id in own_debuff_ids]},
                           "activate_next_round": True}
        triggering_army._create_and_add_single_effect(pending_cleanse, skill_def["id"], triggering_army, triggering_army, opponent_army)
    return happened, logs, dmg_flag


# --- Leandra Base Skill Handlers ---
def handle_base_skill_vengeful_fury(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    burn_factor = cfg.get("burn_factor", 0.0)
    burn_duration = cfg.get("burn_duration", 1)
    if burn_factor > 0:
        burn_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_VENGEFUL_FURY_BURN,
            "dot_type": DoTType.BURN,
            "status_effect_factor": burn_factor,
            "duration": burn_duration,
            "activate_next_round": True,
        }
        created_burn = opponent_army._create_and_add_single_effect(
            burn_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_burn:
            happened = True
            logs.append((
                f"Inflicts '{EFFECT_NAME_VENGEFUL_FURY_BURN}' on {opponent_army.name} (Factor: {burn_factor}) "
                f"for {burn_duration + 1} rounds (starting next round).",
                None,
            ))

    enemy_has_poison = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.POISON
        for eff in opponent_army.active_effects
    )
    bonus_rage = cfg.get("bonus_rage", 0)
    if enemy_has_poison and bonus_rage > 0:
        rage_effect = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_DELAYED_RAGE_GAIN,
            "duration": 0,
            "config": {"rage_amount": float(bonus_rage)},
            "activate_next_round": True,
        }
        created_rage = triggering_army._create_and_add_single_effect(
            rage_effect, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created_rage:
            happened = True
            logs.append((f"Gains {bonus_rage} rage next round because the enemy is poisoned.", None))
    return happened, logs


# --- Margit Base Skill Handlers ---
def handle_base_skill_ride_the_waves(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    base_mag = cfg.get("passive_buff_magnitude", 0.0)
    if base_mag != 0 and not any(
        eff.name == EFFECT_NAME_RIDE_THE_WAVES_PASSIVE and eff.source_skill_id == skill_def["id"]
        for eff in triggering_army.active_effects
    ):
        passive_buff = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_RIDE_THE_WAVES_PASSIVE,
            "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
            "magnitude": base_mag,
            "duration": -1,
            "activate_next_round": False,
            "config": {"is_dispellable": False},
        }
        created_buff = triggering_army._create_and_add_single_effect(
            passive_buff, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            happened = True
            logs.append((
                f"Gains permanent '{EFFECT_NAME_RIDE_THE_WAVES_PASSIVE}' (+{base_mag * 100:.0f}% basic attack damage).",
                None,
            ))

    enemy_has_slow = any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects)
    if enemy_has_slow:
        conditional_chance = cfg.get("conditional_buff_chance", 0.0)
        if random.random() < conditional_chance:
            buff_mag = cfg.get("conditional_buff_magnitude", 0.0)
            buff_dur = cfg.get("conditional_buff_duration", 1)
            if buff_mag != 0:
                surge_buff = {
                    "effect_type": EffectType.STAT_MOD,
                    "name": EFFECT_NAME_RIDE_THE_WAVES_SURGE_BUFF,
                    "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
                    "magnitude": buff_mag,
                    "duration": buff_dur,
                    "activate_next_round": True,
                }
                created_surge = triggering_army._create_and_add_single_effect(
                    surge_buff, skill_def["id"], triggering_army, triggering_army, opponent_army
                )
                if created_surge:
                    happened = True
                    logs.append((
                        f"Gains '{EFFECT_NAME_RIDE_THE_WAVES_SURGE_BUFF}' (+{buff_mag * 100:.0f}% basic damage) "
                        f"for {buff_dur + 1} rounds (starting next round).",
                        None,
                    ))
    return happened, logs

# --- Sasha Base Skill Handlers ---
def handle_base_skill_nature_blessing(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    trigger_interval = cfg.get("trigger_interval", 9)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    mark_gain = int(cfg.get("mark_stacks", 1))
    created = _add_nature_mark_stacks(triggering_army, opponent_army, skill_def, mark_gain)
    if created:
        happened = True
        logs.append((f"Gains {created} Nature Mark stack(s) next round.", None))

    heal_factor = cfg.get("heal_factor", 0.0)
    if heal_factor > 0:
        healed_amount = triggering_army.calculate_and_add_pending_healing(
            heal_factor, triggering_army, opponent_army, source_skill_id=skill_def["id"]
        )
        if healed_amount > 0:
            happened = True
            logs.append((f"Heals self (Factor: {heal_factor}) for {healed_amount:.0f} HP.", None))

    current_stacks = _count_effects_by_name(triggering_army, EFFECT_NAME_NATURE_MARK)
    damage_threshold = cfg.get("damage_threshold", 5)
    evasion_threshold = cfg.get("evasion_threshold", 15)

    if current_stacks >= damage_threshold:
        damage_factor = cfg.get("damage_factor", 0.0)
        if damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((
                f"Nature Blessing damage triggers on {opponent_army.name} (Factor: {damage_factor}).",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            ))

    if current_stacks >= evasion_threshold:
        evasion_duration = cfg.get("evasion_duration", 1)
        evasion_buff = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_NATURE_BLESSING_EVASION,
            "duration": evasion_duration,
            "activate_next_round": True,
            "config": {
                "evasion_chance": cfg.get("evasion_magnitude", 1.0),
                "applies_to": ["BASIC", "COUNTER", "SKILL"],
                "is_dispellable": False,
            },
        }
        created_buff = triggering_army._create_and_add_single_effect(
            evasion_buff, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            happened = True
            logs.append((
                f"Gains evasion buff for {evasion_duration + 1} round(s) (starting next round).",
                None,
            ))
        removed_count = _remove_all_effects_by_name(triggering_army, EFFECT_NAME_NATURE_MARK)
        if removed_count > 0:
            logs.append((f"Removes all Nature Mark stacks ({removed_count} removed).", None))

    return happened, logs

# --- Helgar Base Skill Handlers ---
def handle_base_skill_judgements_fury(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    pending_marker = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
        "duration": 0,
        "config": {"marker_count": 1},
        "activate_next_round": True,
    }
    # Queue a judgement marker for the next round. Mark the skill as having
    # triggered so that subsequent basic attacks in the same round do not add
    # additional markers.
    created_marker = triggering_army._create_and_add_single_effect(
        pending_marker,
        skill_def["id"],
        triggering_army,
        triggering_army,
        opponent_army,
    )
    if created_marker:
        happened = True

    threshold = cfg.get("marker_threshold", 20)
    current_markers = sum(1 for eff in triggering_army.active_effects if eff.name == EFFECT_NAME_JUDGEMENT_MARKER)
    if current_markers >= threshold:
        dmg_factor = cfg.get("damage_factor", 0.0)
        if dmg_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                         {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))

        removed = 0
        for i in range(len(triggering_army.active_effects) - 1, -1, -1):
            eff = triggering_army.active_effects[i]
            if eff.name == EFFECT_NAME_JUDGEMENT_MARKER:
                triggering_army.active_effects.pop(i)
                removed += 1
        if removed > 0 and simulator:
            simulator._log_skill_trigger(triggering_army, skill_def["name"], f"Consumes {removed} Judgement Markers")

        buff_mag = cfg.get("counter_buff", 0.45)
        buff_dur = cfg.get("buff_duration", 2)
        buff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF,
            "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST,
            "magnitude": buff_mag,
            "duration": buff_dur,
            "activate_next_round": True,
        }
        if triggering_army._create_and_add_single_effect(
            buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army
        ):
            happened = True
            logs.append(
                (
                    f"Gains counterattack damage buff for {buff_dur + 1} rounds (starting next round).",
                    None,
                )
            )

    return happened, logs


# --- Lagertha Base Skill Handler ---
def handle_base_skill_shield_breaker(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg = cfg.get("damage_factor", 0.0)
    if dmg > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage (Factor: {dmg}) to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))

    enemy_bleeding = _enemy_bleeding(opponent_army, event_data)
    if enemy_bleeding:
        buff_mag = cfg.get("buff_magnitude", 0.0)
        buff_dur = cfg.get("buff_duration", 1)
        if buff_mag != 0:
            buff_data = {
                "effect_type": EffectType.STAT_MOD,
                "name": EFFECT_NAME_SHIELD_BREAKER_BASIC_BUFF,
                "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
                "magnitude": buff_mag,
                "duration": buff_dur,
                "activate_next_round": True,
            }
            if triggering_army._create_and_add_single_effect(buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army):
                happened = True
                logs.append((f"Gains '{EFFECT_NAME_SHIELD_BREAKER_BASIC_BUFF}' for {buff_dur + 1} rounds (starting next round).", None))
    return happened, logs

