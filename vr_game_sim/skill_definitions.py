# === File: skill_definitions.py ===
from typing import Dict
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
    handle_base_skill_plague
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
    handle_plugin_rapid_attack, handle_plugin_blessed_by_fate,
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
    handle_rage_undead_harvest
)
from .skill_logic.utility_skill_handlers import (
    handle_generic_single_damage_skill,
    handle_generic_heal_skill,
)

SKILL_REGISTRY_GLOBAL: Dict[str, SkillDefinition] = {
    # --- Talent Skills ---
    # ... (All existing talents for Leif, Laird, Yvette, Heahmund, Sigurd, Wooder, Ivana, Ragnar, Athelstan, Verdandi) ...
    "talent_blade_counter": {
        "id": "talent_blade_counter", "name": "Blade Counter", "type": SkillType.TALENT,
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
        "id": "talent_shield_of_resistance", "name": "Shield of Resistance", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_talent_shield_of_resistance,
        "effects_to_apply": [{"effect_type": EffectType.SHIELD, "name": EFFECT_NAME_SHIELD_OF_RESISTANCE,
                              "duration": 1, "magnitude_calc_type": "dynamic_shield_resistance_v1",
                              "shield_factor": 950.0, "activate_next_round": True}]
    },
    "talent_revenge_echo": {
        "id": "talent_revenge_echo", "name": "Revenge Echo", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.25, "target": "SELF",
        "logic_handler": handle_talent_revenge_echo,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 550.0, "conditional_buff": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_REVENGE_ECHO_COUNTER_BOOST,
            "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": 0.30, "duration": 1,
            "activate_next_round": True}}
    },
    "talent_holy_shield": {
        "id": "talent_holy_shield", "name": "Holy Shield", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_HOLY_SHIELD_BOOST,
                              "stat_to_mod": StatType.SHIELD_STRENGTH_MODIFIER, "magnitude": 0.25, "duration": -1}]
    },
    "talent_sacred_counter": {
        "id": "talent_sacred_counter", "name": "Sacred Counter", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 600.0}
    },
    "talent_divine_resistance": {
        "id": "talent_divine_resistance", "name": "Divine Resistance", "type": SkillType.TALENT,
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
        "id": "talent_healing_chords", "name": "Healing Chords", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_HEALING_CHORDS_BOOST,
                              "stat_to_mod": StatType.HEAL_ADJUSTMENT, "magnitude": 0.20, "duration": -1}]
    },
    "talent_healing_hymn": {
        "id": "talent_healing_hymn", "name": "Healing Hymn", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.25, "target": "ENEMY",
        "logic_handler": handle_talent_healing_hymn,
        "config": {"damage_factor": 800.0}
    },
    "talent_horn_of_countering": {
        "id": "talent_horn_of_countering", "name": "Horn of Countering", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 900.0}
    },
    "talent_hold_fast": {
        "id": "talent_hold_fast", "name": "Hold Fast", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.15, "target": "SELF",
        "logic_handler": handle_talent_hold_fast,
        "config": {"shield_factor": 600.0, "shield_duration": 1,
                   "cooldown_rounds": 4, "effect_name": EFFECT_NAME_HOLD_FAST_SHIELD}
    },
    "talent_determined_defense": {
        "id": "talent_determined_defense", "name": "Determined Defense", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_talent_determined_defense,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 300.0, "heal_factor": 300.0, "debuff_duration": 0,
                   "debuff_name": EFFECT_NAME_DETERMINED_DEFENSE_BROKEN_BLADE, "cooldown_rounds": 3}
    },
    "talent_tit_for_tat": {
        "id": "talent_tit_for_tat", "name": "Tit for Tat", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_tit_for_tat,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 500.0, "reduction_magnitude": -0.30, "reduction_duration": 0,
                   "reduction_effect_name": EFFECT_NAME_TIT_FOR_TAT_DMG_RED}
    },
    "talent_fiery_snake_spirit": {
        "id": "talent_fiery_snake_spirit", "name": "Fiery Snake Spirit", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_FIERY_SNAKE_SPIRIT_H1_BOOST,
            "stat_to_mod": StatType.HERO1_RAGE_SKILL_DAMAGE_MODIFIER, "magnitude": 0.30,
            "duration": -1, "activate_next_round": False}]
    },
    "talent_serpents_rage": {
        "id": "talent_serpents_rage", "name": "Serpent's Rage", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 900.0, "trigger_interval": 9}
    },
    "talent_full_focus": {
        "id": "talent_full_focus", "name": "Full Focus", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.35, "target": "ENEMY",
        "logic_handler": handle_talent_full_focus,
        "config": {"damage_factor": 700.0}
    },
    "talent_massive_shield": {
        "id": "talent_massive_shield", "name": "Massive Shield", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_MASSIVE_SHIELD_BOOST,
                              "stat_to_mod": StatType.SHIELD_STRENGTH_MODIFIER, "magnitude": 0.15,
                              "duration": -1, "activate_next_round": False}]
    },
    "talent_bold_charge": {
        "id": "talent_bold_charge", "name": "Bold Charge", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 250.0}
    },
    "talent_specialized_attack": {
        "id": "talent_specialized_attack", "name": "Specialized Attack", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 0.50, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 1250.0}
    },
    "talent_power_of_silence": {
        "id": "talent_power_of_silence", "name": "Power of Silence", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 0.50, "target": "ENEMY",
        "logic_handler": handle_talent_power_of_silence,
        "config": {"rage_reduction": 125}
    },
    "talent_combat_focus": {
        "id": "talent_combat_focus", "name": "Combat Focus", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1000.0, "trigger_interval": 9}
    },
    "talent_time_crunch": {
        "id": "talent_time_crunch", "name": "Time Crunch", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "config": {"damage_factor": 1.0, "trigger_interval": 9}
    },
    "talent_dragons_blood": {
        "id": "talent_dragons_blood", "name": "Dragon's Blood", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "config": {"damage_factor": 2.0, "trigger_interval": 9}
    },
    "talent_deadly_raid": {
        "id": "talent_deadly_raid", "name": "Deadly Raid", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 0.25, "target": "ENEMY",
        "logic_handler": handle_talent_deadly_raid,
        "config": {"damage_factor": 600.0}
    },
    "talent_born_king": {
        "id": "talent_born_king", "name": "Born King", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "config": {"damage_factor": 3.0, "trigger_interval": 9}
    },
    "talent_erudite": {
        "id": "talent_erudite", "name": "Erudite", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_ERUDITE_BURN_BOOST,
             "stat_to_mod": StatType.BURN_DAMAGE_BOOST, "magnitude": 0.15, "duration": -1},
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_ERUDITE_POISON_BOOST,
             "stat_to_mod": StatType.POISON_DAMAGE_BOOST, "magnitude": 0.10, "duration": -1}
        ]
    },
    "talent_strategize": {
        "id": "talent_strategize", "name": "Strategize", "type": SkillType.TALENT,
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
        "id": "talent_adaptable_to_changes", "name": "Adaptable to Changes", "type": SkillType.TALENT,
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
        "id": "talent_hunting_instinct", "name": "Hunting Instinct", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_HUNTING_INSTINCT_BURN_BOOST,
             "stat_to_mod": StatType.BURN_DAMAGE_BOOST, "magnitude": 0.18, "duration": -1}
        ]
    },
    "talent_hunting_experience": {
        "id": "talent_hunting_experience", "name": "Hunting Experience", "type": SkillType.TALENT,
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
        "id": "talent_targeted_strike", "name": "Targeted Strike", "type": SkillType.TALENT,
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
        "id": "talent_scorching_arrow", "name": "Scorching Arrow", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [
            {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SCORCHING_ARROW_BURN_BOOST,
             "stat_to_mod": StatType.BURN_DAMAGE_BOOST, "magnitude": 0.15, "duration": -1}
        ]
    },
    "talent_multi_shot_arrow": {
        "id": "talent_multi_shot_arrow", "name": "Multi-Shot Arrow", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 0.50, "target": "ENEMY",
        "logic_handler": handle_talent_multi_shot_arrow, # Uses generic damage, but specific handler for clarity
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 750.0}
    },
    "talent_poised_shot": {
        "id": "talent_poised_shot", "name": "Poised Shot", "type": SkillType.TALENT,
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
        "id": "talent_hellfire_shelter", "name": "Hellfire Shelter", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_HELLFIRE_SHELTER_COUNTER_REDUCTION,
            "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": -0.40, "duration": -1
        }]
    },
    "talent_pent_up_anger": {
        "id": "talent_pent_up_anger", "name": "Pent-Up Anger", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_pent_up_anger,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "rage_gain": 300}
    },
    "talent_furious_fire": {
        "id": "talent_furious_fire", "name": "Furious Fire", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_serpents_rage,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1100.0, "trigger_interval": 6}
    },
    "talent_heroic_blessing": {
        "id": "talent_heroic_blessing", "name": "Heroic Blessing", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": handle_talent_heroic_blessing,
        "config": {"debuff_duration": 29, "burn_boost_magnitude": 0.15}
    },
    "talent_battle_chime": {
        "id": "talent_battle_chime", "name": "Battle Chime", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_battle_chime,
        "config": {"trigger_interval": 9, "damage_factor": 800.0, "rage_gain_if_lower": 50}
    },
    "talent_flames_judgment": {
        "id": "talent_flames_judgment", "name": "Flame's Judgment", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_OWN_COMMAND_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_flames_judgment,
        "config": {"damage_factor": 1000.0, "damage_chance": 0.30}
    },
    # --- Gregory Talents ---
    "talent_great_morale": {
        "id": "talent_great_morale", "name": "Great Morale", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_GREAT_MORALE_BUFF,
                               "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": 0.30,
                               "duration": -1, "activate_next_round": False}]
    },
    "talent_missing_beat": {
        "id": "talent_missing_beat", "name": "Missing Beat", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_talent_missing_beat,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 400.0, "slow_chance": 0.25, "slow_duration": 1}
    },
    "talent_excite": {
        "id": "talent_excite", "name": "Excite", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 0.40, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 1800.0}
    },
    # --- Jens Talents ---
    "talent_godly_wrath": {
        "id": "talent_godly_wrath", "name": "Godly Wrath", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_godly_wrath,
        "config": {"duration": 29, "magnitude": 0.06}
    },
    "talent_divine_blite": {
        "id": "talent_divine_blite", "name": "Divine Blite", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_generic_heal_skill,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"heal_factor": 450.0}
    },
    "talent_divine_punishment": {
        "id": "talent_divine_punishment", "name": "Divine Punishment", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_divine_punishment,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 0.20, "damage_factor": 500.0}
    },

    # --- Base Skills ---
    # ... (All existing base skills for other heroes) ...
    "base_skill_snake_eyes": {
        "id": "base_skill_snake_eyes", "name": "Snake Eyes", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_snake_eyes,
        "config": { "damage_chance": 0.25, "damage_factor": 500.0, "debuff_chance": 0.20, "debuff_duration": 1 }
    },
    "base_skill_snakes_frenzy": {
        "id": "base_skill_snakes_frenzy", "name": "Snake's Frenzy", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_snakes_frenzy,
        "config": {"damage_factor": 1600.0, "buff_magnitude": 0.15, "buff_duration": 1}
    },
    "base_skill_ready_to_pounce": {
        "id": "base_skill_ready_to_pounce", "name": "Ready to Pounce", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_ready_to_pounce,
        "config": {"buff_magnitude": 1.0, "buff_duration": 1}
    },
    "base_skill_paralyzing_terror": {
        "id": "base_skill_paralyzing_terror", "name": "Paralyzing Terror", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_paralyzing_terror,
        "config": {"damage_factor": 450.0, "shield_factor": 700.0, "shield_duration": 2}
    },
    "base_skill_threatening_blade": {
        "id": "base_skill_threatening_blade", "name": "Threatening Blade", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.30, "target": "ENEMY",
        "logic_handler": handle_base_skill_threatening_blade,
        "config": {"damage_factor": 600.0, "defense_buff_magnitude": 0.30, "defense_buff_duration": 4}
    },
    "base_skill_intimidation": {
        "id": "base_skill_intimidation", "name": "Intimidation", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_intimidation,
        "config": {"damage_factor_hit1": 300.0, "damage_factor_hit2": 600.0,
                   "rage_reduction": 50, "silence_chance": 0.50, "silence_duration": 1}
    },
    "base_skill_unyielding_will": {
        "id": "base_skill_unyielding_will", "name": "Unyielding Will", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_unyielding_will,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"h2_rage_buff_magnitude": 0.20, "h2_rage_buff_duration": 2,
                   "heal_chance": 0.15, "heal_factor": 800.0}
    },
    "base_skill_viking_sage": {
        "id": "base_skill_viking_sage", "name": "Viking Sage", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_viking_sage,
        "config": {"damage_factor": 1400.0, "atk_reduction_magnitude": -0.20, "atk_reduction_duration": 3}
    },
    "base_skill_sharp_pursuit": {
        "id": "base_skill_sharp_pursuit", "name": "Sharp Pursuit", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_sharp_pursuit,
        "config": {"damage_factor": 1500.0, "shield_factor": 600.0, "self_shield_duration": 1, "effect_name": EFFECT_NAME_SHARP_PURSUIT_SHIELD}
    },
    "base_skill_planned_attack": {
        "id": "base_skill_planned_attack", "name": "Planned Attack", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.15, "target": "ENEMY",
        "logic_handler": handle_base_skill_planned_attack,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"hit1_damage_factor": 300.0, "hit2_damage_factor": 420.0}
    },
    "base_skill_flame_guardian": {
        "id": "base_skill_flame_guardian", "name": "Flame Guardian", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_flame_guardian,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 250.0, "shield_chance": 0.50, "shield_factor": 400.0,
                   "self_shield_duration": 1, "effect_name": EFFECT_NAME_FLAME_GUARDIAN_SHIELD}
    },
    "base_skill_sacred_blade": {
        "id": "base_skill_sacred_blade", "name": "Sacred Blade", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_sacred_blade,
        "config": {"damage_factor": 1400.0, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SACRED_BLADE_ATTACK_BOOST,
            "stat_to_mod": StatType.BASE_ATTACK_MULTIPLIER, "magnitude": 0.20, "duration": 2,
            "unit_type_condition": "pikemen", "activate_next_round": True}}
    },
    "base_skill_sanctity_of_life": {
        "id": "base_skill_sanctity_of_life", "name": "Sanctity of Life", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_sanctity_of_life,
        "config": {"heal_chance": 0.20, "heal_factor": 500.0, "buff_hero2_chance": 0.20,
                   "buff_details": {"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SANCTITY_H2_RAGE_BOOST,
                                    "stat_to_mod": StatType.HERO2_RAGE_SKILL_DAMAGE_MODIFIER,
                                    "magnitude": 0.20, "duration": 2, "activate_next_round": True}}
    },
    "base_skill_vital_blessing": {
        "id": "base_skill_vital_blessing", "name": "Vital Blessing", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "SELF",
        "logic_handler": handle_rage_vital_blessing,
        "config": {"heal_factor": 1250.0, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_VITAL_BLESSING_COUNTER_BOOST,
            "stat_to_mod": StatType.COUNTER_DAMAGE_ADJUST, "magnitude": 0.30, "duration": 4,
            "activate_next_round": True}}
    },
    "base_skill_zeal": {
        "id": "base_skill_zeal", "name": "Zeal", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_zeal,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 750.0, "damage_chance": 0.20,
                   "debuff_removal_chance": 0.20, "cooldown_rounds": 3}
    },
    "base_skill_vanquishing_blade": {
        "id": "base_skill_vanquishing_blade", "name": "Vanquishing Blade", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_vanquishing_blade,
        "config": {"damage_factor": 1700.0, "heal_factor": 400.0, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_VANQUISHING_BLADE_REDUCTION,
            "stat_to_mod": StatType.DAMAGE_TAKEN_MULTIPLIER, "magnitude": -0.10, "duration": 1,
            "activate_next_round": True}}
    },
    "base_skill_delayed_rage_example": {
        "id": "base_skill_delayed_rage_example", "name": "Delayed Fury Burst", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 0, "target": "ENEMY",
        "logic_handler": handle_generic_damage_rage_skill,
        "config": {"damage_factor": 1000.0}
    },
    "base_skill_heart_of_tolerance": {
        "id": "base_skill_heart_of_tolerance", "name": "Heart of Tolerance", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_holy_enlightenment", "name": "Holy Enlightenment", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_rapid_fire", "name": "Rapid Fire", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_raining_arrows", "name": "Raining Arrows", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_enchanted_arrow", "name": "Enchanted Arrow", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 0.35, "target": "ENEMY",
        "logic_handler": handle_base_skill_enchanted_arrow,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {
            "burn_factor": 600.0,
            "burn_duration": 1 # For 2 active rounds (applied next round)
        }
    },
    "base_skill_concentration": {
        "id": "base_skill_concentration", "name": "Concentration", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_torment", "name": "Torment", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_incineration", "name": "Incineration", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_blades_judgment", "name": "Blade's Judgment", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_desperate_strike", "name": "Desperate Strike", "type": SkillType.BASE_SKILL,
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
        "id": "base_skill_drumming_disturbance", "name": "Drumming Disturbance", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_base_skill_drumming_disturbance,
        "config": {"heal_factor": 250.0, "heal_duration": 1,
                   "rage_reduction_mag": -0.10, "rage_reduction_duration": 1}
    },
    "base_skill_inspiring_dance": {
        "id": "base_skill_inspiring_dance", "name": "Inspiring Dance", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_inspiring_dance,
        "config": {"bleed_factor": 400.0, "bleed_duration": 1}
    },
    # --- Jens Base Skills ---
    "base_skill_divine_energize": {
        "id": "base_skill_divine_energize", "name": "Divine Energize", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.25, "target": "ENEMY",
        "logic_handler": handle_base_skill_divine_energize,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 300.0, "vulnerability_magnitude": 0.20, "vulnerability_duration": 1}
    },
    "base_skill_heavenly_descent": {
        "id": "base_skill_heavenly_descent", "name": "Heavenly Descent", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_skill_heavenly_descent,
        "config": {"damage_factor": 825.0, "vulnerability_magnitude": 0.10, "vulnerability_duration": 3,
                   "bleed_factor": 0}
    },

    # --- Rollo Skills ---
    "talent_patient_waiting": {
        "id": "talent_patient_waiting", "name": "Patient and Waiting", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_patient_waiting,
        "config": {"duration": 29, "buff_magnitude": 0.20, "damage_chance": 0.50, "damage_factor": 500.0}
    },
    "talent_revolutionary_resolve": {
        "id": "talent_revolutionary_resolve", "name": "Revolutionary Resolve", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_revolutionary_resolve,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 0.40, "damage_factor": 1500.0, "slow_duration": 1}
    },
    "talent_adaptable_agility": {
        "id": "talent_adaptable_agility", "name": "Adaptable Agility", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_adaptable_agility,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance_high": 0.25, "damage_factor": 900.0, "heal_chance_low": 0.20, "heal_factor": 500.0}
    },
    "base_skill_tough_choice": {
        "id": "base_skill_tough_choice", "name": "Tough Choice", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_tough_choice,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"basic_buff": 0.30, "counter_debuff": -0.30, "heal_chance": 0.20, "heal_factor": 900.0}
    },
    "base_skill_bloody_pillage": {
        "id": "base_skill_bloody_pillage", "name": "Bloody Pillage", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_bloody_pillage,
        "config": {"damage_factor": 1500.0, "bleed_factor": 350.0, "bleed_duration": 1}
    },

    # --- Harald Skills ---
    "talent_battle_preparation": {
        "id": "talent_battle_preparation", "name": "Battle Preparation", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_battle_preparation,
        "config": {"duration": 29, "buff_magnitude": 0.45}
    },
    "talent_coordinated_strike": {
        "id": "talent_coordinated_strike", "name": "Coordinated Strike", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_talent_coordinated_strike,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 300.0, "buff_magnitude": 0.12, "buff_duration": 2, "damage_chance": 1.0}
    },
    "talent_slow_strike": {
        "id": "talent_slow_strike", "name": "Slow Strike", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_slow_strike,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"buff_magnitude": 0.50, "damage_chance": 0.30, "damage_factor": 600.0}
    },
    "base_skill_fleet_raider": {
        "id": "base_skill_fleet_raider", "name": "Fleet Raider", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_fleet_raider,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 1.0, "damage_factor": 300.0,
                   "buff_magnitude": 0.25, "buff_duration": 4}
    },
    "base_skill_raging_smash": {
        "id": "base_skill_raging_smash", "name": "Raging Smash", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_raging_smash,
        "config": {"damage_factor": 2000.0, "slow_duration": 3}
    },

    # --- Bjorn Skills ---
    "talent_trained_up": {
        "id": "talent_trained_up", "name": "Trained Up", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.25, "target": "ENEMY",
        "logic_handler": handle_talent_trained_up,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 300.0, "slow_chance": 0.30, "slow_duration": 1, "damage_chance": 1.0}
    },
    "talent_undefeated": {
        "id": "talent_undefeated", "name": "Undefeated", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_COORDINATED_STRIKE_BUFF,
                              "stat_to_mod": StatType.COOPERATION_SKILL_DAMAGE_MODIFIER, "magnitude": 0.15, "duration": -1}]
    },
    "talent_fatal_bleeding": {
        "id": "talent_fatal_bleeding", "name": "Fatal Bleeding", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_fatal_bleeding,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 6, "bleed_factor": 500.0, "bleed_duration": 1}
    },
    "base_skill_crippling_pursuit": {
        "id": "base_skill_crippling_pursuit", "name": "Crippling Pursuit", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_crippling_pursuit,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 1.0, "damage_factor": 500.0,
                   "extra_damage_factor": 250.0}
    },
    "base_skill_lethal_fracture": {
        "id": "base_skill_lethal_fracture", "name": "Lethal Fracture", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_lethal_fracture,
        "config": {"damage_factor": 2000.0, "slow_duration": 2, "attack_buff": 0.15, "attack_duration": 2}
    },

    # --- Hobert Skills ---
    "talent_bold_shieldaxe": {
        "id": "talent_bold_shieldaxe", "name": "Bold Shieldaxe", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_BOLD_SHIELDAXE_BUFF,
                              "stat_to_mod": StatType.BASIC_DAMAGE_ADJUST, "magnitude": 0.35, "duration": -1}]
    },
    "talent_fearless_pursuit": {
        "id": "talent_fearless_pursuit", "name": "Fearless Pursuit", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 350.0, "alt_damage_factor": 700.0}
    },
    "talent_steadfast_armor": {
        "id": "talent_steadfast_armor", "name": "Steadfast Armor", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.30, "target": "ENEMY",
        "logic_handler": handle_talent_steadfast_armor,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"reduction": -0.28, "duration": 0, "slow_duration": 1}
    },
    "base_skill_berserk_fury": {
        "id": "base_skill_berserk_fury", "name": "Berserk Fury", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_base_skill_berserk_fury,
        "config": {"loss_per_stack": 0.06, "basic_buff": 0.12, "rage_per_round": 3}
    },
    "base_skill_brutal_blow": {
        "id": "base_skill_brutal_blow", "name": "Brutal Blow", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_brutal_blow,
        "config": {"damage_factor": 1200.0, "shield_factor": 400.0, "shield_duration": 1,
                   "buff_removal_count": 2, "self_cleanse_count": 1}
    },

    # --- Helgar Skills ---
    "talent_saintly_guardian": {
        "id": "talent_saintly_guardian", "name": "Saintly Guardian", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": handle_talent_saintly_guardian,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SAINTLY_GUARDIAN_SHIELD_BOOST,
                              "stat_to_mod": StatType.SHIELD_STRENGTH_MODIFIER, "magnitude": 0.35, "duration": -1}]
    },
    "talent_war_blessing": {
        "id": "talent_war_blessing", "name": "War Blessing", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.50, "target": "SELF",
        "logic_handler": handle_talent_war_blessing,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"shield_factor": 500.0, "shield_duration": 1}
    },
    "talent_judgement_mark": {
        "id": "talent_judgement_mark", "name": "Judgement Mark", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.50, "target": "ENEMY",
        "logic_handler": handle_talent_judgement_mark,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 350.0}
    },
    "base_skill_judgements_fury": {
        "id": "base_skill_judgements_fury", "name": "Judgement's Fury", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_judgements_fury,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 1150.0, "marker_threshold": 20, "counter_buff": 0.45, "buff_duration": 1}
    },
    "rage_skill_ruling_trial": {
        "id": "rage_skill_ruling_trial", "name": "Ruling Trial", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_ruling_trial,
        "config": {"damage_factor": 1000.0, "low_hp_damage_factor": 1500.0, "extra_damage_factor": 800.0, "hp_threshold": 0.20}
    },

    # --- Lagertha Skills ---
    "talent_shieldaxe_attack": {
        "id": "talent_shieldaxe_attack", "name": "Shieldaxe Attack", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_SHIELDAXE_ATTACK_BLEED_BOOST,
                               "stat_to_mod": StatType.BLEED_DAMAGE_BOOST, "magnitude": 0.25, "duration": -1}]
    },
    "talent_chiefs_might": {
        "id": "talent_chiefs_might", "name": "Chief's Might", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_talent_chiefs_might,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"bleed_factor": 400.0, "bleed_duration": 1}
    },
    "talent_fatal_strike": {
        "id": "talent_fatal_strike", "name": "Fatal Strike", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_fatal_strike,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_chance": 0.50, "damage_factor": 1000.0}
    },
    "base_skill_shield_breaker": {
        "id": "base_skill_shield_breaker", "name": "Shield Breaker", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_base_skill_shield_breaker,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 550.0, "buff_magnitude": 0.50, "buff_duration": 1}
    },
    "rage_skill_showdown": {
        "id": "rage_skill_showdown", "name": "Showdown", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_showdown,
        "config": {"damage_factor": 1500.0, "bleed_factor": 150.0, "bleed_duration": 2,
                   "shield_factor": 800.0, "shield_duration": 2}
    },

    # --- Yulmi Skills ---
    "talent_dreadful_curse": {
        "id": "talent_dreadful_curse", "name": "Dreadful Curse", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF", "logic_handler": None,
        "effects_to_apply": [{"effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_DREADFUL_CURSE_POISON_BOOST,
                               "stat_to_mod": StatType.POISON_DAMAGE_BOOST, "magnitude": 0.25, "duration": -1}]
    },
    "talent_high_fighting_spirit": {
        "id": "talent_high_fighting_spirit", "name": "High Fighting Spirit", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_talent_high_fighting_spirit,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1300.0, "trigger_interval": 9,
                   "buff_magnitude": 0.20, "buff_duration": 4}
    },
    "talent_low_whispers": {
        "id": "talent_low_whispers", "name": "Low Whispers", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_talent_low_whispers,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 6, "reduction": -0.30, "duration": 1, "rage_gain": 180}
    },
    "base_skill_plague": {
        "id": "base_skill_plague", "name": "Plague", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_base_skill_plague,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "poison_factor": 500.0, "poison_duration": 2,
                   "damage_taken_debuff": 0.20, "debuff_duration": 2}
    },
    "rage_skill_undead_harvest": {
        "id": "rage_skill_undead_harvest", "name": "Undead Harvest", "type": SkillType.BASE_SKILL,
        "trigger": SkillTriggerType.RAGE_SKILL, "rage_cost": 1000, "target": "ENEMY",
        "logic_handler": handle_rage_undead_harvest,
        "config": {"damage_factor": 1800.0, "debuff_magnitude": -0.10, "debuff_duration": 1}
    },


    # --- Plugin Skills ---
    # ... (All existing plugin skills) ...
    "plugin_silencer": {
        "id": "plugin_silencer", "name": "Silencer", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_silencer,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 450.0, "silence_duration": 1}
    },
    "plugin_enrage": {
        "id": "plugin_enrage", "name": "Enrage", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_enrage,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 300.0, "rage_gain": 100}
    },
    "plugin_retaliate": {
        "id": "plugin_retaliate", "name": "Retaliate", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.15, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 350.0}
    },
    "plugin_blessed_negation": {
        "id": "plugin_blessed_negation", "name": "Blessed Negation", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_blessed_negation,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 700.0, "trigger_interval": 9, "rage_reduction": 100}
    },
    "plugin_wild_indulgence": {
        "id": "plugin_wild_indulgence", "name": "Wild Indulgence", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_wild_indulgence,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1000.0, "trigger_interval": 10}
    },
    "plugin_breaking_free": {
        "id": "plugin_breaking_free", "name": "Breaking Free", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_breaking_free,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 10,
                   "damage_buff_magnitude": 0.30, "damage_buff_duration": 2,
                   "counter_reduction_magnitude": -0.30, "counter_reduction_duration": 2}
    },
    "plugin_fading_battle": {
        "id": "plugin_fading_battle", "name": "Fading Battle", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_generic_single_damage_skill,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 350.0}
    },
    "plugin_battle_hymn": {
        "id": "plugin_battle_hymn", "name": "Battle Hymn", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.10, "target": "ENEMY",
        "logic_handler": handle_plugin_battle_hymn,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 850.0, "rage_gain": 75, "cooldown_rounds": 5}
    },
    "plugin_rapid_attack": {
        "id": "plugin_rapid_attack", "name": "Rapid Attack", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.10, "target": "ENEMY",
        "logic_handler": handle_plugin_rapid_attack,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 650.0, "broken_blade_duration": 1, "cooldown_rounds": 5}
    },
    "plugin_blessed_by_fate": {
        "id": "plugin_blessed_by_fate", "name": "Blessed by Fate", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_blessed_by_fate,
        "config": {"initial_buff_duration": 29,
                   "initial_buff_magnitude": 0.50,
                   "secondary_proc_chance": 0.30,
                   "secondary_debuff_magnitude": 0.20,
                   "secondary_debuff_duration": 0}
    },
    "plugin_divine_blessing": {
        "id": "plugin_divine_blessing", "name": "Divine Blessing", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_divine_blessing,
        "config": {"initial_effect_duration": 28, "post_initial_trigger_chance": 0.30,
                   "post_initial_effect_duration": 0, "reduction_magnitude": -0.30,
                   "effect_name": EFFECT_NAME_DIVINE_BLESSING_REDUCTION}
    },
    "plugin_shield_support": {
        "id": "plugin_shield_support", "name": "Shield Support", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_shield_support,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"base_shield_factor": 750.0, "boosted_shield_factor": 1000.0,
                   "shield_duration": 1, "trigger_interval": 9, "effect_name": EFFECT_NAME_SHIELD_SUPPORT_EFFECT}
    },
    "plugin_freyas_blessing": {
        "id": "plugin_freyas_blessing", "name": "Freya's Blessing", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.15, "target": "SELF",
        "logic_handler": handle_plugin_freyas_blessing,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"direct_heal_factor": 550.0, "buff_details": {
            "effect_type": EffectType.STAT_MOD, "name": EFFECT_NAME_FREYAS_BLESSING_HEAL_BOOST,
            "stat_to_mod": StatType.HEAL_ADJUSTMENT, "magnitude": 0.25, "duration": 2,
            "activate_next_round": True}}
    },
    "plugin_hymn_of_life": {
        "id": "plugin_hymn_of_life", "name": "Hymn of Life", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_plugin_hymn_of_life,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"hot_heal_factor": 275.0, "hot_duration": 1, "hot_effect_name": EFFECT_NAME_HYMN_OF_LIFE_HOT,
                   "hp_buff_magnitude": 0.10, "hp_buff_duration": 0, "hp_buff_effect_name": EFFECT_NAME_HYMN_OF_LIFE_HP_BOOST}
    },
    "plugin_chance_of_reversal": {
        "id": "plugin_chance_of_reversal", "name": "Chance of Reversal", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_HEALING, "trigger_chance": 0.25, "target": "SELF",
        "logic_handler": handle_plugin_chance_of_reversal,
        "config": {"damage_factor": 550.0, "rage_gain": 50.0}
    },
    "plugin_shield_reflector": {
        "id": "plugin_shield_reflector", "name": "Shield Reflector", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_shield_reflector,
        "config": {}
    },
    "plugin_first_strike": {
        "id": "plugin_first_strike", "name": "First Strike", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_first_strike_control,
        "config": {"apply_aura_on_round": 1, "aura_effect_definition": {
            "effect_type": EffectType.CUSTOM_SKILL_EFFECT, "name": EFFECT_NAME_FIRST_STRIKE_RAGE_AURA,
            "duration": 29, "config": {"rage_per_round": 75, "start_rage_gain_round": 2, "end_rage_gain_round": 31},
            "activate_next_round": False }}
    },
    "plugin_shield_attacker": {
        "id": "plugin_shield_attacker", "name": "Shield Attacker", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_shield_attacker,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 500.0, "proc_chance": 0.50}
    },
    "plugin_awakening": {
        "id": "plugin_awakening", "name": "Awakening", "type": SkillType.PLUGIN_SKILL,
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
        "id": "plugin_baldr_blessing", "name": "Baldr's Blessing", "type": SkillType.PLUGIN_SKILL,
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
        "id": "plugin_lokis_trick", "name": "Loki's Trick", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_lokis_trick,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 450.0, "rage_reduction_chance": 0.30, "rage_reduction_amount": 100.0,
                   "buff_removal_chance": 0.30,
                   "pending_buff_removal_effect_name": EFFECT_NAME_PENDING_LOKIS_TRICK_BUFF_REMOVAL,
                   "cooldown_rounds": 3}
    },
    "plugin_odins_asylum": {
        "id": "plugin_odins_asylum", "name": "Odin's Asylum", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_odins_asylum,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 450.0, "shield_factor": 200.0, "shield_duration": 1,
                   "shield_activate_next_round": True, "shield_name": EFFECT_NAME_ODINS_ASYLUM_SHIELD}
    },
    "plugin_thors_determination": {
        "id": "plugin_thors_determination", "name": "Thor's Determination", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_thors_determination,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "buff_magnitude": 2.25, "buff_duration": 1,
                   "buff_activate_next_round": True, "buff_stat_to_mod": StatType.BASIC_DAMAGE_ADJUST,
                   "buff_name": EFFECT_NAME_THORS_DETERMINATION_BUFF}
    },
    "plugin_disarmament": {
        "id": "plugin_disarmament", "name": "Disarmament", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_disarmament,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 325.0, "disarm_duration": 0,
                   "disarm_effect_name": EFFECT_NAME_DISARM_DEBUFF,
                   "slow_duration": 1, "slow_effect_name": EFFECT_NAME_SLOW_DEBUFF,
                   "activate_debuffs_next_round": True, "cooldown_rounds": 3}
    },

    "plugin_fiery_rage": {
        "id": "plugin_fiery_rage", "name": "Fiery Rage", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.10, "target": "ENEMY",
        "logic_handler": handle_plugin_fiery_rage,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"burn_factor": 350.0, "boosted_burn_factor": 700.0, "burn_duration": 1}
    },
    "plugin_fiery_detonation": {
        "id": "plugin_fiery_detonation", "name": "Fiery Detonation", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_fiery_detonation,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "damage_factor": 600.0,
                   "defense_reduction_magnitude": -0.15, "defense_reduction_duration": 1}
    },
    "plugin_rage_leech": {
        "id": "plugin_rage_leech", "name": "Rage Leech", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_rage_leech,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"heal_factor": 900.0, "rage_gain": 80.0}
    },
    "plugin_enchanted_pursuit": {
        "id": "plugin_enchanted_pursuit", "name": "Enchanted Pursuit", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_enchanted_pursuit,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"burn_chance": 0.10, "burn_factor": 275.0, "burn_duration": 1,
                   "bleed_chance": 0.10, "bleed_factor": 275.0, "bleed_duration": 1}
    },
    "plugin_blow_of_chaos": {
        "id": "plugin_blow_of_chaos", "name": "Blow of Chaos", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_blow_of_chaos,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"damage_factor": 1000.0, "cooldown_rounds": 3}
    },
    "plugin_on_alert": {
        "id": "plugin_on_alert", "name": "On Alert", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_on_alert,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "buff_magnitude": 0.17, "max_stacks": 5,
                   "buff_name": EFFECT_NAME_ON_ALERT_COUNTER_BUFF}
    },
    "plugin_helas_curse": {
        "id": "plugin_helas_curse", "name": "Hela's Curse", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_helas_curse,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 9, "burn_factor": 500.0, "burn_duration": 1,
                   "defense_debuff_chance": 0.50, "defense_debuff_magnitude": -0.20,
                   "defense_debuff_duration": 1}
    },
    "plugin_fearless": {
        "id": "plugin_fearless", "name": "Fearless", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_fearless,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 12, "damage_factor": 800.0,
                   "buff_chance": 0.20, "buff_magnitude": 0.15, "buff_duration": 1}
    },
    "plugin_joint_offense": {
        "id": "plugin_joint_offense", "name": "Joint Offense", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_joint_offense,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 800.0, "proc_chance": 0.50}
    },
    "plugin_bloody_rage": {
        "id": "plugin_bloody_rage", "name": "Bloody Rage", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_bloody_rage,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"hp_threshold_pct": 0.80, "proc_chance": 0.20, "damage_factor": 500.0}
    },
    "plugin_tidal_attack": {
        "id": "plugin_tidal_attack", "name": "Tidal Attack", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "ENEMY",
        "logic_handler": handle_plugin_tidal_attack,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_factor": 290.0, "damage_factor_h1": 370.0}
    },
    "plugin_splinter": {
        "id": "plugin_splinter", "name": "Splinter", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_splinter,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 12, "damage_factor": 800.0,
                   "slow_chance": 0.35, "slow_duration": 1}
    },
    "plugin_hale_of_thorns": {
        "id": "plugin_hale_of_thorns", "name": "Hale of Thorns", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.PASSIVE, "target": "SELF",
        "logic_handler": handle_plugin_hale_of_thorns
    },
    "plugin_halo_of_sacrifice": {
        "id": "plugin_halo_of_sacrifice", "name": "Halo of Sacrifice", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_plugin_halo_of_sacrifice,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"buff_magnitude": 0.75, "buff_duration": 1}
    },
    "plugin_heightened_chance": {
        "id": "plugin_heightened_chance", "name": "Heightened Chance", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.25, "target": "SELF",
        "logic_handler": handle_plugin_heightened_chance,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"basic_buff_magnitude": 0.40, "counter_buff_magnitude": 0.40, "buff_duration": 1}
    },
    "plugin_tenacity": {
        "id": "plugin_tenacity", "name": "Tenacity", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 0.50, "target": "SELF",
        "logic_handler": handle_plugin_tenacity,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"heal_factor": 700.0}
    },
    "plugin_blessed_healing": {
        "id": "plugin_blessed_healing", "name": "Blessed Healing", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_blessed_healing,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"trigger_interval": 12, "heal_factor": 850.0}
    },
    "plugin_dampened_spirits": {
        "id": "plugin_dampened_spirits", "name": "Dampened Spirits", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_OWN_RAGE_SKILL_CAST, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_dampened_spirits,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"damage_proc_chance": 0.50, "damage_factor": 550.0,
                   "rage_reduction_chance": 0.15, "rage_reduction": 300.0}
    },
    "plugin_rapid_defense": {
        "id": "plugin_rapid_defense", "name": "Rapid Defense", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_RECEIVING_RAGE_SKILL_DAMAGE, "trigger_chance": 1.0, "target": "SELF",
        "logic_handler": handle_plugin_rapid_defense,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"buff_magnitude": 0.40, "buff_duration": 1}
    },
    "plugin_rare_viking_hymn": {
        "id": "plugin_rare_viking_hymn", "name": "Rare Viking Hymn", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.30, "target": "SELF",
        "logic_handler": handle_plugin_rare_viking_hymn,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"buff_magnitude": 0.20, "buff_duration": 1}
    },
    "plugin_rare_defense_up": {
        "id": "plugin_rare_defense_up", "name": "Rare Defense Up", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_HIT_BY_BASIC_ATTACK, "trigger_chance": 0.25, "target": "SELF",
        "logic_handler": handle_plugin_rare_defense_up,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"buff_magnitude": 0.20, "buff_duration": 1}
    },
    "plugin_rest_and_counterattack": {
        "id": "plugin_rest_and_counterattack", "name": "Rest and Counterattack", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK, "trigger_chance": 0.15, "target": "SELF",
        "logic_handler": handle_plugin_rest_and_counterattack,
        "labels": [PluginSkillLabel.REACTIVE],
        "config": {"shield_factor": 400.0, "shield_duration": 1, "heal_factor": 400.0,
                   "cooldown_rounds": 4, "shield_effect_name": EFFECT_NAME_REST_AND_COUNTERATTACK_SHIELD}
    },
    "plugin_bloodstained_icefield": {
        "id": "plugin_bloodstained_icefield", "name": "Bloodstained Icefield", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_BASIC_ATTACK, "trigger_chance": 0.20, "target": "SELF",
        "logic_handler": handle_plugin_bloodstained_icefield,
        "labels": [PluginSkillLabel.COOPERATION],
        "config": {"heal_factor": 700.0, "cooldown_rounds": 3}
    },
    "plugin_this_too_shall_pass": {
        "id": "plugin_this_too_shall_pass", "name": "This Too Shall Pass", "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.CHANCE_PER_ROUND, "trigger_chance": 1.0, "target": "ENEMY",
        "logic_handler": handle_plugin_this_too_shall_pass,
        "labels": [PluginSkillLabel.COMMAND],
        "config": {"damage_factor": 1000.0, "heal_factor": 1000.0, "trigger_interval": 9}
    },

    # --- Dummy Talent ---
    "dummy_talent_empty": {
        "id": "dummy_talent_empty", "name": "Empty Talent Slot", "type": SkillType.TALENT,
        "trigger": SkillTriggerType.PASSIVE, "trigger_chance": 0.0, "target": "SELF",
        "effects_to_apply": [], "logic_handler": None
    }
}
