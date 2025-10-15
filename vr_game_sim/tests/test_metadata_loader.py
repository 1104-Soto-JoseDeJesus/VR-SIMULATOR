from vr_game_sim.metadata_loader import get_skill_description


def test_get_skill_description_hero_skill():
    description = get_skill_description("base_skill_inspiring_dance", "Inspiring Dance")
    assert isinstance(description, str) and description
    assert "Bleed" in description or "bleed" in description.lower()


def test_get_skill_description_fallback_basic_attack():
    description = get_skill_description("basic_attack", "Basic Attack")
    assert "damage" in description.lower()
