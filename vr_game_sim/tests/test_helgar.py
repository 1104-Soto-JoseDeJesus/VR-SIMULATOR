from vr_game_sim.hero_definition import Hero, HERO_PRESETS
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL

def test_helgar_preset_loading():
    preset = HERO_PRESETS.get('helgar')
    assert preset is not None
    hero = Hero('Helgar', preset['talents'], preset['base_skills'], preset['plugin_skills'], SKILL_REGISTRY_GLOBAL)
    assert len(hero.skills) == 5  # 3 talents + 2 base skills
