# === File: game_simulator.py ===
import copy
import math
import random
import os
from functools import lru_cache
from typing import List, Optional, Dict, Any, Tuple

import matplotlib.pyplot as plt

from .enums import SkillTriggerType, StatType, EffectType, SkillType, DoTType, PluginSkillLabel
from .unit_definition import Unit
from .army_composition import Army
from .effect_system import EffectInstance
from .skill_system import SkillDefinition, SkillLogicHandler, RageSkillLogicHandler
from .skill_definitions import SKILL_REGISTRY_GLOBAL
from .constants import (
    EFFECT_NAME_BROKEN_BLADE_DEBUFF,
    EFFECT_NAME_DISARM_DEBUFF,
    EFFECT_NAME_SILENCE_DEBUFF,
    EFFECT_NAME_JUDGEMENT_MARKER,
    EFFECT_NAME_HEIMDALL_STEALTH_EVASION,
    EFFECT_NAME_HEIMDALL_RETRIBUTION,
)
from .dynamic_unrevivable_config import (
    UNIT_TYPES as DYNAMIC_UNIT_TYPES,
    get_settings as get_dynamic_unrevivable_settings,
    get_type_settings as get_dynamic_unrevivable_type_settings,
)
from .report_builder import ReportBuilder
from . import troop_scalar_config, heal_shield_pairing_config
from colorama import Fore

# Skills that trigger on active skill casts but have a 1 trigger per 9 rounds limit instead of 2
ACTIVE_CAST_ONE_TRIGGER_SKILLS = {
    "talent_excite",
    "talent_revolutionary_resolve",
    "base_skill_enchanted_arrow",
    "plugin_joint_offense",
    "plugin_dampened_spirits",
}


