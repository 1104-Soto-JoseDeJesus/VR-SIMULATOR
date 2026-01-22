"""
Defines the EffectInstance class, representing an active buff, debuff, shield, etc.
"""
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from .enums import EffectType, StatType, DoTType
from .constants import (
    EFFECT_NAME_AWAKENING_DMG_REDUCTION, EFFECT_NAME_BROKEN_BLADE_DEBUFF,
    EFFECT_NAME_DISARM_DEBUFF, EFFECT_NAME_SLOW_DEBUFF, EFFECT_NAME_SILENCE_DEBUFF,
    EFFECT_NAME_FIRST_STRIKE_RAGE_AURA, EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
    EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
    EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
    EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
    EFFECT_NAME_PENDING_HEIMDALL_PURIFY,
    EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
    EFFECT_NAME_BERSERK_FURY_RAGE_GAIN,
    EFFECT_NAME_DELAYED_RAGE_GAIN,
    EFFECT_NAME_DELAYED_RAGE_REDUCTION,
    EFFECT_NAME_SAINTLY_GUARDIAN_SHIELD_BOOST,
    EFFECT_NAME_WAR_BLESSING_SHIELD,
    EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF,
    EFFECT_NAME_JUDGEMENT_MARKER,
    EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
    EFFECT_NAME_HEIMDALL_STEALTH_EVASION,
    EFFECT_NAME_HEIMDALL_RETRIBUTION,
)

