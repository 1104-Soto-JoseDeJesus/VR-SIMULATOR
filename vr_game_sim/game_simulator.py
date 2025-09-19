# === File: game_simulator.py ===
import math
import random
import os
from functools import lru_cache
from typing import List, Optional, Dict, Any, Tuple

import matplotlib.pyplot as plt

from .enums import SkillTriggerType, StatType, EffectType, SkillType, DoTType, PluginSkillLabel
from .unit_definition import Unit
from .army_composition import Army
from .skill_system import SkillDefinition, SkillLogicHandler, RageSkillLogicHandler
from .skill_definitions import SKILL_REGISTRY_GLOBAL
from .constants import (
    EFFECT_NAME_BROKEN_BLADE_DEBUFF,
    EFFECT_NAME_DISARM_DEBUFF,
    EFFECT_NAME_SILENCE_DEBUFF,
    EFFECT_NAME_JUDGEMENT_MARKER,
)
from .dynamic_unrevivable_config import get_settings as get_dynamic_unrevivable_settings
from .report_builder import ReportBuilder
from colorama import Fore


class GameSimulator:
    SKILL_REGISTRY_GLOBAL = SKILL_REGISTRY_GLOBAL

    @staticmethod
    @lru_cache(maxsize=None)
    def troop_scalar(T: float) -> float:
        # This function calculates a scalar based on troop count.
        if T <= 0: return 0.0
        if 1 <= T <= 100: return math.exp(-0.02426063 * (math.log(T) ** 2) + 0.53658754 * math.log(T) + 5.87457112)
        if 100 < T <= 1000: return 327.53303836 * (T ** 0.45412486)
        if 1000 < T <= 10000: return 315.16611724 * (T ** 0.45876193)
        if 10000 < T <= 100000: return 0.74904783 * T + 14066.58867
        if 100000 < T <= 300000: return 0.20527127 * T + 68444.33684
        if 300000 < T <= 2000000: return 0.20528 * T + 68452
        return T

    @staticmethod
    def advantage_adjust(attacker_unit: Unit, defender_unit: Unit) -> float:
        # Determines combat advantage based on unit types.
        adv = {'archers': 'pikemen', 'pikemen': 'infantry', 'infantry': 'archers'}
        atk_type, def_type = attacker_unit.unit_type, defender_unit.unit_type
        if adv.get(atk_type) == def_type: return 1.05
        if adv.get(def_type) == atk_type: return 0.95
        return 1.0

    def __init__(
        self,
        army1: Army,
        army2: Army,
        report_builder: Optional[ReportBuilder] = None,
        track_stats: bool = True,
        mode: str = "standard",
    ):
        self.army1: Army = army1
        self.army2: Army = army2
        self.army1.register_simulator(self)
        self.army2.register_simulator(self)
        self.round: int = 0
        self.mode: str = mode
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
        self.round_combat_actions_log.append(log_entry)
        if final_hp_damage > 0:
            defender.damage_contributors_this_round[attacker.name] = (
                defender.damage_contributors_this_round.get(attacker.name, 0.0)
                + final_hp_damage
            )
            sid = skill_id or ("counter_attack" if is_counter else "basic_attack")
            attacker.increment_skill_trigger_count(sid)
            skill_map = defender.damage_contributors_by_skill_this_round.setdefault(
                attacker.name, {}
            )
            skill_map[sid] = skill_map.get(sid, 0.0) + final_hp_damage

    def _log_skill_trigger(self, triggered_army: Army, skill_name: str, effect_description: str,
                           damage_details: Optional[Dict[str, Any]] = None):
        log_entry = {"skill_name": skill_name, "effect_description": effect_description}
        if damage_details: log_entry.update(damage_details)
        self.round_skill_triggers_log[triggered_army.name].append(log_entry)

    def _calculate_generic_skill_damage(
        self,
        source_army: Army,
        target_army: Army,
        damage_factor: float,
        is_hero2_rage_skill: bool = False,
        source_skill_def: Optional[SkillDefinition] = None,
        damage_application_target: Optional[Army] = None,
    ) -> Tuple[float, float, int, float]:
        if source_army.current_troop_count <= 0:
            return 0.0, 0.0, 0, 0.0

        calc_target = target_army
        apply_target = damage_application_target or target_army

        own_total_attack = source_army.unit.effective_attack(source_army.active_effects)
        enemy_total_defense = calc_target.unit.effective_defense(calc_target.active_effects)
        if enemy_total_defense <= 0: enemy_total_defense = 1

        own_troop_scalar = GameSimulator.troop_scalar(source_army.current_troop_count)
        skill_damage_percent_boosts = source_army.get_sum_stat_magnitudes(StatType.GENERAL_DAMAGE_MODIFIER)
        relevant_stats = {StatType.GENERAL_DAMAGE_MODIFIER}
        current_skill_trigger_type = source_skill_def.get("trigger") if source_skill_def else None

        if current_skill_trigger_type == SkillTriggerType.RAGE_SKILL:
            if not is_hero2_rage_skill:
                skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                    StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER)
                relevant_stats.add(StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER)
            elif is_hero2_rage_skill:
                skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                    StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER)
                relevant_stats.add(StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER)

        if (
            source_skill_def
            and source_skill_def.get("trigger") == SkillTriggerType.CHANCE_PER_ROUND
            and source_skill_def.get("config", {}).get("trigger_interval", 0) > 0
            and PluginSkillLabel.COMMAND in source_skill_def.get("labels", [])
        ):
            skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                StatType.COMMAND_SKILL_DAMAGE_MODIFIER
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
                StatType.REACTIVE_SKILL_DAMAGE_ADJUST
            )
            relevant_stats.add(StatType.REACTIVE_SKILL_DAMAGE_ADJUST)

        if source_skill_def and PluginSkillLabel.COOPERATION in source_skill_def.get("labels", []):
            skill_damage_percent_boosts += source_army.get_sum_stat_magnitudes(
                StatType.COOPERATION_SKILL_DAMAGE_MODIFIER)
            relevant_stats.add(StatType.COOPERATION_SKILL_DAMAGE_MODIFIER)

        positive_boost_effects = [
            eff
            for eff in source_army.active_effects
            if eff.effect_type == EffectType.STAT_MOD
            and eff.magnitude > 0
            and eff.config.get("stat_to_mod") in relevant_stats
        ]
        total_positive_boost = sum(eff.magnitude for eff in positive_boost_effects)
        attacker_negative_mags = skill_damage_percent_boosts - total_positive_boost

        current_shield_hp = apply_target.get_current_shield_hp()
        damage_taken_percent_mods = calc_target.get_sum_stat_magnitudes(
            StatType.DAMAGE_TAKEN_MULTIPLIER, attack_type_filter="SKILL"
        )
        dr_effects = [
            eff for eff in apply_target.active_effects
            if eff.effect_type == EffectType.STAT_MOD
            and eff.config.get('stat_to_mod') == StatType.DAMAGE_TAKEN_MULTIPLIER
            and eff.magnitude < 0
            and (not eff.config.get('config_filter', {}).get('attack_type')
                 or eff.config.get('config_filter', {}).get('attack_type') == "SKILL")
        ]
        total_dr_magnitude = sum(eff.magnitude for eff in dr_effects)
        defender_positive_mags = damage_taken_percent_mods - total_dr_magnitude

        total_skill_percentage_points = skill_damage_percent_boosts + damage_taken_percent_mods
        final_skill_damage_multiplier = max(0.05, 1.0 + total_skill_percentage_points)

        skill_hp_damage_potential = (own_total_attack / enemy_total_defense) * own_troop_scalar * (
            damage_factor / 200.0)
        damage_after_percent_mods_no_advantage = skill_hp_damage_potential * final_skill_damage_multiplier

        advantage_multiplier = GameSimulator.advantage_adjust(
            source_army.unit, calc_target.unit
        )
        damage_after_all_mods = damage_after_percent_mods_no_advantage * advantage_multiplier

        dmg_multiplier_no_dr = max(
            0.05,
            1.0 + skill_damage_percent_boosts + defender_positive_mags,
        )
        damage_no_dr = skill_hp_damage_potential * dmg_multiplier_no_dr * advantage_multiplier

        dmg_multiplier_no_boost = max(
            0.05, 1.0 + attacker_negative_mags + damage_taken_percent_mods
        )
        damage_no_boost = (
            skill_hp_damage_potential * dmg_multiplier_no_boost * advantage_multiplier
        )

        hp_damage_expected = max(0.0, damage_after_all_mods - current_shield_hp)
        hp_damage_without_dr = max(0.0, damage_no_dr - current_shield_hp)
        hp_saved = max(0.0, hp_damage_without_dr - hp_damage_expected)
        hp_damage_without_boost = max(0.0, damage_no_boost - current_shield_hp)

        raw_damage_for_logging = damage_after_all_mods

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
        extra_hp_from_boost = actual_skill_hp_damage_to_troops - hp_damage_without_boost
        if extra_hp_from_boost > 0 and total_positive_boost > 0:
            for eff in positive_boost_effects:
                weight = eff.magnitude / total_positive_boost
                troops = (extra_hp_from_boost * weight) / enemy_hp_per_troop
                source_army.skill_kill_boost_totals[eff.source_skill_id] = (
                    source_army.skill_kill_boost_totals.get(eff.source_skill_id, 0.0)
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
        # Skill damage is tracked for commitment totals but no longer logged
        # as a combat action.  This keeps combat action reports focused on
        # basic and counter attacks while skill effects are reported solely in
        # the skill trigger section.

        return (
            actual_skill_hp_damage_to_troops,
            skill_damage_absorbed_by_shield,
            potential_skill_kills,
            raw_damage_for_logging,
        )

    def _calculate_shield_magnitude_for_logging(self, owner_army: Army, opponent_for_calc: Army,
                                                shield_factor: float) -> float:
        if not opponent_for_calc or owner_army.current_troop_count <= 0: return 0.0

        own_atk = owner_army.unit.effective_attack(owner_army.active_effects)
        enemy_def = opponent_for_calc.unit.effective_defense(opponent_for_calc.active_effects)
        if enemy_def == 0: enemy_def = 1

        own_troop_scalar = GameSimulator.troop_scalar(owner_army.current_troop_count)
        base_shield_mag = round(((own_atk / enemy_def) * own_troop_scalar * (shield_factor / 200.0)))
        sum_shield_strength_mods = owner_army.get_sum_stat_magnitudes(StatType.SHIELD_STRENGTH_MODIFIER)
        shield_strength_multiplier = 1.0 + sum_shield_strength_mods

        return round(base_shield_mag * shield_strength_multiplier)

    def _process_skill_triggers(self, triggering_army: Army, opponent_army: Army, trigger_type: SkillTriggerType,
                                event_data: Optional[Dict[str, Any]] = None):
        actual_effect_target = opponent_army
        actual_opponent_for_calc = opponent_army
        if event_data:
            if 'direct_target_army' in event_data:
                actual_effect_target = event_data['direct_target_army']
            if 'opponent_for_shield_calc' in event_data:
                actual_opponent_for_calc = event_data['opponent_for_shield_calc']

        for hero in triggering_army.heroes:
            for skill_def in hero.skills:
                if skill_def["id"] == "dummy_talent_empty": continue
                if skill_def["trigger"] == SkillTriggerType.RAGE_SKILL: continue
                if skill_def["trigger"] == SkillTriggerType.PASSIVE: continue

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
                        cooldown = skill_cfg.get("cooldown_rounds")
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
                            if skill_id in triggering_army.triggered_skills_this_round:
                                continue

                        logic_handler: Optional[SkillLogicHandler] = skill_def.get("logic_handler")
                        if logic_handler:
                            handler_event_data = (event_data or {}).copy()
                            handler_event_data['actual_opponent_for_calc'] = actual_opponent_for_calc
                            an_effect_truly_happened, log_details_current_skill = \
                                logic_handler(triggering_army, actual_effect_target, skill_def, handler_event_data, self)
                        elif "sub_effects" in skill_def:
                            for sub_effect_data in skill_def["sub_effects"]:
                                if random.random() < sub_effect_data.get("chance", 1.0):
                                    effect_to_apply = sub_effect_data["effect_to_apply"]
                                    target_sub = actual_effect_target if skill_def.get(
                                        "target") == "ENEMY" else triggering_army
                                    created_effect = triggering_army._create_and_add_single_effect(
                                        effect_to_apply.copy(), skill_id, triggering_army, target_sub,
                                        actual_opponent_for_calc)
                                    if created_effect:
                                        an_effect_truly_happened = True
                                        log_details_current_skill.append(
                                            (f"{sub_effect_data.get('name_suffix', 'Effect')}: {created_effect.get_functionality_description()} for {created_effect.duration + 1} rounds.",
                                             None))
                        elif "effects_to_apply" in skill_def and skill_def["effects_to_apply"]:
                            target_std = actual_effect_target if skill_def.get("target") == "ENEMY" else triggering_army
                            applied_details = triggering_army._add_effects_from_skill_def(
                                skill_def, target_std, triggering_army, actual_opponent_for_calc)
                            if applied_details:
                                an_effect_truly_happened = True
                                for _, desc in applied_details:
                                    log_details_current_skill.append((desc, None))

                        if an_effect_truly_happened:
                            self._log_skill_trigger(triggering_army, skill_def['name'], "Triggered.")
                            for desc_str, dmg_details in log_details_current_skill:
                                self._log_skill_trigger(triggering_army, f"  ↳", desc_str, damage_details=dmg_details)
                            triggering_army.increment_skill_trigger_count(skill_id)

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
                    army.hero1_rage_skill_scheduled_round = None
                    army.hero1_rage_skill_queued_this_round = False
                elif hero_slot == 2:
                    if army.hero2_rage_skill_primed_for_round == army.army_round:
                        army.hero2_rage_skill_primed_for_round += 1
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

        attacker_effective_atk = att.unit.effective_attack(att.active_effects)
        defender_effective_def = dfd.unit.effective_defense(dfd.active_effects)
        if defender_effective_def <= 0: defender_effective_def = 1

        troop_count_scalar = GameSimulator.troop_scalar(att.current_troop_count)
        raw_damage_potential = (attacker_effective_atk / defender_effective_def) * troop_count_scalar

        specific_attack_stat = StatType.COUNTER_DAMAGE_ADJUST if is_counter else StatType.BASIC_DAMAGE_ADJUST
        sum_specific_attack_magnitudes = att.get_sum_stat_magnitudes(specific_attack_stat)
        sum_general_attacker_magnitudes = att.get_sum_stat_magnitudes(StatType.GENERAL_DAMAGE_MODIFIER)

        positive_boost_effects = [
            eff
            for eff in att.active_effects
            if eff.effect_type == EffectType.STAT_MOD
            and eff.magnitude > 0
            and eff.config.get("stat_to_mod") in {specific_attack_stat, StatType.GENERAL_DAMAGE_MODIFIER}
        ]
        total_positive_boost = sum(eff.magnitude for eff in positive_boost_effects)
        attacker_negative_mags = (
            sum_specific_attack_magnitudes
            + sum_general_attacker_magnitudes
            - total_positive_boost
        )

        attack_type_for_defense_filter = "COUNTER" if is_counter else "BASIC"
        current_shield_hp = dfd.get_current_shield_hp()

        sum_defender_reduction_magnitudes = dfd.get_sum_stat_magnitudes(
            StatType.DAMAGE_TAKEN_MULTIPLIER, attack_type_filter=attack_type_for_defense_filter)
        dr_effects = [
            eff for eff in dfd.active_effects
            if eff.effect_type == EffectType.STAT_MOD
            and eff.config.get('stat_to_mod') == StatType.DAMAGE_TAKEN_MULTIPLIER
            and eff.magnitude < 0
            and (not eff.config.get('config_filter', {}).get('attack_type')
                 or eff.config.get('config_filter', {}).get('attack_type') == attack_type_for_defense_filter)
        ]
        total_dr_magnitude = sum(eff.magnitude for eff in dr_effects)
        defender_positive_mags = sum_defender_reduction_magnitudes - total_dr_magnitude

        total_additive_percentage_points = (
            sum_specific_attack_magnitudes +
            sum_general_attacker_magnitudes +
            sum_defender_reduction_magnitudes
        )

        final_damage_multiplier = max(0.05, 1.0 + total_additive_percentage_points)
        damage_with_percent_mods = raw_damage_potential * final_damage_multiplier

        advantage_multiplier = GameSimulator.advantage_adjust(att.unit, dfd.unit)
        damage_after_all_percent_mods = damage_with_percent_mods * advantage_multiplier

        dmg_multiplier_no_dr = max(
            0.05,
            1.0 + sum_specific_attack_magnitudes + sum_general_attacker_magnitudes + defender_positive_mags,
        )
        damage_no_dr = raw_damage_potential * dmg_multiplier_no_dr * advantage_multiplier

        dmg_multiplier_no_boost = max(
            0.05,
            1.0 + attacker_negative_mags + sum_defender_reduction_magnitudes,
        )
        damage_no_boost = raw_damage_potential * dmg_multiplier_no_boost * advantage_multiplier

        hp_damage_expected = max(0.0, damage_after_all_percent_mods - current_shield_hp)
        hp_damage_without_dr = max(0.0, damage_no_dr - current_shield_hp)
        hp_saved = max(0.0, hp_damage_without_dr - hp_damage_expected)
        hp_damage_without_boost = max(0.0, damage_no_boost - current_shield_hp)

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
        self._log_combat_action(
            attacker=att,
            defender=dfd,
            damage_potential_hp=damage_after_all_percent_mods,
            absorbed_hp=absorbed_by_shield,
            final_hp_damage=hp_damage_to_troops,
            potential_kills=potential_units_killed_this_hit_rounded,
            is_counter=is_counter,
            skill_id=sid,
        )

        return hp_damage_to_troops, absorbed_by_shield, damage_after_all_percent_mods, potential_units_killed_this_hit_rounded

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
        if not defender.use_dynamic_unrevivable_ratio:
            return

        opponent_kills = opponent.dynamic_kills_by_opponent.get(
            defender.name, {"combat": 0.0, "skill": 0.0}
        )
        defender_kills = defender.dynamic_kills_by_opponent.get(
            opponent.name, {"combat": 0.0, "skill": 0.0}
        )

        dynamic_settings = get_dynamic_unrevivable_settings()
        combat_base = dynamic_settings["combat_base"]
        combat_bonus = dynamic_settings["combat_bonus_multiplier"]
        skill_base = dynamic_settings["skill_base"]
        skill_bonus = dynamic_settings["skill_bonus_multiplier"]
        non_mutual_base = dynamic_settings["non_mutual_base"]
        non_mutual_bonus = dynamic_settings["non_mutual_bonus_multiplier"]

        if mutual_engagement:
            total_combat_kills = defender_kills.get("combat", 0.0) + opponent_kills.get(
                "combat", 0.0
            )
            enemy_combat_kills = opponent_kills.get("combat", 0.0)
            combat_ratio = combat_base
            if total_combat_kills > 0:
                combat_ratio += (enemy_combat_kills / total_combat_kills) * combat_bonus

            total_skill_kills = defender_kills.get("skill", 0.0) + opponent_kills.get(
                "skill", 0.0
            )
            enemy_skill_kills = opponent_kills.get("skill", 0.0)
            skill_ratio = skill_base
            if total_skill_kills > 0:
                skill_ratio += (enemy_skill_kills / total_skill_kills) * skill_bonus

            combat_unrevivable = round(combat_losses * combat_ratio)
            skill_unrevivable = round(skill_losses * skill_ratio)
            added_unrevivable = combat_unrevivable + skill_unrevivable
            log_message = (
                f"vs {opponent.name}: combat ratio {combat_ratio:.2%} on {combat_losses:.1f} "
                f"losses (+{combat_unrevivable}), skill ratio {skill_ratio:.2%} on "
                f"{skill_losses:.1f} losses (+{skill_unrevivable}) -> +{added_unrevivable} unrevivable."
            )
        else:
            total_combat_kills = defender_kills.get("combat", 0.0) + opponent_kills.get(
                "combat", 0.0
            )
            enemy_combat_kills = opponent_kills.get("combat", 0.0)
            combined_ratio = non_mutual_base
            if total_combat_kills > 0:
                combined_ratio += (enemy_combat_kills / total_combat_kills) * non_mutual_bonus
            combined_losses = combat_losses + skill_losses
            added_unrevivable = round(combined_losses * combined_ratio)
            log_message = (
                f"vs {opponent.name}: non-mutual ratio {combined_ratio:.2%} on {combined_losses:.1f} "
                f"losses -> +{added_unrevivable} unrevivable."
            )

        if added_unrevivable > 0:
            defender.unrevivable_troops = min(
                defender.unit.initial_count,
                defender.unrevivable_troops + added_unrevivable,
            )
        self._log_skill_trigger(defender, "Dynamic Unrevivable", log_message)

    def simulate_battle(self) -> str:
        self.army1.reset_for_new_battle()
        self.army2.reset_for_new_battle()
        self.army1.register_simulator(self)
        self.army2.register_simulator(self)
        self.round = 0

        while self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0:
            self.round += 1
            for army in (self.army1, self.army2):
                army.army_round += 1

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
            if not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
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

            if not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
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

            if not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0): break

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

            if not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0): break

            self.army1.commit_pending_healing_and_damage()
            self.army2.commit_pending_healing_and_damage()
            self.apply_unrevivable_post_commit(mutual_engagement=True)
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
            if not (self.army1.current_troop_count > 0 and self.army2.current_troop_count > 0):
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
        if self.army1.current_troop_count > 0 and self.army2.current_troop_count <= 0:
            winner = self.army1.name
        elif self.army2.current_troop_count > 0 and self.army1.current_troop_count <= 0:
            winner = self.army2.name
        elif self.army1.current_troop_count <= 0 and self.army2.current_troop_count <= 0 and self.round > 0:
            winner = "Mutual Destruction"

        self.report_builder.emit_final(
            winner,
            self.round,
            f"Final State: {self.army1.name}: {self.army1.current_troop_count:.0f} troops",
            f"{self.army2.name}: {self.army2.current_troop_count:.0f} troops")
        if self.track_stats:
            self._generate_round_figures()
        report_text = self.report_builder.get_report_text()
        self.report_builder.print_report()
        return report_text

