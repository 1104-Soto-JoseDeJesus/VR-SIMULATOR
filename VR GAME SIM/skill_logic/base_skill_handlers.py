import random
import uuid
from typing import Tuple, List, Optional, Dict, Any

from enums import EffectType, StatType, SkillTriggerType, DoTType
from effect_system import EffectInstance
from skill_system import SkillDefinition, ArmyRef, GameSimulatorRef
from constants import *


def handle_base_skill_planned_attack(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                                     ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {})
    dmg_fctrs = [sk_cfg.get("hit1_damage_factor", 0.0), sk_cfg.get("hit2_damage_factor", 0.0)]
    for i, dmg_fctr in enumerate(dmg_fctrs):
        if dmg_fctr == 0.0: continue
        if opp_army.current_troop_count <= 0: break
        hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(trig_army, opp_army, dmg_fctr,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp_army.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Hit {i + 1} deals damage to {opp_army.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
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
        hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(trig_army, opp_army, dmg_fctr,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp_army.pending_hp_damage_this_round += hp_dmg; dmg_dealt = True
        if absrb > 0 and not dmg_dealt: dmg_dealt = True
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Deals damage to {opp_army.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
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
            healed_amount = trig_army.calculate_and_add_pending_healing(heal_fctr, trig_army, opp_army)
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
            hp_dmg, absrb, kills, raw_dmg = sim._calculate_generic_skill_damage(trig_army, opp_army, dmg_fctr,
                                                                                source_skill_def=sk_def)
            if hp_dmg > 0: opp_army.pending_hp_damage_this_round += hp_dmg
            if hp_dmg > 0 or absrb > 0: eff_hpnd = True
            logs.append((f"Deals damage to {opp_army.name}.",
                         {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    if random.random() < sk_cfg.get("debuff_removal_chance", 0.0):
        dbuffs_on_army = [eff for eff in trig_army.active_effects if
                          eff.effect_type == EffectType.DEBUFF or eff.config.get(
                              "prevents_counterattack") or eff.config.get(
                              "prevents_basic_attack") or eff.name == EFFECT_NAME_SILENCE_DEBUFF]
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
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                an_effect_happened = True
            log_details.append((
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
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
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor,
                source_skill_def=skill_def
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                an_effect_happened = True
            log_details.append((
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name} (own troops higher).",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
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
                heal_factor, triggering_army, opponent_army
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

    if not (simulator.round > 0 and simulator.round % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    if random.random() < skill_config.get("rage_reduction_chance", 0.0):
        rage_to_reduce = skill_config.get("rage_reduction_amount", 0)
        if rage_to_reduce > 0 and opponent_army.current_rage > 0:
            actual_reduction = min(opponent_army.current_rage, float(rage_to_reduce))
            opponent_army.current_rage -= actual_reduction
            an_effect_happened = True
            log_details.append((f"Reduces {opponent_army.name}'s rage by {actual_reduction:.0f}.", None))
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

    if not (simulator.round > 0 and simulator.round % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    rage_to_reduce = skill_config.get("rage_reduction_amount", 0)
    if rage_to_reduce > 0 and opponent_army.current_rage > 0:
        actual_reduction = min(opponent_army.current_rage, float(rage_to_reduce))
        opponent_army.current_rage -= actual_reduction
        an_effect_happened = True
        log_details.append((f"Reduces {opponent_army.name}'s rage by {actual_reduction:.0f}.", None))

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

    if not (simulator.round > 0 and simulator.round % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills})
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

    if not (simulator.round > 0 and simulator.round % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
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
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills},
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
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills})
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


