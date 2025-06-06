"""
Contains all Enum definitions for types used throughout the simulator.
"""
from enum import Enum

class EffectType(Enum):
    STAT_MOD = "STAT_MOD"
    SHIELD = "SHIELD"
    HEAL_INSTANT = "HEAL_INSTANT"
    HEAL_OVER_TIME = "HEAL_OVER_TIME"
    DAMAGE_OVER_TIME = "DAMAGE_OVER_TIME" # This will be used for Bleed, Poison, Burn
    IMMUNITY = "IMMUNITY"
    DEBUFF = "DEBUFF"
    CUSTOM_SKILL_EFFECT = "CUSTOM_SKILL_EFFECT"

class SkillTriggerType(Enum):
    PASSIVE = "PASSIVE"
    ON_DEALING_DAMAGE = "ON_DEALING_DAMAGE"
    ON_BASIC_ATTACK = "ON_BASIC_ATTACK"
    ON_COUNTER_ATTACK = "ON_COUNTER_ATTACK"
    ON_HIT_BY_BASIC_ATTACK = "ON_HIT_BY_BASIC_ATTACK"
    ON_RECEIVING_HEALING = "ON_RECEIVING_HEALING"
    CHANCE_PER_ROUND = "CHANCE_PER_ROUND" # Used for skills that trigger every X rounds
    RAGE_SKILL = "RAGE_SKILL"
    ON_RECEIVING_RAGE_SKILL_DAMAGE = "ON_RECEIVING_RAGE_SKILL_DAMAGE"
    ON_OWN_RAGE_SKILL_CAST = "ON_OWN_RAGE_SKILL_CAST"
    ON_OWN_COMMAND_SKILL_CAST = "ON_OWN_COMMAND_SKILL_CAST"

class DoTType(Enum): # NEW ENUM for specific DoT types
    BLEED = "BLEED"
    POISON = "POISON"
    BURN = "BURN"
    GENERIC = "GENERIC" # For existing/other DoTs not following the new rules

class StatType(Enum):
    # Base Stat Multipliers
    BASE_ATTACK_MULTIPLIER = "base_attack_multiplier"
    BASE_DEFENSE_MULTIPLIER = "base_defense_multiplier"
    BASE_HP_MULTIPLIER = "base_hp_multiplier"

    # Effective Stat Multipliers
    EFFECTIVE_ATTACK_MULTIPLIER = "effective_attack_multiplier"
    EFFECTIVE_DEFENSE_MULTIPLIER = "effective_defense_multiplier"
    EFFECTIVE_HP_MULTIPLIER = "effective_hp_multiplier"

    # Specific Damage Type Adjustments
    BASIC_DAMAGE_ADJUST = "basic_damage_adjust"
    COUNTER_DAMAGE_ADJUST = "counter_damage_adjust"
    REACTIVE_SKILL_DAMAGE_ADJUST = "reactive_skill_damage_adjust" # For skills triggering from events like ON_HIT, ON_COUNTER etc.

    # General Modifiers
    GENERAL_DAMAGE_MODIFIER = "general_damage_modifier" # General damage dealt increase/decrease by source
    DAMAGE_TAKEN_MULTIPLIER = "damage_taken_multiplier" # General damage taken increase/decrease on target

    # Shield and Healing Modifiers
    SHIELD_STRENGTH_MODIFIER = "shield_strength_modifier"
    HEAL_ADJUSTMENT = "heal_adjustment"

    # Hero-Specific Rage Skill Modifiers
    HERO1_RAGE_SKILL_DAMAGE_MODIFIER = "hero1_rage_skill_damage_modifier"
    HERO2_RAGE_SKILL_DAMAGE_MODIFIER = "hero2_rage_skill_damage_modifier"

    # Specific DoT Damage Boosts (applied by attacker)
    BLEED_DAMAGE_BOOST = "bleed_damage_boost"
    POISON_DAMAGE_BOOST = "poison_damage_boost"
    BURN_DAMAGE_BOOST = "burn_damage_boost"

    # Specific DoT Damage Reductions (applied on target)
    BLEED_DAMAGE_REDUCTION = "bleed_damage_reduction"
    POISON_DAMAGE_REDUCTION = "poison_damage_reduction"
    BURN_DAMAGE_REDUCTION = "burn_damage_reduction"

    # NEW StatType for Athelstan's "Strategize"
    COMMAND_SKILL_DAMAGE_MODIFIER = "command_skill_damage_modifier" # For skills that trigger periodically (e.g. every X rounds)
    COOPERATION_TRIGGER_RATE_MODIFIER = "cooperation_trigger_rate_modifier"


class SkillType(Enum):
    TALENT = "TALENT"
    BASE_SKILL = "BASE_SKILL"
    PLUGIN_SKILL = "PLUGIN_SKILL"
