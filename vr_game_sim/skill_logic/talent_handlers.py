import random
import uuid
from typing import Tuple, List, Optional, Dict, Any

from ..enums import EffectType, StatType, SkillTriggerType, DoTType
from ..effect_system import EffectInstance
from ..skill_system import SkillDefinition, ArmyRef, GameSimulatorRef
from ..constants import *
from .utility_skill_handlers import handle_generic_single_damage_skill


def _get_army_round(army: ArmyRef, simulator: GameSimulatorRef) -> int:
    """Return the round counter for ``army`` with a simulator fallback."""
    if hasattr(army, "army_round"):
        return army.army_round
    return simulator.round if simulator else 0


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
        calc_target = ev_data.get('actual_opponent_for_calc', opp_army) if ev_data else opp_army
        hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(
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
                f"Deals damage to {opp_army.name}.",
                {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills},
            )
        )
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
    calc_target = ev_data.get('actual_opponent_for_calc', opp_army) if ev_data else opp_army
    if not trig_army.healing_hymn_triggered_this_round:
        sk_cfg = sk_def.get("config", {});
        dmg_fctr = sk_cfg.get("damage_factor", 0.0)
        if dmg_fctr > 0 and calc_target:
            hp_dmg, absrb, kills, raw_log_dmg = sim._calculate_generic_skill_damage(
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
                trig_army.healing_hymn_triggered_this_round = True
            logs.append(
                (
                    f"Deals damage to {opp_army.name}.",
                    {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills},
                )
            )
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
        calc_target = ev_data.get('actual_opponent_for_calc', opp_army) if ev_data else opp_army
        hp_dmg, absrb, kills, raw_dmg = sim._calculate_generic_skill_damage(
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
                f"Deals damage to {opp_army.name}.",
                {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absrb), "potential_kills": kills},
            )
        )
    heal_fctr = sk_cfg.get("heal_factor", 0.0)
    if heal_fctr > 0:
        healed_amount = trig_army.calculate_and_add_pending_healing(
            heal_fctr, trig_army, opp_army, source_skill_id=sk_id
        )
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
    if not act_attkr:
        act_attkr = opp_army
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0 and act_attkr:
        hp_dmg, absrb, kills, raw_dmg = sim._calculate_generic_skill_damage(
            trig_army,
            act_attkr,
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
                f"Deals damage to {opp_army.name}.",
                {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absrb), "potential_kills": kills},
            )
        )
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

    if _get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0:
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

    trigger_key = triggering_army.get_skill_trigger_key(skill_def)
    if trigger_key in triggering_army.triggered_skills_this_round:
        return False, []

    if damage_factor > 0:
        calc_target = opponent_army
        if event_data and event_data.get('actual_opponent_for_calc'):
            calc_target = event_data['actual_opponent_for_calc']

        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
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
            if trigger_key not in triggering_army.triggered_skills_this_round:
                triggering_army.triggered_skills_this_round.append(trigger_key)
            log_details.append(
                (
                    f"Deals damage to {opponent_army.name} (Factor: {damage_factor}) due to {skill_def['name']}.",
                    {
                        "damage_done_hp": round(raw_logged_damage),
                        "absorbed_hp": round(absorbed),
                        "potential_kills": kills,
                    },
                )
            )
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
        if opponent_army.current_rage > 0 and rage_reduction > 0:
            actual_reduction = min(opponent_army.current_rage, float(rage_reduction))
            effect_data = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_DELAYED_RAGE_REDUCTION,
                "duration": 0,
                "config": {"rage_reduction": actual_reduction},
                "activate_next_round": True,
            }
            created = opponent_army._create_and_add_single_effect(
                effect_data, skill_def["id"], triggering_army, opponent_army, triggering_army
            )
            if created:
                an_effect_happened = True
                log_details.append(
                    (f"Reduces {opponent_army.name}'s rage by {actual_reduction:.0f} next round (enemy was Silenced).", None))
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

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
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
                    heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
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

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
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

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
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

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
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
    skill_id = skill_def["id"]

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

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    rage_gain = skill_config.get("rage_gain", 0)
    if rage_gain > 0:
        effect_data = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_DELAYED_RAGE_GAIN,
            "duration": 0,
            "config": {"rage_amount": rage_gain},
            "activate_next_round": True,
        }
        created = triggering_army._create_and_add_single_effect(
            effect_data, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created:
            an_effect_happened = True
            log_details.append((f"Gains {rage_gain:.0f} rage next round.", None))

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

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
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
            effect_data = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_DELAYED_RAGE_GAIN,
                "duration": 0,
                "config": {"rage_amount": rage_gain},
                "activate_next_round": True,
            }
            created = triggering_army._create_and_add_single_effect(
                effect_data, skill_def["id"], triggering_army, triggering_army, opponent_army
            )
            if created:
                an_effect_happened = True
                log_details.append((f"Gains {rage_gain:.0f} rage next round.", None))
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
    if _get_army_round(triggering_army, simulator) != 2:
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
    if _get_army_round(triggering_army, simulator) < 2 or _get_army_round(triggering_army, simulator) > 31:
        return False, []
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    skill_id = skill_def["id"]
    if _get_army_round(triggering_army, simulator) == 2:
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
    skill_id = skill_def["id"]
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
            healed = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
            )
            if healed > 0:
                happened = True
                logs.append((f"Heals self for {healed:.0f} HP (Factor: {heal_factor}).", None))
    return happened, logs


