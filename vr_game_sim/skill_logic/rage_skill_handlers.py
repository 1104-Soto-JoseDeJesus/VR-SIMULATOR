from typing import Tuple, List, Optional, Dict, Any
import random
from math import atan2, degrees, hypot

from ..enums import EffectType, StatType, SkillTriggerType, DoTType
from ..skill_system import SkillDefinition, ArmyRef, GameSimulatorRef
from ..effect_system import EffectInstance
from ..constants import *


def _get_army_round(army: ArmyRef, simulator: GameSimulatorRef) -> int:
    """Return the round counter for ``army`` with a simulator fallback."""
    if hasattr(army, "army_round"):
        return army.army_round
    return simulator.round if simulator else 0


def _count_effects_by_name(army: ArmyRef, effect_name: str) -> int:
    return sum(1 for eff in army.active_effects if eff.name == effect_name)


def handle_rage_sharp_pursuit(army: ArmyRef, opp: ArmyRef, sk_def: SkillDefinition, ev_data: Dict[str, Any],
                              sim: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    eff_hpnd, logs, dmg_dealt_flag = False, [], False;
    is_h2_delay = ev_data.get("is_hero2_delayed_rage", False);
    sk_cfg = sk_def.get("config", {});
    sk_id = sk_def["id"]
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0:
        hp_dmg, absrb, kills, raw_log_dmg, calc_steps = sim._calculate_generic_skill_damage(army, opp, dmg_fctr,
                                                                                is_hero2_rage_skill=is_h2_delay,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0:
            eff_hpnd = True
            dmg_dealt_flag = True
        logs.append((f"Deals damage to {opp.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills, "calculation_steps": calc_steps}))
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
        hp_dmg, absrb, kills, raw_dmg, calc_steps = sim._calculate_generic_skill_damage(army, opp, dmg_fctr,
                                                                           is_hero2_rage_skill=is_h2_delay,
                                                                           source_skill_def=sk_def)
        if hp_dmg > 0: opp.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0:
            eff_hpnd = True
            dmg_dealt_flag = True
        logs.append((f"Deals damage to {opp.name}.",
                     {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absrb), "potential_kills": kills, "calculation_steps": calc_steps}))
        if sim.mode in ("battlefield", "arena"):
            engine = getattr(sim, "parent_engine", None)
            if engine:
                attackers = engine.get_direct_attackers(army.name)
                extras = [e for e in attackers if e.name != opp.name]
                if len(extras) > 2:
                    extras = random.sample(extras, 2)
                for other in extras:
                    hp_dmg2, absrb2, kills2, raw_dmg2, calc_steps2 = sim._calculate_generic_skill_damage(
                        army, other, dmg_fctr,
                        is_hero2_rage_skill=is_h2_delay,
                        source_skill_def=sk_def)
                    if hp_dmg2 > 0: other.pending_hp_damage_this_round += hp_dmg2
                    if hp_dmg2 > 0 or absrb2 > 0:
                        eff_hpnd = True
                        dmg_dealt_flag = True
                    logs.append((f"Deals damage to {other.name}.",
                                 {"damage_done_hp": round(raw_dmg2), "absorbed_hp": round(absrb2), "potential_kills": kills2, "calculation_steps": calc_steps2}))
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
        healed_amount = army.calculate_and_add_pending_healing(
            heal_fctr, army, opp, source_skill_id=sk_id
        )
        if healed_amount > 0:
            eff_hpnd = True
            logs.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_fctr}).", None))
        if sim.mode in ("battlefield", "arena"):
            engine = getattr(sim, "parent_engine", None)
            if engine:
                ctx_self = engine._armies.get(army.name)
                if ctx_self:
                    sx, sy = ctx_self.position
                    team = ctx_self.team
                    allies: List[ArmyRef] = []
                    for name, ctx in engine._armies.items():
                        if ctx.team == team and name != army.name:
                            ax, ay = ctx.position
                            # Increase healing radius to 200 units to extend support range
                            if hypot(ax - sx, ay - sy) <= 200:
                                allies.append(ctx.army)
                    if len(allies) > 4:
                        allies = random.sample(allies, 4)
                    for ally in allies:
                        healed_other = ally.calculate_and_add_pending_healing(
                            heal_fctr, army, opp, source_skill_id=sk_id
                        )
                        if healed_other > 0:
                            eff_hpnd = True
                            logs.append((f"Heals {ally.name} for {healed_other:.0f} HP (Factor: {heal_fctr}).", None))
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
        healed_amount = army.calculate_and_add_pending_healing(
            heal_fctr_vb, army, opp, source_skill_id=sk_id
        )
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
        hp_dmg, absrb, kills, raw_log_dmg, calc_steps = sim._calculate_generic_skill_damage(army, opp, dmg_fctr_vb,
                                                                                is_hero2_rage_skill=is_h2_delay,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0:
            eff_hpnd = True
            dmg_dealt_flag = True
        logs.append((f"Deals damage to {opp.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills, "calculation_steps": calc_steps}))
    return eff_hpnd, logs, dmg_dealt_flag


def handle_generic_damage_rage_skill(army: ArmyRef, opp: ArmyRef, sk_def: SkillDefinition, ev_data: Dict[str, Any],
                                     sim: GameSimulatorRef) -> Tuple[
    bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    eff_hpnd, logs, dmg_dealt_flag = False, [], False;
    is_h2_delay = ev_data.get("is_hero2_delayed_rage", False);
    sk_cfg = sk_def.get("config", {});
    dmg_fctr = sk_cfg.get("damage_factor", 0.0)
    if dmg_fctr > 0:
        hp_dmg, absrb, kills, raw_log_dmg, calc_steps = sim._calculate_generic_skill_damage(army, opp, dmg_fctr,
                                                                                is_hero2_rage_skill=is_h2_delay,
                                                                                source_skill_def=sk_def)
        if hp_dmg > 0: opp.pending_hp_damage_this_round += hp_dmg
        if hp_dmg > 0 or absrb > 0:
            eff_hpnd = True
            dmg_dealt_flag = True
        logs.append((f"Deals damage to {opp.name}.",
                     {"damage_done_hp": round(raw_log_dmg), "absorbed_hp": round(absrb), "potential_kills": kills, "calculation_steps": calc_steps}))
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
        ))
        if simulator.mode in ("battlefield", "arena"):
            engine = getattr(simulator, "parent_engine", None)
            if engine:
                attackers = engine.get_direct_attackers(triggering_army.name)
                candidates = [e for e in attackers if e.name != opponent_army.name]
                ctx_self = engine._armies.get(triggering_army.name)
                ctx_direct = engine._armies.get(opponent_army.name)
                if ctx_self and ctx_direct:
                    hx, hy = ctx_self.position
                    dx, dy = ctx_direct.position
                    direct_ang = degrees(atan2(dy - hy, dx - hx))
                    filtered: List[ArmyRef] = []
                    for other in candidates:
                        ctx_o = engine._armies.get(other.name)
                        if not ctx_o:
                            continue
                        ox, oy = ctx_o.position
                        ang = degrees(atan2(oy - hy, ox - hx))
                        diff = abs((ang - direct_ang + 180) % 360 - 180)
                        if diff <= 60:
                            filtered.append(other)
                    if len(filtered) > 2:
                        filtered = random.sample(filtered, 2)
                    for other in filtered:
                        hp_dmg2, absorbed2, kills2, raw2, calc_steps2 = simulator._calculate_generic_skill_damage(
                            triggering_army, other, damage_factor,
                            is_hero2_rage_skill=is_hero2_delayed_rage,
                            source_skill_def=skill_def
                        )
                        if hp_dmg2 > 0:
                            other.pending_hp_damage_this_round += hp_dmg2
                        if hp_dmg2 > 0 or absorbed2 > 0:
                            damage_dealt_flag = True
                        if hp_dmg2 > 0 or absorbed2 > 0:
                            an_effect_happened = True
                        log_details.append(
                            (
                                f"Deals damage (Factor: {damage_factor}) to {other.name}.",
                                {"damage_done_hp": round(raw2), "absorbed_hp": round(absorbed2), "potential_kills": kills2, "calculation_steps": calc_steps2}
                            )
                        )

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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor_hit1,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Hit 1 deals damage (Factor: {damage_factor_hit1}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
        ))

    damage_factor_hit2 = skill_config.get("damage_factor_hit2", 0.0)
    if damage_factor_hit2 > 0 and opponent_army.current_troop_count > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor_hit2,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Hit 2 deals damage (Factor: {damage_factor_hit2}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
        ))

    rage_reduction = skill_config.get("rage_reduction", 0)
    if rage_reduction > 0 and opponent_army.current_rage > 0:
        actual_reduction = min(opponent_army.current_rage, float(rage_reduction))
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
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
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}
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
        "effect_applied_in_round": _get_army_round(triggering_army, simulator)  # Store the round Concentration was cast
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
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
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps})
        )

        if simulator.mode in ("battlefield", "arena"):
            engine = getattr(simulator, "parent_engine", None)
            if engine:
                attackers = engine.get_direct_attackers(triggering_army.name)
                extras = [e for e in attackers if e.name != opponent_army.name]
                if len(extras) > 2:
                    extras = random.sample(extras, 2)
                for other in extras:
                    hp_dmg2, absorbed2, kills2, raw2, calc_steps2 = simulator._calculate_generic_skill_damage(
                        triggering_army, other, damage_factor,
                        is_hero2_rage_skill=is_hero2_delayed_rage,
                        source_skill_def=skill_def
                    )
                    if hp_dmg2 > 0:
                        other.pending_hp_damage_this_round += hp_dmg2
                    if hp_dmg2 > 0 or absorbed2 > 0:
                        damage_dealt_flag = True
                    if hp_dmg2 > 0 or absorbed2 > 0:
                        an_effect_happened = True
                    log_details.append(
                        (f"Deals damage (Factor: {damage_factor}) to {other.name}.",
                         {"damage_done_hp": round(raw2), "absorbed_hp": round(absorbed2), "potential_kills": kills2, "calculation_steps": calc_steps2})
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
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
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
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


def handle_rage_serrated_flourish(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    damage_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    is_hero2 = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = cfg.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2,
            source_skill_def=skill_def,
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
        ))

        if random.random() < cfg.get("poison_chance", 0.0):
            poison_factor = cfg.get("poison_factor", 0.0)
            poison_duration = cfg.get("poison_duration", 1)
            if poison_factor > 0:
                poison_data = {
                    "effect_type": EffectType.DAMAGE_OVER_TIME,
                    "name": EFFECT_NAME_SERRATED_FLOURISH_POISON,
                    "dot_type": DoTType.POISON,
                    "status_effect_factor": poison_factor,
                    "duration": poison_duration,
                    "activate_next_round": True,
                }
                created_poison = opponent_army._create_and_add_single_effect(
                    poison_data, skill_def["id"], triggering_army, opponent_army, triggering_army
                )
                if created_poison:
                    happened = True
                    logs.append((
                        f"Inflicts '{EFFECT_NAME_SERRATED_FLOURISH_POISON}' on {opponent_army.name} (Factor: {poison_factor}) "
                        f"for {poison_duration + 1} rounds (starting next round).",
                        None,
                    ))
        else:
            logs.append((f"Poison chance ({cfg.get('poison_chance', 0.0) * 100:.0f}%) not met.", None))

    extra_chance = cfg.get("extra_damage_chance", 0.0)
    extra_damage_factor = cfg.get("extra_damage_factor", 0.0)
    if extra_damage_factor > 0 and random.random() < extra_chance:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, extra_damage_factor,
            is_hero2_rage_skill=is_hero2,
            source_skill_def=skill_def,
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((
            f"Deals additional damage (Factor: {extra_damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
        ))
    elif extra_damage_factor > 0:
        logs.append((f"Follow-up damage chance ({extra_chance * 100:.0f}%) not met.", None))

    return happened, logs, damage_flag