@dataclass(slots=True)
class EffectInstance:
    id: uuid.UUID
    source_skill_id: str
    effect_type: EffectType
    duration: int
    magnitude: float = 0.0
    config: Dict[str, Any] = field(default_factory=dict)
    name: Optional[str] = None
    applied_this_round: bool = True

    def __post_init__(self):
        if not self.name:
            self.name = f"Unnamed_{self.effect_type.value}_{str(self.id)[:4]}"

    def _stat_type_from_config(self) -> Optional[StatType]:
        stat_to_mod_val = self.config.get("stat_to_mod")
        if isinstance(stat_to_mod_val, StatType):
            return stat_to_mod_val
        if isinstance(stat_to_mod_val, str):
            normalized_value = stat_to_mod_val.lower()
            for stat_option in StatType:
                if stat_option.value == normalized_value or stat_option.name.lower() == normalized_value:
                    return stat_option
        return None

    def _custom_effect_disposition(self) -> str:
        cfg = self.config or {}
        if cfg.get("rage_amount"):
            return "beneficial" if cfg.get("rage_amount", 0.0) > 0 else "harmful"
        if cfg.get("rage_bonus_pct"):
            return "beneficial" if cfg.get("rage_bonus_pct", 0.0) > 0 else "harmful"
        if cfg.get("rage_reduction", 0.0) > 0:
            return "harmful"
        if cfg.get("buff_ids_to_remove"):
            return "harmful"
        if cfg.get("debuff_ids_to_remove"):
            return "beneficial"
        if cfg.get("evasion_chance", 0.0) > 0:
            return "beneficial"
        if cfg.get("retribution_rate", 0.0) > 0:
            return "beneficial"
        if cfg.get("marker_count") or self.name == EFFECT_NAME_JUDGEMENT_MARKER:
            return "harmful"
        if self.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA:
            return "beneficial"
        if self.name in {
            EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
            EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
            EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
            EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
        }:
            return "harmful"
        if self.name in {
            EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
            EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
            EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
            EFFECT_NAME_PENDING_HEIMDALL_PURIFY,
        }:
            return "beneficial"
        return "neutral"

    def is_beneficial_for_target(self) -> bool:
        if self.effect_type == EffectType.STAT_MOD:
            stat_enum = self._stat_type_from_config()
            magnitude = float(self.magnitude or 0.0)
            if stat_enum in {
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                StatType.BLEED_DAMAGE_REDUCTION,
                StatType.POISON_DAMAGE_REDUCTION,
                StatType.BURN_DAMAGE_REDUCTION,
                StatType.LACERATE_DAMAGE_REDUCTION,
            }:
                return magnitude < 0
            return magnitude > 0
        if self.effect_type in {EffectType.SHIELD, EffectType.HEAL_INSTANT, EffectType.HEAL_OVER_TIME, EffectType.IMMUNITY}:
            return True
        if self.effect_type in {EffectType.DEBUFF, EffectType.DAMAGE_OVER_TIME}:
            return False
        if self.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
            return self._custom_effect_disposition() == "beneficial"
        return False

    def is_dispellable_buff_candidate(self, *, include_shields: bool = False) -> bool:
        if self.duration == -1:
            return False
        if not include_shields and self.effect_type == EffectType.SHIELD:
            return False
        if not self.config.get("is_dispellable", True):
            return False
        return self.is_beneficial_for_target()

    def is_harmful_for_target(self) -> bool:
        if self.effect_type == EffectType.STAT_MOD:
            stat_enum = self._stat_type_from_config()
            magnitude = float(self.magnitude or 0.0)
            if stat_enum in {
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                StatType.BLEED_DAMAGE_REDUCTION,
                StatType.POISON_DAMAGE_REDUCTION,
                StatType.BURN_DAMAGE_REDUCTION,
                StatType.LACERATE_DAMAGE_REDUCTION,
            }:
                return magnitude > 0
            return magnitude < 0
        if self.effect_type in {EffectType.DEBUFF, EffectType.DAMAGE_OVER_TIME}:
            return True
        if self.effect_type in {EffectType.SHIELD, EffectType.HEAL_INSTANT, EffectType.HEAL_OVER_TIME, EffectType.IMMUNITY}:
            return False
        if self.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
            return self._custom_effect_disposition() == "harmful"
        return False

    def get_functionality_description(self) -> str:
        desc_parts = []
        if self.effect_type == EffectType.STAT_MOD:
            stat_to_mod_val = self.config.get('stat_to_mod')
            stat_name = "Unknown Stat"
            if isinstance(stat_to_mod_val, StatType):
                stat_name = stat_to_mod_val.name.replace("_", " ").title()
            elif isinstance(stat_to_mod_val, str):
                stat_name = stat_to_mod_val.replace("_", " ").title()

            if self.name == EFFECT_NAME_AWAKENING_DMG_REDUCTION:
                return f"Reduces All Damage Taken by {abs(self.magnitude * 100):.0f}% (from Awakening)"

            if stat_to_mod_val == StatType.DAMAGE_TAKEN_MULTIPLIER:
                reduction_percentage = abs(self.magnitude * 100)
                attack_type_filter = self.config.get('config_filter', {}).get('attack_type')
                verb = "Reduces" if self.magnitude < 0 else "Increases"
                if attack_type_filter:
                    attack_type_desc = attack_type_filter.replace("_", " ").title()
                    desc_parts.append(f"{verb} {attack_type_desc} Damage Taken by {reduction_percentage:.0f}%")
                else:
                    desc_parts.append(f"{verb} All Damage Taken by {reduction_percentage:.0f}%")
            elif stat_to_mod_val == StatType.SHIELD_STRENGTH_MODIFIER:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Shield Strength Received")
            elif stat_to_mod_val == StatType.BASE_ATTACK_MULTIPLIER:
                if self.config.get("unit_type_condition") == "pikemen":
                     desc_parts.append(f"{self.magnitude * 100:+.0f}% to Pikemen Attack Multiplier")
                else:
                     desc_parts.append(f"{self.magnitude * 100:+.0f}% to Base Attack Multiplier")
            elif stat_to_mod_val == StatType.HEAL_ADJUSTMENT:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Healing Received")
            elif stat_to_mod_val == StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Hero #1's Rage Skill Damage")
            elif stat_to_mod_val == StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Hero #2's Rage Skill Damage")
            elif stat_to_mod_val == StatType.BASE_HP_MULTIPLIER:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Base HP Multiplier")
            elif stat_to_mod_val == StatType.COUNTER_DAMAGE_ADJUST:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Counterattack Damage")
            elif stat_to_mod_val == StatType.BASIC_DAMAGE_ADJUST:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Basic Attack Damage")
            elif stat_to_mod_val == StatType.REACTIVE_SKILL_DAMAGE_ADJUST:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Reactive Skill Damage")
            elif stat_to_mod_val == StatType.COOPERATION_TRIGGER_RATE_MODIFIER:
                verb = "Reduces" if self.magnitude < 0 else "Increases"
                desc_parts.append(f"{verb} Cooperation Skill Trigger Rate by {abs(self.magnitude * 100):.0f}%")
            elif stat_to_mod_val == StatType.COOPERATION_SKILL_DAMAGE_MODIFIER:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Cooperation Skill Damage")
            elif stat_to_mod_val == StatType.PASSIVE_SKILL_DAMAGE_MODIFIER:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Passive Skill Damage")
            elif stat_to_mod_val == StatType.GENERAL_DAMAGE_MODIFIER:
                verb = "Reduces General Damage Dealt by" if self.magnitude < 0 else "Increases General Damage Dealt by"
                desc_parts.append(f"{verb} {abs(self.magnitude * 100):.0f}%")
            elif stat_to_mod_val == StatType.DAMAGE_AGAINST_RALLY_ARMIES:
                verb = "Reduces Damage Dealt vs Rally Armies by" if self.magnitude < 0 else "Increases Damage Dealt vs Rally Armies by"
                desc_parts.append(f"{verb} {abs(self.magnitude * 100):.0f}%")
            elif stat_to_mod_val == StatType.BLEED_DAMAGE_BOOST: desc_parts.append(f"{self.magnitude * 100:+.0f}% to Bleed Damage Dealt")
            elif stat_to_mod_val == StatType.POISON_DAMAGE_BOOST: desc_parts.append(f"{self.magnitude * 100:+.0f}% to Poison Damage Dealt")
            elif stat_to_mod_val == StatType.BURN_DAMAGE_BOOST: desc_parts.append(f"{self.magnitude * 100:+.0f}% to Burn Damage Dealt")
            elif stat_to_mod_val == StatType.LACERATE_DAMAGE_BOOST: desc_parts.append(f"{self.magnitude * 100:+.0f}% to Lacerate Damage Dealt")
            elif stat_to_mod_val == StatType.BLEED_DAMAGE_REDUCTION: desc_parts.append(f"Reduces Bleed Damage Taken by {abs(self.magnitude * 100):.0f}%")
            elif stat_to_mod_val == StatType.POISON_DAMAGE_REDUCTION: desc_parts.append(f"Reduces Poison Damage Taken by {abs(self.magnitude * 100):.0f}%")
            elif stat_to_mod_val == StatType.BURN_DAMAGE_REDUCTION: desc_parts.append(f"Reduces Burn Damage Taken by {abs(self.magnitude * 100):.0f}%")
            elif stat_to_mod_val == StatType.LACERATE_DAMAGE_REDUCTION: desc_parts.append(f"Reduces Lacerate Damage Taken by {abs(self.magnitude * 100):.0f}%")
            elif stat_to_mod_val == StatType.RAGE_SKILL_DAMAGE_MODIFIER:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to Rage Skill Damage")
            else:
                desc_parts.append(f"{self.magnitude * 100:+.0f}% to {stat_name}")

        elif self.effect_type == EffectType.SHIELD:
            if self.magnitude > 0:
                desc_parts.append(f"Absorbs {self.magnitude:.0f} HP damage")
            else:
                shield_factor = self.config.get("shield_factor", 0) or self.config.get("shield_value_from_factor", 0)
                if shield_factor > 0: desc_parts.append(f"Provides a shield (Factor: {shield_factor})")
                else: desc_parts.append("Provides a shield")

        elif self.effect_type == EffectType.IMMUNITY:
            immune_to = self.config.get('immune_to', 'Unknown Debuff')
            desc_parts.append(f"Immunity to {immune_to}")

        elif self.effect_type == EffectType.DEBUFF:
            if self.name == EFFECT_NAME_BROKEN_BLADE_DEBUFF: desc_parts.append("Prevents Counterattacks")
            elif self.name == EFFECT_NAME_DISARM_DEBUFF: desc_parts.append("Cannot launch basic attacks")
            elif self.name == EFFECT_NAME_SLOW_DEBUFF: desc_parts.append("Target is Slowed (marker)")
            elif self.name == EFFECT_NAME_SILENCE_DEBUFF: desc_parts.append("Prevents Rage Skill cast")
            else: desc_parts.append(f"Debuff: {self.name}")

        elif self.effect_type == EffectType.DAMAGE_OVER_TIME:
            dot_type_val = self.config.get('dot_type')
            dot_type_str = ""
            if isinstance(dot_type_val, DoTType) and dot_type_val != DoTType.GENERIC:
                dot_type_str = dot_type_val.value.capitalize() + " "
            elif isinstance(dot_type_val, str) and dot_type_val.upper() != DoTType.GENERIC.value:
                 dot_type_str = dot_type_val.capitalize() + " "

            status_factor = self.config.get('status_effect_factor', 0)
            if status_factor > 0 and dot_type_val != DoTType.GENERIC :
                desc_parts.append(f"{dot_type_str}Damage Over Time (Factor: {status_factor:.0f})")
            elif self.config.get("dot_damage_per_round", 0) > 0: # For old generic DoTs
                dot_damage = self.config.get('dot_damage_per_round', 0)
                desc_parts.append(f"Deals {dot_damage:.0f} damage per round")
            else:
                desc_parts.append(f"{dot_type_str}Damage Over Time (unspecified damage/factor)")

        elif self.effect_type == EffectType.HEAL_OVER_TIME:
            desc_parts.append(f"Heals over time (Factor: {self.magnitude:.0f})")

        elif self.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
            if self.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA:
                rage_gain = self.config.get('rage_per_round', 0)
                start_round = self.config.get('start_rage_gain_round', '?'); end_round = self.config.get('end_rage_gain_round', '?')
                desc_parts.append(f"Grants {rage_gain} rage each round (R{start_round}-R{end_round}, unaffected by restrictions)")
            elif self.name in [
                EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
                EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
                EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
                EFFECT_NAME_PENDING_HEIMDALL_PURIFY,
            ]:
                desc_parts.append("Pending debuff cleanse for start of next round")
            elif self.name in [
                EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
                EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
                EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
                EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
            ]:
                desc_parts.append("Pending buff removal for start of next round")
            elif self.name == EFFECT_NAME_DELAYED_RAGE_GAIN or (
                self.effect_type == EffectType.CUSTOM_SKILL_EFFECT
                and self.config.get("rage_amount", 0) > 0
                and self.activate_next_round
            ):
                amt = self.config.get('rage_amount', 0)
                desc_parts.append(f"Gain {amt} rage next round")
            elif self.name == EFFECT_NAME_DELAYED_RAGE_REDUCTION:
                amt = self.config.get('rage_reduction', 0)
                desc_parts.append(f"Reduce rage by {amt} next round")
            elif self.name == EFFECT_NAME_HEIMDALL_STEALTH_EVASION:
                chance = self.config.get('evasion_chance', 0) * 100
                desc_parts.append(
                    f"Evasion: {chance:.1f}% chance to ignore basic, counter, and direct skill damage"
                )
            elif self.name == EFFECT_NAME_HEIMDALL_RETRIBUTION:
                rate = self.config.get('retribution_rate', 0) * 100
                desc_parts.append(f"Retribution: returns {rate:.1f}% of direct damage received")
            elif self.name == EFFECT_NAME_JUDGEMENT_MARKER:
                desc_parts.append("Judgement Marker")
            elif self.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS:
                cnt = self.config.get('marker_count', 1)
                desc_parts.append(f"Pending {cnt} Judgement Marker(s)")
            else:
                desc_parts.append(f"Custom Effect: {self.name}")
        else:
            desc_parts.append(f"{self.effect_type.name.replace('_', ' ').title()}")

        return ", ".join(desc_parts) if desc_parts else "Effect with no description"

    def __repr__(self):
        return (
            f"EffectInstance(Name: {self.name}, Source: {self.source_skill_id}, "
            f"Type: {self.effect_type.value}, Dur: {self.duration}, Mag: {self.magnitude:.2f}, "
            f"AppliedThisRound: {self.applied_this_round}, Config: {self.config})"
        )
