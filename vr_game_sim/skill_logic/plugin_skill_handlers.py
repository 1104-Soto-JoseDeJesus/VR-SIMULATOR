# === File: skill_logic/plugin_skill_handlers.py ===
import random
import uuid
from typing import Tuple, List, Optional, Dict, Any

from ..enums import EffectType, StatType, SkillTriggerType, DoTType
from ..effect_system import EffectInstance
from ..skill_system import SkillDefinition, ArmyRef, GameSimulatorRef
from ..constants import *
from .utility_skill_handlers import handle_generic_single_damage_skill


def _get_army_round(army: ArmyRef, simulator: GameSimulatorRef) -> int:
    """Return the round counter for ``army``.

    Falls back to ``simulator.round`` when an army specific counter is not
    available so the handlers continue to function in stand‑alone simulator
    mode (or ``0`` when no simulator is supplied)."""
    if hasattr(army, "army_round"):
        return army.army_round
    return simulator.round if simulator else 0


def handle_plugin_divine_blessing(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    effect_name = skill_config.get("effect_name", EFFECT_NAME_DIVINE_BLESSING_REDUCTION)
    reduction_magnitude = skill_config.get("reduction_magnitude", -0.30)

    is_any_version_active = any(
        eff.name == effect_name and eff.source_skill_id == skill_id
        for eff_list in [triggering_army.active_effects, triggering_army.upcoming_effects,
                         triggering_army.effects_to_activate_next_round]
        for eff in eff_list
    )

    if _get_army_round(triggering_army, simulator) == 2 and not is_any_version_active:
        initial_duration = skill_config.get("initial_effect_duration", 28)
        effect_data = {"effect_type": EffectType.STAT_MOD, "name": effect_name,
                       "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER,
                       "magnitude": reduction_magnitude, "duration": initial_duration,
                       "activate_next_round": False}
        created_effect = triggering_army._create_and_add_single_effect(
            effect_data, skill_id, triggering_army, triggering_army, opponent_army)
        if created_effect:
            an_effect_happened = True
            log_details.append(
                (f"Initial effect applied: {created_effect.get_functionality_description()}, lasts {initial_duration + 1} rounds (R2-R{2 + initial_duration}).",
                 None))
    elif _get_army_round(triggering_army, simulator) > (2 + skill_config.get("initial_effect_duration", 28)) and not is_any_version_active:
        if skill_def["id"] == "plugin_divine_blessing":
            if random.random() < skill_config.get("post_initial_trigger_chance", 0.0):
                post_initial_duration = skill_config.get("post_initial_effect_duration", 0)
                effect_data = {"effect_type": EffectType.STAT_MOD, "name": effect_name,
                               "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER,
                               "magnitude": reduction_magnitude, "duration": post_initial_duration,
                               "activate_next_round": True}
                created_effect = triggering_army._create_and_add_single_effect(
                    effect_data, skill_id, triggering_army, triggering_army, opponent_army)
                if created_effect:
                    an_effect_happened = True
                    log_details.append(
                        (f"Post-initial effect triggered: {created_effect.get_functionality_description()}, active next round for {post_initial_duration + 1} round(s).",
                         None))
    return an_effect_happened, log_details


def handle_plugin_shield_support(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 9)

    if _get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0:
        effect_name = skill_config.get("effect_name", EFFECT_NAME_SHIELD_SUPPORT_EFFECT)
        already_has_shield_from_this_skill_this_trigger = any(
            eff.name == effect_name and eff.source_skill_id == skill_id and
            (eff in triggering_army.upcoming_effects or eff in triggering_army.effects_to_activate_next_round or
             (eff in triggering_army.active_effects and eff.applied_this_round))
            for eff_list in [triggering_army.active_effects, triggering_army.upcoming_effects,
                             triggering_army.effects_to_activate_next_round]
            for eff in eff_list
        )
        if not already_has_shield_from_this_skill_this_trigger:
            shield_factor = skill_config.get("base_shield_factor", 750.0)
            log_msg_suffix = f"Base factor: {shield_factor}."
            if triggering_army.current_troop_count < opponent_army.current_troop_count:
                shield_factor = skill_config.get("boosted_shield_factor", 1000.0)
                log_msg_suffix = f"Troop count lower, using boosted shield factor: {shield_factor}."
            log_details.append((f"Condition Check: {log_msg_suffix}", None))
            shield_duration = skill_config.get("shield_duration", 1)
            shield_data = {"effect_type": EffectType.SHIELD, "name": effect_name, "duration": shield_duration,
                           "magnitude_calc_type": "dynamic_shield_resistance_v1", "shield_factor": shield_factor,
                           "activate_next_round": True}
            created_shield = triggering_army._create_and_add_single_effect(
                shield_data, skill_id, triggering_army, triggering_army, opponent_army)
            if created_shield:
                an_effect_happened = True
                est_mag = simulator._calculate_shield_magnitude_for_logging(triggering_army, opponent_army, float(
                    shield_factor)) if simulator else created_shield.magnitude
                log_details.append(
                    (f"Grants shield ({created_shield.get_functionality_description()}), active for next {shield_duration + 1} rounds. Est. Mag: {est_mag:.0f}",
                     None))
    return an_effect_happened, log_details


def handle_plugin_freyas_blessing(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    direct_heal_factor = skill_config.get("direct_heal_factor", 0.0)
    if direct_heal_factor > 0:
        healed_amount = triggering_army.calculate_and_add_pending_healing(
            direct_heal_factor,
            triggering_army,
            opponent_army,
            source_skill_id=skill_id,
        )
        if healed_amount > 0:
            an_effect_happened = True
            log_details.append((f"Heals self for {healed_amount:.0f} HP (Factor: {direct_heal_factor}).", None))
    buff_details = skill_config.get("buff_details")
    if buff_details:
        buff_data_copy = buff_details.copy()
        if "name" not in buff_data_copy: buff_data_copy["name"] = EFFECT_NAME_FREYAS_BLESSING_HEAL_BOOST
        created_buff = triggering_army._create_and_add_single_effect(
            buff_data_copy, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            an_effect_happened = True
            log_details.append(
                (f"Grants Healing Boost: {created_buff.get_functionality_description()} for {created_buff.duration + 1} round(s) (starting next round).",
                 None)
            )
    return an_effect_happened, log_details


def handle_plugin_hymn_of_life(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    hot_factor = skill_config.get("hot_heal_factor", 0.0)
    hot_duration = skill_config.get("hot_duration", 1)
    hot_effect_name = skill_config.get("hot_effect_name", EFFECT_NAME_HYMN_OF_LIFE_HOT)
    if hot_factor > 0:
        hot_effect_data = {"effect_type": EffectType.HEAL_OVER_TIME, "name": hot_effect_name,
                           "magnitude": hot_factor, "duration": hot_duration, "activate_next_round": True}
        created_hot = triggering_army._create_and_add_single_effect(
            hot_effect_data, skill_id, triggering_army, triggering_army, opponent_army)
        if created_hot:
            an_effect_happened = True
            log_details.append(
                (f"Applies {created_hot.get_functionality_description()} for next {hot_duration + 1} round(s).", None))
    hp_buff_magnitude = skill_config.get("hp_buff_magnitude", 0.0)
    hp_buff_duration = skill_config.get("hp_buff_duration", 0)
    hp_buff_name = skill_config.get("hp_buff_effect_name", EFFECT_NAME_HYMN_OF_LIFE_HP_BOOST)
    if hp_buff_magnitude != 0:  # Can be positive or negative if design changes
        hp_buff_data = {"effect_type": EffectType.STAT_MOD, "name": hp_buff_name,
                        "stat_to_mod": StatType.BASE_HP_MULTIPLIER, "magnitude": hp_buff_magnitude,
                        "duration": hp_buff_duration, "activate_next_round": True}
        created_hp_buff = triggering_army._create_and_add_single_effect(
            hp_buff_data, skill_id, triggering_army, triggering_army, opponent_army)
        if created_hp_buff:
            an_effect_happened = True
            log_details.append(
                (f"Modifies Base HP: {created_hp_buff.get_functionality_description()} for next {hp_buff_duration + 1} round(s).",
                 None))
    return an_effect_happened, log_details


def handle_plugin_chance_of_reversal(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    if skill_id in triggering_army.triggered_skills_this_round:
        return False, []
    damage_factor = skill_config.get("damage_factor", 0.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_dmg = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0: opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0: an_effect_happened = True
        log_details.append((f"Deals damage to {opponent_army.name}.",
                            {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absorbed),
                             "potential_kills": kills}))
    rage_gain = skill_config.get("rage_gain", 0.0)
    if rage_gain > 0:
        effect_data = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_DELAYED_RAGE_GAIN,
            "duration": 0,
            "config": {"rage_amount": rage_gain},
            "activate_next_round": True,
        }
        created = triggering_army._create_and_add_single_effect(
            effect_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created:
            an_effect_happened = True
            log_details.append((f"Gains {rage_gain:.0f} rage next round.", None))
    if an_effect_happened:
        triggering_army.triggered_skills_this_round.append(skill_id)
    return an_effect_happened, log_details


def handle_plugin_trap_of_despair(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    interval = cfg.get("trigger_interval", 9)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % interval == 0):
        return False, []

    dmg_factor = cfg.get("damage_factor", 0.0)
    if dmg_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, dmg_factor, source_skill_def=skill_def
        )
        if hp_damage > 0:
            opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
        log_details.append(
            (
                f"Deals damage (Factor: {dmg_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills},
            )
        )

    if random.random() < cfg.get("slow_chance", 0.5):
        slow_dur = cfg.get("slow_duration", 1)
        slow_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_SLOW_DEBUFF,
            "duration": slow_dur,
            "activate_next_round": True,
            "config": {},
        }
        created_slow = opponent_army._create_and_add_single_effect(
            slow_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_slow:
            an_effect_happened = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_dur + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details


def handle_plugin_poison_arrow(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    interval = cfg.get("trigger_interval", 9)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % interval == 0):
        return False, []

    poison_factor = cfg.get("poison_factor", 0.0)
    poison_duration = cfg.get("poison_duration", 2)
    if poison_factor > 0:
        poison_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_POISON_ARROW_POISON,
            "magnitude": poison_factor,
            "duration": poison_duration,
            "activate_next_round": True,
            "config": {"dot_type": DoTType.POISON},
        }
        created_poison = opponent_army._create_and_add_single_effect(
            poison_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_poison:
            an_effect_happened = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_POISON_ARROW_POISON}' on {opponent_army.name} (Factor: {poison_factor}) for {poison_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    if random.random() < cfg.get("attack_reduction_chance", 0.35):
        red_mag = cfg.get("attack_reduction_magnitude", -0.15)
        red_dur = cfg.get("attack_reduction_duration", 1)
        debuff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_POISON_ARROW_ATK_REDUCTION,
            "stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER,
            "magnitude": red_mag,
            "duration": red_dur,
            "activate_next_round": True,
        }
        created_debuff = opponent_army._create_and_add_single_effect(
            debuff_data, skill_def["id"], triggering_army, opponent_army, triggering_army
        )
        if created_debuff:
            an_effect_happened = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_POISON_ARROW_ATK_REDUCTION}' on {opponent_army.name} for {red_dur + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details


def handle_plugin_divine_shield(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    cfg = skill_def.get("config", {})
    skill_id = skill_def["id"]

    # Apply the passive shield strength boost if it hasn't been added yet
    has_passive_buff = any(
        eff.name == EFFECT_NAME_DIVINE_SHIELD_STRENGTH and eff.source_skill_id == skill_id
        for eff_list in [
            triggering_army.active_effects,
            triggering_army.upcoming_effects,
            triggering_army.effects_to_activate_next_round,
        ]
        for eff in eff_list
    )
    if not has_passive_buff:
        for eff_data_original in skill_def.get("effects_to_apply", []):
            eff_data = eff_data_original.copy()
            created_buff = triggering_army._create_and_add_single_effect(
                eff_data, skill_id, triggering_army, triggering_army, opponent_army
            )
            if created_buff:
                an_effect_happened = True
                log_details.append(
                    (f"Passive bonus: {created_buff.get_functionality_description()}.", None)
                )

    if triggering_army.started_round_with_active_shield:
        if random.random() < cfg.get("damage_chance", 0.20):
            damage_factor = cfg.get("damage_factor", 0.0)
            if damage_factor > 0:
                hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                    triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
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
        if random.random() < cfg.get("immunity_chance", 0.50):
            imm_dur = cfg.get("immunity_duration", 0)
            immunity_data = {
                "effect_type": EffectType.IMMUNITY,
                "name": EFFECT_NAME_DIVINE_SHIELD_IMMUNITY,
                "immune_to": [EFFECT_NAME_DISARM_DEBUFF, EFFECT_NAME_BROKEN_BLADE_DEBUFF, EFFECT_NAME_SILENCE_DEBUFF],
                "duration": imm_dur,
                "activate_next_round": True,
            }
            created_immunity = triggering_army._create_and_add_single_effect(
                immunity_data, skill_id, triggering_army, triggering_army, opponent_army
            )
            if created_immunity:
                an_effect_happened = True
                log_details.append(
                    (
                        f"Gains immunity from Disarm, Broken Blade, and Silence for {imm_dur + 1} round(s) (starting next round).",
                        None,
                    )
                )

    return an_effect_happened, log_details



def handle_plugin_shield_reflector(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_id = skill_def["id"]
    if triggering_army.started_last_round_with_active_shield:
        boost = skill_def.get("config", {}).get("counterattack_boost", 1.30)
        effect_data = {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SHIELD_REFLECTOR_BUFF,
                       "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": boost,
                       "duration": 0, "activate_next_round": False}  # Activates this round, lasts this round
        created_buff = triggering_army._create_and_add_single_effect(
            effect_data, skill_id, triggering_army, triggering_army, opponent_army)
        if created_buff:
            an_effect_happened = True
            log_details.append((f"Gains buff: {created_buff.get_functionality_description()} for this round.", None))

            pending = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
                "duration": 0,
                "config": {
                    "buff_ids_to_remove": [created_buff.id],
                    "targeted_buff_names_initial_log": [created_buff.name],
                },
                "activate_next_round": True,
            }
            triggering_army._create_and_add_single_effect(
                pending, skill_id, triggering_army, triggering_army, opponent_army
            )
            log_details.append(("Schedules Shield Reflector buff removal for next round.", None))
    return an_effect_happened, log_details


def handle_plugin_first_strike_control(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_id = skill_def["id"]
    skill_config = skill_def.get("config", {})
    apply_on_round = skill_config.get("apply_aura_on_round", 1)
    aura_def = skill_config.get("aura_effect_definition")
    if not aura_def:
        return False, []
    aura_name = aura_def.get("name", EFFECT_NAME_FIRST_STRIKE_RAGE_AURA)
    if not aura_name:
        return False, []
    last_round = triggering_army.skill_last_triggered_round.get(skill_id)
    if last_round is not None and last_round == _get_army_round(triggering_army, simulator):
        return False, []
    if _get_army_round(triggering_army, simulator) == apply_on_round:
        is_aura_already_active = any(
            eff.name == aura_name
            for eff_list in [
                triggering_army.active_effects,
                triggering_army.upcoming_effects,
                triggering_army.effects_to_activate_next_round,
            ]
            for eff in eff_list
        )
        if not is_aura_already_active:
            effect_data_copy = aura_def.copy()
            effect_data_copy["config"] = aura_def.get("config", {}).copy()
            rage_per_round = skill_config.get("rage_per_round")
            if rage_per_round is not None:
                effect_data_copy["config"]["rage_per_round"] = rage_per_round
            created_aura = triggering_army._create_and_add_single_effect(
                effect_data_copy, skill_id, triggering_army, triggering_army, opponent_army
            )
            if created_aura:
                an_effect_happened = True
                log_details.append(
                    (f"Applies aura: {created_aura.get_functionality_description()}.", None)
                )
                triggering_army.skill_last_triggered_round[skill_id] = _get_army_round(triggering_army, simulator)
    return an_effect_happened, log_details


def handle_plugin_shield_attacker(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    if triggering_army.started_round_with_active_shield:
        proc_chance = skill_config.get("proc_chance", 0.50)
        if random.random() < proc_chance:
            damage_factor = skill_config.get("damage_factor", 0.0)
            if damage_factor > 0:
                hp_damage, absorbed, kills, raw_dmg = simulator._calculate_generic_skill_damage(
                    triggering_army, opponent_army, damage_factor,
                    source_skill_def=skill_def
                )
                if hp_damage > 0: opponent_army.pending_hp_damage_this_round += hp_damage
                if hp_damage > 0 or absorbed > 0: an_effect_happened = True
                log_details.append(
                    (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name} (shield was active, {proc_chance * 100:.0f}% chance met).",
                     {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absorbed), "potential_kills": kills}))
    return an_effect_happened, log_details


def handle_plugin_awakening(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_id = skill_def["id"]
    skill_config = skill_def.get("config", {})

    actions_taken_this_trigger = False
    buff_details_data = skill_config.get("buff_details")
    if buff_details_data:
        buff_data_copy = buff_details_data.copy()
        if "name" not in buff_data_copy: buff_data_copy["name"] = EFFECT_NAME_AWAKENING_DMG_REDUCTION
        created_buff = triggering_army._create_and_add_single_effect(
            buff_data_copy, skill_id, triggering_army, triggering_army, opponent_army)
        if created_buff:
            actions_taken_this_trigger = True
            log_details.append(
                (f"Schedules buff: {created_buff.get_functionality_description()} for next round (active for {created_buff.duration + 1} round).",
                 None))

    cleanse_effect_data_template = skill_config.get("cleanse_effect_details")
    if cleanse_effect_data_template:
        debuffs_to_target_ids = []
        for eff in triggering_army.active_effects:  # Check current active effects
            is_debuff = (
                eff.effect_type == EffectType.DEBUFF
                or (
                    eff.effect_type == EffectType.DAMAGE_OVER_TIME
                    and eff.config.get("dot_type")
                    in [DoTType.BLEED, DoTType.POISON, DoTType.BURN]
                )
                or eff.config.get("prevents_counterattack")
                or eff.config.get("prevents_basic_attack")
                or eff.name == EFFECT_NAME_SILENCE_DEBUFF
            )  # Include silence
            if is_debuff:
                debuffs_to_target_ids.append(eff.id)

        if debuffs_to_target_ids:
            cleanse_effect_data_actual = cleanse_effect_data_template.copy()
            if "name" not in cleanse_effect_data_actual:
                cleanse_effect_data_actual["name"] = EFFECT_NAME_PENDING_AWAKENING_CLEANSE

            # Ensure config exists and is a dict before updating
            if "config" not in cleanse_effect_data_actual or not isinstance(cleanse_effect_data_actual["config"], dict):
                cleanse_effect_data_actual["config"] = {}
            cleanse_effect_data_actual["config"]["debuff_ids_to_remove"] = debuffs_to_target_ids

            created_cleanse = triggering_army._create_and_add_single_effect(
                cleanse_effect_data_actual, skill_id, triggering_army, triggering_army, opponent_army)
            if created_cleanse:
                actions_taken_this_trigger = True
                targeted_count = len(debuffs_to_target_ids)
                log_details.append(
                    (f"Schedules targeted debuff cleanse for {targeted_count} effect(s) next round.", None))
        else:
            log_details.append(("Awakening triggered cleanse, but no active debuffs found to target.", None))

    if actions_taken_this_trigger:
        an_effect_happened = True
    return an_effect_happened, log_details


def handle_plugin_baldr_blessing(
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
    chosen_effect_type = random.choice(["shield", "reduction", "heal"])
    log_details.append((f"Randomly chose '{chosen_effect_type}' effect.", None))
    if chosen_effect_type == "shield":
        shield_factor = skill_config.get("shield_factor", 0.0);
        shield_duration = skill_config.get("shield_duration", 1)
        shield_name = skill_config.get("shield_effect_name", EFFECT_NAME_BALDRS_SHIELD)
        if shield_factor > 0:
            shield_data = {"effect_type": EffectType.SHIELD, "name": shield_name, "duration": shield_duration,
                           "magnitude_calc_type": "dynamic_shield_resistance_v1", "shield_factor": shield_factor,
                           "activate_next_round": True}
            created = triggering_army._create_and_add_single_effect(shield_data, skill_id, triggering_army,
                                                                    triggering_army, opponent_army)
            if created:
                an_effect_happened = True;
                est_mag = simulator._calculate_shield_magnitude_for_logging(triggering_army, opponent_army, float(
                    shield_factor)) if simulator else created.magnitude
                log_details.append(
                    (f"Grants '{shield_name}' ({created.get_functionality_description()}), active for {shield_duration + 1} rounds (starting next round). Est. Mag: {est_mag:.0f}",
                     None))
    elif chosen_effect_type == "reduction":
        reduction_magnitude = skill_config.get("damage_reduction_magnitude", 0.0);
        reduction_duration = skill_config.get("damage_reduction_duration", 1)
        reduction_name = skill_config.get("damage_reduction_effect_name", EFFECT_NAME_BALDRS_RESILIENCE)
        if reduction_magnitude != 0:  # Can be negative
            reduction_data = {"effect_type": EffectType.STAT_MOD, "name": reduction_name,
                              "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER,
                              "magnitude": reduction_magnitude, "duration": reduction_duration,
                              "activate_next_round": True}
            created = triggering_army._create_and_add_single_effect(reduction_data, skill_id, triggering_army,
                                                                    triggering_army, opponent_army)
            if created: an_effect_happened = True; log_details.append(
                (f"Grants '{reduction_name}' ({created.get_functionality_description()}) for {reduction_duration + 1} rounds (starting next round).",
                 None))
    elif chosen_effect_type == "heal":
        heal_factor = skill_config.get("heal_factor", 0.0)
        heal_name = skill_config.get("heal_effect_name",
                                     EFFECT_NAME_BALDRS_HEAL)  # Though direct heal, name can be for logging
        if heal_factor > 0:
            healed_amount = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
            )
            if healed_amount > 0:
                an_effect_happened = True
                log_details.append(
                    (f"Heals army ({heal_name}) for {healed_amount:.0f} HP (Factor: {heal_factor}).", None))
    return an_effect_happened, log_details


def handle_plugin_lokis_trick(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    damage_factor = skill_config.get("damage_factor", 0.0)
    damage_attempted_or_done = False
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_dmg = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0: opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0:
            an_effect_happened = True
            damage_attempted_or_done = True
        log_details.append((f"Deals damage to {opponent_army.name}.",
                            {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absorbed),
                             "potential_kills": kills}))

    if damage_attempted_or_done:  # Only proc secondary effects if damage was dealt or absorbed
        if random.random() < skill_config.get("rage_reduction_chance", 0.0):
            rage_to_reduce = skill_config.get("rage_reduction_amount", 0.0)
            if rage_to_reduce > 0 and opponent_army.current_rage > 0:
                actual_reduced = min(opponent_army.current_rage, float(rage_to_reduce))
                effect_data = {
                    "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                    "name": EFFECT_NAME_DELAYED_RAGE_REDUCTION,
                    "duration": 0,
                    "config": {"rage_reduction": actual_reduced},
                    "activate_next_round": True,
                }
                created = opponent_army._create_and_add_single_effect(
                    effect_data, skill_id, triggering_army, opponent_army, triggering_army
                )
                if created:
                    an_effect_happened = True
                    log_details.append((f"Reduces {opponent_army.name}'s rage by {actual_reduced:.0f} next round.", None))

        if random.random() < skill_config.get("buff_removal_chance", 0.0):
            buff_ids_to_target = []
            buff_names_for_initial_log = []
            pending_removal_effect_name = skill_config.get("pending_buff_removal_effect_name",
                                                           EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL)

            for eff in opponent_army.active_effects:  # Target opponent's buffs
                is_removable_buff = (
                        eff.effect_type != EffectType.SHIELD and  # Don't remove shields this way
                        eff.duration != -1 and  # Don't remove permanent effects
                        eff.name != pending_removal_effect_name and  # Don't target self
                        eff.effect_type != EffectType.HEAL_OVER_TIME and  # Don't remove heal over time
                        eff.config.get("is_dispellable", True) and
                        ((eff.effect_type == EffectType.STAT_MOD and eff.magnitude > 0) or \
                         (eff.effect_type != EffectType.DEBUFF and eff.effect_type != EffectType.DAMAGE_OVER_TIME))
                # General buff definition
                )
                if is_removable_buff:
                    buff_ids_to_target.append(eff.id)
                    buff_names_for_initial_log.append(eff.name if eff.name else f"Buff ID ...{str(eff.id)[-4:]}")

            if buff_ids_to_target:
                pending_effect_config = {
                    "buff_ids_to_remove": buff_ids_to_target,
                    "targeted_buff_names_initial_log": buff_names_for_initial_log
                }
                # This custom effect will be applied to the OPPONENT to make THEM remove their own buffs
                pending_data = {
                    "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                    "name": pending_removal_effect_name,
                    "duration": 0,  # Instantaneous next round
                    "config": pending_effect_config,
                    "activate_next_round": True
                }
                created_pending_effect = opponent_army._create_and_add_single_effect(
                    pending_data, skill_id, triggering_army, opponent_army, triggering_army
                    # Owner is Loki's army, target is opponent
                )
                if created_pending_effect:
                    an_effect_happened = True
                    log_details.append(
                        (f"Schedules targeted buff removal on {opponent_army.name} for next round (Targeted: {', '.join(buff_names_for_initial_log) if buff_names_for_initial_log else 'None'}).",
                         None))
            else:
                log_details.append(
                    (f"Loki's Trick attempted buff removal on {opponent_army.name}, but no removable buffs found at this moment.",
                     None))
    return an_effect_happened, log_details


def handle_plugin_odins_asylum(
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
        hp_damage, absorbed, kills, raw_dmg = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0: opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0: an_effect_happened = True
        log_details.append((f"Deals damage to {opponent_army.name} (Factor: {damage_factor}).",
                            {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absorbed),
                             "potential_kills": kills}))
    shield_factor = skill_config.get("shield_factor", 0.0)
    if shield_factor > 0:
        shield_duration = skill_config.get("shield_duration", 1);
        shield_name = skill_config.get("shield_name", EFFECT_NAME_ODINS_ASYLUM_SHIELD)
        shield_activate_next = skill_config.get("shield_activate_next_round", True)
        shield_data = {"effect_type": EffectType.SHIELD, "name": shield_name, "duration": shield_duration,
                       "magnitude_calc_type": "dynamic_shield_resistance_v1", "shield_factor": shield_factor,
                       "activate_next_round": shield_activate_next}
        created_shield = triggering_army._create_and_add_single_effect(shield_data, skill_id, triggering_army,
                                                                       triggering_army, opponent_army)
        if created_shield:
            an_effect_happened = True;
            est_mag = simulator._calculate_shield_magnitude_for_logging(triggering_army, opponent_army, float(
                shield_factor)) if simulator else created_shield.magnitude
            activation_time = "next round" if shield_activate_next else "this round"
            log_details.append(
                (f"Gains shield ({created_shield.get_functionality_description()}) starting {activation_time}, lasting {shield_duration + 1} rounds. Est. Mag: {est_mag:.0f}",
                 None))
    return an_effect_happened, log_details


def handle_plugin_thors_determination(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 9)
    if _get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0:
        buff_name = skill_config.get("buff_name", EFFECT_NAME_THORS_DETERMINATION_BUFF)
        buff_magnitude = skill_config.get("buff_magnitude", 2.25);
        buff_duration = skill_config.get("buff_duration", 1)
        buff_activate_next = skill_config.get("buff_activate_next_round", True)
        buff_stat_enum_or_str = skill_config.get("buff_stat_to_mod",
                                                 StatType.BASIC_DAMAGE_ADJUST)  # Default to BASIC_DAMAGE_ADJUST

        buff_stat = buff_stat_enum_or_str
        if isinstance(buff_stat_enum_or_str, str):  # Convert string to StatType enum if needed
            try:
                buff_stat = StatType[buff_stat_enum_or_str.upper()]
            except KeyError:
                try:
                    buff_stat = StatType(buff_stat_enum_or_str)  # Try direct value match
                except ValueError:
                    print(
                        f"Warning: Invalid stat type string '{buff_stat_enum_or_str}' in Thor's Determination. Defaulting to BASIC_DAMAGE_ADJUST.");
                    buff_stat = StatType.BASIC_DAMAGE_ADJUST

        effect_data = {"effect_type": EffectType.STAT_MOD, "name": buff_name, "stat_to_mod": buff_stat,
                       "magnitude": buff_magnitude, "duration": buff_duration,
                       "activate_next_round": buff_activate_next}
        created_buff = triggering_army._create_and_add_single_effect(effect_data, skill_id, triggering_army,
                                                                     triggering_army, opponent_army)
        if created_buff:
            an_effect_happened = True;
            activation_time = "next round" if buff_activate_next else "this round"
            log_details.append(
                (f"Gains buff: {created_buff.get_functionality_description()}, starting {activation_time} for {buff_duration + 1} rounds.",
                 None))

        if opponent_army and triggering_army.current_troop_count < opponent_army.current_troop_count:
            dmg_red_name = skill_config.get("damage_reduction_name", EFFECT_NAME_THORS_DETERMINATION_DMG_REDUCTION)
            dmg_red_mag = skill_config.get("damage_reduction_magnitude", -0.15)
            dmg_red_dur = skill_config.get("damage_reduction_duration", 2)
            dmg_red_activate_next = skill_config.get("damage_reduction_activate_next_round", True)
            dmg_red_data = {"effect_type": EffectType.STAT_MOD, "name": dmg_red_name,
                           "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER,
                           "magnitude": dmg_red_mag, "duration": dmg_red_dur,
                           "activate_next_round": dmg_red_activate_next}
            created_reduction = triggering_army._create_and_add_single_effect(
                dmg_red_data, skill_id, triggering_army, triggering_army, opponent_army)
            if created_reduction:
                an_effect_happened = True
                activation_time = "next round" if dmg_red_activate_next else "this round"
                log_details.append(
                    (f"Condition met: gains damage reduction ({created_reduction.get_functionality_description()}) starting {activation_time} for {dmg_red_dur + 1} rounds.",
                     None))
    return an_effect_happened, log_details


def handle_plugin_disarmament(
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
        hp_damage, absorbed, kills, raw_dmg = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor,
            source_skill_def=skill_def
        )
        if hp_damage > 0: opponent_army.pending_hp_damage_this_round += hp_damage
        if hp_damage > 0 or absorbed > 0: an_effect_happened = True
        log_details.append((f"Deals damage to {opponent_army.name} (Factor: {damage_factor}).",
                            {"damage_done_hp": round(raw_dmg), "absorbed_hp": round(absorbed),
                             "potential_kills": kills}))

    activate_debuffs_next = skill_config.get("activate_debuffs_next_round", True)
    activation_time_log = "next round" if activate_debuffs_next else "this round"

    disarm_duration = skill_config.get("disarm_duration", 0);
    disarm_name = skill_config.get("disarm_effect_name", EFFECT_NAME_DISARM_DEBUFF)
    disarm_cfg = {"prevents_basic_attack": True} if disarm_name == EFFECT_NAME_DISARM_DEBUFF else {}
    disarm_data = {"effect_type": EffectType.DEBUFF, "name": disarm_name, "duration": disarm_duration,
                   "activate_next_round": activate_debuffs_next, "config": disarm_cfg}
    created_disarm = opponent_army._create_and_add_single_effect(disarm_data, skill_id, triggering_army, opponent_army,
                                                                 triggering_army)
    if created_disarm: an_effect_happened = True; log_details.append(
        (f"Inflicts '{created_disarm.get_functionality_description()}' on {opponent_army.name}, starting {activation_time_log} for {disarm_duration + 1} round(s).",
         None))

    slow_duration = skill_config.get("slow_duration", 1);
    slow_name = skill_config.get("slow_effect_name", EFFECT_NAME_SLOW_DEBUFF);
    slow_cfg = {}  # Slow is just a marker
    slow_data = {"effect_type": EffectType.DEBUFF, "name": slow_name, "duration": slow_duration,
                 "activate_next_round": activate_debuffs_next, "config": slow_cfg}
    created_slow = opponent_army._create_and_add_single_effect(slow_data, skill_id, triggering_army, opponent_army,
                                                               triggering_army)
    if created_slow: an_effect_happened = True; log_details.append(
        (f"Inflicts '{created_slow.get_functionality_description()}' on {opponent_army.name}, starting {activation_time_log} for {slow_duration + 1} round(s).",
         None))
    return an_effect_happened, log_details


# --- NEW PLUGIN SKILL HANDLERS ---

def handle_plugin_silencer(
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
        an_effect_happened = True
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

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
    return an_effect_happened, log_details


def handle_plugin_enrage(
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
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

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


def handle_plugin_blessed_negation(
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

    buff_ids_to_target = []
    buff_names_for_initial_log = []
    for eff in opponent_army.active_effects:
        is_removable_buff = (
                eff.effect_type != EffectType.SHIELD and eff.duration != -1 and
                eff.name != EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL and
                eff.effect_type != EffectType.HEAL_OVER_TIME and
                ((eff.effect_type == EffectType.STAT_MOD and eff.magnitude > 0) or \
                 (eff.effect_type != EffectType.DEBUFF and eff.effect_type != EffectType.DAMAGE_OVER_TIME))
        )
        if is_removable_buff:
            buff_ids_to_target.append(eff.id)
            buff_names_for_initial_log.append(eff.name if eff.name else f"Buff ID ...{str(eff.id)[-4:]}")

    if buff_ids_to_target:
        pending_effect_config = {
            "buff_ids_to_remove": buff_ids_to_target,
            "targeted_buff_names_initial_log": buff_names_for_initial_log
        }
        pending_data = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
            "duration": 0, "config": pending_effect_config, "activate_next_round": True
        }
        created_pending_effect = opponent_army._create_and_add_single_effect(
            pending_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_pending_effect:
            an_effect_happened = True
            log_details.append(
                (f"Schedules targeted buff removal on {opponent_army.name} for next round (Targeted: {', '.join(buff_names_for_initial_log) if buff_names_for_initial_log else 'None'}).",
                 None))
    else:
        log_details.append((f"Attempted buff removal on {opponent_army.name}, but no removable buffs found.", None))

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

    return an_effect_happened, log_details


def handle_plugin_wild_indulgence(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 10)

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

    debuffs_to_target_ids = []
    for eff in triggering_army.active_effects:
        is_debuff = (
            eff.effect_type == EffectType.DEBUFF
            or (
                eff.effect_type == EffectType.DAMAGE_OVER_TIME
                and eff.config.get("dot_type")
                in [DoTType.BLEED, DoTType.POISON, DoTType.BURN]
            )
            or eff.config.get("prevents_counterattack")
            or eff.config.get("prevents_basic_attack")
            or eff.name == EFFECT_NAME_SILENCE_DEBUFF
        )
        if is_debuff:
            debuffs_to_target_ids.append(eff.id)

    if debuffs_to_target_ids:
        cleanse_effect_data_actual = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
            "duration": 0,
            "config": {"debuff_ids_to_remove": debuffs_to_target_ids},
            "activate_next_round": True
        }
        created_cleanse = triggering_army._create_and_add_single_effect(
            cleanse_effect_data_actual, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_cleanse:
            an_effect_happened = True
            targeted_count = len(debuffs_to_target_ids)
            log_details.append((f"Schedules self-cleanse for {targeted_count} debuff(s) next round.", None))
    else:
        log_details.append(("Attempted self-cleanse, but no active debuffs found.", None))

    return an_effect_happened, log_details


def handle_plugin_breaking_free(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 10)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    dmg_buff_mag = skill_config.get("damage_buff_magnitude", 0.0)
    dmg_buff_dur = skill_config.get("damage_buff_duration", 2)
    if dmg_buff_mag > 0:
        dmg_buff_data = {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_BREAKING_FREE_DMG_BUFF,
            "stat_to_mod": StatType.GENERAL_DAMAGE_MODIFIER, "magnitude": dmg_buff_mag,
            "duration": dmg_buff_dur, "activate_next_round": True
        }
        created_dmg_buff = triggering_army._create_and_add_single_effect(
            dmg_buff_data, skill_id, triggering_army, triggering_army, opponent_army)
        if created_dmg_buff:
            an_effect_happened = True
            log_details.append(
                (f"Gains '{EFFECT_NAME_BREAKING_FREE_DMG_BUFF}': {created_dmg_buff.get_functionality_description()} for {created_dmg_buff.duration + 1} rounds.",
                 None))

    counter_reduct_mag = skill_config.get("counter_reduction_magnitude", 0.0)
    counter_reduct_dur = skill_config.get("counter_reduction_duration", 2)
    if counter_reduct_mag < 0:
        counter_reduct_data = {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_BREAKING_FREE_COUNTER_REDUCTION,
            "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": counter_reduct_mag,
            "duration": counter_reduct_dur, "activate_next_round": True,
            "config_filter": {"attack_type": "COUNTER"}
        }
        created_counter_reduct = triggering_army._create_and_add_single_effect(
            counter_reduct_data, skill_id, triggering_army, triggering_army, opponent_army)
        if created_counter_reduct:
            an_effect_happened = True
            log_details.append(
                (f"Gains '{EFFECT_NAME_BREAKING_FREE_COUNTER_REDUCTION}': {created_counter_reduct.get_functionality_description()} for {created_counter_reduct.duration + 1} rounds.",
                 None))

    debuffs_to_target_ids = []
    for eff in triggering_army.active_effects:
        is_debuff = (
            eff.effect_type == EffectType.DEBUFF
            or (
                eff.effect_type == EffectType.DAMAGE_OVER_TIME
                and eff.config.get("dot_type")
                in [DoTType.BLEED, DoTType.POISON, DoTType.BURN]
            )
            or eff.config.get("prevents_counterattack")
            or eff.config.get("prevents_basic_attack")
            or eff.name == EFFECT_NAME_SILENCE_DEBUFF
        )
        if is_debuff:
            debuffs_to_target_ids.append(eff.id)

    if debuffs_to_target_ids:
        cleanse_effect_data_actual = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
            "duration": 0,
            "config": {"debuff_ids_to_remove": debuffs_to_target_ids},
            "activate_next_round": True
        }
        created_cleanse = triggering_army._create_and_add_single_effect(
            cleanse_effect_data_actual, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_cleanse:
            an_effect_happened = True
            targeted_count = len(debuffs_to_target_ids)
            log_details.append((f"Schedules self-cleanse for {targeted_count} debuff(s) next round.", None))
    else:
        log_details.append(("Attempted self-cleanse, but no active debuffs found.", None))

    return an_effect_happened, log_details


def handle_plugin_battle_hymn(
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
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

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


def handle_plugin_rapid_attack(
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
        log_details.append((
            f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
            {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
        ))

    broken_blade_duration = skill_config.get("broken_blade_duration", 1)
    debuff_effect_data = {
        "effect_type": EffectType.DEBUFF,
        "name": EFFECT_NAME_BROKEN_BLADE_DEBUFF,
        "duration": broken_blade_duration,
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


def handle_plugin_rage_purge(
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
            (
                f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills}
            )
        )

    rage_cost = skill_config.get("rage_cost", 0.0)
    if rage_cost > 0 and triggering_army.current_rage > 0:
        actual_cost = min(triggering_army.current_rage, float(rage_cost))
        triggering_army.current_rage -= actual_cost
        an_effect_happened = True
        log_details.append((f"Consumes {actual_cost:.0f} rage.", None))

    return an_effect_happened, log_details


def handle_plugin_blessed_by_fate(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    current_round = _get_army_round(triggering_army, simulator)

    initial_buff_duration = skill_config.get("initial_buff_duration", 29)
    initial_buff_magnitude = skill_config.get("initial_buff_magnitude", 0.50)
    initial_buff_name = EFFECT_NAME_BLESSED_BY_FATE_BASIC_ATK_BUFF

    if current_round == 2:
        already_active_initial = any(
            eff.name == initial_buff_name and eff.source_skill_id == skill_id
            for eff in
            triggering_army.active_effects + triggering_army.upcoming_effects + triggering_army.effects_to_activate_next_round
        )
        if not already_active_initial:
            initial_buff_data = {
                "effect_type": EffectType.STAT_MOD, "name": initial_buff_name,
                "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": initial_buff_magnitude,
                "duration": initial_buff_duration,
                "activate_next_round": False
            }
            created_initial_buff = triggering_army._create_and_add_single_effect(
                initial_buff_data, skill_id, triggering_army, triggering_army, opponent_army
            )
            if created_initial_buff:
                an_effect_happened = True
                log_details.append(
                    (f"Applies '{initial_buff_name}': {created_initial_buff.get_functionality_description()} for {created_initial_buff.duration + 1} rounds (R2-R{2 + initial_buff_duration}).",
                     None))

    if current_round > (1 + initial_buff_duration):
        if random.random() < skill_config.get("secondary_proc_chance", 0.0):
            secondary_debuff_magnitude = skill_config.get("secondary_debuff_magnitude", 0.20)
            secondary_debuff_duration = skill_config.get("secondary_debuff_duration", 0)
            secondary_debuff_name = EFFECT_NAME_BLESSED_BY_FATE_ENEMY_DMG_TAKEN_DEBUFF

            secondary_debuff_data = {
                "effect_type": EffectType.STAT_MOD, "name": secondary_debuff_name,
                "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": secondary_debuff_magnitude,
                "duration": secondary_debuff_duration, "activate_next_round": True
            }
            created_secondary_debuff = opponent_army._create_and_add_single_effect(
                secondary_debuff_data, skill_id, triggering_army, opponent_army, triggering_army
            )
            if created_secondary_debuff:
                an_effect_happened = True
                log_details.append(
                    (f"Inflicts '{secondary_debuff_name}' on {opponent_army.name}: {created_secondary_debuff.get_functionality_description()} for {created_secondary_debuff.duration + 1} round (starting next round).",
                     None))

    return an_effect_happened, log_details


def handle_plugin_fiery_rage(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    burn_factor = skill_config.get("burn_factor", 350.0)
    if any(eff.effect_type == EffectType.DAMAGE_OVER_TIME and
           eff.config.get("dot_type") == DoTType.BURN
           for eff in opponent_army.active_effects):
        burn_factor = skill_config.get("boosted_burn_factor", 700.0)

    burn_duration = skill_config.get("burn_duration", 2)
    burn_effect_data = {
        "effect_type": EffectType.DAMAGE_OVER_TIME,
        "name": EFFECT_NAME_FIERY_RAGE_BURN,
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
            (f"Inflicts '{EFFECT_NAME_FIERY_RAGE_BURN}' on {opponent_army.name} "
             f"(Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
             None)
        )

    return an_effect_happened, log_details


def handle_plugin_fiery_detonation(
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

    enemy_is_burning = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BURN
        for eff in opponent_army.active_effects
    )
    if enemy_is_burning:
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
                (f"Deals additional damage (Factor: {damage_factor}) to {opponent_army.name} (target burning).",
                 {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills})
            )

        def_red_mag = skill_config.get("defense_reduction_magnitude", -0.15)
        def_red_dur = skill_config.get("defense_reduction_duration", 2)
        if def_red_mag != 0:
            debuff_data = {
                "effect_type": EffectType.STAT_MOD,
                "name": EFFECT_NAME_FIERY_DETONATION_DEF_REDUCTION,
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
                    (f"Inflicts '{EFFECT_NAME_FIERY_DETONATION_DEF_REDUCTION}' on {opponent_army.name} for {def_red_dur + 1} rounds (starting next round).",
                     None)
                )

    return an_effect_happened, log_details


def handle_plugin_rage_leech(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    target_burning = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BURN
        for eff in opponent_army.active_effects
    )
    if target_burning:
        heal_factor = skill_config.get("heal_factor", 900.0)
        if heal_factor > 0:
            healed = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
            )
            if healed > 0:
                an_effect_happened = True
                log_details.append((f"Heals for {healed:.0f} HP (Factor: {heal_factor}).", None))
    else:
        rage_gain = skill_config.get("rage_gain", 80.0)
        if rage_gain > 0:
            effect_data = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_DELAYED_RAGE_GAIN,
                "duration": 0,
                "config": {"rage_amount": rage_gain},
                "activate_next_round": True,
            }
            created = triggering_army._create_and_add_single_effect(
                effect_data, skill_id, triggering_army, triggering_army, opponent_army
            )
            if created:
                an_effect_happened = True
                log_details.append((f"Gains {rage_gain:.0f} rage next round.", None))

    return an_effect_happened, log_details


def handle_plugin_enchanted_pursuit(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    if random.random() < skill_config.get("burn_chance", 0.10):
        burn_factor = skill_config.get("burn_factor", 275.0)
        burn_duration = skill_config.get("burn_duration", 2)
        burn_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_ENCHANTED_PURSUIT_BURN,
            "dot_type": DoTType.BURN,
            "status_effect_factor": burn_factor,
            "duration": burn_duration,
            "activate_next_round": True,
        }
        created = opponent_army._create_and_add_single_effect(
            burn_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created:
            an_effect_happened = True
            log_details.append(
                (f"Inflicts '{EFFECT_NAME_ENCHANTED_PURSUIT_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
                 None)
            )

    if random.random() < skill_config.get("bleed_chance", 0.10):
        bleed_factor = skill_config.get("bleed_factor", 275.0)
        bleed_duration = skill_config.get("bleed_duration", 2)
        bleed_data = {
            "effect_type": EffectType.DAMAGE_OVER_TIME,
            "name": EFFECT_NAME_ENCHANTED_PURSUIT_BLEED,
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
            log_details.append(
                (f"Inflicts '{EFFECT_NAME_ENCHANTED_PURSUIT_BLEED}' on {opponent_army.name} (Factor: {bleed_factor}) for {bleed_duration + 1} rounds (starting next round).",
                 None)
            )

    return an_effect_happened, log_details


def handle_plugin_blow_of_chaos(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    enemy_has_status = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and
        eff.config.get("dot_type") in [DoTType.BURN, DoTType.POISON, DoTType.BLEED]
        for eff in opponent_army.active_effects
    )
    if enemy_has_status:
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

    return an_effect_happened, log_details


def handle_plugin_on_alert(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 9)

    current_round = _get_army_round(triggering_army, simulator)
    if not (current_round > 0 and current_round % trigger_interval == 0):
        return False, []

    buff_name = skill_config.get("buff_name", EFFECT_NAME_ON_ALERT_COUNTER_BUFF)
    relevant_effects = [
        eff
        for effect_collection in (
            triggering_army.active_effects,
            triggering_army.upcoming_effects,
            triggering_army.effects_to_activate_next_round,
        )
        for eff in effect_collection
        if eff.name == buff_name and eff.source_skill_id == skill_id
    ]
    existing_stacks = 0
    for eff in relevant_effects:
        eff_stack = int(eff.config.get("stack_count", 1))
        if eff_stack > existing_stacks:
            existing_stacks = eff_stack
    max_stacks = skill_config.get("max_stacks", 5)
    if existing_stacks >= max_stacks:
        return False, []

    buff_mag = skill_config.get("buff_magnitude", 0.17)
    total_stacks = existing_stacks + 1
    total_magnitude = total_stacks * buff_mag
    buff_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": buff_name,
        "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST,
        "magnitude": total_magnitude,
        "duration": -1,
        "activate_next_round": True,
        "config": {"is_dispellable": False, "stack_count": total_stacks},
    }
    created_buff = triggering_army._create_and_add_single_effect(
        buff_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_buff:
        an_effect_happened = True
        total_bonus = total_magnitude * 100
        log_message = (
            "Gains permanent counterattack damage buff "
            f"(+{buff_mag * 100:.0f}% per stack, now +{total_bonus:.0f}% total), "
            f"stack {total_stacks}/{max_stacks}."
        )
        log_details.append((log_message, None))

    return an_effect_happened, log_details


def handle_plugin_helas_curse(
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

    burn_factor = skill_config.get("burn_factor", 500.0)
    burn_duration = skill_config.get("burn_duration", 2)
    burn_data = {
        "effect_type": EffectType.DAMAGE_OVER_TIME,
        "name": EFFECT_NAME_HELAS_CURSE_BURN,
        "dot_type": DoTType.BURN,
        "status_effect_factor": burn_factor,
        "duration": burn_duration,
        "activate_next_round": True,
    }
    created_burn = opponent_army._create_and_add_single_effect(
        burn_data, skill_id, triggering_army, opponent_army, triggering_army
    )
    if created_burn:
        an_effect_happened = True
        log_details.append(
            (f"Inflicts '{EFFECT_NAME_HELAS_CURSE_BURN}' on {opponent_army.name} (Factor: {burn_factor}) for {burn_duration + 1} rounds (starting next round).",
             None)
        )

    if random.random() < skill_config.get("defense_debuff_chance", 0.5):
        def_mag = skill_config.get("defense_debuff_magnitude", -0.20)
        def_dur = skill_config.get("defense_debuff_duration", 2)
        debuff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_HELAS_CURSE_DEF_REDUCTION,
            "stat_to_mod": StatType.BASE_DEFENSE_MULTIPLIER,
            "magnitude": def_mag,
            "duration": def_dur,
            "activate_next_round": True,
        }
        created_def = opponent_army._create_and_add_single_effect(
            debuff_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_def:
            an_effect_happened = True
            log_details.append(
                (f"Inflicts '{EFFECT_NAME_HELAS_CURSE_DEF_REDUCTION}' on {opponent_army.name} for {def_dur + 1} rounds (starting next round).",
                 None)
            )

    return an_effect_happened, log_details


def handle_plugin_fearless(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 12)

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
            (f"Deals damage (Factor: {damage_factor}) to {opponent_army.name}.",
             {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills})
        )

    if random.random() < skill_config.get("buff_chance", 0.20):
        buff_mag = skill_config.get("buff_magnitude", 0.15)
        buff_dur = skill_config.get("buff_duration", 2)
        buff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_FEARLESS_ATTACK_BUFF,
            "stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER,
            "magnitude": buff_mag,
            "duration": buff_dur,
            "activate_next_round": True,
        }
        created_buff = triggering_army._create_and_add_single_effect(
            buff_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_buff:
            an_effect_happened = True
            log_details.append(
                (f"Gains attack buff {buff_mag * 100:.0f}% for {buff_dur + 1} rounds (starting next round).",
                 None)
            )

    return an_effect_happened, log_details


def handle_plugin_joint_offense(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})

    if random.random() < skill_config.get("proc_chance", 0.50):
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

    return an_effect_happened, log_details


def handle_plugin_bloody_rage(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})

    threshold = skill_config.get("hp_threshold_pct", 0.80)
    if triggering_army.current_troop_count < triggering_army.unit.initial_count * threshold:
        if random.random() < skill_config.get("proc_chance", 0.20):
            damage_factor = skill_config.get("damage_factor", 500.0)
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


def handle_plugin_tidal_attack(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    damage_factor = skill_config.get("damage_factor", 290.0)
    is_h1 = (
        triggering_army.heroes
        and len(triggering_army.heroes) > 0
        and skill_id in [s["id"] for s in triggering_army.heroes[0].skills]
    )
    if is_h1:
        damage_factor = skill_config.get("damage_factor_h1", 370.0)

    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
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

    return an_effect_happened, log_details


def handle_plugin_splinter(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 12)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    damage_factor = skill_config.get("damage_factor", 800.0)
    if damage_factor > 0:
        hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
            triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
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

    if random.random() < skill_config.get("slow_chance", 0.35):
        slow_duration = skill_config.get("slow_duration", 2)
        slow_data = {
            "effect_type": EffectType.DEBUFF,
            "name": EFFECT_NAME_SLOW_DEBUFF,
            "duration": slow_duration,
            "activate_next_round": True,
            "config": {},
        }
        created_slow = opponent_army._create_and_add_single_effect(
            slow_data, skill_id, triggering_army, opponent_army, triggering_army
        )
        if created_slow:
            an_effect_happened = True
            log_details.append(
                (
                    f"Inflicts '{EFFECT_NAME_SLOW_DEBUFF}' on {opponent_army.name} for {slow_duration + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details


def handle_plugin_hale_of_thorns(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_id = skill_def["id"]

    is_h1 = (
        triggering_army.heroes
        and len(triggering_army.heroes) > 0
        and skill_id in [s["id"] for s in triggering_army.heroes[0].skills]
    )
    if not is_h1:
        return False, []

    gen_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_HALE_OF_THORNS_GENERAL_REDUCTION,
        "stat_to_mod": StatType.GENERAL_DAMAGE_MODIFIER,
        "magnitude": -0.15,
        "duration": -1,
        "activate_next_round": False,
    }
    ctr_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_HALE_OF_THORNS_COUNTER_BUFF,
        "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST,
        "magnitude": 0.50,
        "duration": -1,
        "activate_next_round": False,
    }
    eff1 = triggering_army._create_and_add_single_effect(gen_data, skill_id, triggering_army, triggering_army, opponent_army)
    if eff1:
        an_effect_happened = True
        log_details.append((f"Gains permanent effect: {eff1.get_functionality_description()}.", None))
    eff2 = triggering_army._create_and_add_single_effect(ctr_data, skill_id, triggering_army, triggering_army, opponent_army)
    if eff2:
        an_effect_happened = True
        log_details.append((f"Gains permanent effect: {eff2.get_functionality_description()}.", None))

    return an_effect_happened, log_details


def handle_plugin_halo_of_sacrifice(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    buff_mag = skill_config.get("buff_magnitude", 0.75)
    buff_dur = skill_config.get("buff_duration", 2)
    buff_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_HALO_OF_SACRIFICE_BASIC_BUFF,
        "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
        "magnitude": buff_mag,
        "duration": buff_dur,
        "activate_next_round": True,
    }
    created_buff = triggering_army._create_and_add_single_effect(
        buff_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_buff:
        an_effect_happened = True
        log_details.append(
            (
                f"Gains basic attack buff {buff_mag * 100:.0f}% for {buff_dur + 1} rounds (starting next round).",
                None,
            )
        )

    debuff_ids = []
    for eff in triggering_army.active_effects:
        is_debuff = (
            eff.effect_type == EffectType.DEBUFF
            or (
                eff.effect_type == EffectType.DAMAGE_OVER_TIME
                and eff.config.get("dot_type")
                in [DoTType.BLEED, DoTType.POISON, DoTType.BURN]
            )
            or eff.config.get("prevents_counterattack")
            or eff.config.get("prevents_basic_attack")
            or eff.name == EFFECT_NAME_SILENCE_DEBUFF
        )
        if is_debuff:
            debuff_ids.append(eff.id)

    if debuff_ids:
        cleanse_data = {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
            "name": EFFECT_NAME_PENDING_HALO_OF_SACRIFICE_CLEANSE,
            "duration": 0,
            "config": {"debuff_ids_to_remove": debuff_ids},
            "activate_next_round": True,
        }
        created_cleanse = triggering_army._create_and_add_single_effect(
            cleanse_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_cleanse:
            an_effect_happened = True
            log_details.append((f"Schedules self-cleanse for {len(debuff_ids)} debuff(s) next round.", None))

    return an_effect_happened, log_details


def handle_plugin_heightened_chance(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    basic_buff_mag = skill_config.get("basic_buff_magnitude", 0.40)
    buff_dur = skill_config.get("buff_duration", 2)
    basic_buff_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_HEIGHTENED_CHANCE_BASIC_BUFF,
        "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
        "magnitude": basic_buff_mag,
        "duration": buff_dur,
        "activate_next_round": True,
    }
    created_basic = triggering_army._create_and_add_single_effect(
        basic_buff_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_basic:
        an_effect_happened = True
        log_details.append(
            (
                f"Gains basic attack buff {basic_buff_mag * 100:.0f}% for {buff_dur + 1} rounds (starting next round).",
                None,
            )
        )

    enemy_has_slow = any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects)
    if enemy_has_slow:
        counter_buff_mag = skill_config.get("counter_buff_magnitude", 0.40)
        counter_buff_data = {
            "effect_type": EffectType.STAT_MOD,
            "name": EFFECT_NAME_HEIGHTENED_CHANCE_COUNTER_BUFF,
            "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST,
            "magnitude": counter_buff_mag,
            "duration": buff_dur,
            "activate_next_round": True,
        }
        created_counter = triggering_army._create_and_add_single_effect(
            counter_buff_data, skill_id, triggering_army, triggering_army, opponent_army
        )
        if created_counter:
            an_effect_happened = True
            log_details.append(
                (
                    f"Enemy slowed; gains counterattack buff {counter_buff_mag * 100:.0f}% for {buff_dur + 1} rounds (starting next round).",
                    None,
                )
            )

    return an_effect_happened, log_details


def handle_plugin_tenacity(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    heal_factor = skill_config.get("heal_factor", 700.0)
    if heal_factor > 0:
        healed_amount = triggering_army.calculate_and_add_pending_healing(
            heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
        )
        if healed_amount > 0:
            an_effect_happened = True
            log_details.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_factor}).", None))

    return an_effect_happened, log_details


def handle_plugin_blessed_healing(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]
    trigger_interval = skill_config.get("trigger_interval", 12)

    if not (_get_army_round(triggering_army, simulator) > 0 and _get_army_round(triggering_army, simulator) % trigger_interval == 0):
        return False, []

    heal_factor = skill_config.get("heal_factor", 850.0)
    if heal_factor > 0:
        healed_amount = triggering_army.calculate_and_add_pending_healing(
            heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
        )
        if healed_amount > 0:
            an_effect_happened = True
            log_details.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_factor}).", None))

    return an_effect_happened, log_details


def handle_plugin_dampened_spirits(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    if random.random() < skill_config.get("damage_proc_chance", 0.50):
        damage_factor = skill_config.get("damage_factor", 550.0)
        if damage_factor > 0:
            hp_damage, absorbed, kills, raw_logged_damage = simulator._calculate_generic_skill_damage(
                triggering_army, opponent_army, damage_factor, source_skill_def=skill_def
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

    if random.random() < skill_config.get("rage_reduction_chance", 0.15):
        rage_reduction = skill_config.get("rage_reduction", 300.0)
        if rage_reduction > 0 and opponent_army.current_rage > 0:
            actual = min(opponent_army.current_rage, float(rage_reduction))
            effect_data = {
                "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                "name": EFFECT_NAME_DELAYED_RAGE_REDUCTION,
                "duration": 0,
                "config": {"rage_reduction": actual},
                "activate_next_round": True,
            }
            created = opponent_army._create_and_add_single_effect(
                effect_data, skill_id, triggering_army, opponent_army, triggering_army
            )
            if created:
                an_effect_happened = True
                log_details.append((f"Reduces enemy rage by {actual:.0f} next round.", None))

    return an_effect_happened, log_details


def handle_plugin_rapid_defense(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    buff_mag = skill_config.get("buff_magnitude", 0.40)
    buff_dur = skill_config.get("buff_duration", 2)
    buff_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_RAPID_DEFENSE_BUFF,
        "stat_to_mod": StatType.BASE_DEFENSE_MULTIPLIER,
        "magnitude": buff_mag,
        "duration": buff_dur,
        "activate_next_round": True,
    }
    created_buff = triggering_army._create_and_add_single_effect(
        buff_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_buff:
        an_effect_happened = True
        log_details.append((f"Gains defense buff {buff_mag * 100:.0f}% for {buff_dur + 1} rounds (starting next round).", None))

    return an_effect_happened, log_details


def handle_plugin_rare_viking_hymn(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    buff_mag = skill_config.get("buff_magnitude", 0.20)
    buff_dur = skill_config.get("buff_duration", 2)
    buff_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_RARE_VIKING_HYMN_ATTACK_BUFF,
        "stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER,
        "magnitude": buff_mag,
        "duration": buff_dur,
        "activate_next_round": True,
    }
    created_buff = triggering_army._create_and_add_single_effect(
        buff_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_buff:
        an_effect_happened = True
        log_details.append((f"Gains attack buff {buff_mag * 100:.0f}% for {buff_dur + 1} rounds (starting next round).", None))

    return an_effect_happened, log_details


def handle_plugin_rare_defense_up(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    buff_mag = skill_config.get("buff_magnitude", 0.20)
    buff_dur = skill_config.get("buff_duration", 2)
    buff_data = {
        "effect_type": EffectType.STAT_MOD,
        "name": EFFECT_NAME_RARE_DEFENSE_UP_BUFF,
        "stat_to_mod": StatType.BASE_DEFENSE_MULTIPLIER,
        "magnitude": buff_mag,
        "duration": buff_dur,
        "activate_next_round": True,
    }
    created_buff = triggering_army._create_and_add_single_effect(
        buff_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_buff:
        an_effect_happened = True
        log_details.append((f"Gains defense buff {buff_mag * 100:.0f}% for {buff_dur + 1} rounds (starting next round).", None))

    return an_effect_happened, log_details


def handle_plugin_rest_and_counterattack(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    heal_factor = skill_config.get("heal_factor", 400.0)
    if heal_factor > 0:
        healed_amount = triggering_army.calculate_and_add_pending_healing(
            heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
        )
        if healed_amount > 0:
            an_effect_happened = True
            log_details.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_factor}).", None))

    shield_factor = skill_config.get("shield_factor", 400.0)
    shield_duration = skill_config.get("shield_duration", 2)
    shield_name = skill_config.get("shield_effect_name", EFFECT_NAME_REST_AND_COUNTERATTACK_SHIELD)
    shield_data = {
        "effect_type": EffectType.SHIELD,
        "name": shield_name,
        "duration": shield_duration,
        "magnitude_calc_type": "dynamic_shield_resistance_v1",
        "shield_factor": shield_factor,
        "activate_next_round": True,
    }
    created_shield = triggering_army._create_and_add_single_effect(
        shield_data, skill_id, triggering_army, triggering_army, opponent_army
    )
    if created_shield:
        an_effect_happened = True
        est_mag = simulator._calculate_shield_magnitude_for_logging(
            triggering_army, opponent_army, float(shield_factor)
        ) if simulator else created_shield.magnitude
        log_details.append((f"Grants shield ({created_shield.get_functionality_description()}) active for next {shield_duration + 1} rounds. Est. Mag: {est_mag:.0f}", None))

    return an_effect_happened, log_details


def handle_plugin_bloodstained_icefield(
        triggering_army: ArmyRef, opponent_army: ArmyRef,
        skill_def: SkillDefinition, event_data: Optional[Dict[str, Any]],
        simulator: GameSimulatorRef
) -> Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]:
    an_effect_happened = False
    log_details: List[Tuple[str, Optional[Dict[str, Any]]]] = []
    skill_config = skill_def.get("config", {})
    skill_id = skill_def["id"]

    enemy_has_slow = any(eff.name == EFFECT_NAME_SLOW_DEBUFF for eff in opponent_army.active_effects)
    enemy_has_bleed = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BLEED
        for eff in opponent_army.active_effects
    )
    if not (enemy_has_slow or enemy_has_bleed):
        return False, []

    heal_factor = skill_config.get("heal_factor", 700.0)
    if heal_factor > 0:
        healed_amount = triggering_army.calculate_and_add_pending_healing(
            heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
        )
        if healed_amount > 0:
            an_effect_happened = True
            log_details.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_factor}).", None))

    return an_effect_happened, log_details


def handle_plugin_this_too_shall_pass(
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

    skill_id = skill_def["id"]
    enemy_has_poison = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.POISON
        for eff in opponent_army.active_effects
    )
    enemy_has_burn = any(
        eff.effect_type == EffectType.DAMAGE_OVER_TIME and eff.config.get("dot_type") == DoTType.BURN
        for eff in opponent_army.active_effects
    )

    if enemy_has_poison:
        damage_factor = skill_config.get("damage_factor", 1000.0)
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
                {"damage_done_hp": round(raw_logged_damage), "absorbed_hp": round(absorbed), "potential_kills": kills},
            ))

    if enemy_has_burn:
        heal_factor = skill_config.get("heal_factor", 1000.0)
        if heal_factor > 0:
            healed_amount = triggering_army.calculate_and_add_pending_healing(
                heal_factor, triggering_army, opponent_army, source_skill_id=skill_id
            )
            if healed_amount > 0:
                an_effect_happened = True
                log_details.append((f"Heals self for {healed_amount:.0f} HP (Factor: {heal_factor}).", None))

    return an_effect_happened, log_details
