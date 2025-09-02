# === File: skill_definitions.py ===
import copy
from typing import Dict, Any
from .enums import (
    EffectType,
    SkillTriggerType,
    StatType,
    SkillType,
    DoTType,
    PluginSkillLabel,
)
from .skill_system import SkillDefinition
from .constants import *

from .skill_logic.talent_handlers import (
    handle_talent_blade_counter, handle_talent_shield_of_resistance, handle_talent_revenge_echo,
    handle_talent_healing_hymn, handle_talent_hold_fast, handle_talent_determined_defense,
    handle_talent_tit_for_tat, handle_talent_serpents_rage, handle_talent_full_focus,
    handle_talent_power_of_silence, handle_talent_deadly_raid,
    handle_talent_strategize, handle_talent_adaptable_to_changes,
    handle_talent_hunting_experience, handle_talent_targeted_strike,
    handle_talent_patient_waiting, handle_talent_revolutionary_resolve,
    handle_talent_adaptable_agility, handle_talent_battle_preparation,
    handle_talent_coordinated_strike, handle_talent_slow_strike,
    handle_talent_trained_up, handle_talent_fatal_bleeding,
    handle_talent_steadfast_armor, handle_talent_fearless_pursuit,
    handle_talent_saintly_guardian, handle_talent_war_blessing, handle_talent_judgement_mark,
    # LAGERTHA TALENT HANDLERS
    handle_talent_chiefs_might, handle_talent_fatal_strike,
    handle_talent_high_fighting_spirit, handle_talent_low_whispers,
    handle_talent_specter_lycan_assault, handle_talent_amazing_attack,
    # OLENA TALENT HANDLERS
    handle_talent_multi_shot_arrow, handle_talent_poised_shot,
    # ARTUR TALENT HANDLER
    handle_talent_pent_up_anger,
    # GREGORY TALENT HANDLER
    handle_talent_missing_beat,
    # JENS TALENT HANDLERS
    handle_talent_godly_wrath, handle_talent_divine_punishment,
    # FREYDIS TALENT HANDLERS
    handle_talent_heroic_blessing, handle_talent_battle_chime, handle_talent_flames_judgment
)
from .skill_logic.base_skill_handlers import (
    handle_base_skill_planned_attack, handle_base_skill_flame_guardian,
    handle_base_skill_sanctity_of_life, handle_base_skill_zeal,
    handle_base_skill_snake_eyes, handle_base_skill_ready_to_pounce,
    handle_base_skill_threatening_blade, handle_base_skill_unyielding_will,
    handle_base_skill_heart_of_tolerance,
    handle_base_skill_rapid_fire,
    # OLENA BASE SKILL HANDLER
    handle_base_skill_enchanted_arrow,
    # ARTUR BASE SKILL HANDLER
    handle_base_skill_torment,
    # GREGORY BASE SKILL HANDLER
    handle_base_skill_drumming_disturbance,
    # JENS BASE SKILL HANDLER
    handle_base_skill_divine_energize,
    # FREYDIS BASE SKILL HANDLER
    handle_base_skill_blades_judgment,
    handle_base_skill_tough_choice, handle_rage_bloody_pillage,
    handle_base_skill_fleet_raider, handle_rage_raging_smash,
    handle_base_skill_crippling_pursuit, handle_rage_lethal_fracture,
    handle_base_skill_berserk_fury, handle_rage_brutal_blow,
    handle_base_skill_judgements_fury,
    handle_base_skill_shield_breaker,
    handle_base_skill_plague, handle_base_skill_throwing_axe
)
from .skill_logic.plugin_skill_handlers import (
    handle_plugin_divine_blessing, handle_plugin_shield_support, handle_plugin_freyas_blessing,
    handle_plugin_hymn_of_life, handle_plugin_chance_of_reversal, handle_plugin_shield_reflector,
    handle_plugin_first_strike_control, handle_plugin_shield_attacker, handle_plugin_awakening,
    handle_plugin_baldr_blessing, handle_plugin_lokis_trick, handle_plugin_odins_asylum,
    handle_plugin_thors_determination, handle_plugin_disarmament, handle_plugin_fiery_rage,
    handle_plugin_fiery_detonation, handle_plugin_rage_leech, handle_plugin_enchanted_pursuit,
    handle_plugin_blow_of_chaos, handle_plugin_on_alert, handle_plugin_helas_curse,
    handle_plugin_fearless, handle_plugin_joint_offense, handle_plugin_bloody_rage,
    handle_plugin_silencer, handle_plugin_enrage, handle_plugin_blessed_negation,
    handle_plugin_wild_indulgence, handle_plugin_breaking_free, handle_plugin_battle_hymn,
    handle_plugin_rapid_attack, handle_plugin_rage_purge, handle_plugin_blessed_by_fate,
    handle_plugin_tidal_attack, handle_plugin_splinter, handle_plugin_hale_of_thorns,
    handle_plugin_halo_of_sacrifice, handle_plugin_heightened_chance, handle_plugin_tenacity,
    handle_plugin_blessed_healing, handle_plugin_dampened_spirits, handle_plugin_rapid_defense,
    handle_plugin_rare_viking_hymn, handle_plugin_rare_defense_up,
    handle_plugin_rest_and_counterattack, handle_plugin_bloodstained_icefield,
    handle_plugin_this_too_shall_pass
)
from .skill_logic.rage_skill_handlers import (
    handle_rage_sharp_pursuit, handle_rage_sacred_blade, handle_rage_vital_blessing,
    handle_rage_vanquishing_blade, handle_generic_damage_rage_skill,
    handle_rage_skill_snakes_frenzy, handle_rage_skill_paralyzing_terror,
    handle_rage_skill_intimidation, handle_rage_skill_viking_sage,
    handle_rage_holy_enlightenment,
    handle_rage_raining_arrows,
    # OLENA RAGE SKILL HANDLER
    handle_rage_concentration,
    # ARTUR RAGE SKILL HANDLER
    handle_rage_incineration,
    # GREGORY RAGE SKILL HANDLER
    handle_rage_inspiring_dance,
    # JENS RAGE SKILL HANDLER
    handle_rage_skill_heavenly_descent,
    # FREYDIS RAGE SKILL HANDLER
    handle_rage_desperate_strike,
    handle_rage_ruling_trial,
    handle_rage_showdown,
    handle_rage_undead_harvest,
    handle_rage_all_kill
)
from .skill_logic.utility_skill_handlers import (
    handle_generic_single_damage_skill,
    handle_generic_heal_skill,
)

# Utility mappings to generate human-readable skill descriptions
TRIGGER_PHRASES = {
    SkillTriggerType.PASSIVE: "Passive",
    SkillTriggerType.ON_DEALING_DAMAGE: "On dealing damage",
    SkillTriggerType.ON_BASIC_ATTACK: "On basic attack",
    SkillTriggerType.ON_COUNTER_ATTACK: "On counter-attack",
    SkillTriggerType.ON_HIT_BY_BASIC_ATTACK: "On being hit by basic attack",
    SkillTriggerType.ON_RECEIVING_HEALING: "On receiving healing",
    SkillTriggerType.CHANCE_PER_ROUND: "Each round",
    SkillTriggerType.RAGE_SKILL: "Rage skill",
    SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE: "On receiving rage skill damage",
    SkillTriggerType.ON_OWN_RAGE_SKILL_CAST: "After own rage skill",
    SkillTriggerType.ON_OWN_COMMAND_SKILL_CAST: "After own command skill",
}

STAT_PHRASES = {
    StatType.BASE_ATTACK_MULTIPLIER: "attack",
    StatType.BASE_DEFENSE_MULTIPLIER: "defense",
    StatType.BASE_HP_MULTIPLIER: "HP",
    StatType.EFFECTIVE_ATTACK_MULTIPLIER: "attack",
    StatType.EFFECTIVE_DEFENSE_MULTIPLIER: "defense",
    StatType.EFFECTIVE_HP_MULTIPLIER: "HP",
    StatType.BASIC_DAMAGE_ADJUST: "basic attack damage",
    StatType.COUNTER_DAMAGE_ADJUST: "counter damage",
    StatType.REACTIVE_SKILL_DAMAGE_ADJUST: "reactive skill damage",
    StatType.GENERAL_DAMAGE_MODIFIER: "damage dealt",
    StatType.DAMAGE_TAKEN_MULTIPLIER: "damage taken",
    StatType.SHIELD_STRENGTH_MODIFIER: "shield strength",
    StatType.HEAL_ADJUSTMENT: "healing",
    StatType.BLEED_DAMAGE_BOOST: "bleed damage",
    StatType.POISON_DAMAGE_BOOST: "poison damage",
    StatType.BURN_DAMAGE_BOOST: "burn damage",
    StatType.BLEED_DAMAGE_REDUCTION: "bleed damage taken",
    StatType.POISON_DAMAGE_REDUCTION: "poison damage taken",
    StatType.BURN_DAMAGE_REDUCTION: "burn damage taken",
    StatType.COMMAND_SKILL_DAMAGE_MODIFIER: "command skill damage",
    StatType.COOPERATION_TRIGGER_RATE_MODIFIER: "cooperation trigger rate",
    StatType.COOPERATION_SKILL_DAMAGE_MODIFIER: "cooperation skill damage",
}


