from typing import Tuple, List, Optional, Dict, Any
import random

from ..enums import EffectType, StatType, SkillTriggerType, DoTType
from ..skill_system import SkillDefinition, ArmyRef, GameSimulatorRef
from ..effect_system import EffectInstance
from ..constants import *


def handle_rage_sharp_pursuit(army: ArmyRef, opp: ArmyRef, sk_def: SkillDefinition, ev_data: Dict[str, Any],
                              sim: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    eff_hpnd, logs, dmg_dealt_flag = False, [], False;
    is_h2_delay = ev_data.get("is_hero2_delayed_rage", False);
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"]
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0:
        hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(army, opp, dmg_fctr,
                                                                                is_hero2_rage_skill=is_h2_delay,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp.pending_hp_damage_this_round += hp_dmg; dmg_dealt_flag = True
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Deals damage to {opp.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    sh_fctr = sk_cfg.get("shield_factor", 0.0);
    self_sh_dur = sk_cfg.get("self_shield_duration", 1)
    if sh_fctr > 0:
        sh_name = sk_cfg.get("effect_name", EFFECT_NAME_SHARP_PURSUIT_SHIELD)
        sh_data = {"effect_type": EffectType.SHIELD, "name": sh_name, "duration": self_sh_dur,
                   "magnitude_calc_type": "dynamic_shield_resistance_v1", "shield_factor": sh_fctr,
                   "activate_next_round": True}
        cr_sh = army._create_and_add_single_effect(sh_data, sk_id, army, army, opp)
        if cr_sh:
            eff_hpnd = True;
            est_mag = sim._calculate_shield_magnitude_for_logging(army, opp, float(sh_fctr)) if sim else cr_sh.magnitude
            logs.append(
                (f"Gains Shield ({cr_sh.get_functionality_description()}), active for next {self_sh_dur + 1} round(s). Est. Mag: {est_mag:.0f}",
                 None))
    return eff_hpnd, logs, dmg_dealt_flag


def handle_rage_sacred_blade(army: ArmyRef, opp: ArmyRef, sk_def: SkillDefinition, ev_data: Dict[str, Any],
                             sim: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    eff_hpnd, logs, dmg_dealt_flag = False, [], False;
    is_h2_delay = ev_data.get("is_hero2_delayed_rage", False);
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"];
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0:
        hp_dmg, absrb, kills, raw_dmg = sim._calculate_generic_skill_damage(army, opp, dmg_fctr,
                                                                            is_hero2_rage_skill=is_h2_delay,
                                                                            source_skill_def=sk_def)
        if hp_dmg > 0: opp.pending_hp_damage_this_round += hp_dmg; dmg_dealt_flag = True
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Deals damage to {opp.name}.",
                     {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    buff_dets = sk_cfg.get("buff_details")
    if buff_dets and army.unit.unit_type == buff_dets.get("unit_type_condition"):
        buff_data_copy = buff_dets.copy()
        cr_buff = army._create_and_add_single_effect(buff_data_copy, sk_id, army, army, opp)
        if cr_buff: eff_hpnd = True; logs.append(
            (f"Gains Buff: {cr_buff.get_functionality_description()} for {cr_buff.duration + 1} round(s) (Pikemen only, starting next round).",
             None))
    return eff_hpnd, logs, dmg_dealt_flag


def handle_rage_vital_blessing(army: ArmyRef, opp: ArmyRef, sk_def: SkillDefinition, ev_data: Dict[str, Any],
                               sim: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    eff_hpnd, logs, dmg_dealt_flag = False, [], False;
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"]
    heal_fctr = sk_cfg.get("heal_factor", 0.0)
    if heal_fctr > 0:
        healed_amount = army.calculate_and_add_pending_healing(heal_fctr, army, opp)
        if healed_amount > 0:
            eff_hpnd = True
            logs.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_fctr}).", None))
    buff_dets = sk_cfg.get("buff_details")
    if buff_dets:
        buff_data_copy = buff_dets.copy()
        cr_buff = army._create_and_add_single_effect(buff_data_copy, sk_id, army, army, opp)
        if cr_buff: eff_hpnd = True; logs.append(
            (f"Gains Buff: {cr_buff.get_functionality_description()} for {cr_buff.duration + 1} round(s) (starting next round).",
             None))
    return eff_hpnd, logs, dmg_dealt_flag


def handle_rage_vanquishing_blade(army: ArmyRef, opp: ArmyRef, sk_def: SkillDefinition, ev_data: Dict[str, Any],
                                  sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    eff_hpnd, logs, dmg_dealt_flag = False, [], False;
    is_h2_delay = ev_data.get("is_hero2_delayed_rage", False);
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"]
    heal_fctr_vb = sk_cfg.get("heal_factor", 0.0)
    if heal_fctr_vb > 0:
        healed_amount = army.calculate_and_add_pending_healing(heal_fctr_vb, army, opp)
        if healed_amount > 0:
            eff_hpnd = True
            logs.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_fctr_vb}).", None))
    buff_dets_vb = sk_cfg.get("buff_details")
    if buff_dets_vb:
        buff_data_copy = buff_dets_vb.copy()
        cr_buff = army._create_and_add_single_effect(buff_data_copy, sk_id, army, army, opp)
        if cr_buff: eff_hpnd = True; logs.append(
            (f"Gains Buff: {cr_buff.get_functionality_description()} for {cr_buff.duration + 1} round(s) (starting next round).",
             None))
    dmg_fctr_vb = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr_vb > 0:
        hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(army, opp, dmg_fctr_vb,
                                                                                is_hero2_rage_skill=is_h2_delay,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp.pending_hp_damage_this_round += hp_dmg; dmg_dealt_flag = True
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Deals damage to {opp.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    return eff_hpnd, logs, dmg_dealt_flag


def handle_generic_damage_rage_skill(army: ArmyRef, opp: ArmyRef, sk_def: SkillDefinition, ev_data: Dict[str, Any],
                                     sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    eff_hpnd, logs, dmg_dealt_flag = False, [], False;
    is_h2_delay = ev_data.get("is_hero2_delayed_rage", False);
    sk_cfg = sk_def.get("config", {});
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0:
        hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(army, opp, dmg_fctr,
                                                                                is_hero2_rage_skill=is_h2_delay,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp.pending_hp_damage_this_round += hp_dmg; dmg_dealt_flag = True
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Deals damage to {opp.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    return eff_hpnd, logs, dmg_dealt_flag


def handle_rage_skill_snakes_frenzy(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    buff_magnitude = skill_config.get("buff_magnitude", 0.0)
    buff_duration = skill_config.get("buff_duration", 1)
    if buff_magnitude > 0:
        buff_effect_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_SNAKES_FRENZY_BUFF,
            "stat_to_mod": StatType.REACTIVE_SKILL_DAMAGE_ADJUST,
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
                f"Gains '{EFFECT_NAME_SNAKES_FRENZY_BUFF}': {created_buff.get_functionality_description()} for {created_buff.duration + 1} rounds (starting next round).",
                None
            ))
    return an_effect_happened, log_details, damage_dealt_flag


def handle_rage_skill_paralyzing_terror(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    shield_factor = skill_config.get("shield_factor", 0.0)
    shield_duration = skill_config.get("shield_duration", 2)

    if shield_factor > 0:
        shield_effect_data = {
            "effect_type": EffectType.SHIELD,
            "name": EFFECT_NAME_PARALYZING_TERROR_SHIELD,
            "duration": shield_duration,
            "magnitude_calc_type": "dynamic_shield_resistance_v1",
            "shield_factor": shield_factor,
            "activate_next_round": True
        }
        created_shield = triggering_army._create_and_add_single_effect(
            shield_effect_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_shield:
            an_effect_happened = True
            est_mag = simulator._calculate_shield_magnitude_for_logging(triggering_army, opponent_army,
                                                                        float(
                                                                            shield_factor)) if simulator else created_shield.magnitude
            log_details.append((
                f"Gains '{EFFECT_NAME_PARALYZING_TERROR_SHIELD}' ({created_shield.get_functionality_description()}), active for {created_shield.duration + 1} rounds. Est. Mag: {est_mag:.0f}",
                None
            ))
    return an_effect_happened, log_details, damage_dealt_flag


def handle_rage_skill_intimidation(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor_hit1 = skill_config.get("damage_factor_hit1", 0.0)
    if damage_factor_hit1 > 0 and opponent_army.current_troop_count > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor_hit1,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Hit 1 deals damage (Factor: {damage_factor_hit1}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    damage_factor_hit2 = skill_config.get("damage_factor_hit2", 0.0)
    if damage_factor_hit2 > 0 and opponent_army.current_troop_count > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor_hit2,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Hit 2 deals damage (Factor: {damage_factor_hit2}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    rage_reduction = skill_config.get("rage_reduction", 0)
    if rage_reduction > 0 and opponent_army.current_rage > 0:
        actual_reduction = min(opponent_army.current_rage, float(rage_reduction))
        opponent_army.current_rage -= actual_reduction
        an_effect_happened = True
        log_details.append((f"Reduces {opponent_army.name}'s rage by {actual_reduction:.0f}.", None))

    if random.random() < skill_config.get("silence_chance", 0.0):
        silence_duration = skill_config.get("silence_duration", 1)
        silence_effect_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_SILENCE_DEBUFF,
            "duration": silence_duration,
            "config": {"prevents_rage_skill_cast": True},
            "activate_next_round": True
        }
        created_silence = opponent_army._create_and_add_single_effect(
            silence_effect_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_silence:
            an_effect_happened = True
            log_details.append((
                f"Inflicts '{EFFECT_NAME_SILENCE_DEBUFF}' on {opponent_army.name} for {created_silence.duration + 1} rounds (starting next round).",
                None
            ))
    return an_effect_happened, log_details, damage_dealt_flag


def handle_rage_skill_viking_sage(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    atk_reduction_magnitude = skill_config.get("atk_reduction_magnitude", 0.0)
    atk_reduction_duration = skill_config.get("atk_reduction_duration", 3)

    if atk_reduction_magnitude < 0:
        debuff_effect_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_VIKING_SAGE_ATK_REDUCTION,
            "stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER,
            "magnitude": atk_reduction_magnitude,
            "duration": atk_reduction_duration,
            "activate_next_round": True
        }
        created_debuff = opponent_army._create_and_add_single_effect(
            debuff_effect_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
            log_details.append((
                f"Inflicts '{EFFECT_NAME_VIKING_SAGE_ATK_REDUCTION}' on {opponent_army.name}: {created_debuff.get_functionality_description()} for {created_debuff.duration + 1} rounds (starting next round).",
                None
            ))
    return an_effect_happened, log_details, damage_dealt_flag


def handle_rage_holy_enlightenment(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    if random.random() < skill_config.get("burn_chance", 0.0):
        burn_factor = skill_config.get("burn_factor", 0.0)
        burn_duration = skill_config.get("burn_duration", 2)
        if burn_factor > 0:
            burn_effect_data = {
                "effect_type": EffectType.DAMAGE_OVER_TIME,
                "name": EFFECT_NAME_HOLY_ENLIGHTENMENT_BURN,
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
                damage_dealt_flag = True
                log_details.append((
                    f"Inflicts '{EFFECT_NAME_HOLY_ENLIGHTENMENT_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                    None
                ))
    else:
        log_details.append((f"Burn chance ({skill_config.get('burn_chance', 0.0) * 100:.0f}%) not met.", None))

    if random.random() < skill_config.get("debuff_chance", 0.0):
        debuff_magnitude = skill_config.get("debuff_magnitude", 0.0)
        debuff_duration = skill_config.get("debuff_duration", 2)
        if debuff_magnitude > 0:
            debuff_effect_data = {
                "effect_type": EffectType.STAT_MOD,
                "name": EFFECT_NAME_HOLY_ENLIGHTENMENT_DMG_TAKEN_DEBUFF,
                "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER,
                "magnitude": debuff_magnitude,
                "duration": debuff_duration,
                "activate_next_round": True
            }
            created_debuff = opponent_army._create_and_add_single_effect(
                debuff_effect_data, skill_id, triggering_army, opponent_army, triggering_army
            )
            if created_debuff:
                an_effect_happened = True
                log_details.append((
                    f"Inflicts '{EFFECT_NAME_HOLY_ENLIGHTENMENT_DMG_TAKEN_DEBUFF}' on {opponent_army.name}: {created_debuff.get_functionality_description()} for {debuff_duration + 1} rounds (starting next round).",
                    None
                ))
    else:
        log_details.append(
            (f"Damage taken debuff chance ({skill_config.get('debuff_chance', 0.0) * 100:.0f}%) not met.", None))

    return an_effect_happened, log_details, damage_dealt_flag


def handle_rage_raining_arrows(  # Verdandi's skill, already exists
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    burn_factor = skill_config.get("burn_factor", 0.0)
    burn_duration = skill_config.get("burn_duration", 1)
    if burn_factor > 0:
        burn_effect_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_RAINING_ARROWS_BURN,
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
            damage_dealt_flag = True
            log_details.append((
                f"Inflicts '{EFFECT_NAME_RAINING_ARROWS_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                None
            ))

    return an_effect_happened, log_details, damage_dealt_flag


# --- OLENA RAGE SKILL HANDLER ---
def handle_rage_concentration(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)  # Olena is likely H1

    # 1. Deal direct damage
    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    # 2. Apply multi-round rage gain effect
    base_rage_gain_per_round = skill_config.get("base_rage_gain", 100)
    bonus_rage_conditional = skill_config.get("bonus_rage_if_burning", 200)
    effect_duration = skill_config.get("rage_gain_duration", 1)  # Duration 1 for 2 rounds of gain (N+1, N+2)

    # Check burn condition on opponent AT THE TIME OF CASTING
    enemy_is_burning_at_cast = False
    for effect in opponent_army.active_effects:
        if effect.effect_type == EffectType.DAMAGE_OVER_TIME and effect.config.get('dot_type') == DoTType.BURN:
            enemy_is_burning_at_cast = True
            break

    if enemy_is_burning_at_cast:
        log_details.append(
            (f"Condition met: Enemy {opponent_army.name} is burning at time of Concentration cast.", None))
    else:
        log_details.append(
            (f"Condition not met: Enemy {opponent_army.name} is not burning at time of Concentration cast.", None))

    rage_gain_effect_config = {
        "base_rage_amount": base_rage_gain_per_round,
        "bonus_rage_amount": bonus_rage_conditional if enemy_is_burning_at_cast else 0,
        # Only set bonus if condition met
        "bonus_applied_round": -1,  # Will be set to the round bonus is applied
        "effect_applied_in_round": simulator.round  # Store the round Concentration was cast
    }

    rage_gain_effect_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_CONCENTRATION_RAGE_GAIN,
        "duration": effect_duration,  # Will last for N+1 and N+2
        "config": rage_gain_effect_config,
        "activate_next_round": True  # Starts processing at the beginning of next round (N+1)
    }
    created_rage_effect = triggering_army._create_and_add_single_effect(
        rage_gain_effect_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_rage_effect:
        an_effect_happened = True
        log_details.append((
            f"Gains '{EFFECT_NAME_CONCENTRATION_RAGE_GAIN}' effect for {effect_duration + 1} rounds (starting next round). "
            f"Base Rage/Round: {base_rage_gain_per_round}. "
            f"Conditional Bonus Next Round: {rage_gain_effect_config['bonus_rage_amount'] if enemy_is_burning_at_cast else 0}.",
            None
        ))

    return an_effect_happened, log_details, damage_dealt_flag


def handle_rage_incineration(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills})
        )

    if random.random() < skill_config.get("burn_boost_chance", 0.0):
        boost_magnitude = skill_config.get("burn_boost_magnitude", 0.0)
        boost_duration = skill_config.get("burn_boost_duration", 0)
        if boost_magnitude != 0:
            buff_effect_data = {
                "effect_type": EffectType.STAT_MOD,
                "name": EFFECT_NAME_INCINERATION_BURN_BOOST,
                "stat_to_mod": StatType.BURN_DAMAGE_BOOST,
                "magnitude": boost_magnitude,
                "duration": boost_duration,
                "activate_next_round": True
            }
            created_buff = triggering_army._create_and_add_single_effect(
                buff_effect_data, skill_id, triggering_army, triggering_army, opponent_army
            )
            if created_buff:
                an_effect_happened = True
                log_details.append(
                    (f"Gains '{EFFECT_NAME_INCINERATION_BURN_BOOST}': {created_buff.get_functionality_description()} for {boost_duration + 1} rounds (starting next round).",
                     None)
                )
    else:
        log_details.append(
            (f"Burn damage boost chance ({skill_config.get('burn_boost_chance', 0.0) * 100:.0f}%) not met.", None))

    return an_effect_happened, log_details, damage_dealt_flag


# --- Freydis Rage Skill Handler ---
def handle_rage_desperate_strike(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills},
            )
        )

    burn_factor = skill_config.get("burn_factor", 0.0)
    burn_duration = skill_config.get("burn_duration", 3)
    if burn_factor > 0:
        burn_effect_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_DESPERATE_STRIKE_BURN,
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
            damage_dealt_flag = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_DESPERATE_STRIKE_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details, damage_dealt_flag


# --- Gregory Rage Skill Handler ---
def handle_rage_inspiring_dance(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    bleed_factor = skill_config.get("bleed_factor", 0.0)
    bleed_duration = skill_config.get("bleed_duration", 2)
    if bleed_factor > 0:
        bleed_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_HEAVENLY_DESCENT_BLEED,
            "dot_type": DoTType.BLEED,
            "status_effect_factor": bleed_factor,
            "duration": bleed_duration,
            "activate_next_round": True,
        }
        created_bleed = opponent_army._create_and_add_single_effect(
            bleed_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_bleed:
            an_effect_happened = True
            damage_dealt_flag = True
            log_details.append(
                (f"Inflicts '{EFFECT_NAME_HEAVENLY_DESCENT_BLEED}' on {opponent_army.name} (Factor: {bleed_factor}) for {bleed_duration + 1} rounds (starting next round).",
                 None)
            )

    return an_effect_happened, log_details, damage_dealt_flag


# --- Jens Rage Skill Handler ---
def handle_rage_skill_heavenly_descent(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills})
        )

    vul_mag = skill_config.get("vulnerability_magnitude", 0.0)
    vul_dur = skill_config.get("vulnerability_duration", 4)
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

    return an_effect_happened, log_details, damage_dealt_flag
