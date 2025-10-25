import html
import os
import random

import pytest

from vr_game_sim.army_composition import Army
from vr_game_sim.unit_definition import Unit

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.enums import (
    EffectType,
    SkillTriggerType,
    SkillType,
    PluginSkillLabel,
)
from vr_game_sim.hero_definition import Hero
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL


def _make_skill_def() -> dict:
    return {
        "id": "test_skill",
        "name": "Test Skill",
        "type": SkillType.PLUGIN_SKILL,
        "trigger": SkillTriggerType.ON_COUNTER_ATTACK,
        "labels": [PluginSkillLabel.REACTIVE],
    }


def _make_armies(bonus_stats: dict | None = None) -> tuple[Army, Army, GameSimulator]:
    atk_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    dfd_unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    atk_unit.base_atk_stat = 1200
    dfd_unit.base_def_stat = 600
    attacker = Army(name="A", unit=atk_unit, bonus_stats_config=bonus_stats or {})
    defender = Army(name="D", unit=dfd_unit)
    sim = GameSimulator(attacker, defender)
    return attacker, defender, sim


def test_reactive_crit_rate_increases_damage():
    skill_def = _make_skill_def()
    attacker, defender, sim = _make_armies()
    random.seed(0)
    base_damage, *_ = sim._calculate_generic_skill_damage(
        attacker,
        defender,
        damage_factor=200.0,
        source_skill_def=skill_def,
    )

    attacker2, defender2, sim2 = _make_armies(
        {"damage_boost": {"reactive_crit_rate": 1.0}}
    )
    random.seed(0)
    crit_damage, *_ = sim2._calculate_generic_skill_damage(
        attacker2,
        defender2,
        damage_factor=200.0,
        source_skill_def=skill_def,
    )

    assert crit_damage > base_damage
    assert pytest.approx(crit_damage / base_damage, rel=1e-6) == 1.5


def test_gem_evasion_counts_damage_reduction():
    skill_def = _make_skill_def()
    attacker, defender, sim = _make_armies()

    effect_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": "Gem Evasion",
        "duration": -1,
        "config": {"evasion_chance": 1.0, "applies_to": ["SKILL"]},
    }
    effect = defender._create_and_add_single_effect(
        effect_data,
        "gem_evasion",
        defender,
        defender,
        attacker,
    )
    assert effect is not None
    defender.activate_queued_effects()

    random.seed(0)
    damage, absorbed, kills, raw = sim._calculate_generic_skill_damage(
        attacker,
        defender,
        damage_factor=200.0,
        source_skill_def=skill_def,
    )

    assert damage == pytest.approx(0.0)
    assert defender.skill_damage_reduction_totals.get("gem_evasion", 0.0) > 0.0


def test_gem_retribution_counts_kills():
    skill_def = _make_skill_def()
    attacker, defender, sim = _make_armies()

    effect_data = {
        "effect_type": EffectType.CUSTOM_SKILL_EFFECT,
        "name": "Gem Retribution",
        "duration": -1,
        "config": {"retribution_rate": 1.0},
    }
    effect = defender._create_and_add_single_effect(
        effect_data,
        "gem_retribution",
        defender,
        defender,
        attacker,
    )
    assert effect is not None
    defender.activate_queued_effects()

    random.seed(0)
    damage, absorbed, kills, raw = sim._calculate_generic_skill_damage(
        attacker,
        defender,
        damage_factor=200.0,
        source_skill_def=skill_def,
    )
    assert damage > 0

    attacker.commit_pending_healing_and_damage()
    defender.commit_pending_healing_and_damage()

    assert defender.skill_kill_totals.get("gem_retribution", 0.0) > 0.0