# --- Greta Rage Skill Handler ---
def handle_rage_time_of_severance(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    damage_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    damage_factor = cfg.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army,
            opponent_army,
            damage_factor,
            is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False),
            source_skill_def=skill_def,
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    if triggering_army.current_troop_count > opponent_army.current_troop_count:
        bleed_factor = cfg.get("bleed_factor", 0.0)
        bleed_duration = cfg.get("bleed_duration", 1)
        if bleed_factor > 0:
            bleed_data = {
                "effect_type": EffectType.DAMAGE_OVER_TIME,
                "name": EFFECT_NAME_TIME_OF_SEVERANCE_BLEED,
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
                damage_flag = True
                logs.append(
                    (
                        f"Inflicts '{EFFECT_NAME_TIME_OF_SEVERANCE_BLEED}' on {opponent_army.name} (Factor: {bleed_factor}) "
                        f"for {bleed_duration + 1} rounds (starting next round).",
                        None,
                    )
                )
    elif triggering_army.current_troop_count < opponent_army.current_troop_count:
        retribution_rate = cfg.get("retribution_rate", 0.0)
        retribution_duration = cfg.get("retribution_duration", 1)
        if retribution_rate > 0:
            retribution_effect = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_TIME_OF_SEVERANCE_RETRIBUTION,
                "duration": retribution_duration,
                "activate_next_round": True,
                "config": {"retribution_rate": retribution_rate, "is_dispellable": True},
            }
            if triggering_army._create_and_add_single_effect(
                retribution_effect, skill_def["id"], triggering_army, triggering_army, opponent_army
            ):
                happened = True
                logs.append(
                    (
                        f"Gains retribution ({retribution_rate * 100:.0f}%) for {retribution_duration + 1} rounds (starting next round).",
                        None,
                    )
                )

    if any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects):
        extra_damage_factor = cfg.get("slow_damage_factor", 0.0)
        if extra_damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army,
                opponent_army,
                extra_damage_factor,
                is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False),
                source_skill_def=skill_def,
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
                damage_flag = True
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append(
                (
                    f"Deals additional damage (Factor: {extra_damage_factor}) to {opponent_army.name} because they are slowed.",
                    {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
                )
            )

    return happened, logs, damage_flag


# --- Sigrid Rage Skill Handler ---
def handle_rage_triumphant_presence(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    damage_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})

    damage_factor = cfg.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army,
            opponent_army,
            damage_factor,
            is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False),
            source_skill_def=skill_def,
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    retribution_rate = cfg.get("retribution_rate", 0.0)
    retribution_duration = cfg.get("retribution_duration", 1)
    if retribution_rate > 0:
        retribution_effect = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_TRIUMPHANT_PRESENCE_RETRIBUTION,
            "duration": retribution_duration,
            "activate_next_round": True,
            "config": {"retribution_rate": retribution_rate, "is_dispellable": True},
        }
        if triggering_army._create_and_add_single_effect(
            retribution_effect, skill_def["id"], triggering_army, triggering_army, opponent_army
        ):
            happened = True
            logs.append(
                (
                    f"Gains retribution ({retribution_rate * 100:.0f}%) for {retribution_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    if any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BLEED
        for eff in opponent_army.active_effects
    ):
        heal_factor = cfg.get("bleed_heal_factor", 0.0)
        if heal_factor > 0:
            healed = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_def["id"]
            )
            if healed > 0:
                happened = True
                logs.append((f"Heals for {healed:.0f} HP (Factor: {heal_factor}) because the enemy is bleeding.", None))

    if any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects):
        extra_damage = cfg.get("slow_damage_factor", 0.0)
        if extra_damage > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army,
                opponent_army,
                extra_damage,
                is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False),
                source_skill_def=skill_def,
            )
            if hp_damage > 0:
                opponent_army.pending_hp_damage_this_round += hp_damage
                damage_flag = True
            if hp_damage > 0 or absorbed > 0:
                happened = True
            logs.append(
                (
                    f"Deals additional damage (Factor: {extra_damage}) to {opponent_army.name} because they are slowed.",
                    {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
                )
            )

    return happened, logs, damage_flag


def handle_rage_raging_tide(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    damage_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    is_hero2 = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = cfg.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2,
            source_skill_def=skill_def,
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
        ))

    bleed_factor = cfg.get("bleed_factor", 0.0)
    bleed_duration = cfg.get("bleed_duration", 1)
    if bleed_factor > 0:
        bleed_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_RAGING_TIDE_BLEED,
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
            damage_flag = True
            logs.append((
                f"Inflicts '{EFFECT_NAME_RAGING_TIDE_BLEED}' on {opponent_army.name} (Factor: {bleed_factor}) "
                f"for {bleed_duration + 1} rounds (starting next round).",
                None,
            ))

    slow_duration = cfg.get("slow_duration", 0)
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
                f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_duration + 1} rounds (starting next round).",
                None,
            ))

    return happened, logs, damage_flag