def _format_duration(duration: int | float | None) -> str:
    if duration is None:
        return ""
    if duration == -1:
        return "permanently"
    rounds = int(duration)
    return f"for {rounds} round{'s' if rounds != 1 else ''}"


def _format_effect_name(name: str) -> str:
    return name.replace("_", " ").replace("DEBUFF", "").replace("Debuff", "").title().strip()


def _describe_effect(effect: Dict[str, Any]) -> str:
    etype = effect.get("effect_type")
    if etype == EffectType.STAT_MOD:
        stat = STAT_PHRASES.get(effect.get("stat_to_mod"), str(effect.get("stat_to_mod")))
        mag = effect.get("magnitude", 0)
        mag_pct = f"{abs(mag) * 100:.0f}%"
        verb = "increase" if mag >= 0 else "reduce"
        dur = _format_duration(effect.get("duration"))
        return f"{verb} {stat} by {mag_pct} {dur}".strip()
    if etype == EffectType.IMMUNITY:
        immune_name = effect.get("immune_to") or effect.get("name", "")
        dur = _format_duration(effect.get("duration"))
        return f"gain {_format_effect_name(immune_name)} immunity {dur}".strip()
    if etype == EffectType.SHIELD:
        dur = _format_duration(effect.get("duration"))
        return f"gain a shield {dur}".strip()
    if etype in (EffectType.HEAL_INSTANT, EffectType.HEAL_OVER_TIME):
        dur = _format_duration(effect.get("duration"))
        prefix = "heal" if etype == EffectType.HEAL_INSTANT else "heal over time"
        return f"{prefix} {dur}".strip()
    if etype == EffectType.DAMAGE_OVER_TIME:
        dot_type = effect.get("dot_type")
        dot_name = dot_type.value.title() if dot_type else "Damage"
        dur = _format_duration(effect.get("duration"))
        return f"inflict {dot_name.lower()} {dur}".strip()
    return effect.get("name", "special effect")


def _effects_from_config(cfg: Dict[str, Any]) -> list[str]:
    effects: list[str] = []
    # Generic factor based effects
    for key, value in cfg.items():
        if key.startswith("damage_factor"):
            effects.append(f"deal {value:.0f}% damage")
        elif key.startswith("heal_factor"):
            effects.append(f"heal {value:.0f}%")
        elif key == "shield_factor":
            dur = _format_duration(cfg.get("shield_duration"))
            effects.append(f"gain a shield {dur}".strip())
        elif key == "buff_magnitude":
            dur = _format_duration(cfg.get("buff_duration"))
            effects.append(f"increase stats by {value * 100:.0f}% {dur}".strip())
        elif key == "reduction_magnitude":
            dur = _format_duration(cfg.get("reduction_duration"))
            effects.append(f"reduce stats by {abs(value) * 100:.0f}% {dur}".strip())
        elif key.endswith("_buff_magnitude") or key.endswith("_reduction_magnitude"):
            base = key.replace("_buff_magnitude", "").replace("_reduction_magnitude", "")
            dur = cfg.get(base + "_buff_duration") or cfg.get(base + "_reduction_duration") or cfg.get(base + "_duration")
            mag = value * 100
            verb = "increase" if key.endswith("_buff_magnitude") and value >= 0 else "reduce"
            effects.append(f"{verb} {base.replace('_', ' ')} by {abs(mag):.0f}% {_format_duration(dur)}".strip())
        elif key.endswith("_chance"):
            base = key[:-7]
            chance = value * 100
            if base + "_duration" in cfg:
                dur = _format_duration(cfg.get(base + "_duration"))
                effects.append(f"{chance:.0f}% chance to {base.replace('_', ' ')} {dur}".strip())
            elif base + "_factor" in cfg:
                factor = cfg.get(base + "_factor")
                effects.append(f"{chance:.0f}% chance to {base.replace('_', ' ')} {factor:.0f}%")
            else:
                effects.append(f"{chance:.0f}% chance to {base.replace('_', ' ')}")
        elif key == "rage_reduction":
            effects.append(f"reduce rage by {value}")
    if "rage_cost" in cfg:
        effects.append(f"costs {cfg['rage_cost']} rage")
    return effects


def build_skill_description(skill: Dict[str, Any]) -> str:
    trigger = TRIGGER_PHRASES.get(skill.get("trigger"), str(skill.get("trigger")))
    if skill.get("trigger") == SkillTriggerType.PASSIVE:
        prefix = f"{trigger}:"
    else:
        prefix = trigger
    chance = skill.get("trigger_chance")
    chance_part = f" {chance * 100:.0f}% chance to" if chance is not None and chance < 1 else ""
    effect_parts: list[str] = []
    for eff in skill.get("effects_to_apply", []):
        effect_parts.append(_describe_effect(eff))
    for sub in skill.get("sub_effects", []):
        sub_desc = _describe_effect(sub.get("effect_to_apply", {}))
        sub_chance = sub.get("chance")
        if sub_chance is not None:
            effect_parts.append(f"{sub_chance * 100:.0f}% chance to {sub_desc}")
        else:
            effect_parts.append(sub_desc)
    if "config" in skill:
        effect_parts.extend(_effects_from_config(skill["config"]))
    if not effect_parts:
        effect_parts.append("trigger its effect")
    if len(effect_parts) > 1:
        joiner = " or " if skill.get("sub_effects") else " and "
        effects_text = joiner.join(effect_parts)
    else:
        effects_text = effect_parts[0]
    if chance_part:
        description = f"{prefix}, {chance_part} {effects_text}"
    else:
        description = f"{prefix}, {effects_text}" if skill.get("trigger") != SkillTriggerType.PASSIVE else f"{prefix} {effects_text}"
    cooldown = skill.get("config", {}).get("cooldown_rounds")
    if cooldown:
        description += f" (cooldown {cooldown} rounds)"
    rage_cost = skill.get("rage_cost")
    if rage_cost:
        description += f" (costs {rage_cost} rage)"
    return " ".join(description.split())