def test_skill_summary_includes_gem_skills():
    gui_main = pytest.importorskip("vr_game_sim.gui_main", exc_type=ImportError)
    build_army_skill_summary = gui_main.build_army_skill_summary

    hero1 = Hero(
        "HeroOne",
        ["dummy_talent_empty", "dummy_talent_empty", "dummy_talent_empty"],
        [],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    hero2 = Hero(
        "HeroTwo",
        ["dummy_talent_empty", "dummy_talent_empty", "dummy_talent_empty"],
        [],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    army = Army(name="SummaryArmy", unit=unit, heroes=[hero1, hero2])

    gem1 = "gem_friggs_agate_piercing_pikes_legendary"
    gem2 = "gem_freyas_amethyst_fearless_blades_legendary"
    army.set_gem_skills({
        "friggs_agate": gem1,
        "freyas_amethyst": gem2,
    })
    army.skill_trigger_counts[gem1] = 2
    army.skill_kill_totals[gem1] = 5
    army.skill_trigger_counts[gem2] = 3
    army.skill_heal_totals[gem2] = 7

    cfg = {
        "heroes": [
            {"hero_name_or_preset": "HeroOne"},
            {"hero_name_or_preset": "HeroTwo"},
        ]
    }

    summary = build_army_skill_summary(army, cfg, "red")
    hero1_skills = summary["skills"][0]
    hero2_skills = summary["skills"][1]

    gem1_entry = next((entry for entry in hero1_skills if entry["id"] == gem1), None)
    gem2_entry = next((entry for entry in hero2_skills if entry["id"] == gem2), None)

    assert gem1_entry is not None
    assert gem1_entry["casts"] == 2
    assert gem1_entry["kills"] == 5
    assert gem1_entry.get("rarity") == "Legendary"

    assert gem2_entry is not None
    assert gem2_entry["casts"] == 3
    assert gem2_entry["heals"] == 7
    assert gem2_entry.get("rarity") == "Legendary"

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PyQt6 import QtWidgets
        from vr_game_sim.gui.arena_stats import SkillStatsRow
    except ImportError:
        return

    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _total(field: str, skills: list[dict]) -> int:
        boost_key = {
            "rage_reduced": "boosted_rage_reduced",
            "damage_reduced": "boosted_damage_reduced",
        }.get(field, f"boosted_{field}")
        total = 0
        for entry in skills:
            if not isinstance(entry, dict):
                continue
            total += int(entry.get(field, 0) or 0)
            if boost_key in entry:
                total += int(entry.get(boost_key, 0) or 0)
        return total

    totals = {
        "kills": _total("kills", hero1_skills),
        "healed": _total("heals", hero1_skills),
        "shielded": _total("shielded", hero1_skills),
        "rage_reduced": _total("rage_reduced", hero1_skills),
        "rage": _total("rage", hero1_skills),
        "damage_reduced": _total("damage_reduced", hero1_skills),
    }

    row = SkillStatsRow(
        gem1_entry,
        totals["kills"],
        totals["healed"],
        totals["shielded"],
        totals["rage_reduced"],
        totals["rage"],
        totals["damage_reduced"],
    )
    name_widget = row.layout().itemAtPosition(0, 0).widget()
    assert isinstance(name_widget, QtWidgets.QLabel)
    assert "Legendary" in name_widget.text()
    row.deleteLater()


def test_export_summary_handles_list_gem_skill(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    gui_main = pytest.importorskip("vr_game_sim.gui_main", exc_type=ImportError)

    try:
        from PyQt6 import QtWidgets
    except ImportError:
        pytest.skip("PyQt6 is required for this test")

    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    hero1 = Hero(
        "HeroOne",
        ["dummy_talent_empty", "dummy_talent_empty", "dummy_talent_empty"],
        [],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    hero2 = Hero(
        "HeroTwo",
        ["dummy_talent_empty", "dummy_talent_empty", "dummy_talent_empty"],
        [],
        [],
        SKILL_REGISTRY_GLOBAL,
    )
    unit = Unit(unit_type="infantry", tier=5, initial_count=100)
    army = Army(name="ExportArmy", unit=unit, heroes=[hero1, hero2])

    gem_skill_id = "gem_friggs_agate_piercing_pikes_legendary"
    army.set_gem_skills({"friggs_agate": [gem_skill_id, ""]})
    assert army.gem_skill_ids.get("friggs_agate") == gem_skill_id

    cfg = {
        "army_name": "ExportArmy",
        "unit_type": "infantry",
        "tier": 5,
        "count": 100,
        "atk_mod": 0.0,
        "def_mod": 0.0,
        "hp_mod": 0.0,
        "bonus_stats": {},
        "heroes": [
            {"hero_name_or_preset": "HeroOne"},
            {"hero_name_or_preset": "HeroTwo"},
        ],
        "gem_skills": {"friggs_agate": [gem_skill_id, "spare"]},
    }

    summary = gui_main.build_army_skill_summary(army, cfg, "red")

    for hero_skills in summary.get("skills", []):
        if not isinstance(hero_skills, list):
            continue
        for entry in hero_skills:
            if isinstance(entry, dict) and entry.get("id") == gem_skill_id:
                entry["name"] = ["List", "Name"]
                entry["rarity"] = ["Legendary"]
                break

    original_get_skill_description = gui_main.get_skill_description

    def _fake_get_skill_description(skill_id, skill_name):
        if skill_id == gem_skill_id:
            return ["Line 1", "Line 2"]
        return original_get_skill_description(skill_id, skill_name)

    monkeypatch.setattr(gui_main, "get_skill_description", _fake_get_skill_description)

    window = gui_main.MainWindow()
    window._last_simulation_payload = {
        "setup": [cfg],
        "army_names": ["ExportArmy", "Opponent"],
        "summary": [summary],
        "win_rate": 0.5,
        "runs": 10,
    }

    save_path = tmp_path / "summary.html"

    monkeypatch.setattr(
        gui_main.QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(save_path), "HTML Files (*.html)"),
    )
    monkeypatch.setattr(gui_main.QtWidgets.QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(gui_main.QtWidgets.QMessageBox, "critical", lambda *args, **kwargs: None)

    window.export_summary_html()

    assert save_path.exists()
    html_content = save_path.read_text(encoding="utf-8")
    expected_badge_snippet = (
        f"<span class=\"hero-name\">{hero1.name}</span>"
        + "<span class=\"hero-badge\">Main Hero</span>"
    )
    assert expected_badge_snippet in html_content
    assert html_content.count("hero-badge") == 1
    window.close()


def test_export_summary_with_sample_sections(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    gui_main = pytest.importorskip("vr_game_sim.gui_main", exc_type=ImportError)

    try:
        from PyQt6 import QtWidgets
    except ImportError:
        pytest.skip("PyQt6 is required for this test")

    _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _make_skill(skill_id: str, name: str, base: int) -> dict:
        return {
            "id": skill_id,
            "name": name,
            "casts": base,
            "kills": base + 1,
            "heals": base + 2,
            "shielded": base + 3,
            "damage_reduced": base + 4,
            "rage": base + 5,
            "rage_reduced": base + 6,
            "boosted_kills": base + 7,
            "boosted_heals": base + 8,
            "boosted_shielded": base + 9,
            "boosted_rage": base + 10,
            "boosted_rage_reduced": base + 11,
            "boosted_damage_reduced": base + 12,
        }

    summary_entries = [
        {
            "initial": 100,
            "remaining": 80,
            "healed": 20,
            "kills": 30,
            "hero_names": ["HeroOne", "HeroTwo"],
            "skills": [
                [_make_skill("skill_a", "Skill A", 1)],
                [_make_skill("skill_b", "Skill B", 2)],
            ],
        },
        {
            "initial": 120,
            "remaining": 60,
            "healed": 40,
            "kills": 50,
            "hero_names": ["HeroThree", "HeroFour"],
            "skills": [
                [_make_skill("skill_c", "Skill C", 3)],
                [_make_skill("skill_d", "Skill D", 4)],
            ],
        },
    ]

    setup_entries = [
        {
            "army_name": "ExportArmy",
            "unit_type": "infantry",
            "tier": 5,
            "count": 100,
            "atk_mod": 0.0,
            "def_mod": 0.0,
            "hp_mod": 0.0,
            "bonus_stats": {},
            "heroes": [
                {"hero_name_or_preset": "HeroOne"},
                {"hero_name_or_preset": "HeroTwo"},
            ],
            "gem_skills": {},
        },
        {
            "army_name": "Opponent",
            "unit_type": "archers",
            "tier": 4,
            "count": 95,
            "atk_mod": 0.1,
            "def_mod": 0.0,
            "hp_mod": -0.05,
            "bonus_stats": {},
            "heroes": [
                {"hero_name_or_preset": "HeroThree"},
                {"hero_name_or_preset": "HeroFour"},
            ],
            "gem_skills": {},
        },
    ]

    sample_rounds = [
        {
            "round": 1,
            "combat_actions": [
                {
                    "attacker_name": "ExportArmy Vanguard",
                    "defender_name": "Opponent Guard",
                    "action_type": "Normal Attack",
                    "damage_potential_hp": 1234,
                    "absorbed_hp": 234,
                    "final_hp_damage": 1000,
                    "potential_kills": 3,
                },
                {
                    "attacker_name": "ExportArmy Vanguard",
                    "defender_name": "Opponent Guard",
                    "action_type": "Heavily Wounded Ratio",
                    "damage_potential_hp": 0,
                    "absorbed_hp": 0,
                    "final_hp_damage": 0,
                    "potential_kills": 0,
                },
                {
                    "attacker_name": "ExportArmy Vanguard",
                    "defender_name": "Opponent Guard",
                    "action_type": "Damage Commit",
                    "damage_potential_hp": 0,
                    "absorbed_hp": 0,
                    "final_hp_damage": 0,
                    "potential_kills": 0,
                },
            ],
            "skill_triggers": {
                "ExportArmy": [
                    {
                        "skill_name": "Skill A",
                        "effect_description": "Deals heavy damage.",
                        "damage_done_hp": 500,
                        "potential_kills": 2,
                    }
                ],
                "Opponent": [
                    {
                        "skill_name": "Shield Skill",
                        "effect_description": "Raises shield.",
                        "shield_hp_gained": 400,
                    }
                ],
            },
            "active_effects": ["ExportArmy gains Battle Cry"],
        }
    ]

    payload = {
        "setup": setup_entries,
        "army_names": ["ExportArmy", "Opponent"],
        "summary": summary_entries,
        "win_rate": 0.6,
        "runs": 10,
        "sample_battle": {
            "seed": 12345,
            "winner": "ExportArmy",
            "army_histories": [
                {"troops": [100, 90, 80], "unrevivable": [0, 5, 10]},
                {"troops": [95, 70, 60], "unrevivable": [0, 7, 15]},
            ],
        },
        "rounds": sample_rounds,
    }

    window = gui_main.MainWindow()
    window._last_simulation_payload = payload

    save_path = tmp_path / "summary_with_sample.html"

    monkeypatch.setattr(
        gui_main.QtWidgets.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(save_path), "HTML Files (*.html)"),
    )
    monkeypatch.setattr(gui_main.QtWidgets.QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(gui_main.QtWidgets.QMessageBox, "critical", lambda *args, **kwargs: None)

    window.export_summary_with_sample_html()

    assert save_path.exists()
    html_content = save_path.read_text(encoding="utf-8")
    expected_hero_sections = sum(len(entry["skills"]) for entry in summary_entries)
    assert html_content.count('<div class="skill-hero">') == expected_hero_sections
    assert html_content.count('<div class="sample-army-card">') == len(summary_entries)
    assert '<script type="application/json" id="troop-history-data">' in html_content
    assert 'class="troop-search"' in html_content
    assert 'troop-tooltip-change' in html_content
    assert 'Sample Battle Log' in html_content
    assert html_content.count('class="round-log"') == len(sample_rounds)
    assert 'Round 1' in html_content
    assert 'ExportArmy gains Battle Cry' in html_content
    assert 'Normal Attack' in html_content
    assert 'Heavily Wounded Ratio' not in html_content
    assert 'Damage Commit' not in html_content
    assert 'Skill A' in html_content
    assert 'Shield Skill' in html_content
    assert 'round-army-name">ExportArmy</span><strong>100</strong>' in html_content
    window.close()


def test_sample_round_html_omits_commitment_entries():
    gui_main = pytest.importorskip("vr_game_sim.gui_main", exc_type=ImportError)

    rounds = [
        {
            "round": 1,
            "skill_triggers": {
                "ExportArmy": [
                    {
                        "skill_name": "Damage Commitment",
                        "effect_description": "Committed 120 damage.",
                    },
                    {
                        "skill_name": "↳ Follow Up",
                        "effect_description": "↳ committed 120 damage.",
                    },
                    {
                        "skill_name": "Dynamic Unrevivable",
                        "effect_description": "Prevents revives.",
                    },
                    {
                        "skill_name": "Heal Commitment",
                        "effect_description": "Committed 60 healing.",
                    },
                    {
                        "skill_name": "Helpful Skill",
                        "effect_description": "Inflicts a minor bleed.",
                    },
                ]
            },
        }
    ]

    rendered_entries: list[str] = []
    for round_data in rounds:
        skill_data = round_data.get("skill_triggers")
        if not isinstance(skill_data, dict):
            continue
        for triggers in skill_data.values():
            if not triggers:
                continue
            for trig in triggers:
                if not isinstance(trig, dict):
                    continue
                raw_skill = str(trig.get("skill_name", "") or "")
                raw_effect = str(trig.get("effect_description", "") or "")
                clean_name = raw_skill.strip()
                clean_effect = raw_effect.strip()
                if gui_main._should_skip_skill_trigger(clean_name, clean_effect):
                    continue
                entry_parts = [
                    "<div class=\"skill-entry\">",
                    f"<strong>{html.escape(clean_name or 'Skill')}</strong>",
                ]
                if clean_effect:
                    entry_parts.append(
                        f"<span class=\"skill-effect\">{html.escape(clean_effect)}</span>"
                    )
                entry_parts.append("</div>")
                rendered_entries.append("".join(entry_parts))

    combined_html = "".join(rendered_entries)
    assert "Damage Commitment" not in combined_html
    assert "Dynamic Unrevivable" not in combined_html
    assert "committed 120 damage" not in combined_html
    assert "Committed 60 healing" not in combined_html
    assert "Helpful Skill" in combined_html