def handle_rage_spirit_battleship(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    cfg = skill_def.get("config", {})
    skill_id = skill_def["id"]
    dmg_factor = cfg.get("damage_factor", 0.0)
    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    def_red_mag = cfg.get("def_reduction_magnitude", -0.30)
    def_red_dur = cfg.get("def_reduction_duration", 3)
    if def_red_mag != 0:
        debuff_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_SPIRIT_BATTLESHIP_DEF_REDUCTION,
            "stat_to_mod": StatType.BASE_DEFENSE_MULTIPLIER,
            "magnitude": def_red_mag,
            "duration": def_red_dur,
            "activate_next_round": True,
        }
        created_debuff = opponent_army._create_and_add_single_effect(
            debuff_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_SPIRIT_BATTLESHIP_DEF_REDUCTION}' on {opponent_army.name} for {def_red_dur + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details, damage_dealt_flag


# --- Ivor Rage Skill Handler ---
def handle_rage_slaughter_feast(triggering_army: ArmyRef, opponent_army: ArmyRef,
                                skill_def: SkillDefinition, event_data: Dict[str, Any],
                                simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False
    cfg = skill_def.get("config", {})
    dmg_factor = cfg.get("damage_factor", 0.0)

    if dmg_factor > 0:
        is_h2_delay = event_data.get("is_hero2_delayed_rage", False)
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor,
            is_hero2_rage_skill=is_h2_delay,
            source_skill_def=skill_def)
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                           {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed),
                            "potential_kills": kills, "calculation_steps": calc_steps}))

        if simulator.mode in ("battlefield", "arena"):
            engine = getattr(simulator, "parent_engine", None)
            if engine:
                attackers = engine.get_direct_attackers(triggering_army.name)
                candidates = [e for e in attackers if e.name != opponent_army.name]
                ctx_self = engine._armies.get(triggering_army.name)
                ctx_direct = engine._armies.get(opponent_army.name)
                if ctx_self and ctx_direct:
                    hx, hy = ctx_self.position
                    dx, dy = ctx_direct.position
                    direct_ang = degrees(atan2(dy - hy, dx - hx))
                    filtered: List[ArmyRef] = []
                    for other in candidates:
                        ctx_o = engine._armies.get(other.name)
                        if not ctx_o:
                            continue
                        ox, oy = ctx_o.position
                        ang = degrees(atan2(oy - hy, ox - hx))
                        diff = abs((ang - direct_ang + 180) % 360 - 180)
                        if diff <= 60:
                            filtered.append(other)
                    if len(filtered) > 2:
                        filtered = random.sample(filtered, 2)
                    for other in filtered:
                        hp_dmg2, absorbed2, kills2, raw2, calc_steps2 = simulator._calculate_generic_skill_damage(
                            triggering_army, other, dmg_factor,
                            is_hero2_rage_skill=is_h2_delay,
                            source_skill_def=skill_def
                        )
                        if hp_dmg2 > 0:
                            other.pending_hp_damage_this_round += hp_dmg2
                        if hp_dmg2 > 0 or absorbed2 > 0:
                            damage_dealt_flag = True
                        if hp_dmg2 > 0 or absorbed2 > 0:
                            an_effect_happened = True
                        log_details.append(
                            (
                                f"Deals damage (Factor: {dmg_factor}) to {other.name}.",
                                {"damage_done_hp": round(raw2), "absorbed_hp": round(absorbed2), "potential_kills": kills2, "calculation_steps": calc_steps2}
                            )
                        )

    atk_buff = cfg.get("attack_buff", 0.0)
    atk_dur = cfg.get("attack_duration", 2)
    if atk_buff != 0:
        buff_data = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SLAUGHTER_FEAST_ATTACK_BUFF,
                     "stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER, "magnitude": atk_buff,
                     "duration": atk_dur, "activate_next_round": True}
        created_buff = triggering_army._create_and_add_single_effect(buff_data, skill_def["id"],
                                                                    triggering_army, triggering_army, opponent_army)
        if created_buff:
            an_effect_happened = True
            log_details.append((f"Gains '{EFFECT_NAME_SLAUGHTER_FEAST_ATTACK_BUFF}' for {atk_dur + 1} rounds (starting next round).",
                               None))

    return an_effect_happened, log_details, damage_dealt_flag


