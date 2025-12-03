import uuid
import random
import math
import copy
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Set, Iterable

from .enums import EffectType, SkillTriggerType, StatType, DoTType
from .unit_definition import Unit
from .hero_definition import Hero
from .effect_system import EffectInstance
from .skill_system import SkillDefinition
from .skill_definitions import SKILL_REGISTRY_GLOBAL
from .constants import (
    EFFECT_NAME_BROKEN_BLADE_DEBUFF, EFFECT_NAME_DISARM_DEBUFF, EFFECT_NAME_SILENCE_DEBUFF,
    EFFECT_NAME_FIRST_STRIKE_RAGE_AURA, EFFECT_NAME_PENDING_AWAKENING_CLEANSE,
    EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_BLESSED_NEGATION_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_WILD_INDULGENCE_CLEANSE,
    EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE,
    EFFECT_NAME_CONCENTRATION_RAGE_GAIN,  # Import Olena's new effect
    EFFECT_NAME_MOUNT_PERIODIC_RAGE_GAIN,
    EFFECT_NAME_BERSERK_FURY_RAGE_GAIN,
    EFFECT_NAME_DELAYED_RAGE_GAIN,
    EFFECT_NAME_DELAYED_RAGE_REDUCTION,
    EFFECT_NAME_PAIN_N_FURY_RAGE_GAIN,
    EFFECT_NAME_PENDING_HEIMDALL_PURIFY,
    EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
    EFFECT_NAME_HEIMDALL_STEALTH_EVASION,
    EFFECT_NAME_HEIMDALL_RETRIBUTION,
    EFFECT_NAME_HEIMDALL_DAMAGE_REDUCTION,
    EFFECT_NAME_PENDING_HEROIC_BLESSING_DEBUFF,
    EFFECT_NAME_PENDING_HEROIC_BLESSING_BUFF,
    EFFECT_NAME_HEROIC_BLESSING_COUNTER_DEBUFF,
    EFFECT_NAME_HEROIC_BLESSING_BURN_BOOST,
    EFFECT_NAME_PENDING_BRUTAL_BLOW_BUFF_REMOVAL,
    EFFECT_NAME_PENDING_SHIELD_REFLECTOR_REMOVAL,
    EFFECT_NAME_PENDING_BRUTAL_BLOW_CLEANSE,
    EFFECT_NAME_PENDING_SEAS_GRACE_PURIFY,
    EFFECT_NAME_SAINTLY_GUARDIAN_SHIELD_BOOST,
    EFFECT_NAME_WAR_BLESSING_SHIELD,
    EFFECT_NAME_JUDGEMENT_FURY_COUNTER_BUFF,
    EFFECT_NAME_JUDGEMENT_MARKER,
    EFFECT_NAME_PENDING_JUDGEMENT_MARKERS,
    EFFECT_NAME_HOLY_ENLIGHTENMENT_DMG_TAKEN_DEBUFF,
    EFFECT_NAME_BLESSED_BY_FATE_ENEMY_DMG_TAKEN_DEBUFF,
    EFFECT_NAME_RAGEBEAST_SOUL_RAGE_GAIN,
)

GameSimulatorRef = "GameSimulator"  # Forward reference

BASIC_ATTACK_ID = "basic_attack"
COUNTER_ATTACK_ID = "counter_attack"
COMBAT_SKILL_IDS = {BASIC_ATTACK_ID, COUNTER_ATTACK_ID}