SKILL_REGISTRY_GLOBAL: Dict[str, SkillDefinition] = {
    # --- Talent Skills ---
    # ... (All existing talents for Leif, Laird, Yvette, Heahmund, Sigurd, Wooder, Ivana, Ragnar, Athelstan, Verdandi) ...
    "talent_blade_counter": {
        "id": "talent_blade_counter", "name": "Blade Counter", "description": "Blade Counter effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_blade_counter,
        "labels": [PluginSkillLabel.REACTIVE],
        "sub_effects": [
            {"name_suffix": "Damage Boost", "chance": 0.15, "effect_to_apply": {
                "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_BLADE_COUNTER_BOOST,
                "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": 0.30, "duration": 3,
                "activate_next_round": True}},
            {"name_suffix": "Broken Blade Immunity", "chance": 0.25, "effect_to_apply": {
                "effect_type": EffectType.IMMUNITY, "name": EFFECT_NAME_BLADE_COUNTER_IMMUNITY,
                "immune_to": EFFECT_NAME_BROKEN_BLADE_DEBUFF, "duration": 3,
                "activate_next_round": True}}
        ]
    },
    "talent_shield_of_resistance": {
        "id": "talent_shield_of_resistance", "name": "Shield of Resistance", "description": "Shield of Resistance effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_talent_shield_of_resistance,
        "effects_to_apply": [{"effect_type": EffectType.SHIELD, "name": EFFECT_NAME_SHIELD_OF_RESISTANCE,
                              "duration": 1, "magnitude_calc_type": "dynamic_shield_resistance_v1",
                              "shield_factor": 950.0, "activate_next_round": True}]
    },
    "talent_revenge_echo": {
        "id": "talent_revenge_echo", "name": "Revenge Echo", "description": "Revenge Echo effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.25, "target": "SELF",
        "logic_handler": handle_talent_revenge_echo,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 550.0, "conditional_buff": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_REVENGE_ECHO_COUNTER_BOOST,
            "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": 0.30, "duration": 1,
            "activate_next_round": True}}
    },
    "talent_holy_shield": {
        "id": "talent_holy_shield", "name": "Holy Shield", "description": "Holy Shield effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_HOLY_SHIELD_BOOST,
                              "stat_to_mod": StatType.SHIELD_STRENGTH_MODIFIER, "magnitude": 0.25, "duration": -1}]
    },
    "talent_sacred_counter": {
        "id": "talent_sacred_counter", "name": "Sacred Counter", "description": "Sacred Counter effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 600.0}
    },
    "talent_divine_resistance": {
        "id": "talent_divine_resistance", "name": "Divine Resistance", "description": "Divine Resistance effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_DIVINE_RESISTANCE_BASIC_DMG_RED,
             "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": -0.40, "duration": -1,
             "config_filter": {"attack_type": "BASIC"}},
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_DIVINE_RESISTANCE_COUNTER_BOOST,
             "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": 0.40, "duration": -1}
        ]
    },
    "talent_healing_chords": {
        "id": "talent_healing_chords", "name": "Healing Chords", "description": "Healing Chords effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_HEALING_CHORDS_BOOST,
                              "stat_to_mod": StatType.HEAL_ADJUSTMENT, "magnitude": 0.20, "duration": -1}]
    },
    "talent_healing_hymn": {
        "id": "talent_healing_hymn", "name": "Healing Hymn", "description": "Healing Hymn effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.25, "target": "ENEMY",
        "logic_handler": handle_talent_healing_hymn,
        "config": {"damage_factor": 900.0}
    },
    "talent_horn_of_countering": {
        "id": "talent_horn_of_countering", "name": "Horn of Countering", "description": "Horn of Countering effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 1000.0}
    },
    "talent_hold_fast": {
        "id": "talent_hold_fast", "name": "Hold Fast", "description": "Hold Fast effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.15, "target": "SELF",
        "logic_handler": handle_talent_hold_fast,
        "config": {"shield_factor": 600.0, "shield_duration": 1,
                   "cooldown_rounds": 4, "effect_name": EFFECT_NAME_HOLD_FAST_SHIELD}
    },
    "talent_determined_defense": {
        "id": "talent_determined_defense", "name": "Determined Defense", "description": "Determined Defense effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_talent_determined_defense,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 300.0, "heal_factor": 300.0, "debuff_duration": 0,
                   "debuff_name": EFFECT_NAME_DETERMINED_DEFENSE_BROKEN_BLADE, "cooldown_rounds": 3}
    },
    "talent_tit_for_tat": {
        "id": "talent_tit_for_tat", "name": "Tit for Tat", "description": "Tit for Tat effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_tit_for_tat,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 500.0, "reduction_magnitude": -0.30, "reduction_duration": 0,
                   "reduction_effect_name": EFFECT_NAME_TIT_FOR_TAT_DMG_RED}
    },
    "talent_fiery_snake_spirit": {
        "id": "talent_fiery_snake_spirit", "name": "Fiery Snake Spirit", "description": "Fiery Snake Spirit effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_FIERY_SNAKE_SPIRIT_H1_BOOST,
            "stat_to_mod": StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER, "magnitude": 0.30,
            "duration": -1, "activate_next_round": False}]
    },
    "talent_serpents_rage": {
        "id": "talent_serpents_rage", "name": "Serpent's Rage", "description": "Serpent's Rage effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 900.0, "trigger_interval": 9}
    },
    "talent_full_focus": {
        "id": "talent_full_focus", "name": "Full Focus", "description": "Full Focus effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.35, "target": "ENEMY",
        "logic_handler": handle_talent_full_focus,
        "config": {"damage_factor": 700.0}
    },
    "talent_massive_shield": {
        "id": "talent_massive_shield", "name": "Massive Shield", "description": "Massive Shield effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_MASSIVE_SHIELD_BOOST,
                              "stat_to_mod": StatType.SHIELD_STRENGTH_MODIFIER, "magnitude": 0.15,
                              "duration": -1, "activate_next_round": False}]
    },
    "talent_bold_charge": {
        "id": "talent_bold_charge", "name": "Bold Charge", "description": "Bold Charge effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 250.0}
    },
    "talent_specialized_attack": {
        "id": "talent_specialized_attack", "name": "Specialized Attack", "description": "Specialized Attack effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 0.50, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 1250.0}
    },
    "talent_power_of_silence": {
        "id": "talent_power_of_silence", "name": "Power of Silence", "description": "Power of Silence effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 0.50, "target": "ENEMY",
        "logic_handler": handle_talent_power_of_silence,
        "config": {"rage_reduction": 125}
    },
    "talent_combat_focus": {
        "id": "talent_combat_focus", "name": "Combat Focus", "description": "Combat Focus effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1000.0, "trigger_interval": 9}
    },
    "talent_time_crunch": {
        "id": "talent_time_crunch", "name": "Time Crunch", "description": "Time Crunch effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "config": {"damage_factor": 1.0, "trigger_interval": 9}
    },
    "talent_dragons_blood": {
        "id": "talent_dragons_blood", "name": "Dragon's Blood", "description": "Dragon's Blood effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "config": {"damage_factor": 2.0, "trigger_interval": 9}
    },
    "talent_deadly_raid": {
        "id": "talent_deadly_raid", "name": "Deadly Raid", "description": "Deadly Raid effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 0.25, "target": "ENEMY",
        "logic_handler": handle_talent_deadly_raid,
        "config": {"damage_factor": 600.0}
    },
    "talent_born_king": {
        "id": "talent_born_king", "name": "Born King", "description": "Born King effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "config": {"damage_factor": 3.0, "trigger_interval": 9}
    },
    "talent_erudite": {
        "id": "talent_erudite", "name": "Erudite", "description": "Erudite effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_ERUDITE_BURN_BOOST,
             "stat_to_mod": StatType.BURN_DAMAGE_BOOST, "magnitude": 0.15, "duration": -1},
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_ERUDITE_POISON_BOOST,
             "stat_to_mod": StatType.POISON_DAMAGE_BOOST, "magnitude": 0.10, "duration": -1}
        ]
    },
    "talent_strategize": {
        "id": "talent_strategize", "name": "Strategize", "description": "Strategize effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_strategize,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "trigger_interval": 9,
            "command_buff_magnitude": 0.35,
            "command_buff_duration": 2,
            "heal_chance_if_enemy_burn": 0.50,
            "heal_factor": 600.0
        }
    },
    "talent_adaptable_to_changes": {
        "id": "talent_adaptable_to_changes", "name": "Adaptable to Changes", "description": "Adaptable to Changes effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_adaptable_to_changes,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "trigger_interval": 6,
            "damage_factor": 650.0,
            "poison_chance": 0.50,
            "poison_factor": 250.0,
            "poison_duration": 1
        }
    },
    "talent_hunting_instinct": {
        "id": "talent_hunting_instinct", "name": "Hunting Instinct", "description": "Hunting Instinct effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_HUNTING_INSTINCT_BURN_BOOST,
             "stat_to_mod": StatType.BURN_DAMAGE_BOOST, "magnitude": 0.18, "duration": -1}
        ]
    },
    "talent_hunting_experience": {
        "id": "talent_hunting_experience", "name": "Hunting Experience", "description": "Hunting Experience effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_hunting_experience,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "trigger_interval": 9,
            "burn_factor": 500.0,
            "burn_duration": 1
        }
    },
    "talent_targeted_strike": {
        "id": "talent_targeted_strike", "name": "Targeted Strike", "description": "Targeted Strike effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_targeted_strike,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "trigger_interval": 6,
            "damage_factor": 550.0,
            "boosted_damage_factor": 1100.0
        }
    },
    # --- OLENA TALENTS ---
    "talent_scorching_arrow": {
        "id": "talent_scorching_arrow", "name": "Scorching Arrow", "description": "Scorching Arrow effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SCORCHING_ARROW_BURN_BOOST,
             "stat_to_mod": StatType.BURN_DAMAGE_BOOST, "magnitude": 0.15, "duration": -1}
        ]
    },
    "talent_multi_shot_arrow": {
        "id": "talent_multi_shot_arrow", "name": "Multi-Shot Arrow", "description": "Multi-Shot Arrow effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 0.50, "target": "ENEMY",
        "logic_handler": handle_talent_multi_shot_arrow, # Uses generic damage, but specific handler for clarity
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 750.0}
    },
    "talent_poised_shot": {
        "id": "talent_poised_shot", "name": "Poised Shot", "description": "Poised Shot effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_poised_shot,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {
            "damage_factor": 575.0,
            "rage_reduction_chance": 0.15,
            "rage_reduction_amount": 150
        }
    },
    # --- Artur Talents ---
    "talent_hellfire_shelter": {
        "id": "talent_hellfire_shelter", "name": "Hellfire Shelter", "description": "Hellfire Shelter effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_HELLFIRE_SHELTER_COUNTER_REDUCTION,
            "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": -0.40, "duration": -1,
            "config_filter": {"attack_type": "COUNTER"}
        }]
    },
    "talent_pent_up_anger": {
        "id": "talent_pent_up_anger", "name": "Pent-Up Anger", "description": "Pent-Up Anger effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_pent_up_anger,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "rage_gain": 300}
    },
    "talent_furious_fire": {
        "id": "talent_furious_fire", "name": "Furious Fire", "description": "Furious Fire effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1100.0, "trigger_interval": 6}
    },
    "talent_heroic_blessing": {
        "id": "talent_heroic_blessing", "name": "Heroic Blessing", "description": "Heroic Blessing effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": handle_talent_heroic_blessing,
        "config": {"debuff_duration": 29, "burn_boost_magnitude": 0.15}
    },
    "talent_battle_chime": {
        "id": "talent_battle_chime", "name": "Battle Chime", "description": "Battle Chime effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_battle_chime,
        "config": {"trigger_interval": 9, "damage_factor": 800.0, "rage_gain_if_lower": 50}
    },
    "talent_flames_judgment": {
        "id": "talent_flames_judgment", "name": "Flame's Judgment", "description": "Flame's Judgment effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_OWN_COMMAND_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_flames_judgment,
        "config": {"damage_factor": 1000.0, "damage_chance": 0.30}
    },
    # --- Gregory Talents ---
    "talent_great_morale": {
        "id": "talent_great_morale", "name": "Great Morale", "description": "Great Morale effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_GREAT_MORALE_BUFF,
                               "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": 0.30,
                               "duration": -1, "activate_next_round": False}]
    },
    "talent_missing_beat": {
        "id": "talent_missing_beat", "name": "Missing Beat", "description": "Missing Beat effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_talent_missing_beat,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 400.0, "slow_chance": 0.25, "slow_duration": 1}
    },
    "talent_excite": {
        "id": "talent_excite", "name": "Excite", "description": "Excite effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 0.40, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 1800.0}
    },
    # --- Jens Talents ---
    "talent_godly_wrath": {
        "id": "talent_godly_wrath", "name": "Godly Wrath", "description": "Godly Wrath effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_godly_wrath,
        "config": {"duration": 29, "magnitude": 0.06}
    },
    "talent_divine_blite": {
        "id": "talent_divine_blite", "name": "Divine Blite", "description": "Divine Blite effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_generic_heal_skill,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"heal_factor": 450.0}
    },
    "talent_divine_punishment": {
        "id": "talent_divine_punishment", "name": "Divine Punishment", "description": "Divine Punishment effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_divine_punishment,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 0.20, "damage_factor": 500.0}
    },

    # --- Base Skills ---
    # ... (All existing base skills for other heroes) ...
    "base_skill_snake_eyes": {
        "id": "base_skill_snake_eyes", "name": "Snake Eyes", "description": "Snake Eyes effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_snake_eyes,
        "config": { "damage_chance": 0.25, "damage_factor": 500.0, "debuff_chance": 0.20, "debuff_duration": 1 }
    },
    "base_skill_snakes_frenzy": {
        "id": "base_skill_snakes_frenzy", "name": "Snake's Frenzy", "description": "Snake's Frenzy effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_snakes_frenzy,
        "config": {"damage_factor": 1600.0, "buff_magnitude": 0.15, "buff_duration": 1}
    },
    "base_skill_ready_to_pounce": {
        "id": "base_skill_ready_to_pounce", "name": "Ready to Pounce", "description": "Ready to Pounce effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_ready_to_pounce,
        "config": {"buff_magnitude": 1.0, "buff_duration": 1}
    },
    "base_skill_paralyzing_terror": {
        "id": "base_skill_paralyzing_terror", "name": "Paralyzing Terror", "description": "Paralyzing Terror effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_paralyzing_terror,
        "config": {"damage_factor": 450.0, "shield_factor": 700.0, "shield_duration": 2}
    },
    "base_skill_threatening_blade": {
        "id": "base_skill_threatening_blade", "name": "Threatening Blade", "description": "Threatening Blade effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.30, "target": "ENEMY",
        "logic_handler": handle_base_skill_threatening_blade,
        "config": {"damage_factor": 600.0, "defense_buff_magnitude": 0.30, "defense_buff_duration": 4}
    },
    "base_skill_intimidation": {
        "id": "base_skill_intimidation", "name": "Intimidation", "description": "Intimidation effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_intimidation,
        "config": {"damage_factor_hit1": 300.0, "damage_factor_hit2": 600.0,
                   "rage_reduction": 50, "silence_chance": 0.50, "silence_duration": 1}
    },
    "base_skill_unyielding_will": {
        "id": "base_skill_unyielding_will", "name": "Unyielding Will", "description": "Unyielding Will effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_unyielding_will,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"h2_rage_buff_magnitude": 0.20, "h2_rage_buff_duration": 2,
                   "heal_chance": 0.15, "heal_factor": 800.0}
    },
    "base_skill_viking_sage": {
        "id": "base_skill_viking_sage", "name": "Viking Sage", "description": "Viking Sage effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_viking_sage,
        "config": {"damage_factor": 1400.0, "atk_reduction_magnitude": -0.20, "atk_reduction_duration": 3}
    },
    "base_skill_sharp_pursuit": {
        "id": "base_skill_sharp_pursuit", "name": "Sharp Pursuit", "description": "Sharp Pursuit effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_sharp_pursuit,
        "config": {"damage_factor": 1500.0, "shield_factor": 600.0, "self_shield_duration": 1, "effect_name": EFFECT_NAME_SHARP_PURSUIT_SHIELD}
    },
    "base_skill_planned_attack": {
        "id": "base_skill_planned_attack", "name": "Planned Attack", "description": "Planned Attack effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.15, "target": "ENEMY",
        "logic_handler": handle_base_skill_planned_attack,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"hit1_damage_factor": 300.0, "hit2_damage_factor": 420.0}
    },
    "base_skill_flame_guardian": {
        "id": "base_skill_flame_guardian", "name": "Flame Guardian", "description": "Flame Guardian effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_flame_guardian,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 250.0, "shield_chance": 0.50, "shield_factor": 400.0,
                   "self_shield_duration": 1, "effect_name": EFFECT_NAME_FLAME_GUARDIAN_SHIELD}
    },
    "base_skill_sacred_blade": {
        "id": "base_skill_sacred_blade", "name": "Sacred Blade", "description": "Sacred Blade effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_sacred_blade,
        "config": {"damage_factor": 1400.0, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SACRED_BLADE_ATTACK_BOOST,
            "stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER, "magnitude": 0.20, "duration": 2,
            "unit_type_condition": "pikemen", "activate_next_round": True}}
    },
    "base_skill_sanctity_of_life": {
        "id": "base_skill_sanctity_of_life", "name": "Sanctity of Life", "description": "Sanctity of Life effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_sanctity_of_life,
        "config": {"heal_chance": 0.20, "heal_factor": 600.0, "buff_hero2_chance": 0.20,
                   "buff_details": {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SANCTITY_H2_RAGE_BOOST,
                                    "stat_to_mod": StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER,
                                    "magnitude": 0.20, "duration": 2, "activate_next_round": True}}
    },
    "base_skill_vital_blessing": {
        "id": "base_skill_vital_blessing", "name": "Vital Blessing", "description": "Vital Blessing effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "SELF",
        "logic_handler": handle_rage_vital_blessing,
        "config": {"heal_factor": 1400.0, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST,
            "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": 0.30, "duration": 4,
            "activate_next_round": True}}
    },
    "base_skill_zeal": {
        "id": "base_skill_zeal", "name": "Zeal", "description": "Zeal effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_zeal,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 750.0, "damage_chance": 0.20,
                   "debuff_removal_chance": 0.20, "cooldown_rounds": 3}
    },
    "base_skill_vanquishing_blade": {
        "id": "base_skill_vanquishing_blade", "name": "Vanquishing Blade", "description": "Vanquishing Blade effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_vanquishing_blade,
        "config": {"damage_factor": 1700.0, "heal_factor": 400.0, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_VANQUISHING_BLADE_REDUCTION,
            "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": -0.10, "duration": 1,
            "activate_next_round": True}}
    },
    "base_skill_delayed_rage_example": {
        "id": "base_skill_delayed_rage_example", "name": "Delayed Fury Burst", "description": "Delayed Fury Burst effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 0, "target": "ENEMY",
        "logic_handler": handle_generic_damage_rage_skill,
        "config": {"damage_factor": 1000.0}
    },
    "base_skill_heart_of_tolerance": {
        "id": "base_skill_heart_of_tolerance", "name": "Heart of Tolerance", "description": "Heart of Tolerance effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_heart_of_tolerance,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "trigger_interval": 9,
            "damage_factor": 900.0,
            "rage_reduction_chance": 0.35,
            "rage_reduction_amount": 50
        }
    },
    "base_skill_holy_enlightenment": {
        "id": "base_skill_holy_enlightenment", "name": "Holy Enlightenment", "description": "Holy Enlightenment effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_holy_enlightenment,
        "config": {
            "damage_factor": 1400.0,
            "burn_chance": 0.50,
            "burn_factor": 200.0,
            "burn_duration": 2,
            "debuff_chance": 0.50,
            "debuff_magnitude": 0.25,
            "debuff_duration": 2
        }
    },
    "base_skill_rapid_fire": { # Verdandi's skill
        "id": "base_skill_rapid_fire", "name": "Rapid Fire", "description": "Rapid Fire effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_rapid_fire,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "trigger_interval": 9,
            "damage_factor": 800.0,
            "rage_reduction_amount": 50 # No chance, direct reduction if skill triggers
        }
    },
    "base_skill_raining_arrows": { # Verdandi's skill
        "id": "base_skill_raining_arrows", "name": "Raining Arrows", "description": "Raining Arrows effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_raining_arrows,
        "config": {
            "damage_factor": 1800.0,
            "burn_factor": 300.0,
            "burn_duration": 1
        }
    },
    # --- OLENA BASE SKILLS ---
    "base_skill_enchanted_arrow": {
        "id": "base_skill_enchanted_arrow", "name": "Enchanted Arrow", "description": "Enchanted Arrow effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 0.35, "target": "ENEMY",
        "logic_handler": handle_base_skill_enchanted_arrow,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "burn_factor": 600.0,
            "burn_duration": 1 # For 2 active rounds (applied next round)
        }
    },
    "base_skill_concentration": {
        "id": "base_skill_concentration", "name": "Concentration", "description": "Concentration effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY", # Damage ENEMY, rage gain SELF
        "logic_handler": handle_rage_concentration,
        "config": {
            "damage_factor": 1250.0,
            "base_rage_gain": 100,      # Rage gained in N+1 and N+2
            "bonus_rage_if_burning": 200, # Additional rage in N+1 if enemy burning at cast
            "rage_gain_duration": 1      # Custom effect lasts for 2 processing ticks (N+1, N+2)
        }
    },
    "base_skill_torment": {
        "id": "base_skill_torment", "name": "Torment", "description": "Torment effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_torment,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "trigger_interval": 9,
            "damage_factor": 700.0,
            "burn_factor": 350.0,
            "burn_duration": 2
        }
    },
    "base_skill_incineration": {
        "id": "base_skill_incineration", "name": "Incineration", "description": "Incineration effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_incineration,
        "config": {
            "damage_factor": 1300.0,
            "burn_boost_chance": 0.50,
            "burn_boost_magnitude": 0.30,
            "burn_boost_duration": 3
        }
    },
    "base_skill_blades_judgment": {
        "id": "base_skill_blades_judgment", "name": "Blade's Judgment", "description": "Blade's Judgment effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_blades_judgment,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "trigger_interval": 9,
            "damage_factor": 240.0,
            "burn_factor": 240.0,
            "burn_duration": 2
        }
    },
    "base_skill_desperate_strike": {
        "id": "base_skill_desperate_strike", "name": "Desperate Strike", "description": "Desperate Strike effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_desperate_strike,
        "config": {
            "damage_factor": 800.0,
            "burn_factor": 350.0,
            "burn_duration": 3
        }
    },
    # --- Gregory Base Skills ---
    "base_skill_drumming_disturbance": {
        "id": "base_skill_drumming_disturbance", "name": "Drumming Disturbance", "description": "Drumming Disturbance effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_base_skill_drumming_disturbance,
        "config": {"heal_factor": 250.0, "heal_duration": 1,
                   "rage_reduction_mag": -0.10, "rage_reduction_duration": 1}
    },
    "base_skill_inspiring_dance": {
        "id": "base_skill_inspiring_dance", "name": "Inspiring Dance", "description": "Inspiring Dance effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_inspiring_dance,
        "config": {"bleed_factor": 400.0, "bleed_duration": 1,
                   "ally_buff_magnitude": 0.50, "ally_buff_duration": 4}
    },
    # --- Jens Base Skills ---
    "base_skill_divine_energize": {
        "id": "base_skill_divine_energize", "name": "Divine Energize", "description": "Divine Energize effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.25, "target": "ENEMY",
        "logic_handler": handle_base_skill_divine_energize,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 300.0, "vulnerability_magnitude": 0.20, "vulnerability_duration": 1}
    },
    "base_skill_heavenly_descent": {
        "id": "base_skill_heavenly_descent", "name": "Heavenly Descent", "description": "Heavenly Descent effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_heavenly_descent,
        "config": {"damage_factor": 825.0, "vulnerability_magnitude": 0.10, "vulnerability_duration": 3,
                   "bleed_factor": 0}
    },

    # --- Rollo Skills ---
    "talent_patient_waiting": {
        "id": "talent_patient_waiting", "name": "Patient and Waiting", "description": "Patient and Waiting effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_patient_waiting,
        "config": {"duration": 29, "buff_magnitude": 0.20, "damage_chance": 0.50, "damage_factor": 500.0}
    },
    "talent_revolutionary_resolve": {
        "id": "talent_revolutionary_resolve", "name": "Revolutionary Resolve", "description": "Revolutionary Resolve effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_revolutionary_resolve,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 0.40, "damage_factor": 1500.0, "slow_duration": 1}
    },
    "talent_adaptable_agility": {
        "id": "talent_adaptable_agility", "name": "Adaptable Agility", "description": "Adaptable Agility effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_adaptable_agility,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance_high": 0.25, "damage_factor": 900.0, "heal_chance_low": 0.20, "heal_factor": 500.0}
    },
    "base_skill_tough_choice": {
        "id": "base_skill_tough_choice", "name": "Tough Choice", "description": "Tough Choice effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_tough_choice,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"basic_buff": 0.30, "counter_debuff": -0.30, "heal_chance": 0.20, "heal_factor": 900.0}
    },
    "base_skill_bloody_pillage": {
        "id": "base_skill_bloody_pillage", "name": "Bloody Pillage", "description": "Bloody Pillage effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_bloody_pillage,
        "config": {"damage_factor": 1500.0, "bleed_factor": 350.0, "bleed_duration": 1}
    },

    # --- Harald Skills ---
    "talent_battle_preparation": {
        "id": "talent_battle_preparation", "name": "Battle Preparation", "description": "Battle Preparation effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_battle_preparation,
        "config": {"duration": 29, "buff_magnitude": 0.45}
    },
    "talent_coordinated_strike": {
        "id": "talent_coordinated_strike", "name": "Coordinated Strike", "description": "Coordinated Strike effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_talent_coordinated_strike,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 300.0, "buff_magnitude": 0.12, "buff_duration": 2, "damage_chance": 1.0}
    },
    "talent_slow_strike": {
        "id": "talent_slow_strike", "name": "Slow Strike", "description": "Slow Strike effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_slow_strike,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"buff_magnitude": 0.50, "damage_chance": 0.30, "damage_factor": 600.0}
    },
    "base_skill_fleet_raider": {
        "id": "base_skill_fleet_raider", "name": "Fleet Raider", "description": "Fleet Raider effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_fleet_raider,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 1.0, "damage_factor": 300.0,
                   "buff_magnitude": 0.25, "buff_duration": 4}
    },
    "base_skill_raging_smash": {
        "id": "base_skill_raging_smash", "name": "Raging Smash", "description": "Raging Smash effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_raging_smash,
        "config": {"damage_factor": 2000.0, "slow_duration": 3}
    },

    # --- Bjorn Skills ---
    "talent_trained_up": {
        "id": "talent_trained_up", "name": "Trained Up", "description": "Trained Up effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.25, "target": "ENEMY",
        "logic_handler": handle_talent_trained_up,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 300.0, "slow_chance": 0.30, "slow_duration": 1, "damage_chance": 1.0}
    },
    "talent_undefeated": {
        "id": "talent_undefeated", "name": "Undefeated", "description": "Undefeated effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_COORDINATED_STRIKE_BUFF,
                              "stat_to_mod": StatType.COOPERATION_SKILL_DAMAGE_MODIFIER, "magnitude": 0.15, "duration": -1}]
    },
    "talent_fatal_bleeding": {
        "id": "talent_fatal_bleeding", "name": "Fatal Bleeding", "description": "Fatal Bleeding effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_fatal_bleeding,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 6, "bleed_factor": 500.0, "bleed_duration": 1}
    },
    "base_skill_crippling_pursuit": {
        "id": "base_skill_crippling_pursuit", "name": "Crippling Pursuit", "description": "Crippling Pursuit effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_crippling_pursuit,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 1.0, "damage_factor": 500.0,
                   "extra_damage_factor": 250.0}
    },
    "base_skill_lethal_fracture": {
        "id": "base_skill_lethal_fracture", "name": "Lethal Fracture", "description": "Lethal Fracture effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_lethal_fracture,
        "config": {"damage_factor": 2000.0, "slow_duration": 2, "attack_buff": 0.15, "attack_duration": 2}
    },

    # --- Hobert Skills ---
    "talent_bold_shieldaxe": {
        "id": "talent_bold_shieldaxe", "name": "Bold Shieldaxe", "description": "Bold Shieldaxe effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_BOLD_SHIELDAXE_BUFF,
                              "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": 0.35, "duration": -1}]
    },
    "talent_fearless_pursuit": {
        "id": "talent_fearless_pursuit", "name": "Fearless Pursuit", "description": "Fearless Pursuit effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 350.0, "alt_damage_factor": 700.0}
    },
    "talent_steadfast_armor": {
        "id": "talent_steadfast_armor", "name": "Steadfast Armor", "description": "Steadfast Armor effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.30, "target": "ENEMY",
        "logic_handler": handle_talent_steadfast_armor,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"reduction": -0.28, "duration": 0, "slow_duration": 1}
    },
    "base_skill_berserk_fury": {
        "id": "base_skill_berserk_fury", "name": "Berserk Fury", "description": "Berserk Fury effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_berserk_fury,
        "config": {"loss_per_stack": 0.06, "basic_buff": 0.12, "rage_per_round": 3}
    },
    "base_skill_brutal_blow": {
        "id": "base_skill_brutal_blow", "name": "Brutal Blow", "description": "Brutal Blow effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_brutal_blow,
        "config": {"damage_factor": 1200.0, "shield_factor": 400.0, "shield_duration": 1,
                   "buff_removal_count": 2, "self_cleanse_count": 1}
    },

    # --- Helgar Skills ---
    "talent_saintly_guardian": {
        "id": "talent_saintly_guardian", "name": "Saintly Guardian", "description": "Saintly Guardian effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": handle_talent_saintly_guardian,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SAINTLY_GUARDIAN_SHIELD_BOOST,
                              "stat_to_mod": StatType.SHIELD_STRENGTH_MODIFIER, "magnitude": 0.35, "duration": -1}]
    },
    "talent_war_blessing": {
        "id": "talent_war_blessing", "name": "War Blessing", "description": "War Blessing effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.50, "target": "SELF",
        "logic_handler": handle_talent_war_blessing,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"shield_factor": 500.0, "shield_duration": 1}
    },
    "talent_judgement_mark": {
        "id": "talent_judgement_mark", "name": "Judgement Mark", "description": "Judgement Mark effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.50, "target": "ENEMY",
        "logic_handler": handle_talent_judgement_mark,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 350.0}
    },
    "base_skill_judgements_fury": {
        "id": "base_skill_judgements_fury", "name": "Judgement's Fury", "description": "Judgement's Fury effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_judgements_fury,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 1150.0, "marker_threshold": 20, "counter_buff": 0.45, "buff_duration": 1}
    },
    "rage_skill_ruling_trial": {
        "id": "rage_skill_ruling_trial", "name": "Ruling Trial", "description": "Ruling Trial effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_ruling_trial,
        "config": {"damage_factor": 1000.0, "low_hp_damage_factor": 1500.0, "extra_damage_factor": 800.0, "hp_threshold": 0.20}
    },

    # --- Lagertha Skills ---
    "talent_shieldaxe_attack": {
        "id": "talent_shieldaxe_attack", "name": "Shieldaxe Attack", "description": "Shieldaxe Attack effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SHIELDAXE_ATTACK_BLEED_BOOST,
                               "stat_to_mod": StatType.BLEED_DAMAGE_BOOST, "magnitude": 0.25, "duration": -1}]
    },
    "talent_chiefs_might": {
        "id": "talent_chiefs_might", "name": "Chief's Might", "description": "Chief's Might effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_talent_chiefs_might,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"bleed_factor": 400.0, "bleed_duration": 1}
    },
    "talent_fatal_strike": {
        "id": "talent_fatal_strike", "name": "Fatal Strike", "description": "Fatal Strike effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_fatal_strike,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 0.50, "damage_factor": 1000.0}
    },
    "base_skill_shield_breaker": {
        "id": "base_skill_shield_breaker", "name": "Shield Breaker", "description": "Shield Breaker effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_shield_breaker,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 550.0, "buff_magnitude": 0.50, "buff_duration": 1}
    },
    "rage_skill_showdown": {
        "id": "rage_skill_showdown", "name": "Showdown", "description": "Showdown effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_showdown,
        "config": {"damage_factor": 1500.0, "bleed_factor": 150.0, "bleed_duration": 2,
                   "shield_factor": 800.0, "shield_duration": 2}
    },

    # --- Yulmi Skills ---
    "talent_dreadful_curse": {
        "id": "talent_dreadful_curse", "name": "Dreadful Curse", "description": "Dreadful Curse effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_DREADFUL_CURSE_POISON_BOOST,
                               "stat_to_mod": StatType.POISON_DAMAGE_BOOST, "magnitude": 0.25, "duration": -1}]
    },
    "talent_high_fighting_spirit": {
        "id": "talent_high_fighting_spirit", "name": "High Fighting Spirit", "description": "High Fighting Spirit effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_high_fighting_spirit,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1300.0, "trigger_interval": 9,
                   "buff_magnitude": 0.20, "buff_duration": 4}
    },
    "talent_low_whispers": {
        "id": "talent_low_whispers", "name": "Low Whispers", "description": "Low Whispers effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_low_whispers,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 6, "reduction": -0.30, "duration": 1, "rage_gain": 180}
    },
    "base_skill_plague": {
        "id": "base_skill_plague", "name": "Plague", "description": "Plague effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_plague,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "poison_factor": 500.0, "poison_duration": 2,
                   "damage_taken_debuff": 0.20, "debuff_duration": 2}
    },
    "rage_skill_undead_harvest": {
        "id": "rage_skill_undead_harvest", "name": "Undead Harvest", "description": "Undead Harvest effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_undead_harvest,
        "config": {"damage_factor": 1800.0, "debuff_magnitude": -0.10, "debuff_duration": 1}
    },

    # --- Ivor Skills ---
    "talent_tactical_rules": {
        "id": "talent_tactical_rules", "name": "Tactical Rules", "description": "Tactical Rules effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_TACTICAL_RULES_RAGE_BUFF,
             "stat_to_mod": StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER, "magnitude": 0.15, "duration": -1},
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_TACTICAL_RULES_RAGE_BUFF,
             "stat_to_mod": StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER, "magnitude": 0.15, "duration": -1}
        ]
    },
    "talent_specter_lycan_assault": {
        "id": "talent_specter_lycan_assault", "name": "Specter Lycan Assault", "description": "Specter Lycan Assault effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_specter_lycan_assault,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 650.0, "trigger_interval": 9}
    },
    "talent_amazing_attack": {
        "id": "talent_amazing_attack", "name": "Amazing Attack", "description": "Amazing Attack effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_amazing_attack,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"troop_threshold": 350000, "damage_boost": 0.05}
    },
    "base_skill_throwing_axe": {
        "id": "base_skill_throwing_axe", "name": "Throwing Axe", "description": "Throwing Axe effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_throwing_axe,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 350.0, "buffed_damage_factor": 450.0}
    },
    "rage_skill_all_kill": {
        "id": "rage_skill_all_kill", "name": "All Kill", "description": "All Kill effect", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_all_kill,
        "config": {"damage_factor": 800.0, "attack_buff": 0.12, "attack_duration": 2}
    },


    # --- Plugin Skills ---
    # ... (All existing plugin skills) ...
    "plugin_silencer": {
        "id": "plugin_silencer", "name": "Silencer", "description": "Silencer effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_silencer,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 450.0, "silence_duration": 1}
    },
    "plugin_enrage": {
        "id": "plugin_enrage", "name": "Enrage", "description": "Enrage effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_enrage,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 300.0, "rage_gain": 100}
    },
    "plugin_retaliate": {
        "id": "plugin_retaliate", "name": "Retaliate", "description": "Retaliate effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.15, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 350.0}
    },
    "plugin_blessed_negation": {
        "id": "plugin_blessed_negation", "name": "Blessed Negation", "description": "Blessed Negation effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_blessed_negation,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 700.0, "trigger_interval": 9, "rage_reduction": 100}
    },
    "plugin_wild_indulgence": {
        "id": "plugin_wild_indulgence", "name": "Wild Indulgence", "description": "Wild Indulgence effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_wild_indulgence,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1000.0, "trigger_interval": 10}
    },
    "plugin_breaking_free": {
        "id": "plugin_breaking_free", "name": "Breaking Free", "description": "Breaking Free effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_breaking_free,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 10,
                   "damage_buff_magnitude": 0.30, "damage_buff_duration": 2,
                   "counter_reduction_magnitude": -0.30, "counter_reduction_duration": 2}
    },
    "plugin_fading_battle": {
        "id": "plugin_fading_battle", "name": "Fading Battle", "description": "Fading Battle effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 350.0}
    },
    "plugin_battle_hymn": {
        "id": "plugin_battle_hymn", "name": "Battle Hymn", "description": "Battle Hymn effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.10, "target": "ENEMY",
        "logic_handler": handle_plugin_battle_hymn,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 850.0, "rage_gain": 75, "cooldown_rounds": 5}
    },
    "plugin_rapid_attack": {
        "id": "plugin_rapid_attack", "name": "Rapid Attack", "description": "Rapid Attack effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.10, "target": "ENEMY",
        "logic_handler": handle_plugin_rapid_attack,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 650.0, "broken_blade_duration": 1, "cooldown_rounds": 5}
    },
    "plugin_rage_purge": {
        "id": "plugin_rage_purge", "name": "Rage Purge", "description": "Rage Purge effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_rage_purge,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 600.0, "rage_cost": 100}
    },
    "plugin_blessed_by_fate": {
        "id": "plugin_blessed_by_fate", "name": "Blessed by Fate", "description": "Blessed by Fate effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_blessed_by_fate,
        "config": {"initial_buff_duration": 29,
                   "initial_buff_magnitude": 0.50,
                   "secondary_proc_chance": 0.30,
                   "secondary_debuff_magnitude": 0.20,
                   "secondary_debuff_duration": 0}
    },
    "plugin_divine_blessing": {
        "id": "plugin_divine_blessing", "name": "Divine Blessing", "description": "Divine Blessing effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_divine_blessing,
        "config": {"initial_effect_duration": 28, "post_initial_trigger_chance": 0.30,
                   "post_initial_effect_duration": 0, "reduction_magnitude": -0.30,
                   "effect_name": EFFECT_NAME_DIVINE_BLESSING_REDUCTION}
    },
    "plugin_shield_support": {
        "id": "plugin_shield_support", "name": "Shield Support", "description": "Shield Support effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_shield_support,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"base_shield_factor": 750.0, "boosted_shield_factor": 1000.0,
                   "shield_duration": 1, "trigger_interval": 9, "effect_name": EFFECT_NAME_SHIELD_SUPPORT_EFFECT}
    },
    "plugin_freyas_blessing": {
        "id": "plugin_freyas_blessing", "name": "Freya's Blessing", "description": "Freya's Blessing effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.15, "target": "SELF",
        "logic_handler": handle_plugin_freyas_blessing,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"direct_heal_factor": 550.0, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_FREYAS_BLESSING_HEAL_BOOST,
            "stat_to_mod": StatType.HEAL_ADJUSTMENT, "magnitude": 0.25, "duration": 2,
            "activate_next_round": True}}
    },
    "plugin_hymn_of_life": {
        "id": "plugin_hymn_of_life", "name": "Hymn of Life", "description": "Hymn of Life effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_plugin_hymn_of_life,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"hot_heal_factor": 275.0, "hot_duration": 1, "hot_effect_name": EFFECT_NAME_HYMN_OF_LIFE_HOT,
                   "hp_buff_magnitude": 0.10, "hp_buff_duration": 0, "hp_buff_effect_name": EFFECT_NAME_HYMN_OF_LIFE_HP_BOOST}
    },
    "plugin_chance_of_reversal": {
        "id": "plugin_chance_of_reversal", "name": "Chance of Reversal", "description": "Chance of Reversal effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.25, "target": "SELF",
        "logic_handler": handle_plugin_chance_of_reversal,
        "config": {"damage_factor": 550.0, "rage_gain": 50.0}
    },
    "plugin_shield_reflector": {
        "id": "plugin_shield_reflector", "name": "Shield Reflector", "description": "Shield Reflector effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_shield_reflector,
        "config": {"counterattack_boost": 1.30}
    },
    "plugin_first_strike": {
        "id": "plugin_first_strike", "name": "First Strike", "description": "First Strike effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_first_strike_control,
        "config": {"apply_aura_on_round": 1, "rage_per_round": 75, "aura_effect_definition": {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT, "name": EFFECT_NAME_FIRST_STRIKE_RAGE_AURA,
            "duration": 30, "config": {"rage_per_round": 75, "start_rage_gain_round": 2, "end_rage_gain_round": 31},
            "activate_next_round": False }}
    },
    "plugin_shield_attacker": {
        "id": "plugin_shield_attacker", "name": "Shield Attacker", "description": "Shield Attacker effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_shield_attacker,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 500.0, "proc_chance": 0.50}
    },
    "plugin_awakening": {
        "id": "plugin_awakening", "name": "Awakening", "description": "Awakening effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_awakening,
        "config": {"cooldown_rounds": 4, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_AWAKENING_DMG_REDUCTION,
            "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": -0.10, "duration": 0,
            "activate_next_round": True},
                   "cleanse_effect_details": {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT, "name": EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
            "duration": 0, "activate_next_round": True}}
    },
    "plugin_baldr_blessing": {
        "id": "plugin_baldr_blessing", "name": "Baldr's Blessing", "description": "Baldr's Blessing effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_baldr_blessing,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "shield_factor": 900.0, "shield_duration": 1,
                   "shield_effect_name": EFFECT_NAME_BALDRS_SHIELD,
                   "damage_reduction_magnitude": -0.30, "damage_reduction_duration": 1,
                   "damage_reduction_effect_name": EFFECT_NAME_BALDRS_RESILIENCE,
                   "heal_factor": 900.0, "heal_effect_name": EFFECT_NAME_BALDRS_HEAL}
    },
    "plugin_lokis_trick": {
        "id": "plugin_lokis_trick", "name": "Loki's Trick", "description": "Loki's Trick effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_lokis_trick,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 450.0, "rage_reduction_chance": 0.30, "rage_reduction_amount": 100.0,
                   "buff_removal_chance": 0.30,
                   "pending_buff_removal_effect_name": EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
                   "cooldown_rounds": 3}
    },
    "plugin_odins_asylum": {
        "id": "plugin_odins_asylum", "name": "Odin's Asylum", "description": "Odin's Asylum effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_odins_asylum,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 450.0, "shield_factor": 200.0, "shield_duration": 1,
                   "shield_activate_next_round": True, "shield_name": EFFECT_NAME_ODINS_ASYLUM_SHIELD}
    },
    "plugin_thors_determination": {
        "id": "plugin_thors_determination", "name": "Thor's Determination", "description": "Thor's Determination effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_thors_determination,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "buff_magnitude": 2.25, "buff_duration": 1,
                   "buff_activate_next_round": True, "buff_stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
                   "buff_name": EFFECT_NAME_THORS_DETERMINATION_BUFF,
                   "damage_reduction_magnitude": -0.15, "damage_reduction_duration": 1,
                   "damage_reduction_activate_next_round": True,
                   "damage_reduction_name": EFFECT_NAME_THORS_DETERMINATION_DMG_REDUCTION}
    },
    "plugin_disarmament": {
        "id": "plugin_disarmament", "name": "Disarmament", "description": "Disarmament effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_disarmament,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 325.0, "disarm_duration": 0,
                   "disarm_effect_name": EFFECT_NAME_DISARM_DEBUFF,
                   "slow_duration": 1, "slow_effect_name": EFFECT_NAME_SLOW_DEBUFF,
                   "activate_debuffs_next_round": True, "cooldown_rounds": 3}
    },

    "plugin_fiery_rage": {
        "id": "plugin_fiery_rage", "name": "Fiery Rage", "description": "Fiery Rage effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.10, "target": "ENEMY",
        "logic_handler": handle_plugin_fiery_rage,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"burn_factor": 350.0, "boosted_burn_factor": 700.0, "burn_duration": 1}
    },
    "plugin_fiery_detonation": {
        "id": "plugin_fiery_detonation", "name": "Fiery Detonation", "description": "Fiery Detonation effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_fiery_detonation,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "damage_factor": 600.0,
                   "defense_reduction_magnitude": -0.15, "defense_reduction_duration": 1}
    },
    "plugin_rage_leech": {
        "id": "plugin_rage_leech", "name": "Rage Leech", "description": "Rage Leech effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_rage_leech,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"heal_factor": 900.0, "rage_gain": 80.0}
    },
    "plugin_enchanted_pursuit": {
        "id": "plugin_enchanted_pursuit", "name": "Enchanted Pursuit", "description": "Enchanted Pursuit effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_enchanted_pursuit,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"burn_chance": 0.10, "burn_factor": 275.0, "burn_duration": 1,
                   "bleed_chance": 0.10, "bleed_factor": 275.0, "bleed_duration": 1}
    },
    "plugin_blow_of_chaos": {
        "id": "plugin_blow_of_chaos", "name": "Blow of Chaos", "description": "Blow of Chaos effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_blow_of_chaos,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 1000.0, "cooldown_rounds": 3}
    },
    "plugin_on_alert": {
        "id": "plugin_on_alert", "name": "On Alert", "description": "On Alert effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_on_alert,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "buff_magnitude": 0.17, "max_stacks": 5,
                   "buff_name": EFFECT_NAME_ON_ALERT_COUNTER_BUFF}
    },
    "plugin_helas_curse": {
        "id": "plugin_helas_curse", "name": "Hela's Curse", "description": "Hela's Curse effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_helas_curse,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "burn_factor": 500.0, "burn_duration": 1,
                   "defense_debuff_chance": 0.50, "defense_debuff_magnitude": -0.20,
                   "defense_debuff_duration": 1}
    },
    "plugin_fearless": {
        "id": "plugin_fearless", "name": "Fearless", "description": "Fearless effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_fearless,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 12, "damage_factor": 800.0,
                   "buff_chance": 0.20, "buff_magnitude": 0.15, "buff_duration": 1}
    },
    "plugin_joint_offense": {
        "id": "plugin_joint_offense", "name": "Joint Offense", "description": "Joint Offense effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_joint_offense,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 800.0, "proc_chance": 0.50}
    },
    "plugin_bloody_rage": {
        "id": "plugin_bloody_rage", "name": "Bloody Rage", "description": "Bloody Rage effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_bloody_rage,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"hp_threshold_pct": 0.80, "proc_chance": 0.20, "damage_factor": 500.0}
    },
    "plugin_tidal_attack": {
        "id": "plugin_tidal_attack", "name": "Tidal Attack", "description": "Tidal Attack effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_tidal_attack,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 290.0, "damage_factor_h1": 370.0}
    },
    "plugin_splinter": {
        "id": "plugin_splinter", "name": "Splinter", "description": "Splinter effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_splinter,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 12, "damage_factor": 800.0,
                   "slow_chance": 0.35, "slow_duration": 1}
    },
    "plugin_hale_of_thorns": {
        "id": "plugin_hale_of_thorns", "name": "Hale of Thorns", "description": "Hale of Thorns effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF",
        "logic_handler": handle_plugin_hale_of_thorns
    },
    "plugin_halo_of_sacrifice": {
        "id": "plugin_halo_of_sacrifice", "name": "Halo of Sacrifice", "description": "Halo of Sacrifice effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_plugin_halo_of_sacrifice,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"buff_magnitude": 0.75, "buff_duration": 1}
    },
    "plugin_heightened_chance": {
        "id": "plugin_heightened_chance", "name": "Heightened Chance", "description": "Heightened Chance effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.25, "target": "SELF",
        "logic_handler": handle_plugin_heightened_chance,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"basic_buff_magnitude": 0.40, "counter_buff_magnitude": 0.40, "buff_duration": 1}
    },
    "plugin_tenacity": {
        "id": "plugin_tenacity", "name": "Tenacity", "description": "Tenacity effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 0.50, "target": "SELF",
        "logic_handler": handle_plugin_tenacity,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"heal_factor": 700.0}
    },
    "plugin_blessed_healing": {
        "id": "plugin_blessed_healing", "name": "Blessed Healing", "description": "Blessed Healing effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_blessed_healing,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 12, "heal_factor": 850.0}
    },
    "plugin_dampened_spirits": {
        "id": "plugin_dampened_spirits", "name": "Dampened Spirits", "description": "Dampened Spirits effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_dampened_spirits,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_proc_chance": 0.50, "damage_factor": 550.0,
                   "rage_reduction_chance": 0.15, "rage_reduction": 300.0}
    },
    "plugin_rapid_defense": {
        "id": "plugin_rapid_defense", "name": "Rapid Defense", "description": "Rapid Defense effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_rapid_defense,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"buff_magnitude": 0.40, "buff_duration": 1}
    },
    "plugin_rare_viking_hymn": {
        "id": "plugin_rare_viking_hymn", "name": "Rare Viking Hymn", "description": "Rare Viking Hymn effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.30, "target": "SELF",
        "logic_handler": handle_plugin_rare_viking_hymn,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"buff_magnitude": 0.20, "buff_duration": 1}
    },
    "plugin_rare_defense_up": {
        "id": "plugin_rare_defense_up", "name": "Rare Defense Up", "description": "Rare Defense Up effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.25, "target": "SELF",
        "logic_handler": handle_plugin_rare_defense_up,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"buff_magnitude": 0.20, "buff_duration": 1}
    },
    "plugin_rest_and_counterattack": {
        "id": "plugin_rest_and_counterattack", "name": "Rest and Counterattack", "description": "Rest and Counterattack effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.15, "target": "SELF",
        "logic_handler": handle_plugin_rest_and_counterattack,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"shield_factor": 400.0, "shield_duration": 1, "heal_factor": 400.0,
                   "cooldown_rounds": 4, "shield_effect_name": EFFECT_NAME_REST_AND_COUNTERATTACK_SHIELD}
    },
    "plugin_bloodstained_icefield": {
        "id": "plugin_bloodstained_icefield", "name": "Bloodstained Icefield", "description": "Bloodstained Icefield effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_plugin_bloodstained_icefield,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"heal_factor": 700.0, "cooldown_rounds": 3}
    },
    "plugin_this_too_shall_pass": {
        "id": "plugin_this_too_shall_pass", "name": "This Too Shall Pass", "description": "This Too Shall Pass effect", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_this_too_shall_pass,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1000.0, "heal_factor": 1000.0, "trigger_interval": 9}
    },

    # --- Dummy Talent ---
    "dummy_talent_empty": {
        "id": "dummy_talent_empty", "name": "Empty Talent Slot", "description": "Empty Talent Slot effect", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "trigger_chance": 0.0, "target": "SELF",
        "effects_to_apply": [], "logic_handler": None
    }
}

# Generate human-readable descriptions for all skills at import time
for _skill in SKILL_REGISTRY_GLOBAL.values():
    _skill["description"] = build_skill_description(_skill)


def _apply_overrides(base: Dict[str, Any], overrides: Dict[str, Any]) -> None:
    """Recursively apply ``overrides`` into ``base`` in-place."""
    for key, val in overrides.items():
        if (
            isinstance(val, dict)
            and isinstance(base.get(key), dict)
        ):
            _apply_overrides(base[key], val)
        else:
            base[key] = val


def build_skill_registry_with_overrides(
    overrides: Dict[str, Dict[str, Any]] | None,
) -> Dict[str, SkillDefinition]:
    """Return a skill registry with ``overrides`` applied.

    Parameters
    ----------
    overrides:
        Mapping of skill id to a dictionary of values that should override the
        defaults from :data:`SKILL_REGISTRY_GLOBAL`.
    """

    registry = {sid: copy.deepcopy(defn) for sid, defn in SKILL_REGISTRY_GLOBAL.items()}
    if not overrides:
        return registry
    for sid, params in overrides.items():
        if sid in registry and isinstance(params, dict):
            _apply_overrides(registry[sid], params)
    return registry
