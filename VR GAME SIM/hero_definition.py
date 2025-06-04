"""
Defines the Hero class and hero presets.
"""
from typing import List, Dict, Optional
from skill_system import SkillDefinition

_SKILL_REGISTRY_TYPE_HINT: Dict[str, SkillDefinition] = {}


class Hero:
    def __init__(self, name: str, talent_ids: List[str], base_skill_ids: List[str],
                 plugin_skill_ids: List[str], skill_registry: Dict[str, SkillDefinition]):
        if len(talent_ids) != 3:
            if len(talent_ids) < 3:
                talent_ids.extend(["dummy_talent_empty"] * (3 - len(talent_ids)))
            else:
                raise ValueError(f"Hero {name} must have exactly 3 talent slots. Got {len(talent_ids)}: {talent_ids}")

        if len(base_skill_ids) > 2:
            raise ValueError(f"Hero {name} base skills limited to a maximum of 2. Got {len(base_skill_ids)}")
        if len(plugin_skill_ids) > 2:
            raise ValueError(f"Hero {name} plugin skills limited to a maximum of 2. Got {len(plugin_skill_ids)}")

        self.name: str = name
        self.talent_ids: List[str] = talent_ids
        self.base_skill_ids: List[str] = base_skill_ids
        self.plugin_skill_ids: List[str] = plugin_skill_ids
        self.skills: List[SkillDefinition] = []

        for skill_id_list in [talent_ids, base_skill_ids, plugin_skill_ids]:
            for skill_id in skill_id_list:
                if skill_id and skill_id.lower() not in ["", "none", "blank"]:
                    if skill_id in skill_registry:
                        self.skills.append(skill_registry[skill_id])
                    else:
                        if skill_id != "dummy_talent_empty":
                            print(f"Warning: Skill ID '{skill_id}' for hero '{name}' not found in SKILL_REGISTRY.")
                        elif "dummy_talent_empty" in skill_registry :
                             self.skills.append(skill_registry["dummy_talent_empty"])


    def __repr__(self):
        skill_names = [s['name'] for s in self.skills if s['id'] != "dummy_talent_empty"]
        return f"Hero(Name: {self.name}, Skills: {skill_names if skill_names else 'None'})"

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
}
