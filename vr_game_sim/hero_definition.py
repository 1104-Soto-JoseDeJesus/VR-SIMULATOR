"""
Defines the Hero class and hero presets.
"""
from dataclasses import dataclass, field, InitVar
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import copy

from .gear_definitions import (
    VALID_GEAR_SLOTS,
    normalize_gear_slot,
    resolve_gear,
)
from .skill_system import SkillDefinition

if TYPE_CHECKING:
    from .gear_definitions import GearDefinition

_SKILL_REGISTRY_TYPE_HINT: Dict[str, SkillDefinition] = {}


@dataclass(slots=True)
class Hero:
    name: str
    talent_ids: List[str]
    base_skill_ids: List[str]
    plugin_skill_ids: List[str]
    skill_registry: InitVar[Dict[str, SkillDefinition]]
    gear_config: InitVar[Dict[str, Any] | None] = None
    mount_skill_ids: List[str] = field(default_factory=list)
    skills: List[SkillDefinition] = field(init=False, default_factory=list)
    gear_ids: Dict[str, str] = field(init=False, default_factory=dict)
    gear_items: Dict[str, "GearDefinition"] = field(init=False, default_factory=dict)

    def __post_init__(
        self,
        skill_registry: Dict[str, SkillDefinition] | None,
        gear_config: Dict[str, Any] | None,
    ):
        if skill_registry is None:
            skill_registry = {}
        if self.mount_skill_ids is None:
            self.mount_skill_ids = []
        elif isinstance(self.mount_skill_ids, (tuple, set)):
            self.mount_skill_ids = list(self.mount_skill_ids)
        elif not isinstance(self.mount_skill_ids, list):
            self.mount_skill_ids = [str(self.mount_skill_ids)]
        if len(self.talent_ids) != 3:
            if len(self.talent_ids) < 3:
                self.talent_ids.extend(["dummy_talent_empty"] * (3 - len(self.talent_ids)))
            else:
                raise ValueError(f"Hero {self.name} must have exactly 3 talent slots. Got {len(self.talent_ids)}: {self.talent_ids}")

        if len(self.base_skill_ids) > 2:
            raise ValueError(f"Hero {self.name} base skills limited to a maximum of 2. Got {len(self.base_skill_ids)}")
        if len(self.plugin_skill_ids) > 2:
            raise ValueError(f"Hero {self.name} plugin skills limited to a maximum of 2. Got {len(self.plugin_skill_ids)}")
        if len(self.mount_skill_ids) > 2:
            raise ValueError(f"Hero {self.name} mount skills limited to a maximum of 2. Got {len(self.mount_skill_ids)}")

        for skill_id_list in [self.talent_ids, self.base_skill_ids, self.plugin_skill_ids]:
            for skill_id in skill_id_list:
                if skill_id and skill_id.lower() not in ["", "none", "blank"]:
                    if skill_id in skill_registry:
                        self.skills.append(copy.deepcopy(skill_registry[skill_id]))
                    else:
                        if skill_id != "dummy_talent_empty":
                            print(f"Warning: Skill ID '{skill_id}' for hero '{self.name}' not found in SKILL_REGISTRY.")
                        elif "dummy_talent_empty" in skill_registry:
                            self.skills.append(copy.deepcopy(skill_registry["dummy_talent_empty"]))

        normalized_mount_ids = [
            skill_id
            for skill_id in self.mount_skill_ids
            if skill_id and str(skill_id).lower() not in ["", "none", "blank"]
        ]
        has_duplicate_mounts = len(set(normalized_mount_ids)) != len(normalized_mount_ids)
        for mount_index, skill_id in enumerate(self.mount_skill_ids):
            if skill_id and str(skill_id).lower() not in ["", "none", "blank"]:
                if skill_id in skill_registry:
                    mount_skill_def = copy.deepcopy(skill_registry[skill_id])
                    if has_duplicate_mounts:
                        mount_skill_def["mount_instance_index"] = mount_index
                    self.skills.append(mount_skill_def)
                else:
                    print(f"Warning: Skill ID '{skill_id}' for hero '{self.name}' not found in SKILL_REGISTRY.")

        self.gear_ids = {}
        self.gear_items = {}
        raw_gear_config: Dict[str, Any] = {}
        if isinstance(gear_config, dict):
            raw_gear_config = gear_config
        elif gear_config is not None:
            print(f"Warning: Gear configuration for hero '{self.name}' must be a mapping. Got {type(gear_config).__name__}.")

        for slot_key, raw_value in raw_gear_config.items():
            slot = normalize_gear_slot(slot_key)
            if not slot or slot not in VALID_GEAR_SLOTS:
                print(
                    f"Warning: Unknown gear slot '{slot_key}' for hero '{self.name}'. Expected one of {sorted(VALID_GEAR_SLOTS)}."
                )
                continue
            gear_def = resolve_gear(raw_value)
            if not gear_def:
                if raw_value not in (None, ""):
                    print(
                        f"Warning: Gear '{raw_value}' for hero '{self.name}' could not be resolved."
                    )
                continue
            if gear_def.slot != slot:
                print(
                    f"Warning: Gear '{gear_def.name} ({gear_def.rarity})' assigned to '{slot_key}' on hero '{self.name}' but is a '{gear_def.slot}' item."
                )
            self.gear_ids[slot] = gear_def.id
            self.gear_items[slot] = gear_def


    def __repr__(self):
        skill_names = [s['name'] for s in self.skills if s['id'] != "dummy_talent_empty"]
        gear_names = [f"{gear.name} ({gear.rarity})" for gear in self.gear_items.values()]
        return (
            f"Hero(Name: {self.name}, Skills: {skill_names if skill_names else 'None'}, "
            f"Gear: {gear_names if gear_names else 'None'})"
        )