# --- Harald Talent Handlers ---
def handle_talent_battle_preparation(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                     skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                     simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    if _get_army_round(triggering_army, simulator) != 2:
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
                     "stat_to_mod": StatType.COOPERATION_SKILL_DAMAGE_MODIFIER,
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
    if _get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % interval == 0:
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
    if any(
        eff.effect_type == EffectType.DEBUFF
        or (
            eff.effect_type == EffectType.DAMAGE_OVER_TIME
            and eff.config.get("dot_type") in [
                DoTType.BLEED,
                DoTType.POISON,
                DoTType.BURN,
                DoTType.LACERATE,
            ]
        )
        for eff in opponent_army.active_effects
    ):
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


# --- Helgar Talent Handlers ---
def handle_talent_saintly_guardian(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    # Passive effect applied via skill definition
    return False, []


def handle_talent_war_blessing(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    shield_factor = cfg.get("shield_factor", 0.0)
    shield_duration = cfg.get("shield_duration", 2)
    if shield_factor > 0:
        shield_data = {
            "effect_type": EffectType.SHIELD,
            "name": EFFECT_NAME_WAR_BLESSING_SHIELD,
            "duration": shield_duration,
            "magnitude_calc_type": "dynamic_shield_resistance_v1",
            "shield_factor": shield_factor,
            "activate_next_round": True,
        }
        created = triggering_army._create_and_add_single_effect(
            shield_data, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created:
            happened = True
            logs.append((f"Gains shield for {shield_duration + 1} rounds (starting next round).", None))
    pending_marker = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
        "duration": 0,
        "config": {"marker_count": 1},
        "activate_next_round": True,
    }
    triggering_army._create_and_add_single_effect(pending_marker, skill_def["id"], triggering_army, triggering_army, opponent_army)
    return happened, logs


def handle_talent_judgement_mark(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    dmg_factor = cfg.get("damage_factor", 0.0)
    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                     {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}))
    pending_marker = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
        "duration": 0,
        "config": {"marker_count": 3},
        "activate_next_round": True,
    }
    triggering_army._create_and_add_single_effect(pending_marker, skill_def["id"], triggering_army, triggering_army, opponent_army)
    return happened, logs


# --- Lagertha Talent Handlers ---
def handle_talent_chiefs_might(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    bleed_factor = skill_config.get("bleed_factor", 0.0)
    bleed_duration = skill_config.get("bleed_duration", 1)
    if bleed_factor > 0:
        bleed_effect_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_CHIEFS_MIGHT_BLEED,
            "dot_type": DoTType.BLEED,
            "status_effect_factor": bleed_factor,
            "duration": bleed_duration,
            "activate_next_round": True,
        }
        created_bleed = opponent_army._create_and_add_single_effect(
            bleed_effect_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_bleed:
            an_effect_happened = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_CHIEFS_MIGHT_BLEED}' on {opponent_army.name} (Factor: {bleed_factor}) for {bleed_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details


def handle_talent_fatal_strike(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    enemy_has_slow = any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects)
    if enemy_has_slow and random.random() < cfg.get("damage_chance", 0.0):
        dmg = cfg.get("damage_factor", 0.0)
        if dmg > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, dmg, source_skill_def=skill_def
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append(
                (
                    f"Deals damage (Factor: {dmg}) to {opponent_army.name}.",
                    {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills},
                )
            )

    return happened, logs


# --- Yulmi Talent Handlers ---
def handle_talent_high_fighting_spirit(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    damage_factor = cfg.get("damage_factor", 0.0)
    trigger_interval = cfg.get("trigger_interval", 9)
    buff_magnitude = cfg.get("buff_magnitude", 0.0)
    buff_duration = cfg.get("buff_duration", 0)

    if _get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0:
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
        if buff_magnitude != 0:
            for stat_type in [StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER, StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER]:
                buff_data = {
                    "effect_type": EffectType.STAT_MOD,
                    "name": EFFECT_NAME_HIGH_FIGHTING_SPIRIT_RAGE_BUFF,
                    "stat_to_mod": stat_type,
                    "magnitude": buff_magnitude,
                    "duration": buff_duration,
                    "activate_next_round": True,
                }
                created_buff = triggering_army._create_and_add_single_effect(
                    buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army
                )
                if created_buff:
                    an_effect_happened = True
            log_details.append(
                (f"Boosts rage skill damage by {buff_magnitude * 100:.0f}% for {buff_duration + 1} rounds.", None)
            )
    return an_effect_happened, log_details


def handle_talent_low_whispers(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    trigger_interval = cfg.get("trigger_interval", 6)
    reduction = cfg.get("reduction", -0.30)
    duration = cfg.get("duration", 1)
    rage_gain = cfg.get("rage_gain", 0)

    if _get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0:
        buff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_LOW_WHISPERS_REDUCTION,
            "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER,
            "magnitude": reduction,
            "duration": duration,
            "activate_next_round": True,
        }
        created_buff = triggering_army._create_and_add_single_effect(
            buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            an_effect_happened = True
            log_details.append(
                (f"Reduces damage taken by {abs(reduction) * 100:.0f}% for {duration + 1} rounds.", None)
            )

        enemy_burning = any(
            eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BURN
            for eff in opponent_army.active_effects
        )
        created_rage = None
        if enemy_burning and rage_gain > 0:
            rage_effect = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_DELAYED_RAGE_GAIN,
                "duration": 0,
                "config": {"rage_amount": rage_gain},
                "activate_next_round": True,
            }
            created_rage = triggering_army._create_and_add_single_effect(
                rage_effect, skill_def["id"], triggering_army, triggering_army, opponent_army
            )
        if created_rage:
            an_effect_happened = True
            log_details.append((f"Gains {rage_gain:.0f} rage next round.", None))
    return an_effect_happened, log_details


# --- Ivor Talent Handlers ---
def handle_talent_specter_lycan_assault(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                        simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    damage_factor = cfg.get("damage_factor", 0.0)
    trigger_interval = cfg.get("trigger_interval", 9)

    if _get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0:
        an_effect_happened = True
        if damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor, source_skill_def=skill_def)
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
            log_details.append((f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                               {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed),
                                "potential_kills": kills}))
    return an_effect_happened, log_details


def handle_talent_amazing_attack(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                 skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
                                 simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    threshold = cfg.get("troop_threshold", 350000)
    magnitude = cfg.get("damage_boost", 0.05)

    if opponent_army.current_troop_count > threshold:
        buff_data = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_AMAZING_ATTACK_BUFF,
                     "stat_to_mod": StatType.GENERAL_DAMAGE_MODIFIER, "magnitude": magnitude, "duration": 0}
        created_buff = triggering_army._create_and_add_single_effect(buff_data, skill_def["id"],
                                                                     triggering_army, triggering_army, opponent_army)
        if created_buff:
            an_effect_happened = True
            log_details.append((f"Gains '{EFFECT_NAME_AMAZING_ATTACK_BUFF}' for this round.", None))
    return an_effect_happened, log_details


def handle_talent_blade_wielder(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    if _get_army_round(triggering_army, simulator) != 1:
        return False, []

    cfg = skill_def.get("config", {})
    duration = cfg.get("duration", 59)
    magnitude = cfg.get("magnitude", 1.5)
    buff_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_BLADE_WIELDER_COUNTER_BOOST,
        "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST,
        "magnitude": magnitude,
        "duration": duration,
        "activate_next_round": True,
    }
    created = triggering_army._create_and_add_single_effect(
        buff_data, skill_def["id"], triggering_army, triggering_army, opponent_army
    )
    if created:
        return True, [(
            f"Gains Counterattack Damage Boost: {created.get_functionality_description()} for {duration + 1} rounds (starting next round).",
            None,
        )]
    return False, []


def handle_talent_maniacal(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    cfg = skill_def.get("config", {})
    heal_factor = cfg.get("heal_factor", 0.0)
    heal_duration = cfg.get("heal_duration", 1)
    if heal_factor <= 0:
        return False, []
    hot_data = {
        "effect_type": EffectType.HEAL_OVER_TIME,
        "name": EFFECT_NAME_MANIACAL_HOT,
        "magnitude": heal_factor,
        "duration": heal_duration,
        "activate_next_round": True,
    }
    created = triggering_army._create_and_add_single_effect(
        hot_data, skill_def["id"], triggering_army, triggering_army, opponent_army
    )
    if created:
        return True, [(
            f"Applies {created.get_functionality_description()} for next {heal_duration + 1} round(s).",
            None,
        )]
    return False, []


def handle_talent_pirate_tricks(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    cfg = skill_def.get("config", {})
    shield_factor = cfg.get("shield_factor", 0.0)
    shield_duration = cfg.get("shield_duration", 2)
    if shield_factor <= 0:
        return False, []
    shield_data = {
        "effect_type": EffectType.SHIELD,
        "name": EFFECT_NAME_PIRATE_TRICKS_SHIELD,
        "duration": shield_duration,
        "magnitude_calc_type": "dynamic_shield_resistance_v1",
        "shield_factor": shield_factor,
        "activate_next_round": True,
    }
    created_shield = triggering_army._create_and_add_single_effect(
        shield_data, skill_def["id"], triggering_army, triggering_army, opponent_army
    )
    if created_shield:
        est_mag = simulator._calculate_shield_magnitude_for_logging(
            triggering_army, opponent_army, float(shield_factor)
        ) if simulator else created_shield.magnitude
        return True, [(
            f"Gains Shield ({created_shield.get_functionality_description()}) for {shield_duration + 1} rounds (starting next round).",
            {"shield_hp_gained": round(est_mag)},
        )]
    return False, []


def handle_talent_flexible_strike(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    enemy_is_burning = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BURN
        for eff in opponent_army.active_effects
    )

    if enemy_is_burning:
        damage_factor = cfg.get("damage_factor", 0.0)
        if damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor,
                source_skill_def=skill_def,
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
                happened = True
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append((
                f"Enemy burning: deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills},
            ))
        else:
            logs.append(("Enemy burning but no damage factor configured.", None))
    else:
        heal_factor = cfg.get("heal_factor", 0.0)
        if heal_factor > 0:
            healed = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_def["id"]
            )
            if healed > 0:
                happened = True
                logs.append((f"Enemy not burning: heals for {healed:.0f} HP (Factor: {heal_factor}).", None))
        else:
            logs.append(("Enemy not burning and no heal factor configured.", None))

    return happened, logs


def handle_talent_opportune_strike(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    cfg = skill_def.get("config", {})
    interval = cfg.get("trigger_interval", 6)
    current_round = _get_army_round(triggering_army, simulator)
    if not (current_round > 0 and current_round % interval == 0):
        return False, []

    poison_factor = cfg.get("poison_factor", 0.0)
    poison_duration = cfg.get("poison_duration", 1)
    if poison_factor <= 0:
        return False, []

    poison_data = {
        "effect_type": EffectType.DAMAGE_OVER_TIME,
        "name": EFFECT_NAME_OPPORTUNE_STRIKE_POISON,
        "dot_type": DoTType.POISON,
        "status_effect_factor": poison_factor,
        "duration": poison_duration,
        "activate_next_round": True,
    }
    created_poison = opponent_army._create_and_add_single_effect(
        poison_data, skill_def["id"], triggering_army, opponent_army, triggering_army
    )
    if created_poison:
        return True, [(
            f"Inflicts '{EFFECT_NAME_OPPORTUNE_STRIKE_POISON}' on {opponent_army.name} (Factor: {poison_factor}) "
            f"for {poison_duration + 1} rounds (starting next round).",
            None,
        )]
    return False, []


def handle_talent_thirst_for_blood(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    enemy_bleeding = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BLEED
        for eff in opponent_army.active_effects
    )
    if not enemy_bleeding:
        logs.append((f"Enemy {opponent_army.name} is not bleeding; no healing triggered.", None))
        return False, logs

    heal_factor = cfg.get("heal_factor", 0.0)
    if heal_factor <= 0:
        return False, []

    healed = triggering_army.calculate_and_add_pending_healing(
        heal_factor, triggering_army, opponent_army, source_skill_id=skill_def["id"]
    )
    if healed > 0:
        happened = True
        logs.append((f"Heals for {healed:.0f} HP (Factor: {heal_factor}) because the target is bleeding.", None))
    return happened, logs


def handle_talent_seas_grace(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    happened = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    interval = cfg.get("trigger_interval", 6)
    current_round = _get_army_round(triggering_army, simulator)
    if not (current_round > 0 and current_round % interval == 0):
        return False, []

    # Purify one random debuff from self
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
            "name": EFFECT_NAME_PENDING_SEAS_GRACE_PURIFY,
            "duration": 0,
            "config": {
                "debuff_ids_to_remove": [selected.id],
                "debuff_names_removed_log": [selected.name],
            },
            "activate_next_round": True,
        }
        created_cleanse = triggering_army._create_and_add_single_effect(
            pending_cleanse, skill_def["id"], triggering_army, triggering_army, opponent_army
        )
        if created_cleanse:
            happened = True
            logs.append((f"Purifies '{selected.name}' next round.", None))
    else:
        logs.append(("No debuffs to purify.", None))

    # Apply random effect to the enemy
    apply_bleed = random.random() < 0.5
    if apply_bleed:
        bleed_factor = cfg.get("bleed_factor", 0.0)
        bleed_duration = cfg.get("bleed_duration", 1)
        if bleed_factor > 0:
            bleed_data = {
                "effect_type": EffectType.DAMAGE_OVER_TIME,
                "name": EFFECT_NAME_SEAS_GRACE_BLEED,
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
                logs.append((
                    f"Random effect: applies '{EFFECT_NAME_SEAS_GRACE_BLEED}' (Factor: {bleed_factor}) for {bleed_duration + 1} rounds (starting next round).",
                    None,
                ))
    else:
        slow_duration = cfg.get("slow_duration", 1)
        if slow_duration > 0:
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
                logs.append((
                    f"Random effect: applies '{EFFECT_NAME_SLOW_DEBUFF}' for {slow_duration + 1} rounds (starting next round).",
                    None,
                ))

    return happened, logs
