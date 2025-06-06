import random
import uuid
from typing import Tuple, List, Optional, Dict, Any

from ..enums import EffectType, StatType, SkillTriggerType, DoTType
from ..effect_system import EffectInstance
from ..skill_system import SkillDefinition, ArmyRef, GameSimulatorRef
from ..constants import *
from .utility_skill_handlers import handle_generic_single_damage_skill


def handle_talent_blade_counter(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                                ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, []
    for sub_eff_def in sk_def.get("sub_effects", []):
        if random.random() < sub_eff_def.get("chance", 1.0):
            eff_data = sub_eff_def["effect_to_apply"].copy()
            if "name" not in eff_data: eff_data["name"] = f"{sk_def['id']}_{sub_eff_def.get('name_suffix', 'Effect')}"
            cr_eff = trig_army._create_and_add_single_effect(eff_data, sk_def["id"], trig_army, trig_army, opp_army)
            if cr_eff: eff_hpnd = True; logs.append(
                (f"{sub_eff_def.get('name_suffix', 'Effect')}: {cr_eff.get_functionality_description()} for {cr_eff.duration + 1} round(s).",
                 None))
    return eff_hpnd, logs


def handle_talent_shield_of_resistance(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                                       ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, []
    for eff_data_orig in sk_def.get("effects_to_apply", []):
        eff_data = eff_data_orig.copy()
        if "name" not in eff_data: eff_data["name"] = f"{sk_def['id']}_Effect"
        cr_eff = trig_army._create_and_add_single_effect(eff_data, sk_def["id"], trig_army, trig_army, opp_army)
        if cr_eff:
            eff_hpnd = True;
            sh_hp = 0
            if cr_eff.effect_type == EffectType.SHIELD:
                shield_factor_calc = float(eff_data.get("shield_factor", 0.0))
                if cr_eff.config.get(
                        "magnitude_calc_type") == "dynamic_shield_resistance_v1" and sim and opp_army and shield_factor_calc > 0:
                    sh_hp = sim._calculate_shield_magnitude_for_logging(trig_army, opp_army, shield_factor_calc)
                else:
                    sh_hp = cr_eff.magnitude
            logs.append((f"Gains Shield: {cr_eff.get_functionality_description()} for {cr_eff.duration + 1} rounds.",
                         {"shield_hp_gained": round(sh_hp)} if cr_eff.effect_type == EffectType.SHIELD else None))
    return eff_hpnd, logs


def handle_talent_revenge_echo(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                               ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"];
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0:
        hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(trig_army, opp_army, dmg_fctr,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp_army.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Deals damage to {opp_army.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    if trig_army.started_round_with_active_shield:
        cond_buff_data = sk_cfg.get("conditional_buff")
        if cond_buff_data:
            buff_cpy = cond_buff_data.copy();
            if "name" not in buff_cpy: buff_cpy["name"] = EFFECT_NAME_REVENGE_ECHO_COUNTER_BOOST
            cr_buff = trig_army._create_and_add_single_effect(buff_cpy, sk_id, trig_army, trig_army, opp_army)
            if cr_buff: eff_hpnd = True; logs.append(
                (f"Gains Shield Condition Buff: {cr_buff.get_functionality_description()} for {cr_buff.duration + 1} round(s) (starting next round).",
                 None))
    return eff_hpnd, logs


def handle_talent_healing_hymn(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                               ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    act_target = ev_data.get('actual_opponent_for_calc', opp_army) if ev_data else opp_army
    if not trig_army.healing_hymn_triggered_this_round:
        sk_cfg = sk_def.get("config", {});
        dmg_fctr = sk_cfg.get("damage_factor", 0.0)
        if dmg_fctr > 0 and act_target:
            hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(trig_army, act_target, dmg_fctr,
                                                                                    source_skill_def=sk_def)
            if hp_dmg > 0: act_target.pending_hp_damage_this_round += hp_dmg
            if hp_dmg > 0 or absrb > 0: eff_hpnd = True; trig_army.healing_hymn_triggered_this_round = True
            logs.append((f"Deals damage to {act_target.name}.",
                         {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    return eff_hpnd, logs


def handle_talent_hold_fast(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                            ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"]
    sh_fctr = sk_cfg.get("shield_factor", 0.0);
    sh_dur = sk_cfg.get("shield_duration", 1);
    eff_name = sk_cfg.get("effect_name", EFFECT_NAME_HOLD_FAST_SHIELD)
    if sh_fctr > 0:
        sh_data = {"effect_type": EffectType.SHIELD, "name": eff_name, "duration": sh_dur,
                   "magnitude_calc_type": "dynamic_shield_resistance_v1", "shield_factor": sh_fctr,
                   "activate_next_round": True}
        cr_sh = trig_army._create_and_add_single_effect(sh_data, sk_id, trig_army, trig_army, opp_army)
        if cr_sh:
            eff_hpnd = True;
            est_mag = sim._calculate_shield_magnitude_for_logging(trig_army, opp_army,
                                                                  float(sh_fctr)) if sim else cr_sh.magnitude
            logs.append(
                (f"Gains Shield ({cr_sh.get_functionality_description()}), active for next {sh_dur + 1} round(s). Est. Mag: {est_mag:.0f}",
                 None))
    return eff_hpnd, logs


def handle_talent_determined_defense(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                                     ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"]
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0:
        hp_dmg, absrb, kills, raw_dmg = sim._calculate_generic_skill_damage(trig_army, opp_army, dmg_fctr,
                                                                            source_skill_def=sk_def)
        if hp_dmg > 0: opp_army.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Deals damage to {opp_army.name}.",
                     {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    heal_fctr = sk_cfg.get("heal_factor", 0.0)
    if heal_fctr > 0:
        healed_amount = trig_army.calculate_and_add_pending_healing(heal_fctr, trig_army, opp_army)
        if healed_amount > 0:
            eff_hpnd = True
            logs.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_fctr}).", None))
    if trig_army.started_round_with_active_shield:
        dbuff_name = sk_cfg.get("debuff_name", EFFECT_NAME_DETERMINED_DEFENSE_BROKEN_BLADE);
        dbuff_dur = sk_cfg.get("debuff_duration", 0);
        dbuff_cfg_load = {}
        if dbuff_name == EFFECT_NAME_BROKEN_BLADE_DEBUFF:
            dbuff_cfg_load["prevents_counterattack"] = True
        elif dbuff_name == EFFECT_NAME_DISARM_DEBUFF:
            dbuff_cfg_load["prevents_basic_attack"] = True
        dbuff_data = {"effect_type": EffectType.DEBUFF, "name": dbuff_name, "duration": dbuff_dur,
                      "config": dbuff_cfg_load, "activate_next_round": True}
        cr_dbuff = opp_army._create_and_add_single_effect(dbuff_data, sk_id, trig_army, opp_army, trig_army)
        if cr_dbuff: eff_hpnd = True; logs.append(
            (f"Applies {cr_dbuff.get_functionality_description()} to {opp_army.name} for next {dbuff_dur + 1} round(s) (shield was active).",
             None))
    return eff_hpnd, logs


def handle_talent_tit_for_tat(trig_army: ArmyRef, opp_army: ArmyRef, sk_def: SkillDefinition,
                              ev_data: Optional[Dict[str, Any]], sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    eff_hpnd, logs = False, [];
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"]
    act_attkr = ev_data.get('attacking_army_for_tit_for_tat', opp_army) if ev_data else opp_army
    if not act_attkr: act_attkr = opp_army
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0 and act_attkr:
        hp_dmg, absrb, kills, raw_dmg = sim._calculate_generic_skill_damage(trig_army, act_attkr, dmg_fctr,
                                                                            source_skill_def=sk_def)
        if hp_dmg > 0: act_attkr.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0: eff_hpnd = True
        logs.append((f"Deals damage back to {act_attkr.name}.",
                     {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absrb), "potential_kills": kills}))
    if not trig_army.started_round_with_active_shield:
        rdct_mag = sk_cfg.get("reduction_magnitude", -0.30);
        rdct_dur = sk_cfg.get("reduction_duration", 0);
        rdct_name = sk_cfg.get("reduction_effect_name", EFFECT_NAME_TIT_FOR_TAT_DMG_RED)
        rdct_data = {"effect_type": EffectType.STAT_MOD, "name": rdct_name,
                     "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": rdct_mag, "duration": rdct_dur,
                     "activate_next_round": True}
        cr_rdct = trig_army._create_and_add_single_effect(rdct_data, sk_id, trig_army, trig_army,
                                                          act_attkr if act_attkr else opp_army)
        if cr_rdct: eff_hpnd = True; logs.append(
            (f"Gains {cr_rdct.get_functionality_description()} for next {rdct_dur + 1} round(s) (no shield was active).",
             None))
    return eff_hpnd, logs


def handle_talent_serpents_rage(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_name = skill_def.get("name", "Periodic Damage Talent")
    damage_factor = skill_config.get("damage_factor", 0.0)
    trigger_interval = skill_config.get("trigger_interval", 9)

    if simulator.round > 0 and simulator.round % trigger_interval == 0:
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
                f"Deals damage to {opponent_army.name} (Factor: {damage_factor}) due to {skill_name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
            ))
    return an_effect_happened, log_details


def handle_talent_full_focus(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_id = skill_def["id"]
    skill_config = skill_def.get("config", {})
    damage_factor = skill_config.get("damage_factor", 0.0)

    if skill_id in triggering_army.triggered_skills_this_round:
        return False, []

    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
            triggering_army.triggered_skills_this_round.append(skill_id)
            log_details.append((
                f"Deals damage to {opponent_army.name} (Factor: {damage_factor}) due to {skill_def['name']}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
            ))
    return an_effect_happened, log_details


def handle_talent_power_of_silence(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})

    is_opponent_silenced = False
    for effect in opponent_army.active_effects:
        if effect.name == EFFECT_NAME_SILENCE_DEBUFF and effect.config.get("prevents_rage_skill_cast"):
            is_opponent_silenced = True
            break

    if is_opponent_silenced:
        rage_reduction = skill_config.get("rage_reduction", 125)
        if opponent_army.current_rage > 0:
            actual_reduction = min(opponent_army.current_rage, float(rage_reduction))
            opponent_army.current_rage -= actual_reduction
            an_effect_happened = True
            log_details.append(
                (f"Reduces {opponent_army.name}'s rage by {actual_reduction:.0f} (enemy was Silenced).", None))
        else:
            log_details.append(
                (f"Attempted to reduce {opponent_army.name}'s rage via {skill_def['name']}, but enemy rage is already 0.",
                 None))
    return an_effect_happened, log_details


def handle_talent_deadly_raid(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    damage_factor = skill_config.get("damage_factor", 0.0)

    has_non_permanent_buff = False
    for effect in triggering_army.active_effects:
        if effect.duration != -1:
            is_buff = False
            if effect.effect_type == EffectType.STAT_MOD and effect.magnitude > 0:
                is_buff = True
            elif effect.effect_type == EffectType.SHIELD and effect.magnitude > 0:
                is_buff = True
            elif effect.effect_type == EffectType.IMMUNITY:
                is_buff = True
            elif effect.effect_type == EffectType.HEAL_OVER_TIME:
                is_buff = True
            elif effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT and effect.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA:
                is_buff = True
            if is_buff: has_non_permanent_buff = True; break

    if has_non_permanent_buff:
        if damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor,
                source_skill_def=skill_def
            )
            if hp_damage > 0: opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0: an_effect_happened = True
            log_details.append((
                f"Deals damage to {opponent_army.name} (Factor: {damage_factor}) due to {skill_def['name']} (non-permanent buff active).",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
            ))
    return an_effect_happened, log_details


def handle_talent_strategize(
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

    command_buff_magnitude = skill_config.get("command_buff_magnitude", 0.0)
    command_buff_duration = skill_config.get("command_buff_duration", 2)

    if command_buff_magnitude > 0:
        buff_effect_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_STRATEGIZE_COMMAND_BUFF,
            "stat_to_mod": StatType.COMMAND_SKILL_DAMAGE_MODIFIER,
            "magnitude": command_buff_magnitude,
            "duration": command_buff_duration,
            "activate_next_round": True
        }
        created_buff = triggering_army._create_and_add_single_effect(
            buff_effect_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            an_effect_happened = True
            log_details.append((
                f"Gains '{EFFECT_NAME_STRATEGIZE_COMMAND_BUFF}': {created_buff.get_functionality_description()} for {command_buff_duration + 1} rounds (starting next round).",
                None
            ))

    is_enemy_burning = False
    for effect in opponent_army.active_effects:
        if effect.effect_type == EffectType.DAMAGE_OVER_TIME and effect.config.get('dot_type') == DoTType.BURN:
            is_enemy_burning = True
            break

    if is_enemy_burning:
        log_details.append((f"Condition met: Enemy {opponent_army.name} is afflicted by Burn.", None))
        if random.random() < skill_config.get("heal_chance_if_enemy_burn", 0.0):
            heal_factor = skill_config.get("heal_factor", 0.0)
            if heal_factor > 0:
                healed_amount = triggering_army.calculate_and_add_pending_healing(
                    heal_factor, triggering_army, opponent_army
                )
                if healed_amount > 0:
                    an_effect_happened = True
                    log_details.append(
                        (f"Heals self for {healed_amount:.0f} HP (Factor: {heal_factor}) due to enemy burning.", None))
        else:
            log_details.append(
                (f"Heal chance ({skill_config.get('heal_chance_if_enemy_burn', 0.0) * 100:.0f}%) not met.", None))
    else:
        log_details.append((f"Condition not met: Enemy {opponent_army.name} is not afflicted by Burn.", None))

    return an_effect_happened, log_details


def handle_talent_adaptable_to_changes(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 6)

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

    if random.random() < skill_config.get("poison_chance", 0.0):
        poison_factor = skill_config.get("poison_factor", 0.0)
        poison_duration = skill_config.get("poison_duration", 1)
        if poison_factor > 0:
            poison_effect_data = {
                "effect_type": EffectType.DAMAGE_OVER_TIME,
                "name": EFFECT_NAME_ADAPTABLE_POISON,
                "dot_type": DoTType.POISON,
                "status_effect_factor": poison_factor,
                "duration": poison_duration,
                "activate_next_round": True
            }
            created_poison = opponent_army._create_and_add_single_effect(
                poison_effect_data, skill_id, triggering_army, opponent_army, triggering_army
            )
            if created_poison:
                an_effect_happened = True
                log_details.append((
                    f"Inflicts '{EFFECT_NAME_ADAPTABLE_POISON}' on {opponent_army.name} (Factor: {poison_factor}) for {poison_duration + 1} rounds (starting next round).",
                    None
                ))
    else:
        log_details.append((f"Poison chance ({skill_config.get('poison_chance', 0.0) * 100:.0f}%) not met.", None))

    return an_effect_happened, log_details


def handle_talent_hunting_experience(
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

    burn_factor = skill_config.get("burn_factor", 0.0)
    burn_duration = skill_config.get("burn_duration", 1)

    if burn_factor > 0:
        burn_effect_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_HUNTING_EXPERIENCE_BURN,
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
                f"Inflicts '{EFFECT_NAME_HUNTING_EXPERIENCE_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                None
            ))
    return an_effect_happened, log_details


def handle_talent_targeted_strike(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 6)

    if not (simulator.round > 0 and simulator.round % trigger_interval == 0):
        return False, []

    damage_factor_base = skill_config.get("damage_factor", 550.0)
    damage_factor_boosted = skill_config.get("boosted_damage_factor", 1100.0)
    final_damage_factor = damage_factor_base

    is_enemy_burning = False
    for effect in opponent_army.active_effects:
        if effect.effect_type == EffectType.DAMAGE_OVER_TIME and effect.config.get('dot_type') == DoTType.BURN:
            is_enemy_burning = True
            break

    if is_enemy_burning:
        final_damage_factor = damage_factor_boosted
        log_details.append(
            (f"Condition met: Enemy {opponent_army.name} is afflicted by Burn. Using boosted damage factor {final_damage_factor}.",
             None))
    else:
        log_details.append(
            (f"Condition not met: Enemy {opponent_army.name} is not burning. Using base damage factor {final_damage_factor}.",
             None))

    if final_damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, final_damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {final_damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))
    return an_effect_happened, log_details


# --- OLENA TALENT HANDLERS ---
def handle_talent_multi_shot_arrow(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    damage_factor = skill_config.get("damage_factor", 0.0)

    # The 50% chance is handled by the simulator calling this handler based on skill_def["trigger_chance"]
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
    return an_effect_happened, log_details


def handle_talent_poised_shot(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        # event_data might contain info about the rage skill cast
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})

    # Deal damage
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

    # Chance to reduce enemy rage
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


# --- Artur Talent Handlers ---
def handle_talent_pent_up_anger(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    trigger_interval = skill_config.get("trigger_interval", 9)

    if not (simulator.round > 0 and simulator.round % trigger_interval == 0):
        return False, []

    rage_gain = skill_config.get("rage_gain", 0)
    if rage_gain > 0:
        triggering_army.current_rage += rage_gain
        an_effect_happened = True
        log_details.append((f"Gains {rage_gain:.0f} rage.", None))

    return an_effect_happened, log_details


# --- Freydis Talent Handlers ---
def handle_talent_heroic_blessing(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_id = skill_def["id"]
    skill_config = skill_def.get("config", {})

    debuff_duration = skill_config.get("debuff_duration", 30)
    burn_boost_magnitude = skill_config.get("burn_boost_magnitude", 0.15)

    pending_debuff_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_HEROIC_BLESSING_DEBUFF,
        "duration": 1,
        "config": {"debuff_duration": debuff_duration},
        "activate_next_round": True,
    }
    created_pending_debuff = triggering_army._create_and_add_single_effect(
        pending_debuff_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_pending_debuff:
        an_effect_happened = True
        log_details.append(
            (
                f"Schedules '{EFFECT_NAME_HEROIC_BLESSING_COUNTER_DEBUFF}' application for next round.",
                None,
            )
        )

    pending_buff_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_HEROIC_BLESSING_BUFF,
        "duration": debuff_duration + 1,
        "config": {"burn_boost_magnitude": burn_boost_magnitude},
        "activate_next_round": True,
    }
    created_pending = triggering_army._create_and_add_single_effect(
        pending_buff_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_pending:
        an_effect_happened = True

    return an_effect_happened, log_details


def handle_talent_battle_chime(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    trigger_interval = skill_config.get("trigger_interval", 9)
    skill_id = skill_def["id"]

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

    if triggering_army.current_rage < opponent_army.current_rage:
        rage_gain = skill_config.get("rage_gain_if_lower", 0)
        if rage_gain > 0:
            triggering_army.current_rage += rage_gain
            an_effect_happened = True
            log_details.append((f"Gains {rage_gain:.0f} rage.", None))
    else:
        log_details.append(("No rage gained (rage not lower than enemy).", None))

    return an_effect_happened, log_details


def handle_talent_flames_judgment(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    if not event_data or "source_command_skill_id" not in event_data:
        return False, []

    enemy_burning = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BURN
        for eff in opponent_army.active_effects
    )
    if not enemy_burning:
        log_details.append((f"Condition not met: Enemy {opponent_army.name} is not burning.", None))
        return False, log_details

    if random.random() < skill_config.get("damage_chance", 0.0):
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
    else:
        log_details.append((f"Damage chance ({skill_config.get('damage_chance', 0.0) * 100:.0f}%) not met.", None))

    return an_effect_happened, log_details


# --- Gregory Talent Handlers ---
def handle_talent_missing_beat(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
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

    if random.random() < skill_config.get("slow_chance", 0.0):
        slow_duration = skill_config.get("slow_duration", 2)
        slow_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_SLOW_DEBUFF,
            "duration": slow_duration,
            "activate_next_round": True,
            "config": {},
        }
        created_slow = opponent_army._create_and_add_single_effect(
            slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_slow:
            an_effect_happened = True
            log_details.append(
                (f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_duration + 1} rounds (starting next round).",
                 None)
            )
    return an_effect_happened, log_details


def handle_talent_godly_wrath(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    if simulator.round != 2:
        return False, []

    duration = skill_def.get("config", {}).get("duration", 30)
    magnitude = skill_def.get("config", {}).get("magnitude", 0.0)
    buff_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_GODLY_WRATH_COOP_RATE,
        "stat_to_mod": StatType.COOPERATION_TRIGGER_RATE_MODIFIER,
        "magnitude": magnitude,
        "duration": duration,
        "activate_next_round": False,
    }
    created = triggering_army._create_and_add_single_effect(
        buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army
    )
    if created:
        return True, [(f"Gains '{EFFECT_NAME_GODLY_WRATH_COOP_RATE}' for {duration + 1} rounds.", None)]
    return False, []


def handle_talent_divine_punishment(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    damage_chance = skill_config.get("damage_chance", 0.0)
    damage_factor = skill_config.get("damage_factor", 0.0)

    # Ensure the permanent basic attack buff is applied once
    has_buff = any(
        eff.name == EFFECT_NAME_DIVINE_PUNISHMENT_BASIC_BUFF and eff.effect_type == EffectType.STAT_MOD
        for eff in triggering_army.active_effects
    )
    if not has_buff:
        buff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_DIVINE_PUNISHMENT_BASIC_BUFF,
            "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
            "magnitude": 0.20,
            "duration": -1,
            "activate_next_round": False,
        }
        created_buff = triggering_army._create_and_add_single_effect(
            buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            an_effect_happened = True
            log_details.append(
                (f"Gains '{EFFECT_NAME_DIVINE_PUNISHMENT_BASIC_BUFF}' permanently.", None)
            )

    enemy_bleeding = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BLEED
        for eff in opponent_army.active_effects
    )
    if enemy_bleeding and random.random() < damage_chance:
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
    return an_effect_happened, log_details


# --- Rollo Talent Handlers ---
def handle_talent_patient_waiting(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                  skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                  simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    if simulator.round < 2 or simulator.round > 31:
        return False, []
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if simulator.round == 2:
        buff_mag = cfg.get("buff_magnitude", 0.2)
        duration = cfg.get("duration", 30)
        buff_data = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_PATIENT_WAITING_BUFF,
                     "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": buff_mag,
                     "duration": duration, "activate_next_round": False}
        created = triggering_army._create_and_add_single_effect(buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army)
        if created:
            happened = True
            logs.append((f"Gains '{EFFECT_NAME_PATIENT_WAITING_BUFF}' for {duration + 1} rounds.", None))
    if random.random() < cfg.get("damage_chance", 0.0):
        dmg_factor = cfg.get("damage_factor", 0.0)
        if dmg_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def)
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((f"Deals damage to {opponent_army.name}.",
                         {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}))
    return happened, logs


def handle_talent_revolutionary_resolve(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                         skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                         simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if random.random() < cfg.get("damage_chance", 0.0):
        dmg_factor = cfg.get("damage_factor", 0.0)
        if dmg_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def)
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((f"Deals damage to {opponent_army.name}.",
                         {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}))
        slow_duration = cfg.get("slow_duration", 2)
        slow_data = {"effect_type": EffectType.DEBUFF, "name": EFFECT_NAME_SLOW_DEBUFF, "duration": slow_duration,
                     "activate_next_round": True, "config": {}}
        created = opponent_army._create_and_add_single_effect(slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army)
        if created:
            happened = True
            logs.append((f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_duration + 1} rounds (starting next round).", None))
    return happened, logs


def handle_talent_adaptable_agility(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                     skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                     simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if triggering_army.current_troop_count > opponent_army.current_troop_count:
        if random.random() < cfg.get("damage_chance_high", 0.0):
            dmg_factor = cfg.get("damage_factor", 0.0)
            if dmg_factor > 0:
                hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                    triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def)
                if hp_damage > 0:
                    opponent_army.pending_hp_damage_this_round += hp_damage
                if hp_damage > 0 or absorbed > 0:
                    happened = True
                logs.append((f"Deals damage to {opponent_army.name}.",
                             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}))
    elif triggering_army.current_troop_count < opponent_army.current_troop_count:
        if random.random() < cfg.get("heal_chance_low", 0.0):
            heal_factor = cfg.get("heal_factor", 0.0)
            healed = triggering_army.calculate_and_add_pending_healing(heal_factor, triggering_army, opponent_army)
            if healed > 0:
                happened = True
                logs.append((f"Heals self for {healed:.0f} HP (Factor: {heal_factor}).", None))
    return happened, logs


# --- Harald Talent Handlers ---
def handle_talent_battle_preparation(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                     skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                     simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    if simulator.round != 2:
        return False, []
    cfg = skill_def.get("config", {})
    duration = cfg.get("duration", 30)
    buff_mag = cfg.get("buff_magnitude", 0.45)
    buff = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_BATTLE_PREPARATION_BUFF,
            "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": buff_mag,
            "duration": duration, "activate_next_round": False}
    created_buff = triggering_army._create_and_add_single_effect(buff, skill_def["id"], triggering_army, triggering_army, opponent_army)
    im_data = {"effect_type": EffectType.IMMUNITY, "name": EFFECT_NAME_BATTLE_PREPARATION_DISARM_IMMUNITY,
               "immune_to": EFFECT_NAME_DISARM_DEBUFF, "duration": duration, "activate_next_round": False}
    created_im = triggering_army._create_and_add_single_effect(im_data, skill_def["id"], triggering_army, triggering_army, opponent_army)
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    happened = False
    if created_buff:
        happened = True
        logs.append((f"Gains '{EFFECT_NAME_BATTLE_PREPARATION_BUFF}' for {duration + 1} rounds.", None))
    if created_im:
        happened = True
        logs.append((f"Gains immunity to Disarm for {duration + 1} rounds.", None))
    return happened, logs


def handle_talent_coordinated_strike(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                      skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                      simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if random.random() < cfg.get("damage_chance", 0.0):
        dmg = cfg.get("damage_factor", 0.0)
        if dmg > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg, source_skill_def=skill_def)
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((f"Deals damage to {opponent_army.name}.",
                         {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}))
        buff_mag = cfg.get("buff_magnitude", 0.12)
        buff_dur = cfg.get("buff_duration", 3)
        buff_data = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_COORDINATED_STRIKE_BUFF,
                     "stat_to_mod": StatType.REACTIVE_SKILL_DAMAGE_ADJUST,
                     "magnitude": buff_mag, "duration": buff_dur, "activate_next_round": True}
        created = triggering_army._create_and_add_single_effect(buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army)
        if created:
            happened = True
            logs.append((f"Gains '{EFFECT_NAME_COORDINATED_STRIKE_BUFF}' for {buff_dur + 1} rounds (starting next round).", None))
    return happened, logs


def handle_talent_slow_strike(triggering_army: ArmyRef, opponent_army: ArmyRef,
                               skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                               simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if not any(eff.name == EFFECT_NAME_SLOW_STRIKE_BASIC_BUFF and eff.source_skill_id == skill_def["id"] for eff in triggering_army.active_effects):
        buff_data = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SLOW_STRIKE_BASIC_BUFF,
                     "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": cfg.get("buff_magnitude", 0.5),
                     "duration": -1, "activate_next_round": False}
        created = triggering_army._create_and_add_single_effect(buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army)
        if created:
            happened = True
            logs.append((f"Gains permanent '{EFFECT_NAME_SLOW_STRIKE_BASIC_BUFF}'.", None))
    enemy_has_slow = any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects)
    if enemy_has_slow and random.random() < cfg.get("damage_chance", 0.0):
        dmg = cfg.get("damage_factor", 0.0)
        if dmg > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg, source_skill_def=skill_def)
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((f"Deals damage to {opponent_army.name}.",
                         {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}))
    return happened, logs


# --- Bjorn Talent Handlers ---
def handle_talent_trained_up(triggering_army: ArmyRef, opponent_army: ArmyRef,
                              skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                              simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if random.random() < cfg.get("damage_chance", 0.0):
        dmg_factor = cfg.get("damage_factor", 0.0)
        if dmg_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def)
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((f"Deals damage to {opponent_army.name}.",
                         {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}))
        if random.random() < cfg.get("slow_chance", 0.0):
            dur = cfg.get("slow_duration", 2)
            slow_data = {"effect_type": EffectType.DEBUFF, "name": EFFECT_NAME_SLOW_DEBUFF,
                         "duration": dur, "activate_next_round": True, "config": {}}
            created = opponent_army._create_and_add_single_effect(slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army)
            if created:
                happened = True
                logs.append((f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {dur + 1} rounds (starting next round).", None))
    return happened, logs


def handle_talent_fatal_bleeding(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                 skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                 simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    cfg = skill_def.get("config", {})
    interval = cfg.get("trigger_interval", 6)
    if simulator.round > 0 and simulator.round % interval == 0:
        bleed_factor = cfg.get("bleed_factor", 0.0)
        duration = cfg.get("bleed_duration", 2)
        bleed_data = {"effect_type": EffectType.DAMAGE_OVER_TIME, "name": EFFECT_NAME_FATAL_BLEEDING_DOT,
                      "dot_type": DoTType.BLEED, "status_effect_factor": bleed_factor,
                      "duration": duration, "activate_next_round": True}
        created = opponent_army._create_and_add_single_effect(bleed_data, skill_def["id"], triggering_army, opponent_army, triggering_army)
        if created:
            return True, [(f"Inflicts '{EFFECT_NAME_FATAL_BLEEDING_DOT}' on {opponent_army.name} (Factor: {bleed_factor}) for {duration + 1} rounds (starting next round).", None)]
    return False, []


def handle_talent_steadfast_armor(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                  skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                  simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    if random.random() < 1.0:
        reduction = cfg.get("reduction", -0.28)
        dur = cfg.get("duration", 1)
        buff = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_STEADFAST_ARMOR_REDUCTION,
                "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": reduction,
                "duration": dur, "activate_next_round": True}
        if triggering_army._create_and_add_single_effect(buff, skill_def["id"], triggering_army, triggering_army, opponent_army):
            happened = True
            logs.append((f"Gains damage reduction for {dur + 1} rounds (starting next round).", None))
        slow_dur = cfg.get("slow_duration", 2)
        slow_data = {"effect_type": EffectType.DEBUFF, "name": EFFECT_NAME_SLOW_DEBUFF,
                     "duration": slow_dur, "activate_next_round": True, "config": {}}
        if opponent_army._create_and_add_single_effect(slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army):
            happened = True
            logs.append((f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_dur + 1} rounds (starting next round).", None))
    return happened, logs


def handle_talent_fearless_pursuit(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                   skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                   simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg = cfg.get("damage_factor", 0.0)
    alt = cfg.get("alt_damage_factor", dmg)
    if any(eff.effect_type == EffectType.DEBUFF for eff in opponent_army.active_effects):
        dmg_factor = alt
    else:
        dmg_factor = dmg
    if dmg_factor > 0 and random.random() < 1.0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def)
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}))
    return happened, logs