class GameSimulator:
    SKILL_REGISTRY_GLOBAL = SKILL_REGISTRY_GLOBAL

    @staticmethod
    @lru_cache(maxsize=None)
    def troop_scalar(T: float) -> float:
        # This function calculates a scalar based on troop count.
        if T <= 0:
            base_scalar = 0.0
        elif 1 <= T <= 100:
            base_scalar = math.exp(
                -0.02426063 * (math.log(T) ** 2)
                + 0.53658754 * math.log(T)
                + 5.87457112
            )
        elif 100 < T <= 1000:
            base_scalar = 327.53303836 * (T ** 0.45412486)
        elif 1000 < T <= 10000:
            base_scalar = 315.16611724 * (T ** 0.45876193)
        elif 10000 < T <= 100000:
            base_scalar = 0.74904783 * T + 14066.58867
        elif 100000 < T <= 300000:
            base_scalar = 0.20527127 * T + 68444.33684
        elif 300000 < T <= 2000000:
            base_scalar = 0.20528 * T + 68452
        elif 2000000 < T:
            base_scalar = 0.20527905760055395 * T + 68453.884798892
        else:
            base_scalar = T
        return base_scalar * troop_scalar_config.get_multiplier()

    @staticmethod
    def advantage_adjust(attacker_unit: Unit, defender_unit: Unit) -> float:
        # Determines combat advantage based on unit types.
        adv = {'archers': 'pikemen', 'pikemen': 'infantry', 'infantry': 'archers'}
        atk_type, def_type = attacker_unit.unit_type, defender_unit.unit_type
        if adv.get(atk_type) == def_type: return 1.05
        if adv.get(def_type) == atk_type: return 0.95
        return 1.0

    def _resolve_advantage_adjustment(
        self, attacker_unit: Unit, defender_unit: Unit
    ) -> tuple[float, float]:
        base_multiplier = GameSimulator.advantage_adjust(attacker_unit, defender_unit)
        normalized_mode = (self.advantage_mode or "multiplicative").lower()
        if normalized_mode == "off":
            return 1.0, 0.0
        if normalized_mode == "additive":
            advantage_bonus = 0.0
            if base_multiplier > 1.0:
                advantage_bonus = 0.05
            elif base_multiplier < 1.0:
                advantage_bonus = -0.05
            return 1.0, advantage_bonus
        return base_multiplier, 0.0

    def _is_mount_skill(self, skill_def: Dict[str, Any]) -> bool:
        skill_type = skill_def.get("type")
        mount_type = getattr(SkillType, "MOUNT_SKILL", None)
        if mount_type is not None and skill_type == mount_type:
            return True
        if isinstance(skill_type, str) and skill_type.upper().endswith("MOUNT_SKILL"):
            return True
        if skill_def.get("is_mount_skill") or skill_def.get("mount_skill"):
            return True
        source_val = skill_def.get("source") or skill_def.get("origin")
        return isinstance(source_val, str) and source_val.lower() == "mount"

    def _cooldown_enabled_for_skill(self, skill_def: Dict[str, Any]) -> bool:
        """Return whether cooldown logic should apply to ``skill_def``.

        The check first consults any explicit per-skill overrides before
        falling back to the category based switches (hero/plugin/gem/mount).
        """
        skill_id = skill_def.get("id")

        # Per-skill overrides take precedence over category flags.  This allows
        # fine grained control from the GUI/debug tools while keeping the
        # original behaviour as the default when no override is present.
        try:
            overrides = getattr(self, "per_skill_cooldown_overrides", None)
        except AttributeError:
            overrides = None
        if overrides and isinstance(skill_id, str):
            if skill_id in overrides:
                return bool(overrides[skill_id])

        skill_type = skill_def.get("type")
        if self._is_mount_skill(skill_def):
            return self.mount_cooldowns_enabled
        if isinstance(skill_type, SkillType):
            if skill_type == SkillType.PLUGIN_SKILL:
                return self.plugin_cooldowns_enabled
            if skill_type == SkillType.GEM_SKILL:
                return self.gem_cooldowns_enabled
            return self.hero_cooldowns_enabled

        if isinstance(skill_type, str):
            normalized = skill_type.upper()
            if normalized.endswith("PLUGIN_SKILL"):
                return self.plugin_cooldowns_enabled
            if normalized.endswith("GEM_SKILL"):
                return self.gem_cooldowns_enabled
            if normalized.endswith("MOUNT_SKILL"):
                return self.mount_cooldowns_enabled

        labels = skill_def.get("labels", [])
        if labels and all(isinstance(label, PluginSkillLabel) for label in labels):
            return self.plugin_cooldowns_enabled

        return self.hero_cooldowns_enabled

    def __init__(
        self,
        army1: Army,
        army2: Army,
        report_builder: Optional[ReportBuilder] = None,
        track_stats: bool = True,
        mode: str = "standard",
        cooldowns_enabled: bool = True,
        *,
        hero_cooldowns_enabled: bool | None = None,
        plugin_cooldowns_enabled: bool | None = None,
        gem_cooldowns_enabled: bool | None = None,
        mount_cooldowns_enabled: bool | None = None,
        damage_reduction_affects_dots: bool = True,
        advantage_mode: str = "multiplicative",
        per_skill_cooldown_overrides: Optional[Dict[str, bool]] = None,
    ):
        self.army1: Army = army1
        self.army2: Army = army2
        self.army1.register_simulator(self)
        self.army2.register_simulator(self)
        self.round: int = 0
        self.mode: str = mode
        self.advantage_mode: str = advantage_mode
        base_cooldown_state = bool(cooldowns_enabled)
        self.hero_cooldowns_enabled: bool = (
            base_cooldown_state if hero_cooldowns_enabled is None else bool(hero_cooldowns_enabled)
        )
        self.plugin_cooldowns_enabled: bool = (
            base_cooldown_state
            if plugin_cooldowns_enabled is None
            else bool(plugin_cooldowns_enabled)
        )
        self.gem_cooldowns_enabled: bool = (
            base_cooldown_state if gem_cooldowns_enabled is None else bool(gem_cooldowns_enabled)
        )
        self.mount_cooldowns_enabled: bool = (
            base_cooldown_state if mount_cooldowns_enabled is None else bool(mount_cooldowns_enabled)
        )
        # Optional fine-grained overrides keyed by skill id.  When an entry is
        # present it decides whether cooldowns are enabled for that specific
        # skill, independent of the category flags above.
        self.per_skill_cooldown_overrides: Dict[str, bool] = (
            dict(per_skill_cooldown_overrides) if per_skill_cooldown_overrides is not None else {}
        )
        self.damage_reduction_affects_dots: bool = bool(damage_reduction_affects_dots)
        self.round_combat_actions_log: List[Dict[str, Any]] = []
        self.round_skill_triggers_log: Dict[str, List[Dict[str, Any]]] = {
            self.army1.name: [], self.army2.name: []
        }
        # Ensure passive skills are applied once the simulator is associated
        # with the armies.  Without this call passive effects would never
        # appear in battle reports.
        self.army1._apply_initial_passive_skills()
        self.army2._apply_initial_passive_skills()
        self.report_builder = report_builder or ReportBuilder()
        self.track_stats = track_stats

    def _log_active_effects_for_report(self) -> List[str]:
        lines: List[str] = []
        for army in [self.army1, self.army2]:
            lines.append(
                f"\n{army.name} active effects (Troops: {army.current_troop_count}, Rage: {army.current_rage:.0f}, Unrevivable: {round(army.unrevivable_troops)}):")
            if not army.active_effects:
                lines.append("  None")
                continue

            marker_count = sum(1 for e in army.active_effects if e.name == EFFECT_NAME_JUDGEMENT_MARKER)
            other_effects = [e for e in army.active_effects if e.name != EFFECT_NAME_JUDGEMENT_MARKER]

            if marker_count > 0:
                lines.append(f"  - Judgement Markers: {marker_count}")

            sorted_effects = sorted(other_effects, key=lambda e: (e.source_skill_id, e.name or ""))
            for eff in sorted_effects:
                source_skill_name = self.SKILL_REGISTRY_GLOBAL.get(eff.source_skill_id, {}).get("name", eff.source_skill_id)
                duration_str = f"{eff.duration + 1} rounds" if eff.duration != -1 else "Permanent"
                lines.append(
                    f"  - Src: {source_skill_name}, Name: {eff.name}, Func: {eff.get_functionality_description()}, Dur: {duration_str}")
        return lines

    def _log_combat_action(
        self,
        attacker: Army,
        defender: Army,
        damage_potential_hp: float,
        absorbed_hp: float,
        final_hp_damage: float,
        potential_kills: int,
        is_counter: bool,
        action_type: Optional[str] = None,
        skill_id: str | None = None,
        calculation_steps: Optional[list[dict[str, Any]]] = None,
    ):
        action_type_str = action_type or ("Counter Attack" if is_counter else "Basic Attack")
        log_entry = {
            "attacker_name": attacker.name,
            "defender_name": defender.name,
            "action_type": action_type_str,
            "damage_potential_hp": damage_potential_hp,
            "absorbed_hp": absorbed_hp,
            "final_hp_damage": final_hp_damage,
            "potential_kills": potential_kills,
        }
        if calculation_steps:
            log_entry["calculation_steps"] = copy.deepcopy(calculation_steps)
        else:
            auto_steps: list[dict[str, Any]] = []
            detail_fields: list[tuple[str, Any, str]] = [
                ("damage_potential_hp", damage_potential_hp, "Raw damage before shields"),
                ("absorbed_hp", absorbed_hp, "Damage absorbed by shields"),
                ("final_hp_damage", final_hp_damage, "Damage that reduced HP"),
                ("potential_kills", potential_kills, "Estimated kills from this attack"),
            ]
            for key, value, note in detail_fields:
                try:
                    numeric_val = float(value)
                except (TypeError, ValueError):
                    numeric_val = None
                if key == "potential_kills" and (numeric_val is None or numeric_val <= 0):
                    continue
                auto_steps.append({"label": key.replace("_", " ").title(), "value": value, "note": note})
            if auto_steps:
                log_entry["calculation_steps"] = auto_steps
        self.round_combat_actions_log.append(log_entry)
        sid = skill_id or ("counter_attack" if is_counter else "basic_attack")
        attacker.increment_skill_trigger_count(sid)
        if final_hp_damage > 0:
            defender.damage_contributors_this_round[attacker.name] = (
                defender.damage_contributors_this_round.get(attacker.name, 0.0)
                + final_hp_damage
            )
            skill_map = defender.damage_contributors_by_skill_this_round.setdefault(
                attacker.name, {}
            )
            skill_map[sid] = skill_map.get(sid, 0.0) + final_hp_damage

    def _log_skill_trigger(
        self,
        triggered_army: Army,
        skill_name: str,
        effect_description: str,
        damage_details: Optional[Dict[str, Any]] = None,
        calculation_steps: Optional[list[dict[str, Any]]] = None,
    ):
        log_entry = {"skill_name": skill_name, "effect_description": effect_description}
        details_copy = copy.deepcopy(damage_details) if damage_details else None
        calc_steps = copy.deepcopy(calculation_steps) if calculation_steps else None
        if details_copy:
            embedded_steps = details_copy.pop("calculation_steps", None)
            if embedded_steps and calc_steps is None:
                calc_steps = embedded_steps
            log_entry.update(details_copy)
        if calc_steps:
            log_entry["calculation_steps"] = calc_steps
        else:
            auto_steps: list[dict[str, Any]] = []
            detail_fields: list[tuple[str, str, str]] = [
                ("damage_done_hp", "Damage dealt", "Final damage applied to the target"),
                ("absorbed_hp", "Damage absorbed", "Damage prevented by shields or mitigation"),
                ("shield_hp_gained", "Shield gained", "Shield amount applied from this effect"),
                ("healed_hp", "Healing applied", "Healing after all bonuses and reductions"),
                ("rage_generated", "Rage generated", "Rage produced by this trigger"),
                ("rage_reduced", "Rage reduced", "Rage removed from the opponent"),
                ("rage_spent", "Rage spent", "Rage consumed to activate the skill"),
                ("potential_kills", "Potential kills", "Troops this effect could defeat"),
            ]
            for key, label, note in detail_fields:
                if key not in log_entry:
                    continue
                value = log_entry.get(key)
                numeric_val: float | None
                try:
                    numeric_val = float(value)
                except (TypeError, ValueError):
                    numeric_val = None
                if key == "potential_kills" and (numeric_val is None or numeric_val <= 0):
                    continue
                auto_steps.append({"label": label, "value": value, "note": note})
            if effect_description:
                auto_steps.append({"label": "Effect source", "value": effect_description})
            if auto_steps:
                log_entry["calculation_steps"] = auto_steps
        self.round_skill_triggers_log[triggered_army.name].append(log_entry)

    def _calculate_generic_skill_damage(
        self,
        source_army: Army,
        target_army: Army,
        damage_factor: float,
        is_hero2_rage_skill: bool = False,
        source_skill_def: Optional[SkillDefinition] = None,
        damage_application_target: Optional[Army] = None,
        *,
        damage_is_over_time: bool = False,
    ) -> Tuple[float, float, int, float, list[dict[str, Any]]]:
        if source_army.current_troop_count <= 0:
            return 0.0, 0.0, 0, 0.0, []

        calc_target = target_army
        apply_target = damage_application_target or target_army

        evasion_effect = None
        calc_steps: list[dict[str, Any]] = []
        if apply_target and not damage_is_over_time:
            evasion_effect = self._attempt_evasion(
                apply_target, source_army, "SKILL", source_skill_def
            )

        own_total_attack = source_army.unit.effective_attack(source_army.active_effects)
        enemy_total_defense = calc_target.unit.effective_defense(calc_target.active_effects)
        if enemy_total_defense <= 0: enemy_total_defense = 1

        own_troop_scalar = GameSimulator.troop_scalar(source_army.current_troop_count)
        target_unit_type = calc_target.unit.unit_type
        attacker_unit_type = source_army.unit.unit_type

        skill_label_context = None
        labels: list[PluginSkillLabel] = []
        if source_skill_def:
            labels = source_skill_def.get("labels", []) or []
            if PluginSkillLabel.REACTIVE in labels:
                skill_label_context = PluginSkillLabel.REACTIVE.value.upper()
            elif PluginSkillLabel.COOPERATION in labels:
                skill_label_context = PluginSkillLabel.COOPERATION.value.upper()
            elif PluginSkillLabel.COMMAND in labels:
                skill_label_context = PluginSkillLabel.COMMAND.value.upper()

        skill_damage_percent_boosts = source_army.get_sum_stat_magnitudes(
            StatType.GENERAL_DAMAGE_MODIFIER,
            attack_type_filter="SKILL",
            target_unit_type=target_unit_type,
            skill_label=skill_label_context,
        )
        relevant_stats = {StatType.GENERAL_DAMAGE_MODIFIER}
        if calc_target.is_rally:
            rally_bonus = source_army.get_sum_stat_magnitudes(
                StatType.DAMAGE_AGAINST_RALLY_ARMIES,
                attack_type_filter="SKILL",
                target_unit_type=target_unit_type,
                skill_label=skill_label_context,
            )
            skill_damage_percent_boosts += rally_bonus
            relevant_stats.add(StatType.DAMAGE_AGAINST_RALLY_ARMIES)
        current_skill_trigger_type = source_skill_def.get("trigger") if source_skill_def else None

        if current_skill_trigger_type == SkillTriggerType.RAGE_SKILL:
            skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                StatType.RAGE_SKILL_DAMAGE_MODIFIER,
                attack_type_filter="SKILL",
                target_unit_type=target_unit_type,
                skill_label=skill_label_context,
            )
            relevant_stats.add(StatType.RAGE_SKILL_DAMAGE_MODIFIER)
            if not is_hero2_rage_skill:
                skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                    StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER,
                    attack_type_filter="SKILL",
                    target_unit_type=target_unit_type,
                    skill_label=skill_label_context,
                )
                relevant_stats.add(StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER)
            elif is_hero2_rage_skill:
                skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                    StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER,
                    attack_type_filter="SKILL",
                    target_unit_type=target_unit_type,
                    skill_label=skill_label_context,
                )
                relevant_stats.add(StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER)

        if (
            source_skill_def
            and source_skill_def.get("trigger") == SkillTriggerType.CHANCE_PER_ROUND
            and source_skill_def.get("config", {}).get("trigger_interval", 0) > 0
            and PluginSkillLabel.COMMAND in source_skill_def.get("labels", [])
        ):
            skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                StatType.COMMAND_SKILL_DAMAGE_MODIFIER,
                attack_type_filter="SKILL",
                target_unit_type=target_unit_type,
                skill_label=skill_label_context,
            )
            relevant_stats.add(StatType.COMMAND_SKILL_DAMAGE_MODIFIER)

        if (
            current_skill_trigger_type
            in [
                SkillTriggerType.ON_COUNTER_ATTACK,
                SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
                SkillTriggerType.ON_RECEIVING_HEALING,
                SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE,
            ]
            and source_skill_def
            and PluginSkillLabel.REACTIVE in source_skill_def.get("labels", [])
        ):
            skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                StatType.REACTIVE_SKILL_DAMAGE_ADJUST,
                attack_type_filter="SKILL",
                target_unit_type=target_unit_type,
                skill_label=skill_label_context,
            )
            relevant_stats.add(StatType.REACTIVE_SKILL_DAMAGE_ADJUST)

        if source_skill_def and PluginSkillLabel.COOPERATION in source_skill_def.get("labels", []):
            skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                StatType.COOPERATION_SKILL_DAMAGE_MODIFIER,
                attack_type_filter="SKILL",
                target_unit_type=target_unit_type,
                skill_label=skill_label_context,
            )
            relevant_stats.add(StatType.COOPERATION_SKILL_DAMAGE_MODIFIER)

        if (
            source_skill_def
            and current_skill_trigger_type != SkillTriggerType.RAGE_SKILL
            and PluginSkillLabel.COMMAND not in labels
            and PluginSkillLabel.COOPERATION not in labels
            and PluginSkillLabel.REACTIVE not in labels
            and source_skill_def.get("type") in {
                SkillType.PLUGIN_SKILL,
                SkillType.BASE_SKILL,
                SkillType.TALENT,
            }
        ):
            skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                StatType.PASSIVE_SKILL_DAMAGE_MODIFIER,
                attack_type_filter="SKILL",
                target_unit_type=target_unit_type,
                skill_label=skill_label_context,
            )
            relevant_stats.add(StatType.PASSIVE_SKILL_DAMAGE_MODIFIER)

        positive_boost_effects: list[EffectInstance] = []
        for stat in relevant_stats:
            positive_boost_effects.extend(
                eff
                for eff in source_army.iter_stat_effects(
                    stat,
                    attack_type_filter="SKILL",
                    target_unit_type=target_unit_type,
                    skill_label=skill_label_context,
                )
                if eff.magnitude > 0
            )
        total_positive_boost = sum(eff.magnitude for eff in positive_boost_effects)
        attacker_negative_mags = skill_damage_percent_boosts - total_positive_boost

        current_shield_hp = apply_target.get_current_shield_hp()
        damage_taken_percent_mods = calc_target.get_sum_stat_magnitudes(
            StatType.DAMAGE_TAKEN_MULTIPLIER,
            attack_type_filter="SKILL",
            attacker_unit_type=attacker_unit_type,
            skill_label=skill_label_context,
        )
        defender_positive_effects: list[EffectInstance] = []
        dr_effects = []
        for eff in apply_target.iter_stat_effects(
            StatType.DAMAGE_TAKEN_MULTIPLIER,
            attack_type_filter="SKILL",
            attacker_unit_type=attacker_unit_type,
            skill_label=skill_label_context,
        ):
            if eff.magnitude < 0:
                dr_effects.append(eff)
            elif eff.magnitude > 0:
                defender_positive_effects.append(eff)

        total_dr_magnitude = sum(eff.magnitude for eff in dr_effects)
        defender_positive_mags = sum(eff.magnitude for eff in defender_positive_effects)

        total_skill_percentage_points = skill_damage_percent_boosts + damage_taken_percent_mods
        base_skill_percentage_points = total_skill_percentage_points

        crit_stat_lookup = {
            PluginSkillLabel.REACTIVE.value.upper(): StatType.REACTIVE_SKILL_CRIT_RATE,
            PluginSkillLabel.COOPERATION.value.upper(): StatType.COOPERATION_SKILL_CRIT_RATE,
            PluginSkillLabel.COMMAND.value.upper(): StatType.COMMAND_SKILL_CRIT_RATE,
        }
        crit_rate = 0.0
        crit_triggered = False
        crit_stat = crit_stat_lookup.get(skill_label_context or "")
        if crit_stat is not None:
            crit_rate = source_army.get_sum_stat_magnitudes(
                crit_stat,
                attack_type_filter="SKILL",
                target_unit_type=target_unit_type,
                skill_label=skill_label_context,
            )
            crit_rate = max(0.0, min(1.0, crit_rate))
        if crit_rate > 0 and random.random() < crit_rate:
            total_skill_percentage_points += 0.5
            crit_triggered = True

        advantage_multiplier, advantage_bonus = self._resolve_advantage_adjustment(
            source_army.unit, calc_target.unit
        )

        def advantaged_multiplier(base_percentage_points: float) -> float:
            return max(0.05, 1.0 + base_percentage_points + advantage_bonus) * advantage_multiplier

        final_skill_damage_multiplier = advantaged_multiplier(total_skill_percentage_points)

        skill_hp_damage_potential = (own_total_attack / enemy_total_defense) * own_troop_scalar * (
            damage_factor / 200.0)
        damage_after_percent_mods = skill_hp_damage_potential * final_skill_damage_multiplier
        damage_after_all_mods = damage_after_percent_mods

        dmg_multiplier_no_dr = advantaged_multiplier(
            skill_damage_percent_boosts + defender_positive_mags
        )
        damage_no_dr = skill_hp_damage_potential * dmg_multiplier_no_dr

        dmg_multiplier_no_boost = advantaged_multiplier(
            attacker_negative_mags + damage_taken_percent_mods
        )
        damage_no_boost = (
            skill_hp_damage_potential * dmg_multiplier_no_boost
        )

        dmg_multiplier_no_defender_positive = advantaged_multiplier(
            skill_damage_percent_boosts + total_dr_magnitude
        )
        damage_no_defender_positive = (
            skill_hp_damage_potential
            * dmg_multiplier_no_defender_positive
        )

        preview_hp_damage_to_troops, preview_absorbed_by_shield = apply_target.preview_shield_absorption(
            damage_after_all_mods
        )
        hp_damage_expected = preview_hp_damage_to_troops
        hp_damage_without_dr = max(0.0, damage_no_dr - current_shield_hp)
        hp_saved = max(0.0, hp_damage_without_dr - hp_damage_expected)
        hp_damage_without_boost = max(0.0, damage_no_boost - current_shield_hp)
        hp_damage_without_defender_positive = max(
            0.0, damage_no_defender_positive - current_shield_hp
        )

        raw_damage_for_logging = damage_after_all_mods

        if evasion_effect is not None:
            prevented_note = ""
            troops_saved = 0.0
            if hp_damage_expected > 0:
                enemy_hp_per_troop = apply_target.unit.effective_hp_per_troop(
                    apply_target.active_effects
                )
                if enemy_hp_per_troop <= 0:
                    enemy_hp_per_troop = 1
                troops_saved = hp_damage_expected / enemy_hp_per_troop
                if troops_saved > 0:
                    apply_target.skill_damage_reduction_totals[evasion_effect.source_skill_id] = (
                        apply_target.skill_damage_reduction_totals.get(
                            evasion_effect.source_skill_id, 0.0
                        )
                        + troops_saved
                    )
                prevented_note = f" preventing {hp_damage_expected:.0f} damage"
                if troops_saved > 0:
                    prevented_note += f" (~{troops_saved:.1f} troops)"
            elif preview_absorbed_by_shield > 0:
                prevented_note = f" preventing {preview_absorbed_by_shield:.0f} damage"

            attack_desc = "skill"
            if source_skill_def:
                skill_name = source_skill_def.get("name") or source_skill_def.get("id", "skill")
                attack_desc = f"skill '{skill_name}'"
            attacker_name = source_army.name if source_army else "Unknown"
            self._log_skill_trigger(
                apply_target,
                evasion_effect.name,
                f"evades the {attack_desc} from {attacker_name}{prevented_note}.",
            )
            return 0.0, 0.0, 0, 0.0, []

        damage_result_skill = apply_target.apply_shields_and_get_hp_damage(
            damage_after_all_mods
        )
        actual_skill_hp_damage_to_troops = damage_result_skill["hp_damage_to_troops"]
        skill_damage_absorbed_by_shield = damage_result_skill["absorbed_by_shield"]

        enemy_hp_per_troop = apply_target.unit.effective_hp_per_troop(
            apply_target.active_effects
        )
        if enemy_hp_per_troop <= 0:
            enemy_hp_per_troop = 1
        if crit_triggered:
            base_multiplier_no_crit = advantaged_multiplier(base_skill_percentage_points)
            damage_without_crit = (
                skill_hp_damage_potential
                * base_multiplier_no_crit
            )
            extra_hp_from_crit = max(0.0, damage_after_all_mods - damage_without_crit)
            crit_troops = (
                extra_hp_from_crit / enemy_hp_per_troop if enemy_hp_per_troop else 0.0
            )
            if crit_troops > 0 and source_skill_def and skill_label_context:
                skill_id = source_skill_def.get("id")
                if isinstance(skill_id, str) and skill_id:
                    crit_totals = source_army.skill_crit_kill_boost_totals.setdefault(
                        skill_id, {}
                    )
                    crit_totals[skill_label_context] = crit_totals.get(
                        skill_label_context, 0.0
                    ) + crit_troops
        extra_hp_from_boost = actual_skill_hp_damage_to_troops - hp_damage_without_boost
        if extra_hp_from_boost > 0 and total_positive_boost > 0:
            for eff in positive_boost_effects:
                weight = eff.magnitude / total_positive_boost
                troops = (extra_hp_from_boost * weight) / enemy_hp_per_troop
                source_army.skill_kill_boost_totals[eff.source_skill_id] = (
                    source_army.skill_kill_boost_totals.get(eff.source_skill_id, 0.0)
                    + troops
                )

        extra_hp_from_defender_positive = (
            actual_skill_hp_damage_to_troops - hp_damage_without_defender_positive
        )
        if (
            extra_hp_from_defender_positive > 0
            and defender_positive_effects
            and defender_positive_mags > 0
        ):
            for eff in defender_positive_effects:
                if eff.magnitude <= 0:
                    continue
                weight = eff.magnitude / defender_positive_mags
                troops = (extra_hp_from_defender_positive * weight) / enemy_hp_per_troop
                owner_name = eff.config.get("source_army_name")
                owner_army = (
                    apply_target._find_army_by_name(owner_name)
                    if owner_name
                    else None
                )
                if owner_army is None:
                    continue
                owner_army.skill_kill_boost_totals[eff.source_skill_id] = (
                    owner_army.skill_kill_boost_totals.get(eff.source_skill_id, 0.0)
                    + troops
                )

        # enemy_hp_per_troop already computed above
        if enemy_hp_per_troop <= 0: enemy_hp_per_troop = 1

        if hp_saved > 0 and total_dr_magnitude < 0:
            for eff in dr_effects:
                weight = abs(eff.magnitude) / abs(total_dr_magnitude)
                troops_saved = (hp_saved * weight) / enemy_hp_per_troop
                apply_target.skill_damage_reduction_totals[eff.source_skill_id] = (
                    apply_target.skill_damage_reduction_totals.get(eff.source_skill_id, 0.0) + troops_saved
                )

        potential_skill_kills = 0
        if actual_skill_hp_damage_to_troops > 0:
            potential_skill_kills = round(actual_skill_hp_damage_to_troops / enemy_hp_per_troop)

        if actual_skill_hp_damage_to_troops > 0:
            apply_target.damage_contributors_this_round[source_army.name] = (
                apply_target.damage_contributors_this_round.get(source_army.name, 0.0)
                + actual_skill_hp_damage_to_troops
            )
            sid = source_skill_def["id"] if source_skill_def else "unknown"
            skill_map = apply_target.damage_contributors_by_skill_this_round.setdefault(
                source_army.name, {}
            )
            skill_map[sid] = skill_map.get(sid, 0.0) + actual_skill_hp_damage_to_troops

        if actual_skill_hp_damage_to_troops > 0 and apply_target:
            skill_name = "skill damage"
            if source_skill_def:
                skill_name = f"skill '{source_skill_def.get('name', source_skill_def.get('id', 'skill'))}'"
            self._apply_retribution_damage(
                defender=apply_target,
                attacker=source_army,
                damage_taken=actual_skill_hp_damage_to_troops,
                context_desc=skill_name,
            )
        # Skill damage is tracked for commitment totals but no longer logged
        # as a combat action.  This keeps combat action reports focused on
        # basic and counter attacks while skill effects are reported solely in
        # the skill trigger section.

        calc_steps.extend(
            [
                {"label": "Effective ATK", "value": own_total_attack},
                {"label": "Effective DEF", "value": enemy_total_defense},
                {"label": "Troop scalar", "value": own_troop_scalar},
                {"label": "Damage factor", "value": damage_factor},
                {"label": "Base potential", "value": skill_hp_damage_potential},
                {
                    "label": "Attacker modifiers",
                    "value": skill_damage_percent_boosts,
                    "note": "Total damage bonus from attacker",
                },
                {
                    "label": "Defender modifiers",
                    "value": damage_taken_percent_mods,
                    "note": "Damage taken adjustments on defender",
                },
                {"label": "Advantage bonus", "value": advantage_bonus},
                {"label": "Advantage multiplier", "value": advantage_multiplier},
                {
                    "label": "Crit applied",
                    "value": crit_triggered,
                    "note": f"Crit rate: {crit_rate:.2f}",
                },
                {"label": "Final multiplier", "value": final_skill_damage_multiplier},
                {"label": "After mods", "value": damage_after_all_mods},
                {"label": "Shield absorbed", "value": skill_damage_absorbed_by_shield},
                {"label": "HP damage", "value": actual_skill_hp_damage_to_troops},
                {"label": "Potential kills", "value": potential_skill_kills},
            ]
        )

        return (
            actual_skill_hp_damage_to_troops,
            skill_damage_absorbed_by_shield,
            potential_skill_kills,
            raw_damage_for_logging,
            calc_steps,
        )

    def _attempt_evasion(
        self,
        defender: Army,
        attacker: Army,
        attack_type: str,
        source_skill_def: Optional[SkillDefinition],
    ) -> Optional[EffectInstance]:
        """Return the evasion effect instance when the attack is avoided."""

        if attack_type.upper() not in {"BASIC", "COUNTER", "SKILL"}:
            return None

        evasion_effects = [
            eff
            for eff in defender.active_effects
            if eff.effect_type == EffectType.CUSTOM_SKILL_EFFECT
            and eff.config.get("evasion_chance", 0) > 0
            and (
                not eff.config.get("applies_to")
                or attack_type.upper()
                in {
                    str(entry).upper()
                    for entry in (eff.config.get("applies_to") or [])
                }
            )
        ]
        if not evasion_effects:
            return None

        random.shuffle(evasion_effects)
        for effect in evasion_effects:
            chance = float(effect.config.get("evasion_chance", 0))
            if chance <= 0:
                continue
            if random.random() >= chance:
                continue

            return effect

        return None

    def _apply_retribution_damage(
        self,
        defender: Army,
        attacker: Army,
        damage_taken: float,
        context_desc: str,
    ) -> None:
        """Apply retribution damage from defender back to attacker if applicable."""

        if damage_taken <= 0 or attacker.current_troop_count <= 0:
            return

        retribution_effects = [
            eff
            for eff in defender.active_effects
            if eff.effect_type == EffectType.CUSTOM_SKILL_EFFECT
            and eff.config.get("retribution_rate", 0) > 0
        ]
        if not retribution_effects:
            return

        for effect in retribution_effects:
            rate = float(effect.config.get("retribution_rate", 0))
            rate = min(max(rate, 0.0), 1.0)
            if rate <= 0:
                continue
            returned_hp = damage_taken * rate
            if returned_hp <= 0:
                continue

            attacker.pending_hp_damage_this_round += returned_hp
            defender_name = defender.name
            attacker.damage_contributors_this_round[defender_name] = (
                attacker.damage_contributors_this_round.get(defender_name, 0.0)
                + returned_hp
            )
            skill_map = attacker.damage_contributors_by_skill_this_round.setdefault(
                defender_name, {}
            )
            skill_map[effect.source_skill_id] = skill_map.get(
                effect.source_skill_id, 0.0
            ) + returned_hp

            self._log_skill_trigger(
                defender,
                effect.name,
                f"reflects {returned_hp:.0f} damage back to {attacker.name} ({context_desc}).",
            )

    def _calculate_shield_magnitude_for_logging(self, owner_army: Army, opponent_for_calc: Army,
                                                shield_factor: float) -> float:
        """Calculate shield magnitude for logging/display purposes.
        
        Note: owner_army is the army receiving the shield (usually same as triggering_army for self-shields).
        opponent_for_calc is the opponent used for the base calculation.
        """
        if not opponent_for_calc or owner_army.current_troop_count <= 0: return 0.0

        own_atk = owner_army.unit.effective_attack(owner_army.active_effects)
        enemy_def = opponent_for_calc.unit.effective_defense(opponent_for_calc.active_effects)
        if enemy_def == 0: enemy_def = 1

        own_troop_scalar = GameSimulator.troop_scalar(owner_army.current_troop_count)
        base_shield_mag = round(((own_atk / enemy_def) * own_troop_scalar * (shield_factor / 200.0)))
        sum_shield_strength_mods = owner_army.get_sum_stat_magnitudes(StatType.SHIELD_STRENGTH_MODIFIER)
        shield_strength_multiplier = 1.0 + sum_shield_strength_mods
        magnitude = round(base_shield_mag * shield_strength_multiplier)
        
        # Apply pairing multiplier (same logic as in _create_and_add_single_effect)
        # For shields, pairing is determined by the army receiving the shield vs its direct target
        # In _create_and_add_single_effect, target_army is the shield recipient
        # Here, owner_army is the shield recipient (for self-shields, owner_army == target_army)
        pairing_opponent = owner_army._get_pairing_opponent_for_shield(owner_army, opponent_for_calc)
        if pairing_opponent:
            pairing_mult = heal_shield_pairing_config.get_multiplier(
                owner_army.unit.unit_type,
                pairing_opponent.unit.unit_type,
                "shield"
            )
            magnitude = round(magnitude * pairing_mult)
        
        return magnitude

    def _mount_skill_has_direct_damage(self, skill_def: SkillDefinition) -> bool:
        cfg = skill_def.get("config", {}) or {}
        return any(cfg.get(key, 0) > 0 for key in ("damage_factor", "instant_damage_factor", "conditional_damage_factor"))

    def _extract_mount_skill_non_damage_components(self, skill_def: SkillDefinition) -> Dict[str, Any]:
        cfg = copy.deepcopy(skill_def.get("config", {}) or {})
        cfg.pop("damage_factor", None)
        cfg.pop("instant_damage_factor", None)
        cfg.pop("conditional_damage_factor", None)

        stat_mods: Dict[str, Dict[str, Any]] = {}
        for mod in cfg.get("stat_mods") or []:
            stat = getattr(mod.get("stat_to_mod"), "value", mod.get("stat_to_mod"))
            magnitude = mod.get("buff_magnitude", 0)
            if stat is None:
                continue
            if stat not in stat_mods or magnitude > stat_mods[stat].get("buff_magnitude", 0):
                stat_mods[stat] = mod
        if stat_mods:
            cfg["stat_mods"] = list(stat_mods.values())
        elif "stat_mods" in cfg:
            cfg["stat_mods"] = []

        for key, value in list(cfg.items()):
            if key == "stat_mods":
                continue
            if isinstance(value, (int, float)):
                continue
            cfg[key] = value

        return cfg

    def _merge_mount_skill_non_damage_configs(self, skill_defs: List[SkillDefinition]) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for skill_def in skill_defs:
            components = self._extract_mount_skill_non_damage_components(skill_def)

            if "stat_mods" in components:
                merged.setdefault("stat_mods", [])
                existing = {getattr(mod.get("stat_to_mod"), "value", mod.get("stat_to_mod")): mod for mod in merged["stat_mods"]}
                for mod in components["stat_mods"]:
                    stat = getattr(mod.get("stat_to_mod"), "value", mod.get("stat_to_mod"))
                    magnitude = mod.get("buff_magnitude", 0)
                    if stat is None:
                        continue
                    if stat not in existing or magnitude > existing[stat].get("buff_magnitude", 0):
                        existing[stat] = mod
                merged["stat_mods"] = list(existing.values())

            for key, value in components.items():
                if key == "stat_mods":
                    continue
                if isinstance(value, (int, float)):
                    current = merged.get(key, float("-inf"))
                    if value > current:
                        merged[key] = value
                elif key not in merged:
                    merged[key] = value

        return merged

    def _apply_mount_skill_non_damage_config(self, base_config: Dict[str, Any], merged_config: Dict[str, Any],
                                             include_non_damage: bool) -> Dict[str, Any]:
        cfg = copy.deepcopy(base_config)
        if not include_non_damage:
            cfg.pop("stat_mods", None)
            for key in merged_config:
                if key in ("damage_factor", "instant_damage_factor", "conditional_damage_factor"):
                    continue
                if key in ("trigger_interval",):
                    continue
                if isinstance(cfg.get(key), (int, float)):
                    cfg[key] = 0
                elif isinstance(cfg.get(key), list):
                    cfg[key] = []
            return cfg

        for key, value in merged_config.items():
            if key == "stat_mods":
                cfg[key] = copy.deepcopy(value)
            elif key not in ("damage_factor", "instant_damage_factor", "conditional_damage_factor"):
                cfg[key] = value
        return cfg

    def _process_skill_triggers(self, triggering_army: Army, opponent_army: Army, trigger_type: SkillTriggerType,
                                event_data: Optional[Dict[str, Any]] = None):
        actual_effect_target = opponent_army
        actual_opponent_for_calc = opponent_army
        if event_data:
            if 'direct_target_army' in event_data:
                actual_effect_target = event_data['direct_target_army']
            if 'opponent_for_shield_calc' in event_data:
                actual_opponent_for_calc = event_data['opponent_for_shield_calc']

        skill_definitions: list[SkillDefinition] = []
        for hero in triggering_army.heroes:
            skill_definitions.extend(hero.skills)
        gem_skills = getattr(triggering_army, "gem_skills", []) or []
        skill_definitions.extend(gem_skills)

        mount_skill_groups: Dict[str, List[SkillDefinition]] = {}
        for skill_def in skill_definitions:
            if skill_def.get("type") == SkillType.MOUNT_SKILL:
                mount_skill_groups.setdefault(skill_def["id"], []).append(skill_def)

        mount_skill_non_damage_configs = {
            skill_id: self._merge_mount_skill_non_damage_configs(defs)
            for skill_id, defs in mount_skill_groups.items()
        }
        mount_skill_damage_allowance = {
            skill_id: sum(1 for sd in defs if self._mount_skill_has_direct_damage(sd))
            for skill_id, defs in mount_skill_groups.items()
        }

        for skill_def in skill_definitions:
            if skill_def["id"] == "dummy_talent_empty":
                continue
            if skill_def["trigger"] == SkillTriggerType.RAGE_SKILL:
                continue
            if skill_def["trigger"] == SkillTriggerType.PASSIVE:
                continue

            if skill_def["trigger"] == trigger_type:
                base_chance = skill_def.get("trigger_chance", 1.0)
                coop_bonus = 0.0
                if (
                    skill_def["trigger"]
                    in [SkillTriggerType.ON_BASIC_ATTACK, SkillTriggerType.ON_OWN_RAGE_SKILL_CAST]
                    and PluginSkillLabel.COOPERATION in skill_def.get("labels", [])
                ):
                    coop_bonus = triggering_army.get_sum_stat_magnitudes(
                        StatType.COOPERATION_TRIGGER_RATE_MODIFIER
                    )
                final_chance = min(1.0, base_chance + coop_bonus)
                if random.random() < final_chance:
                    skill_id = skill_def["id"]
                    skill_cfg = skill_def.get("config", {})
                    cooldown = None
                    if skill_def.get("trigger") != SkillTriggerType.CHANCE_PER_ROUND:
                        cooldown_enabled = self._cooldown_enabled_for_skill(skill_def)
                        if skill_def.get("trigger") == SkillTriggerType.ON_COUNTER_ATTACK:
                            cooldown_enabled = True
                        cooldown = (
                            skill_cfg.get("cooldown_rounds") if cooldown_enabled else None
                        )
                    an_effect_truly_happened = False
                    log_details_current_skill: List[Tuple[str, Optional[Dict[str, Any]]]] = []

                    is_on_cooldown = False
                    if cooldown is not None:
                        last_triggered = triggering_army.skill_last_triggered_round.get(
                            skill_id, -(cooldown + 1)
                        )
                        if triggering_army.army_round < last_triggered + cooldown:
                            is_on_cooldown = True
                    if is_on_cooldown:
                        continue

                    # New cooldown for skills that trigger on active skill casts: 2 triggers max in 9 rounds
                    # Some skills have 1 trigger max in 9 rounds instead
                    # Only apply if cooldowns are enabled for this skill type
                    if skill_def["trigger"] in (SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, SkillTriggerType.ON_OWN_COMMAND_SKILL_CAST):
                        cooldown_enabled_for_active_cast = self._cooldown_enabled_for_skill(skill_def)
                        if cooldown_enabled_for_active_cast:
                            max_triggers_limit = 1 if skill_id in ACTIVE_CAST_ONE_TRIGGER_SKILLS else 2
                            
                            trigger_rounds = triggering_army.skill_active_cast_trigger_rounds.get(skill_id, [])
                            current_round = triggering_army.army_round
                            
                            # Filter out old triggers (more than 9 rounds ago)
                            recent_triggers = [r for r in trigger_rounds if current_round - r < 9]
                            
                            # Block if we've reached the max triggers in the last 9 rounds
                            if len(recent_triggers) >= max_triggers_limit:
                                oldest_recent_trigger = min(recent_triggers)
                                if current_round - oldest_recent_trigger < 9:
                                    continue

                    max_triggers = 1
                    max_triggers_per_target = 1
                    current_triggers = 0
                    targets_triggered = triggering_army.skill_triggers_against_this_round.get(skill_id, set())
                    if self.mode in ("battlefield", "arena"):
                        max_triggers = skill_cfg.get("max_triggers_per_round", 1)
                        max_triggers_per_target = skill_cfg.get("max_triggers_per_target_per_round", 1)
                        current_triggers = triggering_army.skill_trigger_counts_this_round.get(skill_id, 0)

                    if max_triggers > 1:
                        if current_triggers >= max_triggers or (
                            actual_effect_target.name in targets_triggered and max_triggers_per_target == 1
                        ):
                            continue
                    else:
                        if skill_def.get("type") == SkillType.MOUNT_SKILL and skill_id in triggering_army.triggered_skills_this_round:
                            damage_limit = mount_skill_damage_allowance.get(skill_id, 0)
                            damage_used = triggering_army.mount_skill_damage_triggers_this_round.get(skill_id, 0)
                            if not (self._mount_skill_has_direct_damage(skill_def) and damage_used < damage_limit):
                                continue
                        elif skill_id in triggering_army.triggered_skills_this_round:
                            continue

                    effective_skill_def = skill_def
                    include_non_damage = True
                    if skill_def.get("type") == SkillType.MOUNT_SKILL:
                        include_non_damage = skill_id not in triggering_army.mount_skill_non_damage_applied_this_round
                        merged_cfg = mount_skill_non_damage_configs.get(skill_id, {})
                        effective_skill_def = copy.deepcopy(skill_def)
                        base_cfg = effective_skill_def.get("config", {}) or {}
                        effective_skill_def["config"] = self._apply_mount_skill_non_damage_config(
                            base_cfg, merged_cfg, include_non_damage
                        )

                    logic_handler: Optional[SkillLogicHandler] = effective_skill_def.get("logic_handler")
                    if logic_handler:
                        handler_event_data = (event_data or {}).copy()
                        handler_event_data["actual_opponent_for_calc"] = actual_opponent_for_calc
                        an_effect_truly_happened, log_details_current_skill = logic_handler(
                            triggering_army, actual_effect_target, effective_skill_def, handler_event_data, self
                        )
                    elif "sub_effects" in effective_skill_def:
                        for sub_effect_data in effective_skill_def["sub_effects"]:
                            if random.random() < sub_effect_data.get("chance", 1.0):
                                effect_to_apply = sub_effect_data["effect_to_apply"]
                                target_sub = actual_effect_target if effective_skill_def.get("target") == "ENEMY" else triggering_army
                                created_effect = triggering_army._create_and_add_single_effect(
                                    effect_to_apply.copy(),
                                    skill_id,
                                    triggering_army,
                                    target_sub,
                                    actual_opponent_for_calc,
                                )
                                if created_effect:
                                    an_effect_truly_happened = True
                                    log_details_current_skill.append(
                                        (
                                            f"{sub_effect_data.get('name_suffix', 'Effect')}: {created_effect.get_functionality_description()} for {created_effect.duration + 1} rounds.",
                                            None,
                                        )
                                    )
                    elif "effects_to_apply" in effective_skill_def and effective_skill_def["effects_to_apply"]:
                        target_std = actual_effect_target if effective_skill_def.get("target") == "ENEMY" else triggering_army
                        applied_details = triggering_army._add_effects_from_skill_def(
                            effective_skill_def, target_std, triggering_army, actual_opponent_for_calc
                        )
                        if applied_details:
                            an_effect_truly_happened = True
                            for _, desc in applied_details:
                                log_details_current_skill.append((desc, None))

                    if an_effect_truly_happened:
                        self._log_skill_trigger(triggering_army, effective_skill_def["name"], "Triggered.")
                        for desc_str, dmg_details in log_details_current_skill:
                            self._log_skill_trigger(triggering_army, f"  ↳", desc_str, damage_details=dmg_details)
                        triggering_army.increment_skill_trigger_count(skill_id)

                        if include_non_damage and skill_def.get("type") == SkillType.MOUNT_SKILL:
                            triggering_army.mount_skill_non_damage_applied_this_round.add(skill_id)

                        if skill_def.get("type") == SkillType.MOUNT_SKILL and self._mount_skill_has_direct_damage(effective_skill_def):
                            had_damage = any(details for _, details in log_details_current_skill if details and "damage_done_hp" in details)
                            if had_damage:
                                triggering_army.mount_skill_damage_triggers_this_round[skill_id] = (
                                    triggering_army.mount_skill_damage_triggers_this_round.get(skill_id, 0) + 1
                                )

                        if skill_def.get("trigger") == SkillTriggerType.CHANCE_PER_ROUND:
                            self._process_skill_triggers(
                                triggering_army,
                                actual_effect_target,
                                SkillTriggerType.ON_OWN_COMMAND_SKILL_CAST,
                                event_data={
                                    "source_command_skill_id": skill_id,
                                    "opponent_for_shield_calc": actual_opponent_for_calc,
                                    "direct_target_army": actual_effect_target,
                                },
                            )

                        if cooldown is not None:
                            triggering_army.skill_last_triggered_round[skill_id] = triggering_army.army_round

                        # Record trigger round for active skill cast cooldown tracking
                        # Only track if cooldowns are enabled for this skill type
                        if skill_def["trigger"] in (SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, SkillTriggerType.ON_OWN_COMMAND_SKILL_CAST):
                            cooldown_enabled_for_active_cast = self._cooldown_enabled_for_skill(skill_def)
                            if cooldown_enabled_for_active_cast:
                                max_triggers_to_keep = 1 if skill_id in ACTIVE_CAST_ONE_TRIGGER_SKILLS else 2
                                
                                if skill_id not in triggering_army.skill_active_cast_trigger_rounds:
                                    triggering_army.skill_active_cast_trigger_rounds[skill_id] = []
                                current_round = triggering_army.army_round
                                # Clean up old triggers (more than 9 rounds ago) before adding new one
                                triggering_army.skill_active_cast_trigger_rounds[skill_id] = [
                                    r for r in triggering_army.skill_active_cast_trigger_rounds[skill_id]
                                    if current_round - r < 9
                                ]
                                # Add the new trigger round
                                triggering_army.skill_active_cast_trigger_rounds[skill_id].append(current_round)
                                # Keep only the max allowed triggers (1 for special skills, 2 for others)
                                if len(triggering_army.skill_active_cast_trigger_rounds[skill_id]) > max_triggers_to_keep:
                                    triggering_army.skill_active_cast_trigger_rounds[skill_id] = sorted(
                                        triggering_army.skill_active_cast_trigger_rounds[skill_id]
                                    )[-max_triggers_to_keep:]

                        if max_triggers > 1:
                            triggering_army.skill_trigger_counts_this_round[skill_id] = current_triggers + 1
                            targets_triggered.add(actual_effect_target.name)
                            triggering_army.skill_triggers_against_this_round[skill_id] = targets_triggered
                        else:
                            if skill_id not in triggering_army.triggered_skills_this_round:
                                triggering_army.triggered_skills_this_round.append(skill_id)

    def _execute_rage_skills(self, army: Army, opponent: Army, is_hero2_delayed_trigger: bool = False):
        skill_to_execute_id: Optional[str] = None
        hero_who_triggered_name: str = "Unknown Hero"
        hero_slot = 0

        if is_hero2_delayed_trigger:
            skill_to_execute_id = army.hero2_rage_skill_id
            if len(army.heroes) > 1 and army.heroes[1]: hero_who_triggered_name = army.heroes[1].name
            hero_slot = 2
        else:
            if army.hero1_rage_skill_queued_this_round and army.hero1_rage_skill_id:
                skill_to_execute_id = army.hero1_rage_skill_id
                if army.heroes and army.heroes[0]: hero_who_triggered_name = army.heroes[0].name
                hero_slot = 1
            else:
                return

        if not skill_to_execute_id:
            return
        skill_def = army.hero1_rage_skill_def if hero_slot == 1 else army.hero2_rage_skill_def
        if not skill_def:
            print(f"Warning: Rage skill ID '{skill_to_execute_id}' not available for {army.name}.")
            if hero_slot == 1:
                army.hero1_rage_skill_queued_this_round = False
                army.hero1_rage_skill_scheduled_round = None
            elif hero_slot == 2:
                if army.hero2_rage_skill_primed_for_round == army.army_round:
                    army.hero2_rage_skill_primed_for_round = None
            return

        is_silenced = False

        if not is_hero2_delayed_trigger:
            rage_cost = skill_def.get("rage_cost", 1000)
            if army.current_rage < rage_cost:
                army.hero1_rage_skill_queued_this_round = False
                army.hero1_rage_skill_scheduled_round = None
                self._log_skill_trigger(
                    army,
                    skill_def['name'],
                    "Trigger canceled due to insufficient rage.")
                return

        for effect in army.active_effects:
            if effect.name == EFFECT_NAME_SILENCE_DEBUFF and effect.config.get("prevents_rage_skill_cast"):
                is_silenced = True
                self._log_skill_trigger(army, skill_def['name'],
                                        f"Cast blocked by Silence from {effect.source_skill_id}.")
                if hero_slot == 1:
                    army.hero1_rage_skill_cast_blocked_by_silence_this_round = True
                    army.hero1_rage_skill_scheduled_round = army.army_round + 1
                    army.hero1_rage_skill_queued_this_round = False
                    self._log_skill_trigger(
                        army,
                        skill_def['name'],
                        f"Hero 1 rage skill deferred to Round {army.hero1_rage_skill_scheduled_round} due to Silence.",
                    )
                elif hero_slot == 2:
                    next_attempt_round = army.army_round + 1
                    army.hero2_rage_skill_primed_for_round = next_attempt_round
                    self._log_skill_trigger(
                        army,
                        skill_def['name'],
                        f"Hero 2 skill cast re-primed for Round {army.hero2_rage_skill_primed_for_round} due to Silence.",
                    )
                return

        log_prefix = f"(Delayed Hero 2) " if is_hero2_delayed_trigger else f"{hero_who_triggered_name}'s "
        an_effect_happened_rage = False
        log_details_rage: List[Tuple[str, Optional[Dict[str, Any]]]] = []
        damage_dealt_by_rage = False
        rage_before_cast = army.current_rage

        current_round_rage_gain = army.rage_added_this_round
        if not is_hero2_delayed_trigger:
            rage_cost = skill_def.get("rage_cost", 1000)
            # Rage cost is used only as a trigger threshold; all existing rage is reset
            army.current_rage = max(0.0, current_round_rage_gain)
            army.army_used_rage_skill_this_round_for_rage_gain_block = True
            army.hero1_rage_skill_used_round = army.army_round
            army.hero1_rage_skill_queued_this_round = False
            delay_rounds = 0
            if army.hero1_rage_skill_scheduled_round is not None:
                delay_rounds = army.army_round - army.hero1_rage_skill_scheduled_round
            army.hero1_rage_skill_scheduled_round = None

            if army.hero2_rage_skill_id and len(army.heroes) > 1:
                if delay_rounds >= 2:
                    army.hero2_rage_skill_primed_for_round = None
                else:
                    next_rage_round = army.army_round + (2 if self.mode == "standard" else 1)
                    army.hero2_rage_skill_primed_for_round = next_rage_round
        else:
            if army.hero2_rage_skill_primed_for_round == army.army_round:
                army.hero2_rage_skill_primed_for_round = None

        rage_logic_handler: Optional[RageSkillLogicHandler] = skill_def.get("logic_handler")
        if rage_logic_handler:
            handler_event_data = {
                "is_hero2_delayed_rage": is_hero2_delayed_trigger,
                "triggering_hero_slot": hero_slot,
                "current_rage_before_cast": rage_before_cast,
                "actual_opponent_for_calc": opponent
            }
            if (
                self.mode in ("arena", "battlefield")
                and skill_def.get("id") == "base_skill_indomitable_spirit"
                and "additional_targets" not in handler_event_data
            ):
                engine = getattr(self, "parent_engine", None)
                if engine:
                    extras = []
                    get_direct_attackers = getattr(engine, "get_direct_attackers", None)
                    for attacker in ((get_direct_attackers(army.name) if get_direct_attackers else []) or []):
                        if not attacker or attacker is opponent:
                            continue
                        if attacker.current_troop_count <= 0:
                            continue
                        extras.append(attacker)
                        if len(extras) >= 3:
                            break
                    if extras:
                        handler_event_data["additional_targets"] = extras
            an_effect_happened_rage, log_details_rage, damage_dealt_by_rage = \
                rage_logic_handler(army, opponent, skill_def, handler_event_data, self)
        elif "effects_to_apply" in skill_def:
            target_army_for_effect = opponent if skill_def.get("target") == "ENEMY" else army
            applied_details = army._add_effects_from_skill_def(skill_def, target_army_for_effect, army, opponent)
            if applied_details:
                an_effect_happened_rage = True
                for _, desc in applied_details:
                    log_details_rage.append((desc, None))
                if skill_def.get("target") == "ENEMY":
                    for eff_data in skill_def["effects_to_apply"]:
                        if eff_data.get("effect_type") == EffectType.DAMAGE_OVER_TIME:
                            damage_dealt_by_rage = True;
                            break

        if an_effect_happened_rage:
            self._log_skill_trigger(army, f"{log_prefix}{skill_def['name']}", "Rage Skill Triggered.")
            for desc_str, dmg_details in log_details_rage:
                self._log_skill_trigger(army, "  ↳", desc_str, damage_details=dmg_details)
            army.increment_skill_trigger_count(skill_def["id"])

            self._process_skill_triggers(army, opponent, SkillTriggerType.ON_OWN_RAGE_SKILL_CAST,
                                         event_data={"source_rage_skill_id": skill_to_execute_id,
                                                     "hero_slot": hero_slot,
                                                     "opponent_for_shield_calc": opponent})
            army.activate_queued_effects()
            if opponent.current_troop_count > 0:
                opponent.activate_queued_effects()

        if damage_dealt_by_rage and opponent.current_troop_count > 0:
            self._process_skill_triggers(opponent, army, SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE,
                                         event_data={'attacking_army_for_tit_for_tat': army,
                                                     "opponent_for_shield_calc": army})
            opponent.activate_queued_effects()
            if army.current_troop_count > 0:
                army.activate_queued_effects()

    def _apply_base_rage_gain(self) -> None:
        """Grant each army 100 rage at end of round unless their Hero 1 rage skill was used or blocked."""
        for army in [self.army1, self.army2]:
            if army.army_round < 1:
                army.base_rage_awarded_this_round = False
                continue
            # In battlefield mode a defender may participate in multiple
            # engagements within the same global round.  ``_apply_base_rage_gain``
            # can therefore be invoked multiple times for the same army which
            # previously caused base rage to stack erroneously.  Guard against
            # this by skipping processing if base rage has already been awarded
            # for the current round.
            if army.base_rage_awarded_this_round:
                continue

            if (
                army.army_used_rage_skill_this_round_for_rage_gain_block
                or army.hero1_rage_skill_cast_blocked_by_silence_this_round
            ):
                army.base_rage_awarded_this_round = False
            else:
                army.add_rage(100, source_skill_id="base_rage")
                army.base_rage_awarded_this_round = True

    def _generate_round_figures(self) -> None:
        base_dir = os.path.join(os.path.dirname(__file__), "histograms")
        os.makedirs(base_dir, exist_ok=True)
        rounds = list(range(1, len(self.army1.damage_dealt_history) + 1))

        def save_plot(data: List[float], fname: str, title: str, ylabel: str, color: str) -> None:
            with plt.style.context("ggplot"):
                fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
                fig.patch.set_facecolor("#2e2e2e")
                ax.set_facecolor("#2e2e2e")
                ax.plot(rounds, data, color=color, linewidth=1)
                ax.set_title(title, fontsize=6, color="white")
                ax.set_xlabel("Round", fontsize=6, color="white")
                ax.set_ylabel(ylabel, fontsize=6, color="white")
                ax.tick_params(axis="both", labelsize=6, colors="white")
                ax.grid(linewidth=0.2)
                fig.tight_layout()
                fig.savefig(os.path.join(base_dir, fname), dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
                plt.close(fig)

        save_plot(self.army1.damage_dealt_history, "damage_accumulated_army1.png", f"{self.army1.name} Damage Dealt", "Damage", "green")
        save_plot(self.army2.damage_dealt_history, "damage_accumulated_army2.png", f"{self.army2.name} Damage Dealt", "Damage", "red")
        save_plot(self.army1.heal_received_history, "heal_accumulated_army1.png", f"{self.army1.name} Healing Received", "Healing", "green")
        save_plot(self.army2.heal_received_history, "heal_accumulated_army2.png", f"{self.army2.name} Healing Received", "Healing", "red")
        save_plot(self.army1.shield_received_history, "shield_accumulated_army1.png", f"{self.army1.name} Shield Received", "Shield", "green")
        save_plot(self.army2.shield_received_history, "shield_accumulated_army2.png", f"{self.army2.name} Shield Received", "Shield", "red")
        save_plot(self.army1.rage_gained_history, "rage_per_round_army1.png", f"{self.army1.name} Rage Per Round", "Rage", "green")
        save_plot(self.army2.rage_gained_history, "rage_per_round_army2.png", f"{self.army2.name} Rage Per Round", "Rage", "red")

    def _calculate_and_log_attack(self, att: Army, dfd: Army, is_counter: bool) -> Tuple[float, float, float, int]:
        if att.current_troop_count <= 0: return 0.0, 0.0, 0.0, 0

        prevent_config_key = "prevents_counterattack" if is_counter else "prevents_basic_attack"
        prevent_effect_name = EFFECT_NAME_BROKEN_BLADE_DEBUFF if is_counter else EFFECT_NAME_DISARM_DEBUFF
        action_name_log = "counter-attack" if is_counter else "basic attack"

        for effect in att.active_effects:
            if effect.name == prevent_effect_name or effect.config.get(prevent_config_key):
                self._log_skill_trigger(att, effect.name, f"{att.name} cannot {action_name_log} due to {effect.name}.")
                return 0.0, 0.0, 0.0, 0

        attack_type_code = "COUNTER" if is_counter else "BASIC"
        evasion_effect = self._attempt_evasion(dfd, att, attack_type_code, None)

        attacker_effective_atk = att.unit.effective_attack(att.active_effects)
        defender_effective_def = dfd.unit.effective_defense(dfd.active_effects)
        if defender_effective_def <= 0: defender_effective_def = 1

        troop_count_scalar = GameSimulator.troop_scalar(att.current_troop_count)
        raw_damage_potential = (attacker_effective_atk / defender_effective_def) * troop_count_scalar

        specific_attack_stat = StatType.COUNTER_DAMAGE_ADJUST if is_counter else StatType.BASIC_DAMAGE_ADJUST
        target_unit_type = dfd.unit.unit_type
        attacker_unit_type = att.unit.unit_type
        attack_type_for_defense_filter = "COUNTER" if is_counter else "BASIC"
        sum_specific_attack_magnitudes = att.get_sum_stat_magnitudes(
            specific_attack_stat,
            attack_type_filter=attack_type_for_defense_filter,
            target_unit_type=target_unit_type,
        )
        sum_general_attacker_magnitudes = att.get_sum_stat_magnitudes(
            StatType.GENERAL_DAMAGE_MODIFIER,
            attack_type_filter=attack_type_for_defense_filter,
            target_unit_type=target_unit_type,
        )
        sum_rally_bonus = 0.0
        if dfd.is_rally:
            sum_rally_bonus = att.get_sum_stat_magnitudes(
                StatType.DAMAGE_AGAINST_RALLY_ARMIES,
                attack_type_filter=attack_type_for_defense_filter,
                target_unit_type=target_unit_type,
            )

        positive_boost_effects = [
            eff
            for eff in att.iter_stat_effects(
                specific_attack_stat,
                attack_type_filter=attack_type_for_defense_filter,
                target_unit_type=target_unit_type,
            )
            if eff.magnitude > 0
        ]
        positive_boost_effects.extend(
            eff
            for eff in att.iter_stat_effects(
                StatType.GENERAL_DAMAGE_MODIFIER,
                attack_type_filter=attack_type_for_defense_filter,
                target_unit_type=target_unit_type,
            )
            if eff.magnitude > 0
        )
        if dfd.is_rally:
            positive_boost_effects.extend(
                eff
                for eff in att.iter_stat_effects(
                    StatType.DAMAGE_AGAINST_RALLY_ARMIES,
                    attack_type_filter=attack_type_for_defense_filter,
                    target_unit_type=target_unit_type,
                )
                if eff.magnitude > 0
            )
        total_positive_boost = sum(eff.magnitude for eff in positive_boost_effects)
        attacker_negative_mags = (
            sum_specific_attack_magnitudes
            + sum_general_attacker_magnitudes
            + sum_rally_bonus
            - total_positive_boost
        )

        current_shield_hp = dfd.get_current_shield_hp()

        defender_positive_effects: list[EffectInstance] = []
        dr_effects: list[EffectInstance] = []
        for eff in dfd.iter_stat_effects(
            StatType.DAMAGE_TAKEN_MULTIPLIER,
            attack_type_filter=attack_type_for_defense_filter,
            attacker_unit_type=attacker_unit_type,
        ):
            if eff.magnitude < 0:
                dr_effects.append(eff)
            elif eff.magnitude > 0:
                defender_positive_effects.append(eff)

        total_dr_magnitude = sum(eff.magnitude for eff in dr_effects)
        defender_positive_mags = sum(eff.magnitude for eff in defender_positive_effects)
        sum_defender_reduction_magnitudes = total_dr_magnitude + defender_positive_mags

        total_additive_percentage_points = (
            sum_specific_attack_magnitudes +
            sum_general_attacker_magnitudes +
            sum_rally_bonus +
            sum_defender_reduction_magnitudes
        )

        advantage_multiplier, advantage_bonus = self._resolve_advantage_adjustment(
            att.unit, dfd.unit
        )

        def advantaged_multiplier(base_percentage_points: float) -> float:
            return max(0.05, 1.0 + base_percentage_points + advantage_bonus) * advantage_multiplier

        final_damage_multiplier = advantaged_multiplier(total_additive_percentage_points)
        damage_after_all_percent_mods = raw_damage_potential * final_damage_multiplier

        dmg_multiplier_no_dr = advantaged_multiplier(
            sum_specific_attack_magnitudes + sum_general_attacker_magnitudes + defender_positive_mags,
        )
        damage_no_dr = raw_damage_potential * dmg_multiplier_no_dr

        dmg_multiplier_no_boost = advantaged_multiplier(
            attacker_negative_mags + sum_defender_reduction_magnitudes,
        )
        damage_no_boost = raw_damage_potential * dmg_multiplier_no_boost

        dmg_multiplier_no_defender_positive = advantaged_multiplier(
            sum_specific_attack_magnitudes
            + sum_general_attacker_magnitudes
            + total_dr_magnitude,
        )
        damage_no_defender_positive = (
            raw_damage_potential * dmg_multiplier_no_defender_positive
        )

        preview_hp_damage_to_troops, preview_absorbed_by_shield = dfd.preview_shield_absorption(
            damage_after_all_percent_mods
        )
        hp_damage_expected = preview_hp_damage_to_troops
        hp_damage_without_dr = max(0.0, damage_no_dr - current_shield_hp)
        hp_saved = max(0.0, hp_damage_without_dr - hp_damage_expected)
        hp_damage_without_boost = max(0.0, damage_no_boost - current_shield_hp)
        hp_damage_without_defender_positive = max(
            0.0, damage_no_defender_positive - current_shield_hp
        )

        if evasion_effect is not None:
            prevented_note = ""
            troops_saved = 0.0
            if hp_damage_expected > 0:
                defender_hp_per_troop = dfd.unit.effective_hp_per_troop(dfd.active_effects)
                if defender_hp_per_troop <= 0:
                    defender_hp_per_troop = 1
                troops_saved = hp_damage_expected / defender_hp_per_troop
                if troops_saved > 0:
                    dfd.skill_damage_reduction_totals[evasion_effect.source_skill_id] = (
                        dfd.skill_damage_reduction_totals.get(evasion_effect.source_skill_id, 0.0)
                        + troops_saved
                    )
                prevented_note = f" preventing {hp_damage_expected:.0f} damage"
                if troops_saved > 0:
                    prevented_note += f" (~{troops_saved:.1f} troops)"
            elif preview_absorbed_by_shield > 0:
                prevented_note = f" preventing {preview_absorbed_by_shield:.0f} damage"

            attack_desc = "counter-attack" if is_counter else "basic attack"
            attacker_name = att.name if att else "Unknown"
            self._log_skill_trigger(
                dfd,
                evasion_effect.name,
                f"evades the {attack_desc} from {attacker_name}{prevented_note}.",
            )
            return 0.0, 0.0, 0.0, 0

        shield_processing_result = dfd.apply_shields_and_get_hp_damage(damage_after_all_percent_mods)
        hp_damage_to_troops = shield_processing_result['hp_damage_to_troops']
        absorbed_by_shield = shield_processing_result['absorbed_by_shield']
        extra_hp_from_boost = hp_damage_to_troops - hp_damage_without_boost
        if extra_hp_from_boost > 0 and total_positive_boost > 0:
            defender_hp_per_troop = dfd.unit.effective_hp_per_troop(dfd.active_effects)
            if defender_hp_per_troop <= 0:
                defender_hp_per_troop = 1
            for eff in positive_boost_effects:
                weight = eff.magnitude / total_positive_boost
                troops = (extra_hp_from_boost * weight) / defender_hp_per_troop
                att.skill_kill_boost_totals[eff.source_skill_id] = (
                    att.skill_kill_boost_totals.get(eff.source_skill_id, 0.0) + troops
                )

        extra_hp_from_defender_positive = (
            hp_damage_to_troops - hp_damage_without_defender_positive
        )
        if (
            extra_hp_from_defender_positive > 0
            and defender_positive_effects
            and defender_positive_mags > 0
        ):
            defender_hp_per_troop = dfd.unit.effective_hp_per_troop(dfd.active_effects)
            if defender_hp_per_troop <= 0:
                defender_hp_per_troop = 1
            for eff in defender_positive_effects:
                if eff.magnitude <= 0:
                    continue
                weight = eff.magnitude / defender_positive_mags
                troops = (extra_hp_from_defender_positive * weight) / defender_hp_per_troop
                owner_name = eff.config.get("source_army_name")
                owner_army = dfd._find_army_by_name(owner_name) if owner_name else None
                if owner_army is None:
                    continue
                owner_army.skill_kill_boost_totals[eff.source_skill_id] = (
                    owner_army.skill_kill_boost_totals.get(eff.source_skill_id, 0.0)
                    + troops
                )

        if hp_damage_to_troops > 0:
            dfd.pending_hp_damage_this_round += hp_damage_to_troops

        defender_hp_per_troop = dfd.unit.effective_hp_per_troop(dfd.active_effects)
        if defender_hp_per_troop <= 0: defender_hp_per_troop = 1

        if hp_saved > 0 and total_dr_magnitude < 0:
            for eff in dr_effects:
                weight = abs(eff.magnitude) / abs(total_dr_magnitude)
                troops_saved = (hp_saved * weight) / defender_hp_per_troop
                dfd.skill_damage_reduction_totals[eff.source_skill_id] = (
                    dfd.skill_damage_reduction_totals.get(eff.source_skill_id, 0.0) + troops_saved
                )

        potential_units_killed_this_hit_rounded = 0
        if hp_damage_to_troops > 0:
            potential_units_killed_this_hit_float = hp_damage_to_troops / defender_hp_per_troop
            potential_units_killed_this_hit_rounded = round(potential_units_killed_this_hit_float)

        sid = "counter_attack" if is_counter else "basic_attack"
        calc_steps = [
            {"label": "Effective ATK", "value": attacker_effective_atk},
            {"label": "Effective DEF", "value": defender_effective_def},
            {"label": "Troop scalar", "value": troop_count_scalar},
            {"label": "Raw potential", "value": raw_damage_potential},
            {"label": "Total % mods", "value": total_additive_percentage_points},
            {"label": "Advantage bonus", "value": advantage_bonus},
            {"label": "Advantage multiplier", "value": advantage_multiplier},
            {"label": "Final multiplier", "value": final_damage_multiplier},
            {"label": "After mods", "value": damage_after_all_percent_mods},
            {"label": "Shield absorbed", "value": absorbed_by_shield},
            {"label": "HP damage", "value": hp_damage_to_troops},
        ]

        self._log_combat_action(
            attacker=att,
            defender=dfd,
            damage_potential_hp=damage_after_all_percent_mods,
            absorbed_hp=absorbed_by_shield,
            final_hp_damage=hp_damage_to_troops,
            potential_kills=potential_units_killed_this_hit_rounded,
            is_counter=is_counter,
            skill_id=sid,
            calculation_steps=calc_steps,
        )

        if hp_damage_to_troops > 0:
            context = "counter-attack" if is_counter else "basic attack"
            self._apply_retribution_damage(
                defender=dfd,
                attacker=att,
                damage_taken=hp_damage_to_troops,
                context_desc=context,
            )

        return hp_damage_to_troops, absorbed_by_shield, damage_after_all_percent_mods, potential_units_killed_this_hit_rounded

    def _estimate_post_wound_troops(self, army: Army) -> float:
        if army.pending_hp_damage_this_round <= 0 or army.current_troop_count <= 0:
            return army.current_troop_count
        hp_per_troop = army.unit.effective_hp_per_troop(army.active_effects)
        if hp_per_troop <= 0:
            hp_per_troop = 1
        lost_float = army.pending_hp_damage_this_round / hp_per_troop
        lost_round = round(lost_float)
        available_troops = min(round(army.current_troop_count), lost_round)
        return max(0.0, army.current_troop_count - available_troops)

    def _apply_sizeref_unrevivable_ratios(self) -> None:
        armies = (self.army1, self.army2)
        if not any(
            army.resolve_unrevivable_ratio_method() == "sizeref" for army in armies
        ):
            for army in armies:
                army.pending_unrevivable_ratio = None
            return

        army1_post_wound = self._estimate_post_wound_troops(self.army1)
        army2_post_wound = self._estimate_post_wound_troops(self.army2)
        larger_count = max(army1_post_wound, army2_post_wound)
        smaller_count = min(army1_post_wound, army2_post_wound)
        if smaller_count <= 0 or larger_count <= 0:
            smaller_ratio = 1.0
            larger_ratio = 1.0
        else:
            log_ratio = math.log10(larger_count / smaller_count)
            smaller_ratio = 0.1 + (0.8 * log_ratio)
            larger_ratio = 0.1 + (0.4 * log_ratio)
            smaller_ratio = min(1.0, max(0.0, smaller_ratio))
            larger_ratio = min(1.0, max(0.0, larger_ratio))

        for army in armies:
            if army.resolve_unrevivable_ratio_method() != "sizeref":
                army.pending_unrevivable_ratio = None
                continue
            other_army = self.army2 if army is self.army1 else self.army1
            current_post = army1_post_wound if army is self.army1 else army2_post_wound
            other_post = army2_post_wound if army is self.army1 else army1_post_wound
            if current_post <= other_post:
                army.pending_unrevivable_ratio = smaller_ratio
            else:
                army.pending_unrevivable_ratio = larger_ratio

    def apply_unrevivable_post_commit(self, mutual_engagement: bool = True) -> None:
        self._apply_dynamic_unrevivable_between(
            self.army1, self.army2, mutual_engagement
        )

    def _apply_dynamic_unrevivable_between(
        self, army_a: Army, army_b: Army, mutual_engagement: bool
    ) -> None:
        self._apply_dynamic_unrevivable_direction(army_a, army_b, mutual_engagement)
        self._apply_dynamic_unrevivable_direction(army_b, army_a, mutual_engagement)
        army_a.dynamic_losses_by_opponent.pop(army_b.name, None)
        army_b.dynamic_losses_by_opponent.pop(army_a.name, None)
        army_a.dynamic_kills_by_opponent.pop(army_b.name, None)
        army_b.dynamic_kills_by_opponent.pop(army_a.name, None)

    def _apply_dynamic_unrevivable_direction(
        self, defender: Army, opponent: Army, mutual_engagement: bool
    ) -> None:
        losses = defender.dynamic_losses_by_opponent.get(opponent.name)
        if not losses:
            return
        combat_losses = losses.get("combat", 0.0)
        skill_losses = losses.get("skill", 0.0)
        total_losses = combat_losses + skill_losses
        if total_losses <= 0.0:
            return
        if defender.resolve_unrevivable_ratio_method() != "dynamic":
            return

        opponent_kills = opponent.dynamic_kills_by_opponent.get(
            defender.name,
            {"combat_basic": 0.0, "combat_counter": 0.0, "skill": 0.0},
        )
        defender_kills = defender.dynamic_kills_by_opponent.get(
            opponent.name,
            {"combat_basic": 0.0, "combat_counter": 0.0, "skill": 0.0},
        )

        dynamic_settings = get_dynamic_unrevivable_settings()
        attacker_type = (getattr(opponent.unit, "unit_type", "") or "").lower()
        normalized_type = (
            attacker_type if attacker_type in DYNAMIC_UNIT_TYPES else DYNAMIC_UNIT_TYPES[0]
        )
        type_specific = get_dynamic_unrevivable_type_settings(normalized_type, dynamic_settings)
        combat_basic_base = type_specific["combat_basic_base"]
        combat_basic_bonus = type_specific["combat_basic_bonus_multiplier"]
        combat_counter_base = type_specific["combat_counter_base"]
        combat_counter_bonus = type_specific["combat_counter_bonus_multiplier"]
        skill_base = type_specific["skill_base"]
        skill_bonus = type_specific["skill_bonus_multiplier"]

        type_label = normalized_type.capitalize()

        total_basic_kills = defender_kills.get("combat_basic", 0.0) + opponent_kills.get(
            "combat_basic", 0.0
        )
        enemy_basic_kills = opponent_kills.get("combat_basic", 0.0)
        total_counter_kills = defender_kills.get("combat_counter", 0.0) + opponent_kills.get(
            "combat_counter", 0.0
        )
        enemy_counter_kills = opponent_kills.get("combat_counter", 0.0)
        total_combat_kills = total_basic_kills + total_counter_kills

        basic_ratio = combat_basic_base
        if total_basic_kills > 0:
            basic_ratio += (enemy_basic_kills / total_basic_kills) * combat_basic_bonus
        counter_ratio = combat_counter_base
        if total_counter_kills > 0:
            counter_ratio += (enemy_counter_kills / total_counter_kills) * combat_counter_bonus

        if total_combat_kills > 0:
            combat_ratio = 0.0
            if total_basic_kills > 0:
                combat_ratio += (total_basic_kills / total_combat_kills) * basic_ratio
            if total_counter_kills > 0:
                combat_ratio += (total_counter_kills / total_combat_kills) * counter_ratio
        else:
            combat_ratio = (basic_ratio + counter_ratio) / 2.0

        total_skill_kills = defender_kills.get("skill", 0.0) + opponent_kills.get("skill", 0.0)
        enemy_skill_kills = opponent_kills.get("skill", 0.0)
        skill_ratio = skill_base
        if total_skill_kills > 0:
            skill_ratio += (enemy_skill_kills / total_skill_kills) * skill_bonus

        combat_unrevivable = round(combat_losses * combat_ratio)
        skill_unrevivable = round(skill_losses * skill_ratio)
        added_unrevivable = combat_unrevivable + skill_unrevivable
        engagement_label = "mutual" if mutual_engagement else "non-mutual"
        log_message = (
            f"vs {opponent.name} ({engagement_label}): combat ratio {combat_ratio:.2%} "
            f"(basic {basic_ratio:.2%}, counter {counter_ratio:.2%}) on {combat_losses:.1f} "
            f"losses (+{combat_unrevivable}), skill ratio {skill_ratio:.2%} on "
            f"{skill_losses:.1f} losses (+{skill_unrevivable}) -> +{added_unrevivable} "
            f"unrevivable (using {type_label} attacker settings)."
        )

        if added_unrevivable > 0:
            # Allow unrevivable_troops to accumulate without cap - it represents total casualties
            # In rally mode, armies can receive reinforcements, so casualties can exceed initial count
            defender.unrevivable_troops = defender.unrevivable_troops + added_unrevivable
            # Track unrevivable caused by opponent (attacker) to this defender
            opponent.unrevivable_caused_by_opponent[defender.name] = (
                opponent.unrevivable_caused_by_opponent.get(defender.name, 0.0) + added_unrevivable
            )
        self._log_skill_trigger(defender, "Dynamic Unrevivable", log_message)

    def _apply_rally_reinforcements(self, army: Army, round: int) -> None:
        """Apply rally reinforcements to an army if rally mode is enabled and configured."""
        if not army.is_rally or not army.rally_config:
            return
        
        config = army.rally_config
        reinforcement_applied = False
        
        # Periodic reinforcements
        periodic = config.get("periodic", {})
        if periodic.get("enabled", False):
            interval = periodic.get("interval", 1)
            if interval > 0 and round % interval == 0:
                amount = float(periodic.get("amount", 0))
                army.current_troop_count += amount
                army.max_troop_count_reached = max(army.max_troop_count_reached, army.current_troop_count)
                reinforcement_applied = True
        
        # Loss-based reinforcements
        loss_based = config.get("loss_based", {})
        if loss_based.get("enabled", False):
            threshold = float(loss_based.get("threshold", 0))
            losses_since_last = army.troops_at_last_reinforcement - army.current_troop_count
            if losses_since_last >= threshold:
                amount = float(loss_based.get("amount", 0))
                army.current_troop_count += amount
                army.max_troop_count_reached = max(army.max_troop_count_reached, army.current_troop_count)
                reinforcement_applied = True
        
        # Round-specific reinforcements
        round_specific = config.get("round_specific", {})
        if round_specific.get("enabled", False):
            reinforcements = round_specific.get("reinforcements", [])
            for reinf in reinforcements:
                if isinstance(reinf, dict) and reinf.get("round") == round:
                    amount = float(reinf.get("amount", 0))
                    army.current_troop_count += amount
                    army.max_troop_count_reached = max(army.max_troop_count_reached, army.current_troop_count)
                    reinforcement_applied = True
        
        # Update tracking after any reinforcement
        if reinforcement_applied:
            army.troops_at_last_reinforcement = army.current_troop_count

    def simulate_battle(self, max_rounds: int | None = None) -> str:
        self.army1.reset_for_new_battle()
        self.army2.reset_for_new_battle()
        self.army1.register_simulator(self)
        self.army2.register_simulator(self)
        self.army1._apply_initial_passive_skills()
        self.army2._apply_initial_passive_skills()
        self.round = 0
        reached_max_rounds = False

        # When max_rounds is set, continue until max_rounds is reached regardless of troop counts
        # When max_rounds is not set, stop when one side has zero troops
        while (max_rounds is None or self.round < max_rounds):
            # Check if we should continue based on troop counts (only when max_rounds is not set)
            if max_rounds is None and not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
                break
            
            self.round += 1
            if max_rounds is not None and self.round >= max_rounds:
                reached_max_rounds = True
            for army in (self.army1, self.army2):
                army.army_round += 1
            
            # Apply rally reinforcements at the start of each round
            self._apply_rally_reinforcements(self.army1, self.round)
            self._apply_rally_reinforcements(self.army2, self.round)

            self.army1.rage_added_this_round = 0.0
            self.army2.rage_added_this_round = 0.0
            self.army1.shield_hp_gained_this_round = 0.0
            self.army2.shield_hp_gained_this_round = 0.0

            # CORRECTED: Reset pending damage/healing at the start of each round
            self.army1.pending_hp_damage_this_round = 0.0
            self.army1.pending_hp_healing_this_round = 0.0
            self.army2.pending_hp_damage_this_round = 0.0
            self.army2.pending_hp_healing_this_round = 0.0
            self.army1.damage_contributors_this_round = {}
            self.army2.damage_contributors_this_round = {}
            self.army1.damage_contributors_by_skill_this_round = {}
            self.army2.damage_contributors_by_skill_this_round = {}
            self.army1.heal_contributors_this_round = {}
            self.army2.heal_contributors_this_round = {}
            self.army1.kills_dealt_this_round = 0.0
            self.army2.kills_dealt_this_round = 0.0
            self.army1.clear_dynamic_unrevivable_tracking()
            self.army2.clear_dynamic_unrevivable_tracking()

            self.round_combat_actions_log.clear()
            self.round_skill_triggers_log = {self.army1.name: [], self.army2.name: []}
            # Reset flags that do not affect base rage calculation. Rage-related
            # flags are reset later so we can inspect last round's values.
            for army in [self.army1, self.army2]:
                army.triggered_skills_this_round.clear()
                army.skill_trigger_counts_this_round.clear()
                army.skill_triggers_against_this_round.clear()
                army.mount_skill_damage_triggers_this_round.clear()
                army.mount_skill_non_damage_applied_this_round.clear()
                army.maniacal_hot_triggered_this_round = False
                army.healing_hymn_triggered_this_round = False
                army.base_rage_awarded_this_round = False

            for army in [self.army1, self.army2]:
                if army.effects_to_activate_next_round:
                    army.upcoming_effects.extend(army.effects_to_activate_next_round)
                    army.effects_to_activate_next_round.clear()
                army.activate_queued_effects()
                army.decrement_effect_durations()

            self.army1.started_last_round_with_active_shield = self.army1.started_round_with_active_shield
            self.army2.started_last_round_with_active_shield = self.army2.started_round_with_active_shield
            self.army1.started_round_with_active_shield = self.army1.get_current_shield_hp() > 0
            self.army2.started_round_with_active_shield = self.army2.get_current_shield_hp() > 0

            # Determine if any rage skills were scheduled for this round
            for army in (self.army1, self.army2):
                army.hero1_rage_skill_queued_this_round = (
                    army.hero1_rage_skill_scheduled_round == self.round
                )

            # Rage skills will be executed after start-of-round effects
            # Only break early if max_rounds is not set
            if max_rounds is None and not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
                break
            if reached_max_rounds:
                break

            for army, opponent in [(self.army1, self.army2), (self.army2, self.army1)]:
                if army.current_troop_count <= 0: continue
                army.activate_queued_effects()
                army.apply_start_of_round_rage_deductions()
                army.process_periodic_effects('start_of_round', opponent=opponent)
                army.activate_queued_effects()
                self._process_skill_triggers(army, opponent, SkillTriggerType.CHANCE_PER_ROUND,
                                             event_data={'opponent_for_shield_calc': opponent})
                army.activate_queued_effects()
            # Schedule rage skills if rage threshold reached after start-of-round effects
            for army in (self.army1, self.army2):
                if (
                    army.current_troop_count > 0
                    and army.hero1_rage_skill_id
                    and army.hero1_rage_skill_scheduled_round is None
                    and (
                        army.hero2_rage_skill_primed_for_round is None
                        or army.hero2_rage_skill_primed_for_round != self.round + (2 if self.mode == "standard" else 1)
                    )
                ):
                    skill_def = army.hero1_rage_skill_def
                    if skill_def is not None and army.current_rage >= skill_def.get("rage_cost", 1000):
                        army.hero1_rage_skill_scheduled_round = self.round + 1
                        army.army_used_rage_skill_this_round_for_rage_gain_block = True

            # Only break early if max_rounds is not set
            if max_rounds is None and not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
                break
            if reached_max_rounds:
                break

            # Execute any queued rage skills after start-of-round effects.
            if self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0:
                if self.army1.hero1_rage_skill_queued_this_round:
                    self._execute_rage_skills(self.army1, self.army2, is_hero2_delayed_trigger=False)
                if self.army2.hero1_rage_skill_queued_this_round:
                    self._execute_rage_skills(self.army2, self.army1, is_hero2_delayed_trigger=False)

                if self.army1.hero2_rage_skill_primed_for_round == self.round:
                    self._execute_rage_skills(self.army1, self.army2, is_hero2_delayed_trigger=True)
                if self.army2.hero2_rage_skill_primed_for_round == self.round:
                    self._execute_rage_skills(self.army2, self.army1, is_hero2_delayed_trigger=True)



            if self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0:
                army1_disarmed = any(
                    eff.name == EFFECT_NAME_DISARM_DEBUFF or eff.config.get("prevents_basic_attack")
                    for eff in self.army1.active_effects
                )
                if not army1_disarmed:
                    self._process_skill_triggers(
                        self.army1,
                        self.army2,
                        SkillTriggerType.ON_BASIC_ATTACK,
                        event_data={"opponent_for_shield_calc": self.army2, "direct_target_army": self.army2},
                    )
                    self.army1.activate_queued_effects();
                    self.army2.activate_queued_effects()
                self._calculate_and_log_attack(self.army1, self.army2, is_counter=False)

                if self.army2.current_troop_count > 0:
                    if not army1_disarmed:
                        self._process_skill_triggers(
                            self.army2,
                            self.army1,
                            SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
                            event_data={
                                "opponent_for_shield_calc": self.army1,
                                "direct_target_army": self.army1,
                            },
                        )
                        self.army2.activate_queued_effects();
                        self.army1.activate_queued_effects()
                    self._process_skill_triggers(
                        self.army2,
                        self.army1,
                        SkillTriggerType.ON_COUNTER_ATTACK,
                        event_data={
                            "opponent_for_shield_calc": self.army1,
                            "direct_target_army": self.army1,
                        },
                    )
                    self.army2.activate_queued_effects();
                    self.army1.activate_queued_effects()
                    self._calculate_and_log_attack(self.army2, self.army1, is_counter=True)

            # Only break early if max_rounds is not set
            if max_rounds is None and not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
                break
            if reached_max_rounds:
                break

            if self.army2.current_troop_count > 0 and self.army1.current_troop_count > 0:
                army2_disarmed = any(
                    eff.name == EFFECT_NAME_DISARM_DEBUFF or eff.config.get("prevents_basic_attack")
                    for eff in self.army2.active_effects
                )
                if not army2_disarmed:
                    self._process_skill_triggers(
                        self.army2,
                        self.army1,
                        SkillTriggerType.ON_BASIC_ATTACK,
                        event_data={"opponent_for_shield_calc": self.army1, "direct_target_army": self.army1},
                    )
                    self.army2.activate_queued_effects();
                    self.army1.activate_queued_effects()
                self._calculate_and_log_attack(self.army2, self.army1, is_counter=False)

                if self.army1.current_troop_count > 0:
                    if not army2_disarmed:
                        self._process_skill_triggers(
                            self.army1,
                            self.army2,
                            SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
                            event_data={
                                "opponent_for_shield_calc": self.army2,
                                "direct_target_army": self.army2,
                            },
                        )
                        self.army1.activate_queued_effects();
                        self.army2.activate_queued_effects()
                    self._process_skill_triggers(
                        self.army1,
                        self.army2,
                        SkillTriggerType.ON_COUNTER_ATTACK,
                        event_data={
                            "opponent_for_shield_calc": self.army2,
                            "direct_target_army": self.army2,
                        },
                    )
                    self.army1.activate_queued_effects();
                    self.army2.activate_queued_effects()
                    self._calculate_and_log_attack(self.army1, self.army2, is_counter=True)

            # Only break early if max_rounds is not set
            if max_rounds is None and not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
                break
            if reached_max_rounds:
                break

            self._apply_sizeref_unrevivable_ratios()
            self.army1.commit_pending_healing_and_damage()
            self.army2.commit_pending_healing_and_damage()
            self.apply_unrevivable_post_commit(mutual_engagement=True)
            self.army1.troop_count_history.append(self.army1.current_troop_count)
            self.army2.troop_count_history.append(self.army2.current_troop_count)
            self.army1.unrevivable_history.append(self.army1.unrevivable_troops)
            self.army2.unrevivable_history.append(self.army2.unrevivable_troops)
            if self.track_stats:
                heal1 = self.army1.pending_hp_healing_this_round
                heal2 = self.army2.pending_hp_healing_this_round
            active_lines = self._log_active_effects_for_report()
            self.report_builder.emit_round(
                self.round,
                self.round_combat_actions_log,
                self.round_skill_triggers_log,
                active_effects=active_lines,
            )
            # Only break early if max_rounds is not set
            if max_rounds is None and not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
                if self.track_stats:
                    self.army1.kills_dealt_history.append(self.army1.kills_dealt_this_round)
                    self.army2.kills_dealt_history.append(self.army2.kills_dealt_this_round)
                break
            if reached_max_rounds:
                if self.track_stats:
                    self.army1.kills_dealt_history.append(self.army1.kills_dealt_this_round)
                    self.army2.kills_dealt_history.append(self.army2.kills_dealt_this_round)
                break

            for army, opponent in [(self.army1, self.army2), (self.army2, self.army1)]:
                if army.current_troop_count <= 0: continue
                army.process_periodic_effects('end_of_round', opponent=opponent)
                army.activate_queued_effects()

            # Apply base rage gain after combat and end-of-round effects
            self._apply_base_rage_gain()
            for army in [self.army1, self.army2]:
                army.army_used_rage_skill_this_round_for_rage_gain_block = False
                army.hero1_rage_skill_cast_blocked_by_silence_this_round = False

            if self.track_stats:
                dmg1 = self.army2.pending_hp_damage_this_round
                dmg2 = self.army1.pending_hp_damage_this_round
                prev = self.army1.damage_dealt_history[-1] if self.army1.damage_dealt_history else 0
                self.army1.damage_dealt_history.append(prev + dmg1)
                prev = self.army2.damage_dealt_history[-1] if self.army2.damage_dealt_history else 0
                self.army2.damage_dealt_history.append(prev + dmg2)
                prev = self.army1.heal_received_history[-1] if self.army1.heal_received_history else 0
                self.army1.heal_received_history.append(prev + heal1)
                prev = self.army2.heal_received_history[-1] if self.army2.heal_received_history else 0
                self.army2.heal_received_history.append(prev + heal2)
                prev = self.army1.shield_received_history[-1] if self.army1.shield_received_history else 0
                self.army1.shield_received_history.append(prev + self.army1.shield_hp_gained_this_round)
                prev = self.army2.shield_received_history[-1] if self.army2.shield_received_history else 0
                self.army2.shield_received_history.append(prev + self.army2.shield_hp_gained_this_round)
                self.army1.rage_gained_history.append(self.army1.rage_added_this_round)
                self.army2.rage_gained_history.append(self.army2.rage_added_this_round)
                self.army1.kills_dealt_history.append(self.army1.kills_dealt_this_round)
                self.army2.kills_dealt_history.append(self.army2.kills_dealt_this_round)

            for army in [self.army1, self.army2]:
                if army.current_troop_count <= 0:
                    continue
                if (
                    army.hero1_rage_skill_id
                    and army.hero1_rage_skill_scheduled_round is None
                    and (
                        army.hero2_rage_skill_primed_for_round is None
                        or army.hero2_rage_skill_primed_for_round != self.round + (2 if self.mode == "standard" else 1)
                    )
                ):
                    skill_def_h1_rage = army.hero1_rage_skill_def
                    if skill_def_h1_rage is not None and army.current_rage >= skill_def_h1_rage.get("rage_cost", 1000):
                        army.hero1_rage_skill_scheduled_round = self.round + 1

            if not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0): break


            self.report_builder.lines.append(
                f"\nEnd of Round {self.round} Status -> "
                f"{self.army1.name}: {self.army1.current_troop_count:.0f} troops "
                f"(Rage: {self.army1.current_rage:.0f}, DMG Taken: "
                f"{self.report_builder._c(str(round(self.army1.pending_hp_damage_this_round)), Fore.RED)}, "
                f"Healing: {self.report_builder._c(str(round(self.army1.pending_hp_healing_this_round)), Fore.GREEN)}); "
                f"{self.army2.name}: {self.army2.current_troop_count:.0f} troops "
                f"(Rage: {self.army2.current_rage:.0f}, DMG Taken: "
                f"{self.report_builder._c(str(round(self.army2.pending_hp_damage_this_round)), Fore.RED)}, "
                f"Healing: {self.report_builder._c(str(round(self.army2.pending_hp_healing_this_round)), Fore.GREEN)})")

        self.report_builder.lines.append("\n--- Skill Trigger Counts ---")
        for army_obj in [self.army1, self.army2]:
            self.report_builder.lines.append(f"\n*{army_obj.name}*:")
            if not army_obj.heroes:
                self.report_builder.lines.append("  No heroes.")
                continue
            has_printed_for_army = False
            for hero_obj in army_obj.heroes:
                talents_triggered, base_skills_triggered, plugin_skills_triggered = [], [], []
                for skill_def_obj in hero_obj.skills:
                    if skill_def_obj['id'] == "dummy_talent_empty": continue
                    count = army_obj.skill_trigger_counts.get(skill_def_obj['id'], 0)
                    skill_entry = f"    - {skill_def_obj['name']}: {count} time(s)"
                    skill_type_val = skill_def_obj.get('type')
                    if isinstance(skill_type_val, SkillType):
                        if skill_type_val == SkillType.TALENT:
                            talents_triggered.append(skill_entry)
                        elif skill_type_val == SkillType.BASE_SKILL:
                            base_skills_triggered.append(skill_entry)
                        elif skill_type_val == SkillType.PLUGIN_SKILL:
                            plugin_skills_triggered.append(skill_entry)

                if talents_triggered or base_skills_triggered or plugin_skills_triggered:
                    has_printed_for_army = True
                    self.report_builder.lines.append(f"\n  *{hero_obj.name}*:")
                    if talents_triggered:
                        self.report_builder.lines.append("    Talents:")
                        self.report_builder.lines.append("\n".join(talents_triggered))
                    if base_skills_triggered:
                        self.report_builder.lines.append("    Base Skills:")
                        self.report_builder.lines.append("\n".join(base_skills_triggered))
                    if plugin_skills_triggered:
                        self.report_builder.lines.append("    Plugin Skills:")
                        self.report_builder.lines.append("\n".join(plugin_skills_triggered))
            if not has_printed_for_army:
                self.report_builder.lines.append("  No skills triggered or no skills equipped for any hero.")

        self.report_builder.lines.append(f"\nTotal Rounds: {self.round}")
        winner = "Neither (Draw - Both armies were defeated simultaneously)"
        
        # Check if battle ended due to max_rounds and both armies are still alive
        if max_rounds is not None and self.round >= max_rounds and self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0:
            # Determine winner based on total damage dealt (kills + unrevivable)
            army1_total_damage = sum(self.army1.kills_dealt_history) + sum(self.army1.unrevivable_caused_by_opponent.values())
            army2_total_damage = sum(self.army2.kills_dealt_history) + sum(self.army2.unrevivable_caused_by_opponent.values())
            if army1_total_damage > army2_total_damage:
                winner = self.army1.name
            elif army2_total_damage > army1_total_damage:
                winner = self.army2.name
            else:
                winner = "Draw (Equal damage)"
        elif self.army1.current_troop_count > 0 and self.army2.current_troop_count <= 0:
            winner = self.army1.name
        elif self.army2.current_troop_count > 0 and self.army1.current_troop_count <= 0:
            winner = self.army2.name
        elif self.army1.current_troop_count <= 0 and self.army2.current_troop_count <= 0 and self.round > 0:
            winner = "Mutual Destruction"

        self.report_builder.emit_final(
            winner,
            self.round,
            f"Final State: {self.army1.name}: {self.army1.current_troop_count:.0f} troops (Unrevivable: {self.army1.unrevivable_troops:.0f})",
            f"{self.army2.name}: {self.army2.current_troop_count:.0f} troops (Unrevivable: {self.army2.unrevivable_troops:.0f})",
        )
        if self.track_stats:
            self._generate_round_figures()
        report_text = self.report_builder.get_report_text()
        self.report_builder.print_report()
        return report_text