HERO_PRESETS: Dict[str, Dict[str, List[str]]] = {
    'leif': {
        'talents': ["talent_blade_counter", "talent_shield_of_resistance", "talent_revenge_echo"],
        'base_skills': ["base_skill_planned_attack", "base_skill_sharp_pursuit"],
        'plugin_skills': [],
    },
    'laird': {
        'talents': ["talent_holy_shield", "talent_sacred_counter", "talent_divine_resistance"],
        'base_skills': ["base_skill_flame_guardian", "base_skill_sacred_blade"],
        'plugin_skills': [],
    },
    'yvette': {
        'talents': ["talent_healing_chords", "talent_healing_hymn", "talent_horn_of_countering"],
        'base_skills': ["base_skill_sanctity_of_life", "base_skill_vital_blessing"],
        'plugin_skills': [],
    },
    'heahmund': {
        'talents': ["talent_hold_fast", "talent_tit_for_tat", "talent_determined_defense"],
        'base_skills': ["base_skill_zeal", "base_skill_vanquishing_blade"],
        'plugin_skills': [],
    },
    'sigurd': {
        'talents': ["talent_fiery_snake_spirit", "talent_serpents_rage", "talent_full_focus"],
        'base_skills': ["base_skill_snake_eyes", "base_skill_snakes_frenzy"],
        'plugin_skills': [],
    },
    'wooder': {
        'talents': ["talent_massive_shield", "talent_bold_charge", "talent_specialized_attack"],
        'base_skills': ["base_skill_ready_to_pounce", "base_skill_paralyzing_terror"],
        'plugin_skills': [],
    },
    'ivana': {
        'talents': ["talent_power_of_silence", "talent_combat_focus", "talent_time_crunch"],
        'base_skills': ["base_skill_threatening_blade", "base_skill_intimidation"],
        'plugin_skills': [],
    },
    'ragnar': {
        'talents': ["talent_dragons_blood", "talent_deadly_raid", "talent_born_king"],
        'base_skills': ["base_skill_unyielding_will", "base_skill_viking_sage"],
        'plugin_skills': [],
    },
    'athelstan': {
        'talents': ["talent_erudite", "talent_strategize", "talent_adaptable_to_changes"],
        'base_skills': ["base_skill_heart_of_tolerance", "base_skill_holy_enlightenment"],
        'plugin_skills': [],
    },
    'verdandi': {
        'talents': ["talent_hunting_instinct", "talent_hunting_experience", "talent_targeted_strike"],
        'base_skills': ["base_skill_rapid_fire", "base_skill_raining_arrows"],
        'plugin_skills': [],
    },
    # NEW HERO: Olena
    'olena': {
        'talents': ["talent_scorching_arrow", "talent_multi_shot_arrow", "talent_poised_shot"],
        'base_skills': ["base_skill_enchanted_arrow", "base_skill_concentration"],
        'plugin_skills': [], # No plugin skills specified
    },
    'artur': {
        'talents': ["talent_hellfire_shelter", "talent_pent_up_anger", "talent_furious_fire"],
        'base_skills': ["base_skill_torment", "base_skill_incineration"],
        'plugin_skills': [],
    },
    'freydis': {
        'talents': ["talent_heroic_blessing", "talent_battle_chime", "talent_flames_judgment"],
        'base_skills': ["base_skill_blades_judgment", "base_skill_desperate_strike"],
        'plugin_skills': [],
    },
    'gregory': {
        'talents': ["talent_great_morale", "talent_missing_beat", "talent_excite"],
        'base_skills': ["base_skill_drumming_disturbance", "base_skill_inspiring_dance"],
        'plugin_skills': [],
    },
    'jens': {
        'talents': ["talent_godly_wrath", "talent_divine_blite", "talent_divine_punishment"],
        'base_skills': ["base_skill_divine_energize", "base_skill_heavenly_descent"],
        'plugin_skills': [],
    },
    'rollo': {
        'talents': ["talent_patient_waiting", "talent_revolutionary_resolve", "talent_adaptable_agility"],
        'base_skills': ["base_skill_tough_choice", "base_skill_bloody_pillage"],
        'plugin_skills': [],
    },
    'harald': {
        'talents': ["talent_battle_preparation", "talent_coordinated_strike", "talent_slow_strike"],
        'base_skills': ["base_skill_fleet_raider", "base_skill_raging_smash"],
        'plugin_skills': [],
    },
    'bjorn': {
        'talents': ["talent_trained_up", "talent_undefeated", "talent_fatal_bleeding"],
        'base_skills': ["base_skill_crippling_pursuit", "base_skill_lethal_fracture"],
        'plugin_skills': [],
    },
    'naya': {
        'talents': ["talent_forceful_ambush", "talent_trapped_beasts_struggle", "talent_bear_spirit_protection"],
        'base_skills': ["base_skill_nayas_hunting_instinct", "base_skill_blizzard_spear"],
        'plugin_skills': [],
    },
    'rolfe': {
        'talents': ["talent_assassination_raid", "talent_scale_armor_shield", "talent_feigned_death_strike"],
        'base_skills': ["base_skill_inspiration_arrives", "base_skill_indomitable_spirit"],
        'plugin_skills': [],
    },
    'hobert': {
        'talents': ["talent_bold_shieldaxe", "talent_fearless_pursuit", "talent_steadfast_armor"],
        'base_skills': ["base_skill_berserk_fury", "base_skill_brutal_blow"],
        'plugin_skills': [],
    },
    'helgar': {
        'talents': ["talent_saintly_guardian", "talent_war_blessing", "talent_judgement_mark"],
        'base_skills': ["base_skill_judgements_fury", "rage_skill_ruling_trial"],
        'plugin_skills': [],
    },
    'lagertha': {
        'talents': ["talent_shieldaxe_attack", "talent_chiefs_might", "talent_fatal_strike"],
        'base_skills': ["base_skill_shield_breaker", "rage_skill_showdown"],
        'plugin_skills': [],
    },
    'leandra': {
        'talents': ["talent_soul_awakening", "talent_flexible_strike", "talent_opportune_strike"],
        'base_skills': ["base_skill_vengeful_fury", "base_skill_serrated_flourish"],
        'plugin_skills': [],
    },
    'margit': {
        'talents': ["talent_cutting_blade", "talent_thirst_for_blood", "talent_seas_grace"],
        'base_skills': ["base_skill_ride_the_waves", "base_skill_raging_tide"],
        'plugin_skills': [],
    },
    'yulmi': {
        'talents': ["talent_dreadful_curse", "talent_high_fighting_spirit", "talent_low_whispers"],
        'base_skills': ["base_skill_plague", "rage_skill_undead_harvest"],
        'plugin_skills': [],
    },
    'rosky': {
        'talents': ["talent_blade_wielder", "talent_maniacal", "talent_pirate_tricks"],
        'base_skills': ["base_skill_flurry", "rage_skill_spirit_battleship"],
        'plugin_skills': [],
    },
    'ivor': {
        'talents': ["talent_tactical_rules", "talent_specter_lycan_assault", "talent_amazing_attack"],
        'base_skills': ["base_skill_throwing_axe", "rage_skill_all_kill"],
        'plugin_skills': [],
    },
    'alf': {
        'talents': ["talent_fiery_poison_bullet", "talent_fiery_poison_bomb", "talent_agile_missile"],
        'base_skills': ["base_skill_huginns_slingshot", "base_skill_chain_meteor"],
        'plugin_skills': [],
    },
    'sasha': {
        'talents': ["talent_forest_force", "talent_natures_killer", "talent_life_cycle"],
        'base_skills': ["base_skill_nature_blessing", "base_skill_floral_burial"],
        'plugin_skills': [],
    },
    'greta': {
        'talents': ["talent_shattered_edge", "talent_oathbreakers_blade", "talent_exiled_bloodblade"],
        'base_skills': ["base_skill_broken_blade_charge", "rage_skill_time_of_severance"],
        'plugin_skills': [],
    },
    'sigrid': {
        'talents': ["talent_northern_blood_feast", "talent_cold_iron_oath", "talent_royal_authority"],
        'base_skills': ["base_skill_winters_coronation", "rage_skill_triumphant_presence"],
        'plugin_skills': [],
    },
    'vali': {
        'talents': ["talent_icy_edge", "talent_ice_cleave", "talent_an_eye_for_an_eye"],
        'base_skills': ["base_skill_curse_of_the_frost", "rage_skill_frostblade"],
        'plugin_skills': [],
    },
    'sephina': {
        'talents': ["talent_raven_feather_blade", "talent_death_ravens_shadow", "talent_ominous_raven_feather"],
        'base_skills': ["base_skill_darkmoon_elegy", "rage_skill_moonlit_strike"],
        'plugin_skills': [],
    },
}
