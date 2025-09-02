# === File: army_composition.py ===
import uuid
import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Set

from .enums import EffectType, SkillTriggerType, StatType, DoTType
from .unit_definition import Unit
from .hero_definition import Hero
from .effect_system import EffectInstance
from .skill_system import SkillDefinition
from .constants import (
    EFFECT_NAME_BROKEN_BLADE_DEBUFF, EFFECT_NAME_DISARM_DEBUFF, EFFECT_NAME_SILENCE_DEBUFF,
    EFFECT_NAME_FIRST_STRIKE_RAGE_AURA, EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
    EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
    EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
    EFFECT_NAME_CONCENTRATION_RAGE_GAIN,  # Import Olena's new effect
    EFFECT_NAME_BERSERK_FURY_RAGE_GAIN,
    EFFECT_NAME_DELAYED_RAGE_GAIN,
    EFFECT_NAME_DELAYED_RAGE_REDUCTION,
    EFFECT_NAME_PENDING_HEROIC_BLESSING_DEBUFF,
    EFFECT_NAME_PENDING_HEROIC_BLESSING_BUFF,
    EFFECT_NAME_HEROIC_BLESSING_COUNTER_DEBUFF,
    EFFECT_NAME_HEROIC_BLESSING_BURN_BOOST,
    EFFECT_NAME_PENDING_BRUTAL_BLOW_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
    EFFECT_NAME_PENDING_BRUTAL_BLOW_CLEANSE,
    EFFECT_NAME_SAINTLY_GUARDIAN_SHIELD_BOOST,
    EFFECT_NAME_WAR_BLESSING_SHIELD,
    EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF,
    EFFECT_NAME_JUDGEMENT_MARKER,
    EFFECT_NAME_PENDING_JUDGEMENT_MARKERS
)

GameSimulatorRef = "GameSimulator"  # Forward reference