# --- Yulmi Rage Skill Handler ---
def handle_rage_undead_harvest(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any], simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    damage_dealt_flag = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    damage_factor = cfg.get("damage_factor", 0.0)
    debuff_magnitude = cfg.get("debuff_magnitude", 0.0)
    debuff_duration = cfg.get("debuff_duration", 1)

    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=event_data.get("is_hero2_delayed_rage", False),
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps})
        )

    if debuff_magnitude != 0:
        debuff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_UNDEAD_HARVEST_HP_REDUCTION,
            "stat_to_mod": StatType.BASE_HP_MULTIPLIER,
            "magnitude": debuff_magnitude,
            "duration": debuff_duration,
            "activate_next_round": True,
        }
        created_debuff = opponent_army._create_and_add_single_effect(
            debuff_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
            log_details.append(
                (f"Reduces {opponent_army.name}'s HP by {abs(debuff_magnitude) * 100:.0f}% for {debuff_duration + 1} rounds.", None)
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

    if simulator.mode in ("battlefield", "arena"):
        engine = getattr(simulator, "parent_engine", None)
        if engine:
            ctx_self = engine._armies.get(triggering_army.name)
            if ctx_self:
                sx, sy = ctx_self.position
                team = ctx_self.team
                allies: List[ArmyRef] = []
                for name, ctx in engine._armies.items():
                    if ctx.team == team and name != triggering_army.name:
                        ax, ay = ctx.position
                        if hypot(ax - sx, ay - sy) <= 150:
                            allies.append(ctx.army)
                if len(allies) > 5:
                    allies = random.sample(allies, 5)
                buff_mag = skill_config.get("ally_buff_magnitude", 0.5)
                buff_dur = skill_config.get("ally_buff_duration", 2)
                for ally in allies:
                    buff_data = {
                        "effect_type": EffectType.STAT_MOD,
                        "name": EFFECT_NAME_INSPIRING_DANCE_BASIC_BUFF,
                        "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
                        "magnitude": buff_mag,
                        "duration": buff_dur,
                        "activate_next_round": True,
                    }
                    created_buff = ally._create_and_add_single_effect(
                        buff_data, skill_id, triggering_army, ally, opponent_army
                    )
                    if created_buff:
                        an_effect_happened = True
                        log_details.append(
                            (f"Grants {ally.name} Buff: {created_buff.get_functionality_description()} for {buff_dur + 1} round(s) (starting next round).",
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps})
        )
        if simulator.mode in ("battlefield", "arena"):
            engine = getattr(simulator, "parent_engine", None)
            if engine:
                ctx_self = engine._armies.get(triggering_army.name)
                if ctx_self:
                    sx, sy = ctx_self.position
                    team_self = ctx_self.team
                    extras: List[ArmyRef] = []
                    for name, ctx in engine._armies.items():
                        if (
                            ctx.team != team_self
                            and name != opponent_army.name
                            and ctx.direct_target == triggering_army.name
                        ):
                            ex, ey = ctx.position
                            if hypot(ex - sx, ey - sy) <= 150:
                                extras.append(ctx.army)
                    if len(extras) > 4:
                        extras = random.sample(extras, 4)
                    for extra in extras:
                        hp2, abs2, kills2, raw2, calc_steps2 = simulator._calculate_generic_skill_damage(
                            triggering_army, extra, damage_factor,
                            is_hero2_rage_skill=is_hero2_delayed_rage,
                            source_skill_def=skill_def
                        )
                        if hp2 > 0:
                            extra.pending_hp_damage_this_round += hp2
                            damage_dealt_flag = True
                        if hp2 > 0 or abs2 > 0:
                            an_effect_happened = True
                        log_details.append(
                            (f"Deals damage (Factor: {damage_factor}) to {extra.name}.",
                             {"damage_done_hp": round(raw2), "absorbed_hp": round(abs2), "potential_kills": kills2, "calculation_steps": calc_steps2})
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


# --- Helgar Rage Skill Handler ---
def handle_rage_ruling_trial(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    cfg = skill_def.get("config", {})
    skill_id = skill_def["id"]
    is_hero2_delayed_rage = event_data.get("is_hero2_delayed_rage", False)

    base_factor = cfg.get("damage_factor", 0.0)
    high_factor = cfg.get("low_hp_damage_factor", base_factor)
    extra_factor = cfg.get("extra_damage_factor", 0.0)
    threshold = cfg.get("hp_threshold", 0.2)

    enemy_ratio = opponent_army.current_troop_count / max(1.0, opponent_army.unit.initial_count)
    dmg_factor = high_factor if enemy_ratio < threshold else base_factor

    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                           {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))

    marker_count = sum(1 for eff in triggering_army.active_effects if eff.name == EFFECT_NAME_JUDGEMENT_MARKER)
    if marker_count > 5 and extra_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, extra_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append((f"Deals extra damage (Factor: {extra_factor}) to {opponent_army.name}.",
                           {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps}))

    # Apply base damage to up to three other direct attackers in battlefield/arena modes
    if simulator.mode in ("battlefield", "arena") and base_factor > 0:
        engine = getattr(simulator, "parent_engine", None)
        if engine:
            attackers = engine.get_direct_attackers(triggering_army.name)
            extras = [e for e in attackers if e.name != opponent_army.name]
            if len(extras) > 3:
                extras = random.sample(extras, 3)
            for other in extras:
                hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                    triggering_army, other, base_factor,
                    is_hero2_rage_skill=is_hero2_delayed_rage,
                    source_skill_def=skill_def,
                )
                if hp_damage > 0:
                    other.pending_hp_damage_this_round += hp_damage
                    damage_dealt_flag = True
                if hp_damage > 0 or absorbed > 0:
                    an_effect_happened = True
                log_details.append((f"Deals damage (Factor: {base_factor}) to {other.name}.",
                                   {"damage_done_hp": round(raw_logged_damage),
                                    "absorbed_hp": round(absorbed),
                                    "potential_kills": kills, "calculation_steps": calc_steps}))

    return an_effect_happened, log_details, damage_dealt_flag


# --- Lagertha Rage Skill Handler ---
def handle_rage_showdown(
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
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            is_hero2_rage_skill=is_hero2_delayed_rage,
            source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    bleed_factor = skill_config.get("bleed_factor", 0.0)
    bleed_duration = skill_config.get("bleed_duration", 2)
    if bleed_factor > 0:
        bleed_effect_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_SHOWDOWN_BLEED,
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
            damage_dealt_flag = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_SHOWDOWN_BLEED}' on {opponent_army.name} (Factor: {bleed_factor}) for {bleed_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    shield_factor = skill_config.get("shield_factor", 0.0)
    shield_duration = skill_config.get("shield_duration", 2)
    if shield_factor > 0:
        shield_effect_data = {
            "effect_type": EffectType.SHIELD,
            "name": EFFECT_NAME_SHOWDOWN_SHIELD,
            "duration": shield_duration,
            "magnitude_calc_type": "dynamic_shield_resistance_v1",
            "shield_factor": shield_factor,
            "activate_next_round": True,
        }
        created_shield = triggering_army._create_and_add_single_effect(
            shield_effect_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_shield:
            an_effect_happened = True
            est_mag = simulator._calculate_shield_magnitude_for_logging(triggering_army, opponent_army, float(shield_factor)) if simulator else created_shield.magnitude
            log_details.append(
                (
                    f"Gains '{EFFECT_NAME_SHOWDOWN_SHIELD}' ({created_shield.get_functionality_description()}), active for {created_shield.duration + 1} rounds. Est. Mag: {est_mag:.0f}",
                    {"shield_hp_gained": round(est_mag)},
                )
            )

    return an_effect_happened, log_details, damage_dealt_flag


def handle_rage_blizzard_spear(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            damage_dealt_flag = True
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
            )
        )

    broken_blade_active = any(
        eff.name == EFFECT_NAME_BROKEN_BLADE_DEBUFF for eff in opponent_army.active_effects
    )
    shield_factor = (
        skill_config.get("boosted_shield_factor", 0.0)
        if broken_blade_active
        else skill_config.get("shield_factor", 0.0)
    )
    shield_duration = skill_config.get("shield_duration", 1)
    if shield_factor > 0:
        shield_effect_data = {
            "effect_type": EffectType.SHIELD,
            "name": EFFECT_NAME_BLIZZARD_SPEAR_SHIELD,
            "duration": shield_duration,
            "magnitude_calc_type": "dynamic_shield_resistance_v1",
            "shield_factor": shield_factor,
            "activate_next_round": True,
        }
        created_shield = triggering_army._create_and_add_single_effect(
            shield_effect_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_shield:
            an_effect_happened = True
            est_mag = (
                simulator._calculate_shield_magnitude_for_logging(triggering_army, opponent_army, float(shield_factor))
                if simulator
                else created_shield.magnitude
            )
            log_details.append(
                (
                    f"Gains '{EFFECT_NAME_BLIZZARD_SPEAR_SHIELD}' ({created_shield.get_functionality_description()}), active for {created_shield.duration + 1} rounds. Est. Mag: {est_mag:.0f}",
                    {"shield_hp_gained": round(est_mag)},
                )
            )

    return an_effect_happened, log_details, damage_dealt_flag


def handle_rage_indomitable_spirit(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    damage_dealt_flag = False

    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    potential_targets = [opponent_army]
    additional_targets = event_data.get("additional_targets") or []
    for extra in additional_targets:
        if extra and extra not in potential_targets and extra.current_troop_count > 0:
            potential_targets.append(extra)

    for target in potential_targets:
        if not target or target.current_troop_count <= 0:
            continue
        below_half_troops = target.current_troop_count < (0.5 * float(target.unit.initial_count))
        damage_factor = (
            skill_config.get("boosted_damage_factor", 0.0) if below_half_troops else skill_config.get("damage_factor", 0.0)
        )
        if damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
                triggering_army, target, damage_factor, source_skill_def=skill_def
            )
            if hp_damage > 0:
                target.pending_hp_damage_this_round += hp_damage
            if hp_damage > 0 or absorbed > 0:
                damage_dealt_flag = True
                an_effect_happened = True
            log_details.append(
                (
                    f"Deals damage (Factor: {damage_factor}) to {target.name}.",
                    {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
                )
            )

        debuff_duration = skill_config.get("debuff_duration", 1)
        debuff_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_BROKEN_BLADE_DEBUFF,
            "duration": debuff_duration,
            "config": {"prevents_counterattack": True},
            "activate_next_round": True,
        }
        created_debuff = target._create_and_add_single_effect(
            debuff_data, skill_id, triggering_army, target, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_BROKEN_BLADE_DEBUFF}' on {target.name} for {created_debuff.duration + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details, damage_dealt_flag


# --- Alf Rage Skill Handler ---
def handle_rage_chain_meteor(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    damage_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    is_hero2 = event_data.get("is_hero2_delayed_rage", False)

    damage_factor = cfg.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor, is_hero2_rage_skill=is_hero2, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
        ))

    if random.random() < cfg.get("burn_chance", 0.0):
        burn_factor = cfg.get("burn_factor", 0.0)
        burn_duration = cfg.get("burn_duration", 2)
        if burn_factor > 0:
            burn_effect = {
                "effect_type": EffectType.DAMAGE_OVER_TIME,
                "name": EFFECT_NAME_CHAIN_METEOR_BURN,
                "dot_type": DoTType.BURN,
                "status_effect_factor": burn_factor,
                "duration": burn_duration,
                "activate_next_round": True,
            }
            created_burn = opponent_army._create_and_add_single_effect(
                burn_effect, skill_def["id"], triggering_army, opponent_army, triggering_army
            )
            if created_burn:
                happened = True
                logs.append((
                    f"Inflicts '{EFFECT_NAME_CHAIN_METEOR_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                    None,
                ))

    if random.random() < cfg.get("poison_chance", 0.0):
        poison_factor = cfg.get("poison_factor", 0.0)
        poison_duration = cfg.get("poison_duration", 2)
        if poison_factor > 0:
            poison_effect = {
                "effect_type": EffectType.DAMAGE_OVER_TIME,
                "name": EFFECT_NAME_CHAIN_METEOR_POISON,
                "dot_type": DoTType.POISON,
                "status_effect_factor": poison_factor,
                "duration": poison_duration,
                "activate_next_round": True,
            }
            created_poison = opponent_army._create_and_add_single_effect(
                poison_effect, skill_def["id"], triggering_army, opponent_army, triggering_army
            )
            if created_poison:
                happened = True
                logs.append((
                    f"Inflicts '{EFFECT_NAME_CHAIN_METEOR_POISON}' on {opponent_army.name} (Factor: {poison_factor}) for {poison_duration + 1} rounds (starting next round).",
                    None,
                ))

    return happened, logs, damage_flag


# --- Sasha Rage Skill Handler ---
def handle_rage_floral_burial(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Dict[str, Any],
        simulator: GameSimulatorRef) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]:
    happened = False
    damage_flag = False
    logs: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    is_hero2 = event_data.get("is_hero2_delayed_rage", False)

    poison_factor = cfg.get("poison_factor", 0.0)
    poison_duration = cfg.get("poison_duration", 2)
    if poison_factor > 0:
        poison_effect = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_FLORAL_BURIAL_POISON,
            "dot_type": DoTType.POISON,
            "status_effect_factor": poison_factor,
            "duration": poison_duration,
            "activate_next_round": True,
        }
        created_poison = opponent_army._create_and_add_single_effect(
            poison_effect, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_poison:
            happened = True
            logs.append((
                f"Inflicts '{EFFECT_NAME_FLORAL_BURIAL_POISON}' on {opponent_army.name} (Factor: {poison_factor}) for {poison_duration + 1} rounds (starting next round).",
                None,
            ))

    current_marks = _count_effects_by_name(triggering_army, EFFECT_NAME_NATURE_MARK)
    damage_factor = cfg.get("damage_factor", 0.0) if current_marks >= cfg.get("damage_threshold", 5) else 0.0
    heal_conversion = cfg.get("heal_conversion", 0.5) if current_marks >= cfg.get("heal_threshold", 10) else 0.0

    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage, calc_steps = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor, is_hero2_rage_skill=is_hero2, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
            damage_flag = True
        if hp_damage > 0 or absorbed > 0:
            happened = True
        logs.append((
            f"Deals Floral Burial damage to {opponent_army.name} (Factor: {damage_factor}).",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills, "calculation_steps": calc_steps},
        ))

        if heal_conversion > 0 and hp_damage > 0:
            heal_amount = hp_damage * heal_conversion
            triggering_army.pending_hp_healing_this_round += heal_amount
            healer_name = getattr(triggering_army, "name", None) or ""
            skill_map = triggering_army.heal_contributors_this_round.setdefault(
                healer_name, {}
            )
            skill_map[skill_def.get("id", "")] = skill_map.get(
                skill_def.get("id", ""), 0.0
            ) + heal_amount
            happened = True
            logs.append((
                f"Converts {heal_conversion * 100:.0f}% of damage into healing ({heal_amount:.0f} HP).",
                None,
            ))

    return happened, logs, damage_flag

