"""
Defines the EffectInstance class, representing an active buff, debuff, shield, etc.
"""
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable

from .enums import EffectType, StatType, DoTType
from .constants import (
    EFFECT_NAME_AWAKENING_DMG_REDUCTION,
    EFFECT_NAME_BROKEN_BLADE_DEBUFF,
    EFFECT_NAME_DISARM_DEBUFF,
    EFFECT_NAME_SLOW_DEBUFF,
    EFFECT_NAME_SILENCE_DEBUFF,
    EFFECT_NAME_FIRST_STRIKE_RAGE_AURA,
    EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
    EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
    EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
    EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
    EFFECT_NAME_BERSERK_FURY_RAGE_GAIN,
    EFFECT_NAME_DELAYED_RAGE_GAIN,
    EFFECT_NAME_DELAYED_RAGE_REDUCTION,
    EFFECT_NAME_SAINTLY_GUARDIAN_SHIELD_BOOST,
    EFFECT_NAME_WAR_BLESSING_SHIELD,
    EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF,
    EFFECT_NAME_JUDGEMENT_MARKER,
    EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
)


@dataclass(slots=True)
class EffectInstance:
    """Runtime representation of an effect applied to an army."""

    source_skill_id: str
    effect_type: EffectType
    duration: int
    magnitude: float = 0.0
    config: Dict[str, Any] = field(default_factory=dict)
    name: Optional[str] = None
    applied_this_round: bool = True
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"Unnamed_{self.effect_type.value}_{str(self.id)[:4]}"

    # --- Description helpers -------------------------------------------------
    def _describe_stat_mod(self) -> str:
        stat_to_mod_val = self.config.get("stat_to_mod")
        stat_name = "Unknown Stat"
        if isinstance(stat_to_mod_val, StatType):
            stat_name = stat_to_mod_val.name.replace("_", " ").title()
        elif isinstance(stat_to_mod_val, str):
            stat_name = stat_to_mod_val.replace("_", " ").title()

        if self.name == EFFECT_NAME_AWAKENING_DMG_REDUCTION:
            return f"Reduces All Damage Taken by {abs(self.magnitude * 100):.0f}% (from Awakening)"

        desc_parts = []
        if stat_to_mod_val == StatType.DAMAGE_TAKEN_MULTIPLIER:
            reduction_percentage = abs(self.magnitude * 100)
            attack_type_filter = self.config.get("config_filter", {}).get("attack_type")
            verb = "Reduces" if self.magnitude < 0 else "Increases"
            if attack_type_filter:
                attack_type_desc = attack_type_filter.replace("_", " ").title()
                desc_parts.append(
                    f"{verb} {attack_type_desc} Damage Taken by {reduction_percentage:.0f}%"
                )
            else:
                desc_parts.append(
                    f"{verb} All Damage Taken by {reduction_percentage:.0f}%"
                )
        elif stat_to_mod_val == StatType.SHIELD_STRENGTH_MODIFIER:
            desc_parts.append(f"{self.magnitude * 100:+.0f}% to Shield Strength Received")
        elif stat_to_mod_val == StatType.BASE_ATTACK_MULTIPLIER:
            if self.config.get("unit_type_condition") == "pikemen":
                desc_parts.append(
                    f"{self.magnitude * 100:+.0f}% to Pikemen Attack Multiplier"
                )
            else:
                desc_parts.append(
                    f"{self.magnitude * 100:+.0f}% to Base Attack Multiplier"
                )
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
            desc_parts.append(
                f"{verb} Cooperation Skill Trigger Rate by {abs(self.magnitude * 100):.0f}%"
            )
        elif stat_to_mod_val == StatType.COOPERATION_SKILL_DAMAGE_MODIFIER:
            desc_parts.append(f"{self.magnitude * 100:+.0f}% to Cooperation Skill Damage")
        elif stat_to_mod_val == StatType.GENERAL_DAMAGE_MODIFIER:
            verb = (
                "Reduces General Damage Dealt by"
                if self.magnitude < 0
                else "Increases General Damage Dealt by"
            )
            desc_parts.append(f"{verb} {abs(self.magnitude * 100):.0f}%")
        elif stat_to_mod_val == StatType.BLEED_DAMAGE_BOOST:
            desc_parts.append(f"{self.magnitude * 100:+.0f}% to Bleed Damage Dealt")
        elif stat_to_mod_val == StatType.POISON_DAMAGE_BOOST:
            desc_parts.append(f"{self.magnitude * 100:+.0f}% to Poison Damage Dealt")
        elif stat_to_mod_val == StatType.BURN_DAMAGE_BOOST:
            desc_parts.append(f"{self.magnitude * 100:+.0f}% to Burn Damage Dealt")
        elif stat_to_mod_val == StatType.BLEED_DAMAGE_REDUCTION:
            desc_parts.append(
                f"Reduces Bleed Damage Taken by {abs(self.magnitude * 100):.0f}%"
            )
        elif stat_to_mod_val == StatType.POISON_DAMAGE_REDUCTION:
            desc_parts.append(
                f"Reduces Poison Damage Taken by {abs(self.magnitude * 100):.0f}%"
            )
        elif stat_to_mod_val == StatType.BURN_DAMAGE_REDUCTION:
            desc_parts.append(
                f"Reduces Burn Damage Taken by {abs(self.magnitude * 100):.0f}%"
            )
        else:
            desc_parts.append(f"{self.magnitude * 100:+.0f}% to {stat_name}")

        return ", ".join(desc_parts) if desc_parts else "Effect with no description"

    def _describe_shield(self) -> str:
        if self.magnitude > 0:
            return f"Absorbs {self.magnitude:.0f} HP damage"
        shield_factor = self.config.get("shield_factor", 0) or self.config.get(
            "shield_value_from_factor", 0
        )
        if shield_factor > 0:
            return f"Provides a shield (Factor: {shield_factor})"
        return "Provides a shield"

    def _describe_immunity(self) -> str:
        immune_to = self.config.get("immune_to", "Unknown Debuff")
        return f"Immunity to {immune_to}"

    def _describe_debuff(self) -> str:
        if self.name == EFFECT_NAME_BROKEN_BLADE_DEBUFF:
            return "Prevents Counterattacks"
        if self.name == EFFECT_NAME_DISARM_DEBUFF:
            return "Cannot launch basic attacks"
        if self.name == EFFECT_NAME_SLOW_DEBUFF:
            return "Target is Slowed (marker)"
        if self.name == EFFECT_NAME_SILENCE_DEBUFF:
            return "Prevents Rage Skill cast"
        return f"Debuff: {self.name}"

    def _describe_damage_over_time(self) -> str:
        dot_type_val = self.config.get("dot_type")
        dot_type_str = ""
        if isinstance(dot_type_val, DoTType) and dot_type_val != DoTType.GENERIC:
            dot_type_str = dot_type_val.value.capitalize() + " "
        elif isinstance(dot_type_val, str) and dot_type_val.upper() != DoTType.GENERIC.value:
            dot_type_str = dot_type_val.capitalize() + " "

        status_factor = self.config.get("status_effect_factor", 0)
        if status_factor > 0 and dot_type_val != DoTType.GENERIC:
            return f"{dot_type_str}Damage Over Time (Factor: {status_factor:.0f})"
        if self.config.get("dot_damage_per_round", 0) > 0:
            dot_damage = self.config.get("dot_damage_per_round", 0)
            return f"Deals {dot_damage:.0f} damage per round"
        return f"{dot_type_str}Damage Over Time (unspecified damage/factor)"

    def _describe_heal_over_time(self) -> str:
        return f"Heals over time (Factor: {self.magnitude:.0f})"

    def _describe_custom_skill_effect(self) -> str:
        if self.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA:
            rage_gain = self.config.get("rage_per_round", 0)
            start_round = self.config.get("start_rage_gain_round", "?")
            end_round = self.config.get("end_rage_gain_round", "?")
            return (
                f"Grants {rage_gain} rage each round (R{start_round}-R{end_round}, "
                "unaffected by restrictions)"
            )
        if self.name in [
            EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
            EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
            EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
        ]:
            return "Pending debuff cleanse for start of next round"
        if self.name in [
            EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
            EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
            EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
        ]:
            return "Pending buff removal for start of next round"
        if self.name == EFFECT_NAME_DELAYED_RAGE_GAIN:
            amt = self.config.get("rage_amount", 0)
            return f"Gain {amt} rage next round"
        if self.name == EFFECT_NAME_DELAYED_RAGE_REDUCTION:
            amt = self.config.get("rage_reduction", 0)
            return f"Reduce rage by {amt} next round"
        if self.name == EFFECT_NAME_JUDGEMENT_MARKER:
            return "Judgement Marker"
        if self.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS:
            cnt = self.config.get("marker_count", 1)
            return f"Pending {cnt} Judgement Marker(s)"
        return f"Custom Effect: {self.name}"

    def _describe_default(self) -> str:
        return self.effect_type.name.replace("_", " ").title()

    def get_functionality_description(self) -> str:
        handlers: Dict[EffectType, Callable[[], str]] = {
            EffectType.STAT_MOD: self._describe_stat_mod,
            EffectType.SHIELD: self._describe_shield,
            EffectType.IMMUNITY: self._describe_immunity,
            EffectType.DEBUFF: self._describe_debuff,
            EffectType.DAMAGE_OVER_TIME: self._describe_damage_over_time,
            EffectType.HEAL_OVER_TIME: self._describe_heal_over_time,
            EffectType.CUSTOM_SKILL_EFFECT: self._describe_custom_skill_effect,
        }
        handler = handlers.get(self.effect_type, self._describe_default)
        desc = handler()
        return desc if desc else "Effect with no description"

    def __repr__(self) -> str:  # pragma: no cover - representation method
        return (
            f"EffectInstance(Name: {self.name}, Source: {self.source_skill_id}, "
            f"Type: {self.effect_type.value}, Dur: {self.duration}, Mag: {self.magnitude:.2f}, "
            f"AppliedThisRound: {self.applied_this_round}, Config: {self.config})"
        )
