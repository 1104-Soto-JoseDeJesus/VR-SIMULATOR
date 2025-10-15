from vr_game_sim.metadata_loader import get_skill_description


def test_get_skill_description_hero_skill():
    description = get_skill_description("base_skill_inspiring_dance", "Inspiring Dance")
    assert isinstance(description, str) and description
    assert "Bleed" in description or "bleed" in description.lower()


def test_get_skill_description_fallback_basic_attack():
    description = get_skill_description("basic_attack", "Basic Attack")
    assert "damage" in description.lower()


def test_get_skill_description_jewel_with_rarity_alias():
    description = get_skill_description(
        "gem_friggs_agate_piercing_pikes_legendary",
        "Piercing Pikes (Legendary)",
    )
    expected = (
        "Triggers on the first round of battle (and is applied on the 2nd round of battle), "
        "this army's pikemen (if own army is pikemen) troops deal 9.5% more overall damage "
        "(+0.095 to applicable damage multipliers, remember this doesn't apply to DOTs) for "
        "30 rounds (IE round 31 is the final round this applies in), Removable"
    )
    assert description == expected