def normalize_gem_skill_id(value: Any) -> str:
    """Return a normalized jewel skill identifier extracted from ``value``."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = normalize_gem_skill_id(item)
            if normalized:
                return normalized
        return ""
    if isinstance(value, dict):
        for key in ("id", "skill_id", "skill", "name"):
            if key in value:
                normalized = normalize_gem_skill_id(value.get(key))
                if normalized:
                    return normalized
        for item in value.values():
            normalized = normalize_gem_skill_id(item)
            if normalized:
                return normalized
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value).strip()
    if isinstance(value, bool):
        return ""
    text = str(value).strip()
    return text if text else ""


@dataclass(slots=True)
class Army:
    name: str
    unit: Unit
    heroes: List[Hero] = field(default_factory=list)
    unrevivable_ratio: float = 0.65
    use_dynamic_unrevivable_ratio: bool = False
    is_rally: bool = False
    bonus_stats_config: Dict[str, Any] = field(default_factory=dict)
    gem_skill_ids: Dict[str, str] = field(default_factory=dict)
    gem_skills: List[SkillDefinition] = field(init=False, default_factory=list)
    simulator: Optional[GameSimulatorRef] = field(init=False, default=None)
    simulators: List[GameSimulatorRef] = field(init=False, default_factory=list)
    army_round: int = field(init=False, default=0)

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
    troop_count_history: List[float] = field(init=False, default_factory=list)
    unrevivable_history: List[float] = field(init=False, default_factory=list)
    troops_healed_total: float = field(init=False, default=0.0)
    shield_hp_gained_this_round: float = field(init=False, default=0.0)
    rage_added_this_round: float = field(init=False, default=0.0)
    kills_dealt_this_round: float = field(init=False, default=0.0)
    damage_contributors_this_round: Dict[str, float] = field(init=False, default_factory=dict)
    damage_contributors_by_skill_this_round: Dict[str, Dict[str, float]] = field(
        init=False, default_factory=dict
    )
    dynamic_losses_by_opponent: Dict[str, Dict[str, float]] = field(
        init=False, default_factory=dict
    )
    dynamic_kills_by_opponent: Dict[str, Dict[str, float]] = field(
        init=False, default_factory=dict
    )
    heal_contributors_this_round: Dict[str, Dict[str, float]] = field(
        init=False, default_factory=dict
    )
    skill_kill_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_heal_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_shield_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_rage_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_damage_reduction_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_rage_reduction_totals: Dict[str, float] = field(init=False, default_factory=dict)
    # Totals contributed indirectly via boost effects
    skill_kill_boost_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_heal_boost_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_shield_boost_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_rage_boost_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_damage_reduction_boost_totals: Dict[str, float] = field(init=False, default_factory=dict)
    skill_rage_reduction_boost_totals: Dict[str, float] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self.reset_for_new_battle()

    def register_simulator(self, simulator: GameSimulatorRef):
        self.simulator = simulator
        if simulator not in self.simulators:
            self.simulators.append(simulator)

    def clear_dynamic_unrevivable_tracking(self) -> None:
        self.dynamic_losses_by_opponent.clear()
        self.dynamic_kills_by_opponent.clear()

    def _record_dynamic_losses(self, opponent_name: str, combat: float, skill: float) -> None:
        if combat <= 0 and skill <= 0:
            return
        record = self.dynamic_losses_by_opponent.setdefault(
            opponent_name, {"combat": 0.0, "skill": 0.0}
        )
        record["combat"] += combat
        record["skill"] += skill

    def _record_dynamic_kills(
        self, opponent_name: str, basic: float, counter: float, skill: float
    ) -> None:
        if basic <= 0 and counter <= 0 and skill <= 0:
            return
        record = self.dynamic_kills_by_opponent.setdefault(
            opponent_name,
            {"combat_basic": 0.0, "combat_counter": 0.0, "skill": 0.0},
        )
        record["combat_basic"] += basic
        record["combat_counter"] += counter
        record["skill"] += skill

    def _find_army_by_name(self, name: str) -> Optional["Army"]:
        if name == self.name:
            return self
        if self.simulator is not None:
            if getattr(self.simulator, "army1", None) and self.simulator.army1.name == name:
                return self.simulator.army1
            if getattr(self.simulator, "army2", None) and self.simulator.army2.name == name:
                return self.simulator.army2
        for sim in self.simulators:
            if sim.army1.name == name:
                return sim.army1
            if sim.army2.name == name:
                return sim.army2
            engine = getattr(sim, "parent_engine", None)
            if engine and name in engine._armies:
                return engine._armies[name].army
        return None

    def increment_skill_trigger_count(self, skill_id: str):
        self.skill_trigger_counts[skill_id] = self.skill_trigger_counts.get(skill_id, 0) + 1

    def _get_rage_gain_multiplier(self) -> tuple[float, list[EffectInstance]]:
        """Return the multiplier and contributing effects for rage gains."""
        effects = [
            eff
            for eff in self.active_effects
            if eff.config.get("rage_bonus_pct", 0.0) > 0.0
        ]
        bonus = sum(eff.config.get("rage_bonus_pct", 0.0) for eff in effects)
        return 1.0 + bonus, effects

    def add_rage(self, amount: float, source_skill_id: Optional[str] = None) -> float:
        """Add rage to the army, applying any Berserk Fury bonuses and track source."""
        if amount <= 0:
            return 0.0
        multiplier, bonus_effects = self._get_rage_gain_multiplier()
        gained = math.floor(amount * multiplier + 1e-9)
        base_gain = math.floor(amount + 1e-9)
        extra_gain = gained - base_gain
        self.current_rage += gained
        self.rage_added_this_round += gained
        if source_skill_id:
            self.skill_rage_totals[source_skill_id] = (
                self.skill_rage_totals.get(source_skill_id, 0.0) + gained
            )
        if extra_gain > 0 and bonus_effects:
            total_bonus = sum(eff.config.get("rage_bonus_pct", 0.0) for eff in bonus_effects)
            if total_bonus > 0:
                for eff in bonus_effects:
                    weight = eff.config.get("rage_bonus_pct", 0.0) / total_bonus
                    self.skill_rage_boost_totals[eff.source_skill_id] = (
                        self.skill_rage_boost_totals.get(eff.source_skill_id, 0.0)
                        + extra_gain * weight
                    )
        return gained

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

    def _reload_gem_skills(self) -> None:
        """Refresh cached jewel skill definitions from the global registry."""

        self.gem_skills = []
        if not self.gem_skill_ids:
            return
        for slot, skill_id in self.gem_skill_ids.items():
            if not skill_id or not isinstance(skill_id, str):
                continue
            skill_def = SKILL_REGISTRY_GLOBAL.get(skill_id)
            if not skill_def:
                print(
                    f"Warning: Jewel skill '{skill_id}' for army '{self.name}' not found in registry."
                )
                continue
            self.gem_skills.append(copy.deepcopy(skill_def))

    def set_gem_skills(self, gem_skills: Dict[str, Any] | None) -> None:
        """Assign jewel skills to this army using ``gem_skills`` mapping."""

        normalized: Dict[str, str] = {}
        if gem_skills:
            for slot, skill_id in gem_skills.items():
                if not isinstance(slot, str):
                    continue
                normalized_id = normalize_gem_skill_id(skill_id)
                if normalized_id:
                    normalized[slot] = normalized_id
        self.gem_skill_ids = normalized
        self._reload_gem_skills()

    def _apply_initial_passive_skills(
        self, *, simulator: Optional[GameSimulatorRef] = None
    ) -> None:
        sim = simulator if simulator is not None else self.simulator

        skill_definitions: List[SkillDefinition] = []
        for hero in self.heroes:
            if not hero:
                continue
            skill_definitions.extend(hero.skills)
        skill_definitions.extend(self.gem_skills)

        for skill_def in skill_definitions:
            is_passive_trigger = skill_def.get("trigger") == SkillTriggerType.PASSIVE
            has_passive_effects = bool(skill_def.get("passive_effects"))
            if (
                (not is_passive_trigger and not has_passive_effects)
                or skill_def.get("id") == "dummy_talent_empty"
            ):
                continue

            # Passive skills may be applied multiple times when armies join new
            # engagements. Skip any skill that has already triggered once to
            # avoid stacking permanent effects.
            if self.skill_trigger_counts.get(skill_def.get("id")):
                continue

            an_effect_truly_happened_passive = False
            log_details_passive: List[Tuple[str, Optional[Dict[str, Any]]]] = []

            if is_passive_trigger:
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
                                effect_data=effect_to_apply_data.copy(),
                                source_skill_id=skill_def["id"],
                                owner_army=self,
                                target_army=self,
                                opponent_of_owner_for_calc=None,
                            )
                            if created_effect:
                                an_effect_truly_happened_passive = True
                                log_details_passive.append(
                                    (
                                        f"{sub_effect_data.get('name_suffix', 'Effect')}: "
                                        f"{created_effect.get_functionality_description()} "
                                        f"for {created_effect.duration + 1} rounds.",
                                        None,
                                    )
                                )
                elif skill_def.get("logic_handler") and sim:
                    opponent = sim.army2 if self is sim.army1 else sim.army1
                    logic_handler = skill_def.get("logic_handler")
                    an_effect_truly_happened_passive, log_details_passive = logic_handler(
                        self, opponent, skill_def, None, sim
                    )
                else:
                    # Without a simulator we cannot safely run custom logic handlers.
                    if skill_def.get("logic_handler"):
                        continue

            for effect_data in skill_def.get("passive_effects", []) or []:
                created_effect = self._create_and_add_single_effect(
                    effect_data=effect_data.copy(),
                    source_skill_id=skill_def.get("id", ""),
                    owner_army=self,
                    target_army=self,
                    opponent_of_owner_for_calc=None,
                )
                if created_effect:
                    an_effect_truly_happened_passive = True
                    log_details_passive.append(
                        (
                            created_effect.get_functionality_description(),
                            None,
                        )
                    )

            if an_effect_truly_happened_passive:
                if sim:
                    sim._log_skill_trigger(
                        self, skill_def["name"], "Passive applied at start."
                    )
                    for desc_str, dmg_details in log_details_passive:
                        sim._log_skill_trigger(
                            self, "  ↳", desc_str, damage_details=dmg_details
                        )
                self.increment_skill_trigger_count(skill_def["id"])
        self.activate_queued_effects()

    @staticmethod
    def _filter_match(filter_value: Any, candidate: Optional[str]) -> bool:
        if isinstance(filter_value, (list, tuple, set)):
            return any(Army._filter_match(val, candidate) for val in filter_value)
        if candidate is None:
            return False
        return str(filter_value).lower() == str(candidate).lower()

    def _effect_matches_filters(
        self,
        effect: EffectInstance,
        attack_type_filter: Optional[str] = None,
        target_unit_type: Optional[str] = None,
        attacker_unit_type: Optional[str] = None,
        skill_label: Optional[str] = None,
    ) -> bool:
        cfg_filter = effect.config.get("config_filter")
        if not cfg_filter:
            return True
        if not isinstance(cfg_filter, dict):
            return True
        if "attack_type" in cfg_filter:
            if not self._filter_match(cfg_filter["attack_type"], attack_type_filter):
                return False
        if "target_unit_type" in cfg_filter:
            if not self._filter_match(cfg_filter["target_unit_type"], target_unit_type):
                return False
        if "attacker_unit_type" in cfg_filter:
            if not self._filter_match(cfg_filter["attacker_unit_type"], attacker_unit_type):
                return False
        if "skill_label" in cfg_filter:
            if not self._filter_match(cfg_filter["skill_label"], skill_label):
                return False
        return True

    def iter_stat_effects(
        self,
        stat_type: StatType,
        *,
        attack_type_filter: Optional[str] = None,
        target_unit_type: Optional[str] = None,
        attacker_unit_type: Optional[str] = None,
        skill_label: Optional[str] = None,
    ) -> Iterable[EffectInstance]:
        for effect in self.active_effects:
            if effect.effect_type != EffectType.STAT_MOD:
                continue
            if effect.config.get("stat_to_mod") != stat_type:
                continue
            if not self._effect_matches_filters(
                effect,
                attack_type_filter=attack_type_filter,
                target_unit_type=target_unit_type,
                attacker_unit_type=attacker_unit_type,
                skill_label=skill_label,
            ):
                continue
            yield effect

    def get_sum_stat_magnitudes(
        self,
        stat_type: StatType,
        attack_type_filter: Optional[str] = None,
        target_unit_type: Optional[str] = None,
        attacker_unit_type: Optional[str] = None,
        skill_label: Optional[str] = None,
    ) -> float:
        return sum(
            eff.magnitude
            for eff in self.iter_stat_effects(
                stat_type,
                attack_type_filter=attack_type_filter,
                target_unit_type=target_unit_type,
                attacker_unit_type=attacker_unit_type,
                skill_label=skill_label,
            )
        )

    def _get_holy_blessed_damage_taken_bonus(
        self, effects: Iterable[EffectInstance]
    ) -> float:
        relevant_names = {
            EFFECT_NAME_HOLY_ENLIGHTENMENT_DMG_TAKEN_DEBUFF,
            EFFECT_NAME_BLESSED_BY_FATE_ENEMY_DMG_TAKEN_DEBUFF,
        }
        bonus = 0.0
        for effect in effects:
            if (
                effect.effect_type == EffectType.STAT_MOD
                and effect.name in relevant_names
                and effect.config.get("stat_to_mod") == StatType.DAMAGE_TAKEN_MULTIPLIER
                and effect.magnitude > 0
            ):
                bonus += effect.magnitude
        return bonus

    def get_current_shield_hp(self) -> float:
        return sum(effect.magnitude for effect in self.active_effects if
                   effect.effect_type == EffectType.SHIELD and effect.magnitude > 0)

    def preview_shield_absorption(self, incoming_damage: float) -> tuple[float, float]:
        """Return the (hp_damage_to_troops, absorbed_by_shield) without altering shields."""

        if incoming_damage <= 0:
            return 0.0, 0.0

        hp_dmg_final = incoming_damage
        absorbed_total = 0.0

        active_shields = sorted(
            [
                eff
                for eff in self.active_effects
                if eff.effect_type == EffectType.SHIELD and eff.magnitude > 0
            ],
            key=lambda e: e.duration,
        )

        for shield_eff in active_shields:
            if hp_dmg_final <= 0:
                break
            can_absorb = min(hp_dmg_final, shield_eff.magnitude)
            hp_dmg_final -= can_absorb
            absorbed_total += can_absorb

        return max(0.0, hp_dmg_final), absorbed_total

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
                            healer_army = None
                            for sim in self.simulators:
                                engine = getattr(sim, "parent_engine", None)
                                if not engine:
                                    continue
                                armies = getattr(engine, "_armies", {})
                                entry = armies.get(src)
                                if entry:
                                    healer_army = getattr(entry, "army", entry)
                                    break
                            if healer_army is None:
                                healer_army = self._find_army_by_name(src)
                            if healer_army:
                                for sid, hp in skills.items():
                                    portion = actual_healed_hp * (hp / total_contrib_hp)
                                    healer_army.skill_heal_totals[sid] = healer_army.skill_heal_totals.get(sid, 0.0) + (
                                        portion / hp_per_troop
                                    )

                    # Preserve the healed amount for logging in the simulator.
                    # It will be cleared at the start of the next round.
                    self.heal_contributors_this_round = {}
                    self.pending_hp_healing_this_round = actual_healed_hp

        if self.pending_hp_damage_this_round > 0 and self.current_troop_count > 0:
            hp_per_troop = self.unit.effective_hp_per_troop(self.active_effects)
            if hp_per_troop <= 0:
                hp_per_troop = 1

            lost_float = self.pending_hp_damage_this_round / hp_per_troop
            lost_round = round(lost_float)
            available_troops = min(round(self.current_troop_count), lost_round)
            dynamic_mode = self.use_dynamic_unrevivable_ratio
            unrevivable_increase = (
                0 if dynamic_mode else round(available_troops * self.unrevivable_ratio)
            )
            for sim in self.simulators:
                applied_loss_note = (
                    f" Applied loss: {available_troops}."
                    if available_troops != lost_round
                    else ""
                )
                if dynamic_mode:
                    unrevivable_note = " Dynamic unrevivable pending."
                else:
                    unrevivable_note = f" {unrevivable_increase} unrevivable."
                sim._log_skill_trigger(
                    self,
                    "Damage Commitment",
                    f"Commits {self.pending_hp_damage_this_round:.0f} pending HP damage, resulting in {lost_round} troops lost.{applied_loss_note}{unrevivable_note}",
                )
                for src, dmg in self.damage_contributors_this_round.items():
                    sim._log_skill_trigger(self, "  ↳", f"{src} committed {dmg:.0f} damage")
            self.current_troop_count = max(0, self.current_troop_count - available_troops)
            if not dynamic_mode:
                self.unrevivable_troops = min(
                    self.unit.initial_count,
                    self.unrevivable_troops + unrevivable_increase,
                )
            total_dmg = sum(self.damage_contributors_this_round.values())
            if available_troops > 0 and total_dmg > 0:
                for src, dmg in self.damage_contributors_this_round.items():
                    kills = available_troops * (dmg / total_dmg)
                    army_obj = self._find_army_by_name(src)
                    skill_map = self.damage_contributors_by_skill_this_round.get(src, {})
                    skill_total = sum(skill_map.values())
                    basic_kills = 0.0
                    counter_kills = 0.0
                    skill_kills = 0.0
                    if skill_total > 0:
                        for sid, sdmg in skill_map.items():
                            portion = kills * (sdmg / skill_total)
                            if army_obj:
                                army_obj.skill_kill_totals[sid] = (
                                    army_obj.skill_kill_totals.get(sid, 0.0) + portion
                                )
                            if sid == BASIC_ATTACK_ID:
                                basic_kills += portion
                            elif sid == COUNTER_ATTACK_ID:
                                counter_kills += portion
                            elif sid in COMBAT_SKILL_IDS:
                                basic_kills += portion
                            else:
                                skill_kills += portion
                    else:
                        basic_kills = kills
                    if army_obj:
                        army_obj.kills_dealt_this_round += kills
                    combat_kills = basic_kills + counter_kills
                    if combat_kills > 0 or skill_kills > 0:
                        self._record_dynamic_losses(src, combat_kills, skill_kills)
                        if army_obj:
                            army_obj._record_dynamic_kills(
                                self.name, basic_kills, counter_kills, skill_kills
                            )
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
        positive_heal_adj_effects = [
            eff
            for eff in self.active_effects
            if eff.effect_type == EffectType.STAT_MOD
            and eff.config.get("stat_to_mod") == StatType.HEAL_ADJUSTMENT
            and eff.magnitude > 0
        ]
        total_positive_heal_adj = sum(eff.magnitude for eff in positive_heal_adj_effects)
        total_negative_heal_adj = total_heal_adj_recipient - total_positive_heal_adj
        heal_adj_mult = (
            1.0
            + total_negative_heal_adj
            + total_positive_heal_adj
            + skill_heal_adjustment_magnitude
        )
        opp_def_calc = opponent_of_healer.unit.effective_defense(opponent_of_healer.active_effects)
        if opp_def_calc == 0: opp_def_calc = 1

        hp_healed_raw = round(
            (healer_atk / opp_def_calc)
            * healer_troop_scalar
            * (heal_factor / 200.0)
            * heal_adj_mult
        )

        if hp_healed_raw > 0 and total_positive_heal_adj > 0:
            base_mult = 1.0 + total_negative_heal_adj + skill_heal_adjustment_magnitude
            hp_without_boost = round(
                (healer_atk / opp_def_calc)
                * healer_troop_scalar
                * (heal_factor / 200.0)
                * base_mult
            )
            extra_hp = hp_healed_raw - hp_without_boost
            if extra_hp > 0:
                hp_per_troop = self.unit.effective_hp_per_troop(self.active_effects)
                if hp_per_troop <= 0:
                    hp_per_troop = 1
                for eff in positive_heal_adj_effects:
                    weight = eff.magnitude / total_positive_heal_adj
                    troops = (extra_hp * weight) / hp_per_troop
                    self.skill_heal_boost_totals[eff.source_skill_id] = (
                        self.skill_heal_boost_totals.get(eff.source_skill_id, 0.0)
                        + troops
                    )

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
                current_round = getattr(
                    target_army,
                    "army_round",
                    target_army.simulator.round,
                )
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
        if isinstance(dot_type_value, DoTType) and dot_type_value in [
            DoTType.BLEED,
            DoTType.POISON,
            DoTType.BURN,
            DoTType.LACERATE,
        ]:
            is_special_dot = True
        elif isinstance(dot_type_value, str) and dot_type_value.upper() in [d.value for d in
                                                                            [
                                                                                DoTType.BLEED,
                                                                                DoTType.POISON,
                                                                                DoTType.BURN,
                                                                                DoTType.LACERATE,
                                                                            ]]:
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
            positive_shield_effects = [
                eff
                for eff in target_army.active_effects
                if eff.effect_type == EffectType.STAT_MOD
                and eff.config.get("stat_to_mod") == StatType.SHIELD_STRENGTH_MODIFIER
                and eff.magnitude > 0
            ]
            total_positive_shield = sum(eff.magnitude for eff in positive_shield_effects)
            total_negative_shield = sum_shield_strength_mods_recipient - total_positive_shield
            shield_strength_multiplier = 1.0 + sum_shield_strength_mods_recipient
            magnitude = round(base_shield_magnitude * shield_strength_multiplier)
            if total_positive_shield > 0 and base_shield_magnitude > 0:
                magnitude_without_boost = round(
                    base_shield_magnitude * (1.0 + total_negative_shield)
                )
                extra_hp = magnitude - magnitude_without_boost
                if extra_hp > 0:
                    hp_per_troop_boost = target_army.unit.effective_hp_per_troop(
                        target_army.active_effects
                    )
                    if hp_per_troop_boost <= 0:
                        hp_per_troop_boost = 1
                    for eff in positive_shield_effects:
                        weight = eff.magnitude / total_positive_shield
                        troops = (extra_hp * weight) / hp_per_troop_boost
                        target_army.skill_shield_boost_totals[eff.source_skill_id] = (
                            target_army.skill_shield_boost_totals.get(eff.source_skill_id, 0.0)
                            + troops
                        )
            if self.simulator:
                target_army.shield_hp_gained_this_round += magnitude
            hp_per_troop = target_army.unit.effective_hp_per_troop(target_army.active_effects)
            if hp_per_troop <= 0:
                hp_per_troop = 1
            shielded_troops = magnitude / hp_per_troop
            owner_army.skill_shield_totals[source_skill_id] = (
                owner_army.skill_shield_totals.get(source_skill_id, 0.0) + shielded_troops
            )

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
                EFFECT_NAME_PENDING_BRUTAL_BLOW_BUFF_REMOVAL,
                EFFECT_NAME_PENDING_BRUTAL_BLOW_CLEANSE,
                EFFECT_NAME_PENDING_HEIMDALL_PURIFY,
                EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
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
                    DoTType.LACERATE,
                ]
                potential_dot_damage_tick = 0.0
                base_dot_damage_for_log = 0.0
                final_dot_multiplier_for_log = 1.0
                dot_damage_after_target_debuffs = 0.0
                total_positive_dot = 0.0

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
                    positive_dot_effects: list[EffectInstance] = []
                    specific_stat = None
                    if caster_army:
                        if dot_type == DoTType.BLEED:
                            specific_stat = StatType.BLEED_DAMAGE_BOOST
                        elif dot_type == DoTType.POISON:
                            specific_stat = StatType.POISON_DAMAGE_BOOST
                        elif dot_type == DoTType.BURN:
                            specific_stat = StatType.BURN_DAMAGE_BOOST
                        elif dot_type == DoTType.LACERATE:
                            specific_stat = StatType.LACERATE_DAMAGE_BOOST
                        if specific_stat:
                            current_specific_dot_boost = caster_army.get_sum_stat_magnitudes(
                                specific_stat
                            )
                            positive_dot_effects = [
                                eff
                                for eff in caster_army.active_effects
                                if eff.effect_type == EffectType.STAT_MOD
                                and eff.config.get("stat_to_mod") == specific_stat
                                and eff.magnitude > 0
                            ]
                    total_positive_dot = sum(eff.magnitude for eff in positive_dot_effects)

                    current_specific_dot_reduction = 0.0
                    if dot_type == DoTType.BLEED:
                        current_specific_dot_reduction = self.get_sum_stat_magnitudes(StatType.BLEED_DAMAGE_REDUCTION)
                    elif dot_type == DoTType.POISON:
                        current_specific_dot_reduction = self.get_sum_stat_magnitudes(StatType.POISON_DAMAGE_REDUCTION)
                    elif dot_type == DoTType.BURN:
                        current_specific_dot_reduction = self.get_sum_stat_magnitudes(StatType.BURN_DAMAGE_REDUCTION)
                    elif dot_type == DoTType.LACERATE:
                        current_specific_dot_reduction = self.get_sum_stat_magnitudes(StatType.LACERATE_DAMAGE_REDUCTION)

                    base_dot_damage_for_log = ((snap_atk / snap_def) * snap_scalar * (status_factor / 200.0))
                    snapshot_bonus = effect.config.get("holy_blessed_damage_taken_snapshot", 0.0)
                    base_multiplier = 1.0 + current_specific_dot_boost + current_specific_dot_reduction
                    final_dot_multiplier_for_log = max(0.05, base_multiplier + snapshot_bonus)
                    potential_dot_damage_tick = base_dot_damage_for_log * final_dot_multiplier_for_log
                    dot_damage_after_target_debuffs = potential_dot_damage_tick  # For DoTs, this is the final pre-shield damage
                    current_shield_hp_dot = self.get_current_shield_hp()

                elif dot_type == DoTType.GENERIC and effect.config.get("dot_damage_per_round", 0) > 0:
                    base_dot_damage_for_log = effect.config["dot_damage_per_round"]
                    snapshot_bonus = effect.config.get("holy_blessed_damage_taken_snapshot", 0.0)
                    final_dot_multiplier_for_log = max(0.05, 1.0 + snapshot_bonus)
                    potential_dot_damage_tick = base_dot_damage_for_log * final_dot_multiplier_for_log
                    dot_damage_after_target_debuffs = potential_dot_damage_tick

                if dot_damage_after_target_debuffs > 0:  # Use damage after target's specific DoT reductions
                    damage_result_dict = self.apply_shields_and_get_hp_damage(dot_damage_after_target_debuffs)
                    hp_damage_to_troops_dot = damage_result_dict['hp_damage_to_troops']
                    absorbed_by_shield_dot = damage_result_dict['absorbed_by_shield']
                    if total_positive_dot > 0:
                        multiplier_without_positive = max(
                            0.05, 1.0 + current_specific_dot_reduction + effect.config.get("holy_blessed_damage_taken_snapshot", 0.0)
                        )
                        dmg_without_boost = base_dot_damage_for_log * multiplier_without_positive
                        hp_without_boost = max(0.0, dmg_without_boost - current_shield_hp_dot)
                        extra_hp = hp_damage_to_troops_dot - hp_without_boost
                        if extra_hp > 0 and caster_army:
                            hp_per_troop_boost = self.unit.effective_hp_per_troop(self.active_effects)
                            if hp_per_troop_boost <= 0:
                                hp_per_troop_boost = 1
                            for eff in positive_dot_effects:
                                weight = eff.magnitude / total_positive_dot
                                troops = (extra_hp * weight) / hp_per_troop_boost
                                caster_army.skill_kill_boost_totals[eff.source_skill_id] = (
                                    caster_army.skill_kill_boost_totals.get(eff.source_skill_id, 0.0)
                                    + troops
                                )

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
                    enemy_hp_per_troop = self.unit.effective_hp_per_troop(self.active_effects)
                    if enemy_hp_per_troop <= 0:
                        enemy_hp_per_troop = 1
                    potential_kills = 0
                    if hp_damage_to_troops_dot > 0:
                        potential_kills = round(hp_damage_to_troops_dot / enemy_hp_per_troop)

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
                            "potential_kills": int(potential_kills),
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
                    current_round = getattr(self, "army_round", self.simulator.round if self.simulator else 0)
                    if start_gain_round <= current_round <= end_gain_round:
                        rage_to_gain = effect.config.get("rage_per_round", 0)
                        if rage_to_gain > 0:
                            self.add_rage(rage_to_gain, effect.source_skill_id)

            # Handle multi-round rage gain effects
            elif effect.name in (
                EFFECT_NAME_CONCENTRATION_RAGE_GAIN,
                EFFECT_NAME_MOUNT_PERIODIC_RAGE_GAIN,
            ) and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round':
                    current_sim_round = getattr(self, "army_round", self.simulator.round if self.simulator else 0)
                    effect_applied_in_round = effect.config.get("effect_applied_in_round", -1)
                    base_rage = effect.config.get("base_rage_amount", 0)
                    bonus_rage = effect.config.get("bonus_rage_amount",
                                                   0)  # This is the pre-calculated bonus (200 or 0)
                    bonus_applied_round = effect.config.get("bonus_applied_round", -1)
                    bonus_tick = effect.config.get("bonus_tick", 1)
                    total_ticks = effect.config.get("ticks", 2)

                    gained_this_tick = 0
                    log_parts = []

                    tick_offset = current_sim_round - effect_applied_in_round
                    if 1 <= tick_offset <= total_ticks:
                        if base_rage > 0:
                            gained = self.add_rage(base_rage, effect.source_skill_id)
                            gained_this_tick += gained
                            log_parts.append(f"{gained:.0f} base rage")
                        if (
                            bonus_rage > 0
                            and bonus_applied_round == -1
                            and tick_offset == bonus_tick
                        ):  # Apply bonus only on the configured tick if applicable
                            gained_bonus = self.add_rage(bonus_rage, effect.source_skill_id)
                            gained_this_tick += gained_bonus
                            effect.config["bonus_applied_round"] = current_sim_round  # Mark bonus as applied
                            log_parts.append(f"{gained_bonus:.0f} bonus rage")

                    if gained_this_tick > 0:
                        self.simulator._log_skill_trigger(self, effect.name,
                                                          f"gains {', '.join(log_parts)} ({gained_this_tick} total this round). New rage: {self.current_rage:.0f}")
                    if tick_offset >= total_ticks and effect in self.active_effects:
                        self.active_effects.remove(effect)

            elif effect.name in (
                EFFECT_NAME_DELAYED_RAGE_GAIN,
                EFFECT_NAME_PAIN_N_FURY_RAGE_GAIN,
                EFFECT_NAME_RAGEBEAST_SOUL_RAGE_GAIN,
            ) and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round' and effect.duration <= 0:
                    rage_amt = effect.config.get("rage_amount", 0)
                    if rage_amt > 0:
                        gained = self.add_rage(rage_amt, effect.source_skill_id)
                        if self.simulator:
                            self.simulator._log_skill_trigger(
                                self, effect.name,
                                f"gains {gained:.0f} rage (delayed). New rage: {self.current_rage:.0f}")
                    if effect in self.active_effects:
                        self.active_effects.remove(effect)

            elif effect.name == EFFECT_NAME_DELAYED_RAGE_REDUCTION and effect.effect_type == EffectType.CUSTOM_SKILL_EFFECT:
                if phase == 'start_of_round' and effect.duration <= 0:
                    reduction = effect.config.get("rage_reduction", 0)
                    if reduction > 0 and self.current_rage > 0:
                        actual = min(self.current_rage, float(reduction))
                        self.current_rage -= actual
                        if self.simulator and effect.source_skill_id:
                            src_name = effect.config.get("source_army_name")
                            src_army = None
                            if src_name == self.simulator.army1.name:
                                src_army = self.simulator.army1
                            elif src_name == self.simulator.army2.name:
                                src_army = self.simulator.army2
                            if src_army:
                                src_army.skill_rage_reduction_totals[effect.source_skill_id] = (
                                    src_army.skill_rage_reduction_totals.get(effect.source_skill_id, 0.0)
                                    + actual
                                )
                            self.simulator._log_skill_trigger(
                                self, effect.name,
                                f"loses {actual:.0f} rage (delayed). New rage: {self.current_rage:.0f}")
                        elif effect.source_skill_id:
                            self.skill_rage_reduction_totals[effect.source_skill_id] = (
                                self.skill_rage_reduction_totals.get(effect.source_skill_id, 0.0)
                                + actual
                            )
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
                                 EFFECT_NAME_PENDING_BREAKING_FREE_CLEANSE, EFFECT_NAME_PENDING_BRUTAL_BLOW_CLEANSE,
                                 EFFECT_NAME_PENDING_SEAS_GRACE_PURIFY, EFFECT_NAME_PENDING_HEIMDALL_PURIFY] \
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
                                 EFFECT_NAME_PENDING_HEIMDALL_DISPEL,
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

        if effects_to_add_to_active:
            future_effects = list(self.active_effects) + effects_to_add_to_active
            snapshot_bonus = self._get_holy_blessed_damage_taken_bonus(future_effects)
            for effect in effects_to_add_to_active:
                if effect.effect_type == EffectType.DAMAGE_OVER_TIME:
                    effect.config["holy_blessed_damage_taken_snapshot"] = snapshot_bonus

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
                    if self.simulator and eff.source_skill_id:
                        source_army_name = eff.config.get("source_army_name")
                        source_army = None
                        if source_army_name == self.simulator.army1.name:
                            source_army = self.simulator.army1
                        elif source_army_name == self.simulator.army2.name:
                            source_army = self.simulator.army2
                        if source_army:
                            source_army.skill_rage_reduction_totals[eff.source_skill_id] = (
                                source_army.skill_rage_reduction_totals.get(eff.source_skill_id, 0.0)
                                + actual
                            )
                        self.simulator._log_skill_trigger(
                            self,
                            eff.name,
                            f"loses {actual:.0f} rage (delayed). New rage: {self.current_rage:.0f}",
                        )
                    elif eff.source_skill_id:
                        # If no simulator is present, fall back to tracking on self
                        self.skill_rage_reduction_totals[eff.source_skill_id] = (
                            self.skill_rage_reduction_totals.get(eff.source_skill_id, 0.0)
                            + actual
                        )
                to_remove.append(eff)
        for r in to_remove:
            if r in self.active_effects:
                self.active_effects.remove(r)

    def has_active_debuff(self, debuff_name: str) -> bool:
        for effect in self.active_effects:
            if effect.name == debuff_name:
                if effect.effect_type == EffectType.DEBUFF:
                    return True
                if effect.config.get("prevents_counterattack"):
                    return True
                if effect.config.get("prevents_basic_attack"):
                    return True
                if effect.config.get("prevents_rage_skill_cast"):
                    return True
                if (
                    effect.effect_type == EffectType.DAMAGE_OVER_TIME
                    and effect.config.get("dot_type") in [
                        DoTType.BLEED,
                        DoTType.POISON,
                        DoTType.BURN,
                        DoTType.LACERATE,
                    ]
                ):
                    return True
        return False

    def reset_for_new_battle(self):
        self.simulator = None
        self.simulators.clear()
        self._reload_gem_skills()
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
        self.army_round = 0

        self.damage_dealt_history = []
        self.heal_received_history = []
        self.shield_received_history = []
        self.rage_gained_history = []
        self.kills_dealt_history = []
        self.troop_count_history = [self.current_troop_count]
        self.unrevivable_history = [self.unrevivable_troops]
        self.troops_healed_total = 0.0
        self.shield_hp_gained_this_round = 0.0
        self.rage_added_this_round = 0.0
        self.kills_dealt_this_round = 0.0
        self.damage_contributors_this_round = {}
        self.damage_contributors_by_skill_this_round = {}
        self.heal_contributors_this_round = {}
        self.clear_dynamic_unrevivable_tracking()
        self.skill_kill_totals.clear()
        self.skill_heal_totals.clear()
        self.skill_shield_totals.clear()
        self.skill_rage_totals.clear()
        self.skill_damage_reduction_totals.clear()
        self.skill_rage_reduction_totals.clear()
        self.skill_kill_boost_totals.clear()
        self.skill_heal_boost_totals.clear()
        self.skill_shield_boost_totals.clear()
        self.skill_rage_boost_totals.clear()
        self.skill_damage_reduction_boost_totals.clear()
        self.skill_rage_reduction_boost_totals.clear()

        self._identify_hero_rage_skills()
        self._apply_bonus_stats()
        self._apply_gear_effects()

    def _apply_bonus_stats(self) -> None:
        if not self.bonus_stats_config:
            return

        def add_effect(
            magnitude: float,
            stat_type: StatType,
            name: str,
            *,
            filter_cfg: Optional[Dict[str, Any]] = None,
        ) -> None:
            if abs(magnitude) <= 1e-9:
                return
            config = {
                "stat_to_mod": stat_type,
                "is_dispellable": False,
                "manual_bonus_stat": True,
            }
            if filter_cfg:
                config["config_filter"] = filter_cfg
            effect = EffectInstance(
                uuid.uuid4(),
                "manual_bonus_stats",
                EffectType.STAT_MOD,
                -1,
                magnitude,
                config,
                name=f"Bonus Stat: {name}",
                applied_this_round=False,
            )
            self.active_effects.append(effect)

        cfg = self.bonus_stats_config
        damage_reduction = cfg.get("damage_reduction", {}) or {}
        add_effect(
            -float(damage_reduction.get("all", 0.0)),
            StatType.DAMAGE_TAKEN_MULTIPLIER,
            "Damage Reduction",
        )
        for troop in ("pikemen", "archers", "infantry"):
            val = -float(damage_reduction.get(f"vs_{troop}", 0.0))
            add_effect(
                val,
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                f"Damage Reduction vs {troop.title()}",
                filter_cfg={"attacker_unit_type": troop},
            )
        for label_key, label_name in (
            ("reactive", "Reactive"),
            ("cooperation", "Cooperation"),
            ("command", "Command"),
        ):
            val = -float(damage_reduction.get(label_key, 0.0))
            add_effect(
                val,
                StatType.DAMAGE_TAKEN_MULTIPLIER,
                f"Damage Reduction vs {label_name} Skills",
                filter_cfg={
                    "skill_label": label_name.upper(),
                    "attack_type": "SKILL",
                },
            )

        damage_boost = cfg.get("damage_boost", {}) or {}
        add_effect(
            float(damage_boost.get("all", 0.0)),
            StatType.GENERAL_DAMAGE_MODIFIER,
            "Damage Boost",
        )
        for troop in ("pikemen", "archers", "infantry"):
            val = float(damage_boost.get(f"vs_{troop}", 0.0))
            add_effect(
                val,
                StatType.GENERAL_DAMAGE_MODIFIER,
                f"Damage Boost vs {troop.title()}",
                filter_cfg={"target_unit_type": troop},
            )

        crit_entries = [
            (
                "reactive_crit_rate",
                StatType.REACTIVE_SKILL_CRIT_RATE,
                "Reactive Skill Critical Rate",
                "REACTIVE",
            ),
            (
                "cooperation_crit_rate",
                StatType.COOPERATION_SKILL_CRIT_RATE,
                "Cooperation Skill Critical Rate",
                "COOPERATION",
            ),
            (
                "command_crit_rate",
                StatType.COMMAND_SKILL_CRIT_RATE,
                "Command Skill Critical Rate",
                "COMMAND",
            ),
        ]
        for key, stat, label, skill_label in crit_entries:
            add_effect(
                float(damage_boost.get(key, 0.0)),
                stat,
                label,
                filter_cfg={
                    "skill_label": skill_label,
                    "attack_type": "SKILL",
                },
            )

        add_effect(
            float(cfg.get("shield_gain", 0.0)),
            StatType.SHIELD_STRENGTH_MODIFIER,
            "Shield Gain",
        )
        add_effect(
            float(cfg.get("burn_boost", 0.0)),
            StatType.BURN_DAMAGE_BOOST,
            "Burn Boost",
        )
        add_effect(
            float(cfg.get("poison_boost", 0.0)),
            StatType.POISON_DAMAGE_BOOST,
            "Poison Boost",
        )
        add_effect(
            float(cfg.get("lacerate_boost", 0.0)),
            StatType.LACERATE_DAMAGE_BOOST,
            "Lacerate Boost",
        )
        add_effect(
            float(cfg.get("basic_boost", 0.0)),
            StatType.BASIC_DAMAGE_ADJUST,
            "Basic Attack Boost",
        )
        add_effect(
            float(cfg.get("counter_boost", 0.0)),
            StatType.COUNTER_DAMAGE_ADJUST,
            "Counterattack Boost",
        )
        add_effect(
            float(cfg.get("reactive_skill_boost", 0.0)),
            StatType.REACTIVE_SKILL_DAMAGE_ADJUST,
            "Reactive Skill Damage Boost",
        )
        add_effect(
            float(cfg.get("rage_skill_boost", 0.0)),
            StatType.RAGE_SKILL_DAMAGE_MODIFIER,
            "Rage Skill Damage Boost",
        )
        add_effect(
            float(cfg.get("cooperation_skill_boost", 0.0)),
            StatType.COOPERATION_SKILL_DAMAGE_MODIFIER,
            "Cooperation Skill Damage Boost",
        )
        add_effect(
            float(cfg.get("command_skill_boost", 0.0)),
            StatType.COMMAND_SKILL_DAMAGE_MODIFIER,
            "Command Skill Damage Boost",
        )

    def _apply_gear_effects(self) -> None:
        if not self.heroes:
            return

        for hero in self.heroes:
            if not hero or not getattr(hero, "gear_items", None):
                continue
            for gear_def in hero.gear_items.values():
                for gear_effect in gear_def.effects:
                    magnitude = float(gear_effect.magnitude)
                    if abs(magnitude) <= 1e-9:
                        continue
                    effect = EffectInstance(
                        uuid.uuid4(),
                        f"gear::{gear_def.id}",
                        EffectType.STAT_MOD,
                        -1,
                        magnitude,
                        {
                            "stat_to_mod": gear_effect.stat,
                            "is_dispellable": False,
                            "manual_bonus_stat": True,
                            "gear_id": gear_def.id,
                            "gear_name": gear_def.name,
                            "gear_rarity": gear_def.rarity,
                            "gear_slot": gear_def.slot,
                            "gear_owner": hero.name,
                        },
                        name=f"{gear_def.name} ({gear_def.rarity}) [{hero.name}]",
                        applied_this_round=False,
                    )
                    self.active_effects.append(effect)

    def __repr__(self):
        hero_names = [h.name for h in self.heroes if h] if self.heroes else []
        return (
            f"Army(Name: {self.name}, Unit: {self.unit.unit_type} T{self.unit.tier}, Troops: {self.current_troop_count:.0f}/{self.unit.initial_count} "
            f"(Unrev: {round(self.unrevivable_troops)}), Rage: {self.current_rage:.0f}, Rally: {self.is_rally}, Heroes: {hero_names}, Active Effects: {len(self.active_effects)})")