@dataclass(slots=True)
class Army:
    name: str
    unit: Unit
    heroes: List[Hero] = field(default_factory=list)
    unrevivable_ratio: float = 0.65
    simulator: Optional[GameSimulatorRef] = field(init=False, default=None)
    simulators: List[GameSimulatorRef] = field(init=False, default_factory=list)

    current_troop_count: float = field(init=False, default=0.0)
    active_effects: List[EffectInstance] = field(init=False, default_factory=list)
    upcoming_effects: List[EffectInstance] = field(init=False, default_factory=list)
    effects_to_activate_next_round: List[EffectInstance] = field(init=False, default_factory=list)

    triggered_skills_this_round: List[str] = field(init=False, default_factory=list)
    skill_trigger_counts_this_round: Dict[str, int] = field(init=False, default_factory=dict)
    skill_triggers_against_this_round: Dict[str, Set[str]] = field(init=False, default_factory=dict)
    pending_hp_damage_this_round: float = field(init=False, default=0.0)
    pending_hp_healing_this_round: float = field(init=False, default=0.0)
    unrevivable_troops: float = field(init=False, default=0.0)

    skill_trigger_counts: Dict[str, int] = field(init=False, default_factory=dict)
    skill_last_triggered_round: Dict[str, int] = field(init=False, default_factory=dict)
    debuff_last_applied_round: Dict[str, int] = field(init=False, default_factory=dict)

    current_rage: float = field(init=False, default=0.0)
    hero1_rage_skill_id: Optional[str] = field(init=False, default=None)
    hero2_rage_skill_id: Optional[str] = field(init=False, default=None)
    hero1_rage_skill_def: Optional[SkillDefinition] = field(init=False, default=None)
    hero2_rage_skill_def: Optional[SkillDefinition] = field(init=False, default=None)
    hero1_rage_skill_queued_this_round: bool = field(init=False, default=False)
    hero1_rage_skill_used_round: Optional[int] = field(init=False, default=None)
    hero2_rage_skill_primed_for_round: Optional[int] = field(init=False, default=None)
    hero1_rage_skill_scheduled_round: Optional[int] = field(init=False, default=None)

    army_used_rage_skill_this_round_for_rage_gain_block: bool = field(init=False, default=False)
    base_rage_awarded_this_round: bool = field(init=False, default=False)
    healing_hymn_triggered_this_round: bool = field(init=False, default=False)
    started_round_with_active_shield: bool = field(init=False, default=False)
    started_last_round_with_active_shield: bool = field(init=False, default=False)
    hero1_rage_skill_cast_blocked_by_silence_this_round: bool = field(init=False, default=False)

    damage_dealt_history: List[float] = field(init=False, default_factory=list)
    heal_received_history: List[float] = field(init=False, default_factory=list)
    shield_received_history: List[float] = field(init=False, default_factory=list)
    rage_gained_history: List[float] = field(init=False, default_factory=list)
    kills_dealt_history: List[float] = field(init=False, default_factory=list)
    troops_healed_total: float = field(init=False, default=0.0)
    shield_hp_gained_this_round: float = field(init=False, default=0.0)
    rage_added_this_round: float = field(init=False, default=0.0)
    kills_dealt_this_round: float = field(init=False, default=0.0)
    damage_contributors_this_round: Dict[str, float] = field(init=False, default_factory=dict)
    damage_contributors_by_skill_this_round: Dict[str, Dict[str, float]] = field(
        init=False, default_factory=dict
    )
    heal_contributors_this_round: Dict[str, Dict[str, float]] = field(
        init=False, default_factory=dict
    )
    skill_kill_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_heal_totals: Dict[str, float] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self.reset_for_new_battle()

    def register_simulator(self, simulator: GameSimulatorRef):
        self.simulator = simulator
        if simulator not in self.simulators:
            self.simulators.append(simulator)

    def increment_skill_trigger_count(self, skill_id: str):
        self.skill_trigger_counts[skill_id] = self.skill_trigger_counts.get(skill_id, 0) + 1

    def _identify_hero_rage_skills(self):
        self.hero1_rage_skill_id = None
        self.hero2_rage_skill_id = None
        self.hero1_rage_skill_def = None
        self.hero2_rage_skill_def = None
        if self.heroes:
            if len(self.heroes) > 0 and self.heroes[0]:
                for skill_def in self.heroes[0].skills:
                    if skill_def.get("trigger") == SkillTriggerType.RAGE_SKILL:
                        self.hero1_rage_skill_id = skill_def["id"]
                        self.hero1_rage_skill_def = skill_def
                        break
            if len(self.heroes) > 1 and self.heroes[1]:
                for skill_def in self.heroes[1].skills:
                    if skill_def.get("trigger") == SkillTriggerType.RAGE_SKILL:
                        self.hero2_rage_skill_id = skill_def["id"]
                        self.hero2_rage_skill_def = skill_def
                        break

    def _apply_initial_passive_skills(self):
        sim = self.simulator

        for hero in self.heroes:
            for skill_def in hero.skills:
                if (
                    skill_def["trigger"] == SkillTriggerType.PASSIVE
                    and skill_def.get("id") != "dummy_talent_empty"
                ):
                    # Passive skills may be applied multiple times when armies
                    # join new engagements.  Skip any skill that has already
                    # triggered once to avoid stacking permanent effects.
                    if self.skill_trigger_counts.get(skill_def.get("id")):
                        continue
                    an_effect_truly_happened_passive = False
                    log_details_passive: List[Tuple[str, Optional[Dict[str, Any]]]] = []

                    if skill_def.get("effects_to_apply"):
                        applied_logs = self._add_effects_from_skill_def(
                            skill_def, self, source_army=self, opponent_for_calc=None
                        )
                        for _, desc in applied_logs:
                            log_details_passive.append((desc, None))
                        if applied_logs:
                            an_effect_truly_happened_passive = True
                    elif skill_def.get("sub_effects"):
                        for sub_effect_data in skill_def["sub_effects"]:
                            if random.random() < sub_effect_data.get("chance", 1.0):
                                effect_to_apply_data = sub_effect_data["effect_to_apply"]
                                created_effect = self._create_and_add_single_effect(
                                    effect_data=effect_to_apply_data.copy(), source_skill_id=skill_def["id"],
                                    owner_army=self, target_army=self, opponent_of_owner_for_calc=None)
                                if created_effect:
                                    an_effect_truly_happened_passive = True
                                    log_details_passive.append(
                                        (f"{sub_effect_data.get('name_suffix', 'Effect')}: {created_effect.get_functionality_description()} for {created_effect.duration + 1} rounds.",
                                         None)
                                    )
                    elif skill_def.get("logic_handler") and sim:
                        opponent = (
                            sim.army2 if self is sim.army1 else sim.army1
                        )
                        logic_handler = skill_def.get("logic_handler")
                        an_effect_truly_happened_passive, log_details_passive = logic_handler(
                            self, opponent, skill_def, None, sim
                        )
                    else:
                        # Without a simulator we cannot safely run custom logic handlers.
                        if skill_def.get("logic_handler"):
                            continue

                    if an_effect_truly_happened_passive:
                        if sim:
                            sim._log_skill_trigger(self, skill_def['name'], "Passive applied at start.")
                            for desc_str, dmg_details in log_details_passive:
                                sim._log_skill_trigger(self, "  ↳", desc_str, damage_details=dmg_details)
                        self.increment_skill_trigger_count(skill_def["id"])
        self.activate_queued_effects()

    def get_sum_stat_magnitudes(self, stat_type: StatType, attack_type_filter: Optional[str] = None) -> float:
        sum_of_magnitudes = 0.0
        for effect in self.active_effects:
            if effect.effect_type == EffectType.STAT_MOD and effect.config.get('stat_to_mod') == stat_type:
                eff_filter = effect.config.get('config_filter', {}).get('attack_type')
                if attack_type_filter:
                    if not eff_filter or eff_filter == attack_type_filter:
                        sum_of_magnitudes += effect.magnitude
                else:
                    if not eff_filter:
                        sum_of_magnitudes += effect.magnitude
        return sum_of_magnitudes

    def get_current_shield_hp(self) -> float:
        return sum(effect.magnitude for effect in self.active_effects if
                   effect.effect_type == EffectType.SHIELD and effect.magnitude > 0)

    def apply_shields_and_get_hp_damage(self, damage_after_percent_mods: float) -> Dict[str, float]:
        hp_dmg_final = damage_after_percent_mods
        absorbed_total = 0.0

        active_shields = sorted(
            [eff for eff in self.active_effects if eff.effect_type == EffectType.SHIELD and eff.magnitude > 0],
            key=lambda e: e.duration)

        for shield_eff in active_shields:
            if hp_dmg_final <= 0: break
            can_absorb = min(hp_dmg_final, shield_eff.magnitude)
            shield_eff.magnitude -= can_absorb
            hp_dmg_final -= can_absorb
            absorbed_total += can_absorb

        hp_dmg_final = max(0, hp_dmg_final)

        self.active_effects = [eff for eff in self.active_effects if
                               not (eff.effect_type == EffectType.SHIELD and eff.magnitude <= 0.001)]

        return {'hp_damage_to_troops': hp_dmg_final, 'absorbed_by_shield': absorbed_total}

    def commit_pending_healing_and_damage(self):
        # Healing is committed before damage so that only troops lost in
        # previous rounds are eligible to be revived. Damage taken during the
        # current round cannot be healed until the following round.
        if self.pending_hp_healing_this_round > 0:
            max_healable_count = self.unit.initial_count - round(self.unrevivable_troops)
            if self.current_troop_count < max_healable_count:
                hp_per_troop = self.unit.effective_hp_per_troop(self.active_effects)
                if hp_per_troop <= 0: hp_per_troop = 1

                hp_needed_to_reach_cap = (max_healable_count - self.current_troop_count) * hp_per_troop
                actual_healed_hp = max(0, min(self.pending_hp_healing_this_round, hp_needed_to_reach_cap))

                if actual_healed_hp > 0:
                    healed_troops_float = actual_healed_hp / hp_per_troop
                    healed_troops_round = round(healed_troops_float)
                    for sim in self.simulators:
                        sim._log_skill_trigger(
                            self,
                            "Healing Commitment",
                            f"Commits {actual_healed_hp:.0f} HP healing, restoring {healed_troops_round} troops. Unrevivable: {round(self.unrevivable_troops)}",
                        )
                    self.troops_healed_total += healed_troops_float
                    self.current_troop_count = min(
                        max_healable_count,
                        self.current_troop_count + healed_troops_round,
                    )

                    total_contrib_hp = sum(
                        sum(skills.values()) for skills in self.heal_contributors_this_round.values()
                    )
                    if total_contrib_hp > 0:
                        for src, skills in self.heal_contributors_this_round.items():
                            for sim in self.simulators:
                                engine = getattr(sim, "parent_engine", None)
                                if engine and src in engine._armies:
                                    healer_army = engine._armies[src].army
                                    for sid, hp in skills.items():
                                        portion = actual_healed_hp * (hp / total_contrib_hp)
                                        healer_army.skill_heal_totals[sid] = healer_army.skill_heal_totals.get(sid, 0.0) + (
                                            portion / hp_per_troop
                                        )
                                    break

                    self.heal_contributors_this_round = {}
                    self.pending_hp_healing_this_round = 0.0

        if self.pending_hp_damage_this_round > 0 and self.current_troop_count > 0:
            hp_per_troop = self.unit.effective_hp_per_troop(self.active_effects)
            if hp_per_troop <= 0:
                hp_per_troop = 1

            lost_float = self.pending_hp_damage_this_round / hp_per_troop
            lost_round = round(lost_float)

            unrevivable_increase = round(lost_round * self.unrevivable_ratio)
            for sim in self.simulators:
                sim._log_skill_trigger(
                    self,
                    "Damage Commitment",
                    f"Commits {self.pending_hp_damage_this_round:.0f} pending HP damage, resulting in {lost_round} troops lost. {unrevivable_increase} unrevivable.",
                )
                for src, dmg in self.damage_contributors_this_round.items():
                    sim._log_skill_trigger(self, "  ↳", f"{src} committed {dmg:.0f} damage")
            self.current_troop_count = max(0, self.current_troop_count - lost_round)
            self.unrevivable_troops = min(
                self.unit.initial_count,
                self.unrevivable_troops + unrevivable_increase,
            )
            total_dmg = sum(self.damage_contributors_this_round.values())
            if lost_round > 0 and total_dmg > 0:
                for src, dmg in self.damage_contributors_this_round.items():
                    kills = lost_round * (dmg / total_dmg)
                    for sim in self.simulators:
                        engine = getattr(sim, "parent_engine", None)
                        if engine and src in engine._armies:
                            army_obj = engine._armies[src].army
                            army_obj.kills_dealt_this_round += kills
                            skill_map = self.damage_contributors_by_skill_this_round.get(src, {})
                            skill_total = sum(skill_map.values())
                            if skill_total > 0:
                                for sid, sdmg in skill_map.items():
                                    army_obj.skill_kill_totals[sid] = army_obj.skill_kill_totals.get(sid, 0.0) + (
                                        kills * (sdmg / skill_total)
                                    )
                            break
            self.damage_contributors_this_round = {}
            self.damage_contributors_by_skill_this_round = {}
        # self.pending_hp_damage_this_round = 0.0 # Resetting this at start of round in game_simulator.py
    def calculate_and_add_pending_healing(
        self,
        heal_factor: float,
        healer_army: 'Army',
        opponent_of_healer: 'Army',
        skill_heal_adjustment_magnitude: float = 0.0,
        source_skill_id: str | None = None,
    ) -> float:
        if not self.simulator or healer_army.current_troop_count <= 0: return 0.0

        healer_atk = healer_army.unit.effective_attack(healer_army.active_effects)
        healer_troop_scalar = self.simulator.troop_scalar(healer_army.current_troop_count)
        total_heal_adj_recipient = self.get_sum_stat_magnitudes(StatType.HEAL_ADJUSTMENT)
        heal_adj_mult = 1.0 + total_heal_adj_recipient + skill_heal_adjustment_magnitude
        opp_def_calc = opponent_of_healer.unit.effective_defense(opponent_of_healer.active_effects)
        if opp_def_calc == 0: opp_def_calc = 1

        hp_healed_raw = round(
            ((healer_atk / opp_def_calc) * healer_troop_scalar * (heal_factor / 200.0) * heal_adj_mult))

        if hp_healed_raw > 0:
            self.pending_hp_healing_this_round += hp_healed_raw
            if source_skill_id:
                skill_map = self.heal_contributors_this_round.setdefault(
                    healer_army.name, {}
                )
                skill_map[source_skill_id] = skill_map.get(source_skill_id, 0.0) + hp_healed_raw
            self.simulator._process_skill_triggers(
                self,
                opponent_of_healer,
                SkillTriggerType.ON_RECEIVING_HEALING,
                event_data={
                    'healed_army': self,
                    'opponent_for_shield_calc': opponent_of_healer,
                    'heal_amount_hp': hp_healed_raw,
                    'source_heal_factor': heal_factor,
                },
            )
            self.activate_queued_effects()
            if opponent_of_healer.current_troop_count > 0:
                opponent_of_healer.activate_queued_effects()
            return hp_healed_raw
        return 0.0

    def _create_and_add_single_effect(self, effect_data: Dict[str, Any], source_skill_id: str,
                                      owner_army: 'Army', target_army: 'Army',
                                      opponent_of_owner_for_calc: Optional['Army'] = None) -> Optional[EffectInstance]:
        canonical_effect_name = effect_data.get("name")
        if not canonical_effect_name:
            print(f"Warning: Effect from {source_skill_id} is missing a 'name'. Skipping effect.")
            return None

        for active_immunity_effect in target_army.active_effects:
            if active_immunity_effect.effect_type == EffectType.IMMUNITY and \
                    active_immunity_effect.config.get("immune_to") == canonical_effect_name:
                if self.simulator: self.simulator._log_skill_trigger(target_army, active_immunity_effect.name,
                                                                     f"Immune to '{canonical_effect_name}' from skill '{source_skill_id}'.")
                return None

        debuff_limit_names = {
            EFFECT_NAME_DISARM_DEBUFF,
            EFFECT_NAME_BROKEN_BLADE_DEBUFF,
            EFFECT_NAME_SILENCE_DEBUFF,
        }
        if canonical_effect_name in debuff_limit_names:
            if any(eff.name == canonical_effect_name for eff in target_army.active_effects):
                return None
            if target_army.simulator:
                current_round = target_army.simulator.round
                last_round = target_army.debuff_last_applied_round.get(canonical_effect_name, -999)
                if current_round < last_round + 2:
                    return None
                target_army.debuff_last_applied_round[canonical_effect_name] = current_round

        new_effect_duration = effect_data.get("duration", 1)
        activate_next_round_flag = effect_data.get("activate_next_round", False)
        magnitude = effect_data.get("magnitude", 0.0)

        final_config: Dict[str, Any] = {}
        keys_to_exclude_from_config = ["effect_type", "name", "duration", "magnitude", "magnitude_calc",
                                       "dot_damage_calc", "magnitude_calc_type", "shield_factor", "activate_next_round",
                                       "stat_to_mod", "immune_to", "config", "dot_type",
                                       "status_effect_factor", "unit_type_condition", "config_filter"]
        for k, v in effect_data.items():
            if k not in keys_to_exclude_from_config: final_config[k] = v
        if "config" in effect_data and isinstance(effect_data["config"], dict):
            final_config.update(effect_data["config"])
        if "unit_type_condition" in effect_data: final_config["unit_type_condition"] = effect_data[
            "unit_type_condition"]
        if "config_filter" in effect_data: final_config["config_filter"] = effect_data["config_filter"]

        dot_type_value = effect_data.get('dot_type')
        is_special_dot = False
        if isinstance(dot_type_value, DoTType) and dot_type_value in [DoTType.BLEED, DoTType.POISON, DoTType.BURN]:
            is_special_dot = True
        elif isinstance(dot_type_value, str) and dot_type_value.upper() in [d.value for d in
                                                                            [DoTType.BLEED, DoTType.POISON,
                                                                             DoTType.BURN]]:
            is_special_dot = True
            dot_type_value = DoTType(dot_type_value.upper())

        if effect_data.get("effect_type") == EffectType.DAMAGE_OVER_TIME and is_special_dot:
            final_config['dot_type'] = dot_type_value
            final_config['status_effect_factor'] = float(effect_data.get("status_effect_factor", 0.0))
            final_config['original_caster_army_name'] = owner_army.name

            if self.simulator and opponent_of_owner_for_calc:
                final_config['snapshotted_attacker_total_attack'] = owner_army.unit.effective_attack(
                    owner_army.active_effects)
                final_config['snapshotted_attacker_troop_scalar'] = self.simulator.troop_scalar(
                    owner_army.current_troop_count)
                final_config['snapshotted_defender_total_defense'] = target_army.unit.effective_defense(
                    target_army.active_effects)
            else:
                final_config['snapshotted_attacker_total_attack'] = owner_army.unit.base_atk_stat
                final_config['snapshotted_attacker_troop_scalar'] = 1.0
                final_config['snapshotted_defender_total_defense'] = target_army.unit.base_def_stat

            # Remove any duplicate upcoming instances from this skill
            for effect_list in [target_army.upcoming_effects, target_army.effects_to_activate_next_round]:
                for i in range(len(effect_list) - 1, -1, -1):
                    queued_eff = effect_list[i]
                    if (queued_eff.effect_type == EffectType.DAMAGE_OVER_TIME and
                            queued_eff.config.get('dot_type') == dot_type_value and
                            queued_eff.source_skill_id == source_skill_id):
                        effect_list.pop(i)
                        if self.simulator:
                            self.simulator._log_skill_trigger(target_army, queued_eff.name,
                                                              "Upcoming replaced by new application.")
                        break

            magnitude = 0

        elif effect_data.get("effect_type") == EffectType.SHIELD:
            base_shield_magnitude = 0.0
            shield_factor_val = float(effect_data.get("shield_factor", 0.0))
            if self.simulator and opponent_of_owner_for_calc and shield_factor_val > 0:
                own_atk = owner_army.unit.effective_attack(owner_army.active_effects)
                enemy_def = opponent_of_owner_for_calc.unit.effective_defense(opponent_of_owner_for_calc.active_effects)
                if enemy_def == 0: enemy_def = 1
                owner_troop_scalar = self.simulator.troop_scalar(owner_army.current_troop_count)
                base_shield_magnitude = ((own_atk / enemy_def) * owner_troop_scalar * (shield_factor_val / 200.0))
            else:
                base_shield_magnitude = magnitude

            sum_shield_strength_mods_recipient = target_army.get_sum_stat_magnitudes(StatType.SHIELD_STRENGTH_MODIFIER)
            shield_strength_multiplier = 1.0 + sum_shield_strength_mods_recipient
            magnitude = round(base_shield_magnitude * shield_strength_multiplier)
            if self.simulator:
                target_army.shield_hp_gained_this_round += magnitude

            if effect_data.get("shield_factor") and "shield_factor" not in final_config:
                final_config["shield_factor"] = effect_data["shield_factor"]

        elif "magnitude_calc" in effect_data:
            try:
                magnitude = float(eval(effect_data["magnitude_calc"], {
                    "self_army_max_hp": target_army.unit.initial_count * target_army.unit.effective_hp_per_troop(
                        target_army.active_effects)
                }))
            except Exception as e:
                print(f"Error in magnitude_calc for {canonical_effect_name} from {source_skill_id}: {e}");
                magnitude = 0.0

        if effect_data.get("effect_type") == EffectType.DAMAGE_OVER_TIME and not is_special_dot:
            dot_damage = 0.0
            if "dot_damage_calc" in effect_data and self.simulator and owner_army:
                try:
                    dot_damage = float(eval(effect_data["dot_damage_calc"], {
                        "attacker_total_attack": owner_army.unit.effective_attack(
                            owner_army.active_effects) * self.simulator.troop_scalar(owner_army.current_troop_count)
                    }))
                except Exception as e:
                    print(f"Error in dot_damage_calc for {canonical_effect_name} from {source_skill_id}: {e}");
                    dot_damage = 0.0
            final_config["dot_damage_per_round"] = dot_damage
            final_config['dot_type'] = DoTType.GENERIC

        if effect_data.get("stat_to_mod") and "stat_to_mod" not in final_config: final_config["stat_to_mod"] = \
        effect_data["stat_to_mod"]
        if effect_data.get("immune_to") and "immune_to" not in final_config: final_config["immune_to"] = effect_data[
            "immune_to"]
        if canonical_effect_name == EFFECT_NAME_BROKEN_BLADE_DEBUFF: final_config["prevents_counterattack"] = True
        if canonical_effect_name == EFFECT_NAME_DISARM_DEBUFF: final_config["prevents_basic_attack"] = True
        if canonical_effect_name == EFFECT_NAME_SILENCE_DEBUFF: final_config["prevents_rage_skill_cast"] = True

        if owner_army:
            final_config.setdefault("source_army_name", owner_army.name)
        inst = EffectInstance(
            id=uuid.uuid4(),
            source_skill_id=source_skill_id,
            name=canonical_effect_name,
            effect_type=effect_data["effect_type"],
            duration=new_effect_duration,
            magnitude=magnitude,
            config=final_config,
        )
        if activate_next_round_flag:
            target_army.effects_to_activate_next_round.append(inst)
        else:
            target_army.upcoming_effects.append(inst)
        return inst

    def _add_effects_from_skill_def(self, skill_def: SkillDefinition, target_army: 'Army',
                                    source_army: Optional['Army'] = None,
                                    opponent_for_calc: Optional['Army'] = None) -> List[Tuple[str, str]]:
        if source_army is None: source_army = self
        applied_effect_logs = []
        for effect_data_original in skill_def.get("effects_to_apply", []):
            effect_data = effect_data_original.copy()
            created_effect_instance = self._create_and_add_single_effect(
                effect_data=effect_data, source_skill_id=skill_def["id"],
                owner_army=source_army,
                target_army=target_army,
                opponent_of_owner_for_calc=opponent_for_calc
            )
            if created_effect_instance:
                applied_effect_logs.append(
                    (created_effect_instance.name,
                     f"{created_effect_instance.get_functionality_description()} for {created_effect_instance.duration + 1} rounds"))
        return applied_effect_logs

    def process_periodic_effects(
        self,
        phase: str,
        opponent: Optional["Army"] = None,
        skip_dot_at_start: bool = False,
    ):
        if phase not in ["start_of_round", "end_of_round"]:
            return
        if not self.simulator:
            return

        for effect in list(self.active_effects):
            is_immediate_custom_effect = effect.name in [
                EFFECT_NAME_FIRST_STRIKE_RAGE_AURA,
                EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
                EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
                EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
                EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
                EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
                EFFECT_NAME_CONCENTRATION_RAGE_GAIN,  # Add Olena's custom rage gain effect
                EFFECT_NAME_BERSERK_FURY_RAGE_GAIN,
                EFFECT_NAME_PENDING_BRUTAL_BLOW_BUFF_REMOVAL,
                EFFECT_NAME_PENDING_BRUTAL_BLOW_CLEANSE,
                EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
            ]
            if (
                effect.applied_this_round
                and phase == "start_of_round"
                and not is_immediate_custom_effect
            ):
                continue

            if effect.effect_type == EffectType.DAMAGE_OVER_TIME:
                if skip_dot_at_start and phase == "start_of_round":
                    continue
                dot_type = effect.config.get("dot_type")
                is_special_dot = isinstance(dot_type, DoTType) and dot_type in [
                    DoTType.BLEED,
                    DoTType.POISON,
                    DoTType.BURN,
                ]
                potential_dot_damage_tick = 0.0
                base_dot_damage_for_log = 0.0
                final_dot_multiplier_for_log = 1.0
                dot_damage_after_target_debuffs = 0.0

                if is_special_dot:
                    snap_atk = effect.config.get('snapshotted_attacker_total_attack', 0.0)
                    snap_def = effect.config.get('snapshotted_defender_total_defense', 1.0)
                    if snap_def == 0: snap_def = 1.0
                    snap_scalar = effect.config.get('snapshotted_attacker_troop_scalar', 0.0)
                    status_factor = effect.config.get('status_effect_factor', 0.0)
                    original_caster_name = effect.config.get('original_caster_army_name')
                    caster_army = None
                    if original_caster_name == self.simulator.army1.name:
                        caster_army = self.simulator.army1
                    elif original_caster_name == self.simulator.army2.name:
                        caster_army = self.simulator.army2

                    current_specific_dot_boost = 0.0
                    if caster_army:
                        if dot_type == DoTType.BLEED:
                            current_specific_dot_boost = caster_army.get_sum_stat_magnitudes(
                                StatType.BLEED_DAMAGE_BOOST)
                        elif dot_type == DoTType.POISON:
                            current_specific_dot_boost = caster_army.get_sum_stat_magnitudes(
                                StatType.POISON_DAMAGE_BOOST)
                        elif dot_type == DoTType.BURN:
                            current_specific_dot_boost = caster_army.get_sum_stat_magnitudes(StatType.BURN_DAMAGE_BOOST)

                    current_specific_dot_reduction = 0.0
                    if dot_type == DoTType.BLEED:
                        current_specific_dot_reduction = self.get_sum_stat_magnitudes(StatType.BLEED_DAMAGE_REDUCTION)
                    elif dot_type == DoTType.POISON:
                        current_specific_dot_reduction = self.get_sum_stat_magnitudes(StatType.POISON_DAMAGE_REDUCTION)
                    elif dot_type == DoTType.BURN:
                        current_specific_dot_reduction = self.get_sum_stat_magnitudes(StatType.BURN_DAMAGE_REDUCTION)

                    base_dot_damage_for_log = ((snap_atk / snap_def) * snap_scalar * (status_factor / 200.0))
                    # IMPORTANT: DoTs are NOT affected by general DAMAGE_TAKEN_MULTIPLIER. Only specific DoT boosts/reductions.
                    final_dot_multiplier_for_log = max(0.05,
                                                       1.0 + current_specific_dot_boost + current_specific_dot_reduction)  # Reduction is negative
                    potential_dot_damage_tick = base_dot_damage_for_log * final_dot_multiplier_for_log
                    dot_damage_after_target_debuffs = potential_dot_damage_tick  # For DoTs, this is the final pre-shield damage

                elif dot_type == DoTType.GENERIC and effect.config.get("dot_damage_per_round", 0) > 0:
                    potential_dot_damage_tick = effect.config["dot_damage_per_round"]
                    # Generic DoTs also should not be affected by general DAMAGE_TAKEN_MULTIPLIER
                    dot_damage_after_target_debuffs = potential_dot_damage_tick
                    base_dot_damage_for_log = potential_dot_damage_tick
                    final_dot_multiplier_for_log = 1.0

                if dot_damage_after_target_debuffs > 0:  # Use damage after target's specific DoT reductions
                    damage_result_dict = self.apply_shields_and_get_hp_damage(dot_damage_after_target_debuffs)
                    hp_damage_to_troops_dot = damage_result_dict['hp_damage_to_troops']
                    absorbed_by_shield_dot = damage_result_dict['absorbed_by_shield']

                    attacker_name = effect.config.get("source_army_name", "Unknown")
                    if hp_damage_to_troops_dot > 0:
                        self.pending_hp_damage_this_round += hp_damage_to_troops_dot
                        self.damage_contributors_this_round[attacker_name] = (
                            self.damage_contributors_this_round.get(attacker_name, 0.0)
                            + hp_damage_to_troops_dot
                        )
                        skill_map = self.damage_contributors_by_skill_this_round.setdefault(
                            attacker_name, {}
                        )
                        skill_map[effect.source_skill_id] = skill_map.get(
                            effect.source_skill_id, 0.0
                        ) + hp_damage_to_troops_dot

                    dot_type_str = dot_type.value if isinstance(dot_type, DoTType) else "DoT"
                    log_msg = f"takes {hp_damage_to_troops_dot:.0f} HP ({dot_type_str}) damage (pending)."
                    if absorbed_by_shield_dot > 0:
                        log_msg += f" {absorbed_by_shield_dot:.0f} HP absorbed by shield."

                    log_msg += f" Potential: {dot_damage_after_target_debuffs:.0f}"
                    if is_special_dot:
                        log_msg += f" (Base: {base_dot_damage_for_log:.0f}, SpecificMult: {final_dot_multiplier_for_log:.2f})"
                    self.simulator._log_skill_trigger(
                        self,
                        effect.name,
                        log_msg,
                        damage_details={
                            "damage_done_hp": round(dot_damage_after_target_debuffs),
                            "absorbed_hp": round(absorbed_by_shield_dot),
                        },
                    )

            elif effect.effect_type == EffectType.HEAL_OVER_TIME and effect.magnitude > 0:
                if phase != "start_of_round":
                    continue
                if opponent:
                    hot_amount_this_tick = self.calculate_and_add_pending_healing(
                        heal_factor=effect.magnitude,
                        healer_army=self,
                        opponent_of_healer=opponent,
                        source_skill_id=effect.source_skill_id,
                    )
                    if hot_amount_this_tick > 0 and self.simulator:
                        self.simulator._log_skill_trigger(
                            self,
                            effect.name,
                            f"heals for {hot_amount_this_tick:.0f} HP (pending) from HoT (Factor: {effect.magnitude:.0f}).",
                        )

            elif effect.name == EFFECT_NAME_FIRST_STRIKE_RAGE_AURA and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round':
                    start_gain_round = effect.config.get("start_rage_gain_round", 0);
                    end_gain_round = effect.config.get("end_rage_gain_round", 0)
                    current_round = self.simulator.round
                    if start_gain_round <= current_round <= end_gain_round:
                        rage_to_gain = effect.config.get("rage_per_round", 0)
                        if rage_to_gain > 0:
                            self.current_rage += rage_to_gain
                            self.rage_added_this_round += rage_to_gain

            # Handle Olena's Concentration Rage Gain
            elif effect.name == EFFECT_NAME_CONCENTRATION_RAGE_GAIN and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round':
                    current_sim_round = self.simulator.round
                    effect_applied_in_round = effect.config.get("effect_applied_in_round", -1)
                    base_rage = effect.config.get("base_rage_amount", 0)
                    bonus_rage = effect.config.get("bonus_rage_amount",
                                                   0)  # This is the pre-calculated bonus (200 or 0)
                    bonus_applied_round = effect.config.get("bonus_applied_round", -1)

                    gained_this_tick = 0
                    log_parts = []

                    # Round N+1 processing (first round after cast)
                    if current_sim_round == effect_applied_in_round + 1:
                        if base_rage > 0:
                            self.current_rage += base_rage
                            self.rage_added_this_round += base_rage
                            gained_this_tick += base_rage
                            log_parts.append(f"{base_rage} base rage")
                        if bonus_rage > 0 and bonus_applied_round == -1:  # Apply bonus only on the first tick if applicable
                            self.current_rage += bonus_rage
                            self.rage_added_this_round += bonus_rage
                            gained_this_tick += bonus_rage
                            effect.config["bonus_applied_round"] = current_sim_round  # Mark bonus as applied
                            log_parts.append(f"{bonus_rage} bonus rage")

                    # Round N+2 processing (second round after cast)
                    elif current_sim_round == effect_applied_in_round + 2:
                        if base_rage > 0:
                            self.current_rage += base_rage
                            self.rage_added_this_round += base_rage
                            gained_this_tick += base_rage
                            log_parts.append(f"{base_rage} base rage")

                    if gained_this_tick > 0:
                        self.simulator._log_skill_trigger(self, effect.name,
                                                          f"gains {', '.join(log_parts)} ({gained_this_tick} total this round). New rage: {self.current_rage:.0f}")

            elif effect.name == EFFECT_NAME_BERSERK_FURY_RAGE_GAIN and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round':
                    gain_amt = effect.config.get("rage_per_round", 0)
                    if gain_amt > 0:
                        self.current_rage += gain_amt
                        self.rage_added_this_round += gain_amt
                        if self.simulator:
                            self.simulator._log_skill_trigger(
                                self, effect.name,
                                f"gains {gain_amt} rage from Berserk Fury. New rage: {self.current_rage:.0f}")

            elif effect.name == EFFECT_NAME_DELAYED_RAGE_GAIN and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round' and effect.duration <= 0:
                    rage_amt = effect.config.get("rage_amount", 0)
                    if rage_amt > 0:
                        self.current_rage += rage_amt
                        self.rage_added_this_round += rage_amt
                        if self.simulator:
                            self.simulator._log_skill_trigger(
                                self, effect.name,
                                f"gains {rage_amt} rage (delayed). New rage: {self.current_rage:.0f}")
                    if effect in self.active_effects:
                        self.active_effects.remove(effect)

            elif effect.name == EFFECT_NAME_DELAYED_RAGE_REDUCTION and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round' and effect.duration <= 0:
                    reduction = effect.config.get("rage_reduction", 0)
                    if reduction > 0 and self.current_rage > 0:
                        actual = min(self.current_rage, float(reduction))
                        self.current_rage -= actual
                        if self.simulator:
                            self.simulator._log_skill_trigger(
                                self, effect.name,
                                f"loses {actual:.0f} rage (delayed). New rage: {self.current_rage:.0f}")
                    if effect in self.active_effects:
                        self.active_effects.remove(effect)

            elif effect.name == EFFECT_NAME_PENDING_JUDGEMENT_MARKERS and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'end_of_round':
                    cnt = int(effect.config.get("marker_count", 1))
                    for _ in range(cnt):
                        marker_data = {
                            "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
                            "name": EFFECT_NAME_JUDGEMENT_MARKER,
                            "duration": -1,
                        }
                        self._create_and_add_single_effect(marker_data, effect.source_skill_id, self, self, opponent)
                    if self.simulator:
                        self.simulator._log_skill_trigger(self, effect.name, f"gains {cnt} Judgement Marker(s).")
                    if effect in self.active_effects:
                        self.active_effects.remove(effect)

            elif effect.name == EFFECT_NAME_PENDING_HEROIC_BLESSING_DEBUFF and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round' and effect.duration <= 0:
                    debuff_duration = effect.config.get("debuff_duration", 30)
                    debuff_data = {
                        "effect_type": EffectType.STAT_MOD,
                        "name": EFFECT_NAME_HEROIC_BLESSING_COUNTER_DEBUFF,
                        "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST,
                        "magnitude": -0.30,
                        "duration": debuff_duration,
                    }
                    created = self._create_and_add_single_effect(
                        debuff_data, effect.source_skill_id, self, self, opponent
                    )
                    if created:
                        self.simulator._log_skill_trigger(
                            self,
                            effect.name,
                            f"Gains '{EFFECT_NAME_HEROIC_BLESSING_COUNTER_DEBUFF}': {created.get_functionality_description()} for {debuff_duration} rounds."
                        )
                    if effect in self.active_effects:
                        self.active_effects.remove(effect)

            elif effect.name == EFFECT_NAME_PENDING_HEROIC_BLESSING_BUFF and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round' and effect.duration <= 0:
                    boost_mag = effect.config.get("burn_boost_magnitude", 0.0)
                    if boost_mag != 0:
                        buff_data = {
                            "effect_type": EffectType.STAT_MOD,
                            "name": EFFECT_NAME_HEROIC_BLESSING_BURN_BOOST,
                            "stat_to_mod": StatType.BURN_DAMAGE_BOOST,
                            "magnitude": boost_mag,
                            "duration": -1,
                        }
                        created = self._create_and_add_single_effect(
                            buff_data, effect.source_skill_id, self, self, opponent
                        )
                        if created:
                            self.simulator._log_skill_trigger(
                                self,
                                effect.name,
                                f"Heroic Blessing debuff expired. Gains permanent burn damage boost (+{boost_mag*100:.0f}%)."
                            )
                    for i in range(len(self.active_effects) - 1, -1, -1):
                        if self.active_effects[i].name == EFFECT_NAME_HEROIC_BLESSING_COUNTER_DEBUFF:
                            self.active_effects.pop(i)
                            break
                    if effect in self.active_effects:
                        self.active_effects.remove(effect)


            elif effect.name in [EFFECT_NAME_PENDING_AWAKENING_CLEANSE, EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
                                 EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE, EFFECT_NAME_PENDING_BRUTAL_BLOW_CLEANSE] \
                    and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round':
                    debuff_ids_to_remove = effect.config.get("debuff_ids_to_remove", [])
                    debuff_names_removed_log = []

                    new_active_effects_after_cleanse = []
                    for current_eff_in_army in list(self.active_effects):
                        if current_eff_in_army.id in debuff_ids_to_remove:
                            debuff_names_removed_log.append(
                                current_eff_in_army.name if current_eff_in_army.name else f"Unnamed Debuff ({str(current_eff_in_army.id)[:4]})")
                        else:
                            new_active_effects_after_cleanse.append(current_eff_in_army)

                    if debuff_names_removed_log:
                        self.active_effects = new_active_effects_after_cleanse
                        self.simulator._log_skill_trigger(self, effect.name,
                                                          f"Removes targeted debuffs: {', '.join(debuff_names_removed_log)}.")

            elif effect.name in [EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
                                 EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
                                 EFFECT_NAME_PENDING_BRUTAL_BLOW_BUFF_REMOVAL,
                                 EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL] \
                    and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round':
                    buff_ids_to_remove = effect.config.get("buff_ids_to_remove", [])
                    targeted_buff_names_initial_log = effect.config.get("targeted_buff_names_initial_log", [])
                    actually_removed_names_this_step = []

                    new_active_effects_after_removal = []
                    for current_eff_in_army in list(self.active_effects):
                        if current_eff_in_army.id in buff_ids_to_remove:
                            actually_removed_names_this_step.append(
                                current_eff_in_army.name if current_eff_in_army.name else f"Buff ID ...{str(current_eff_in_army.id)[-4:]}")
                        else:
                            new_active_effects_after_removal.append(current_eff_in_army)

                    source_skill_name = self.simulator.SKILL_REGISTRY_GLOBAL.get(effect.source_skill_id, {}).get("name",
                                                                                                                 effect.source_skill_id)
                    if actually_removed_names_this_step:
                        self.active_effects = new_active_effects_after_removal
                        self.simulator._log_skill_trigger(self, f"{source_skill_name} ({effect.name})",
                                                          f"Removes targeted buffs from self: {', '.join(actually_removed_names_this_step)}.")
                    elif targeted_buff_names_initial_log:
                        self.simulator._log_skill_trigger(self, f"{source_skill_name} ({effect.name} Attempt)",
                                                          f"Targeted buffs ({', '.join(targeted_buff_names_initial_log)}) were no longer active or already expired on self.")

    def activate_queued_effects(self):
        effects_to_add_to_active = []
        for new_effect in self.upcoming_effects:
            allow_duplicates = new_effect.name in {
                EFFECT_NAME_JUDGEMENT_MARKER,
                EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
            }
            if not allow_duplicates:
                replaced_in_active = False
                for i in range(len(self.active_effects) - 1, -1, -1):
                    existing_active_effect = self.active_effects[i]
                    if (
                        existing_active_effect.name == new_effect.name
                        and existing_active_effect.source_skill_id == new_effect.source_skill_id
                    ):
                        self.active_effects.pop(i)
                        replaced_in_active = True
                        break

                replaced_in_staged = False
                for i in range(len(effects_to_add_to_active) - 1, -1, -1):
                    already_staged_effect = effects_to_add_to_active[i]
                    if (
                        already_staged_effect.name == new_effect.name
                        and already_staged_effect.source_skill_id == new_effect.source_skill_id
                    ):
                        effects_to_add_to_active.pop(i)
                        replaced_in_staged = True
                        break

            new_effect.applied_this_round = True
            effects_to_add_to_active.append(new_effect)

        self.active_effects.extend(effects_to_add_to_active)
        self.upcoming_effects.clear()

    def decrement_effect_durations(self):
        next_active_effects = []
        for eff in self.active_effects:
            if eff.duration == -1:
                eff.applied_this_round = False
                next_active_effects.append(eff)
                continue

            if eff.applied_this_round:
                eff.applied_this_round = False
                if eff.duration >= 0:
                    next_active_effects.append(eff)
            else:
                eff.duration -= 1
                if eff.duration >= 0:
                    next_active_effects.append(eff)
        self.active_effects = next_active_effects

    def apply_start_of_round_rage_deductions(self):
        """Apply all pending rage reduction effects before other start-of-round logic."""
        to_remove = []
        for eff in list(self.active_effects):
            if (eff.name == EFFECT_NAME_DELAYED_RAGE_REDUCTION and
                    eff.effect_type == EffectType.CUSTOM_SKILL_EFFECT and
                    eff.duration <= 0):
                reduction = eff.config.get("rage_reduction", 0)
                if reduction > 0 and self.current_rage > 0:
                    actual = min(self.current_rage, float(reduction))
                    self.current_rage -= actual
                    if self.simulator:
                        self.simulator._log_skill_trigger(
                            self,
                            eff.name,
                            f"loses {actual:.0f} rage (delayed). New rage: {self.current_rage:.0f}",
                        )
                to_remove.append(eff)
        for r in to_remove:
            if r in self.active_effects:
                self.active_effects.remove(r)

    def has_active_debuff(self, debuff_name: str) -> bool:
        for effect in self.active_effects:
            if effect.name == debuff_name:
                if effect.effect_type == EffectType.DEBUFF: return True
                if effect.config.get("prevents_counterattack"): return True
                if effect.config.get("prevents_basic_attack"): return True
                if effect.config.get("prevents_rage_skill_cast"): return True
        return False

    def reset_for_new_battle(self):
        self.simulator = None
        self.simulators.clear()
        self.current_troop_count = float(self.unit.initial_count)
        self.active_effects.clear()
        self.upcoming_effects.clear()
        self.effects_to_activate_next_round.clear()
        self.triggered_skills_this_round.clear()
        self.skill_trigger_counts_this_round.clear()
        self.skill_triggers_against_this_round.clear()
        self.pending_hp_damage_this_round = 0.0  # Reset here is good
        self.pending_hp_healing_this_round = 0.0  # Reset here is good
        self.unrevivable_troops = 0.0
        self.skill_trigger_counts.clear()
        self.skill_last_triggered_round.clear()
        self.debuff_last_applied_round.clear()
        self.current_rage = 0.0
        self.hero1_rage_skill_queued_this_round = False
        self.hero1_rage_skill_used_round = None
        self.hero2_rage_skill_primed_for_round = None
        self.hero1_rage_skill_scheduled_round = None
        self.army_used_rage_skill_this_round_for_rage_gain_block = False
        self.base_rage_awarded_this_round = False
        self.started_round_with_active_shield = False
        self.started_last_round_with_active_shield = False
        self.healing_hymn_triggered_this_round = False
        self.hero1_rage_skill_cast_blocked_by_silence_this_round = False

        self.damage_dealt_history = []
        self.heal_received_history = []
        self.shield_received_history = []
        self.rage_gained_history = []
        self.kills_dealt_history = []
        self.troops_healed_total = 0.0
        self.shield_hp_gained_this_round = 0.0
        self.rage_added_this_round = 0.0
        self.kills_dealt_this_round = 0.0
        self.damage_contributors_this_round = {}
        self.damage_contributors_by_skill_this_round = {}
        self.heal_contributors_this_round = {}
        self.skill_kill_totals.clear()
        self.skill_heal_totals.clear()

        self._identify_hero_rage_skills()
        self._apply_initial_passive_skills()

    def __repr__(self):
        hero_names = [h.name for h in self.heroes if h] if self.heroes else []
        return (
            f"Army(Name: {self.name}, Unit: {self.unit.unit_type} T{self.unit.tier}, Troops: {self.current_troop_count:.0f}/{self.unit.initial_count} "
            f"(Unrev: {round(self.unrevivable_troops)}), Rage: {self.current_rage:.0f}, Heroes: {hero_names}, Active Effects: {len(self.active_effects)})")

