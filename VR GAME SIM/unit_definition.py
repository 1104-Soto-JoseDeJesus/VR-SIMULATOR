"""
Defines the Unit class, its base stats, and methods for calculating effective stats.
"""
from typing import List, Dict, Tuple, Optional
from enums import StatType, EffectType # Assuming enums.py is in the same directory
from effect_system import EffectInstance # Assuming effect_system.py is in the same directory

class Unit:
    ALLOWED_TYPES = {'pikemen', 'archers', 'infantry'}
    ALLOWED_TIERS = {5, 6, 7}
    BASE_STATS: Dict[Tuple[str, int], Dict[str, int]] = {
        ('pikemen', 5): {'hp': 169, 'atk': 172, 'def': 196},
        ('pikemen', 6): {'hp': 180, 'atk': 182, 'def': 208},
        ('pikemen', 7): {'hp': 199, 'atk': 202, 'def': 231},
        ('archers', 5): {'hp': 169, 'atk': 196, 'def': 172},
        ('archers', 6): {'hp': 180, 'atk': 209, 'def': 183},
        ('archers', 7): {'hp': 200, 'atk': 231, 'def': 201},
        ('infantry', 5): {'hp': 198, 'atk': 166, 'def': 174},
        ('infantry', 6): {'hp': 209, 'atk': 177, 'def': 185},
        ('infantry', 7): {'hp': 231, 'atk': 196, 'def': 205},
    }

    def __init__(self, unit_type: str, tier: int, count: int,
                 initial_atk_modifier: float = 0.0, initial_def_modifier: float = 0.0,
                 initial_hp_modifier: float = 0.0):
        if unit_type not in Unit.ALLOWED_TYPES:
            raise ValueError(f"Invalid unit type: {unit_type}")
        if tier not in Unit.ALLOWED_TIERS:
            raise ValueError(f"Invalid tier: {tier}")
        if not isinstance(count, int) or count <= 0:
            raise ValueError("Unit count must be a positive integer.")

        stats = Unit.BASE_STATS[(unit_type, tier)]
        self.unit_type: str = unit_type
        self.tier: int = tier
        self.base_atk_stat: int = stats['atk']
        self.base_def_stat: int = stats['def']
        self.base_hp_stat: int = stats['hp']
        self.atk_multiplier: float = initial_atk_modifier # Initial tech/gear/etc. base multiplier
        self.def_multiplier: float = initial_def_modifier
        self.hp_multiplier: float = initial_hp_modifier
        self.initial_count: int = count

    def get_stat_with_effects(self, base_value: float, current_initial_multiplier: float,
                              base_multiplier_stat_type: Optional[StatType],
                              effective_multiplier_stat_type: Optional[StatType],
                              army_effects: List[EffectInstance]) -> float:
        # 1. Apply base multipliers from effects
        mod_base_multiplier = current_initial_multiplier # Start with hero/tech/gear base multiplier
        for effect in army_effects:
            if effect.effect_type == EffectType.STAT_MOD and \
               effect.config.get('stat_to_mod') == base_multiplier_stat_type:
                unit_condition = effect.config.get("unit_type_condition")
                if not unit_condition or self.unit_type == unit_condition:
                    mod_base_multiplier += effect.magnitude

        # Value after all base stat multipliers are summed
        value_after_base_mods = base_value * (1 + mod_base_multiplier)

        # 2. Apply effective multipliers from effects (these usually stack multiplicatively)
        final_effective_multiplier = 1.0
        for effect in army_effects:
            if effect.effect_type == EffectType.STAT_MOD and \
               effect.config.get('stat_to_mod') == effective_multiplier_stat_type:
                final_effective_multiplier *= (1 + effect.magnitude)

        return value_after_base_mods * final_effective_multiplier

    def effective_attack(self, army_effects: List[EffectInstance]) -> float:
        return self.get_stat_with_effects(float(self.base_atk_stat), self.atk_multiplier,
                                          StatType.BASE_ATTACK_MULTIPLIER,
                                          StatType.EFFECTIVE_ATTACK_MULTIPLIER, army_effects)

    def effective_defense(self, army_effects: List[EffectInstance]) -> float:
        return self.get_stat_with_effects(float(self.base_def_stat), self.def_multiplier,
                                          StatType.BASE_DEFENSE_MULTIPLIER,
                                          StatType.EFFECTIVE_DEFENSE_MULTIPLIER, army_effects)

    def effective_hp_per_troop(self, army_effects: List[EffectInstance]) -> float:
        return self.get_stat_with_effects(float(self.base_hp_stat), self.hp_multiplier,
                                          StatType.BASE_HP_MULTIPLIER,
                                          StatType.EFFECTIVE_HP_MULTIPLIER, army_effects)