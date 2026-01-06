"""
Defines the Unit class, its base stats, and methods for calculating effective stats.
"""
from dataclasses import dataclass, field, InitVar
from typing import List, Dict, Tuple, Optional, ClassVar
from .enums import StatType, EffectType
from .effect_system import EffectInstance


@dataclass(slots=True)
class Unit:
    ALLOWED_TYPES: ClassVar[set] = {'pikemen', 'archers', 'infantry'}
    ALLOWED_TIERS: ClassVar[set] = {4, 5, 6, 7}
    BASE_STATS: ClassVar[Dict[Tuple[str, int], Dict[str, int]]] = {
        ('pikemen', 4): {'hp': 152, 'atk': 154, 'def': 176},
        ('pikemen', 5): {'hp': 169, 'atk': 172, 'def': 196},
        ('pikemen', 6): {'hp': 180, 'atk': 182, 'def': 208},
        ('pikemen', 7): {'hp': 199, 'atk': 202, 'def': 231},
        ('archers', 4): {'hp': 153, 'atk': 176, 'def': 154},
        ('archers', 5): {'hp': 169, 'atk': 196, 'def': 172},
        ('archers', 6): {'hp': 180, 'atk': 209, 'def': 183},
        ('archers', 7): {'hp': 200, 'atk': 231, 'def': 201},
        ('infantry', 4): {'hp': 177, 'atk': 149, 'def': 157},
        ('infantry', 5): {'hp': 198, 'atk': 166, 'def': 174},
        ('infantry', 6): {'hp': 209, 'atk': 177, 'def': 185},
        ('infantry', 7): {'hp': 231, 'atk': 196, 'def': 205},
    }

    unit_type: str
    tier: int
    initial_count: int
    initial_atk_modifier: float = 0.0
    initial_def_modifier: float = 0.0
    initial_hp_modifier: float = 0.0

    base_atk_stat: int = field(init=False)
    base_def_stat: int = field(init=False)
    base_hp_stat: int = field(init=False)
    atk_multiplier: float = field(init=False)
    def_multiplier: float = field(init=False)
    hp_multiplier: float = field(init=False)

    def __post_init__(self):
        if self.unit_type not in Unit.ALLOWED_TYPES:
            raise ValueError(f"Invalid unit type: {self.unit_type}")
        if self.tier not in Unit.ALLOWED_TIERS:
            raise ValueError(f"Invalid tier: {self.tier}")
        if not isinstance(self.initial_count, int) or self.initial_count <= 0:
            raise ValueError("Unit count must be a positive integer.")

        stats = Unit.BASE_STATS[(self.unit_type, self.tier)]
        self.base_atk_stat = stats['atk']
        self.base_def_stat = stats['def']
        self.base_hp_stat = stats['hp']
        self.atk_multiplier = self.initial_atk_modifier
        self.def_multiplier = self.initial_def_modifier
        self.hp_multiplier = self.initial_hp_modifier

    def get_stat_with_effects(self, base_value: float, current_initial_multiplier: float,
                              base_multiplier_stat_type: Optional[StatType],
                              effective_multiplier_stat_type: Optional[StatType],
                              army_effects: List[EffectInstance]) -> float:
        mod_base_multiplier = current_initial_multiplier
        mod_effect_types = {EffectType.STAT_MOD, EffectType.DEBUFF}
        for effect in army_effects:
            if effect.effect_type in mod_effect_types and \
               effect.config.get('stat_to_mod') == base_multiplier_stat_type:
                unit_condition = effect.config.get("unit_type_condition")
                if not unit_condition or self.unit_type == unit_condition:
                    mod_base_multiplier += effect.magnitude

        value_after_base_mods = base_value * (1 + mod_base_multiplier)

        final_effective_multiplier = 1.0
        for effect in army_effects:
            if effect.effect_type in mod_effect_types and \
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

