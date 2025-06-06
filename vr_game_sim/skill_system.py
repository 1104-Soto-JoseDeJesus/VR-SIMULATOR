"""
Defines type aliases and base structures for the skill system.
"""
from typing import Dict, Any, Callable, Tuple, List, Optional
# It's good practice to use forward references as strings if classes are in different files
# to avoid circular import issues, though for this single-file generation it's less critical.
ArmyRef = "Army"
GameSimulatorRef = "GameSimulator"
SkillDefinition = Dict[str, Any]

# Type alias for skill logic handlers
# Parameters: triggering_army, opponent_army, skill_definition, event_data, simulator_instance
# Returns: (bool_effect_happened, list_of_log_details_tuples)
SkillLogicHandler = Callable[
    [ArmyRef, ArmyRef, SkillDefinition, Optional[Dict[str, Any]], GameSimulatorRef],
    Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]]]
]

# Type alias for rage skill logic handlers
# Adds a boolean for 'damage_dealt_flag' in the return tuple
RageSkillLogicHandler = Callable[
    [ArmyRef, ArmyRef, SkillDefinition, Dict[str, Any], GameSimulatorRef],
    Tuple[bool, List[Tuple[str, Optional[Dict[str, Any]]]], bool]
]

# SKILL_REGISTRY_GLOBAL will be populated in skill_definitions.py and imported where needed.