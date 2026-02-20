import contextlib
import html
import io
import json

import streamlit as st
import streamlit.components.v1 as components

from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.gear_definitions import GEAR_REGISTRY, GEAR_SLOT_ORDER
from vr_game_sim.hero_definition import HERO_PRESETS
from vr_game_sim.main import create_armies_from_data
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL, SkillType

st.set_page_config(page_title="VR Simulator", layout="wide")
st.title("🛡️ Viking Rise Battle Simulator")

HERO_OPTIONS = sorted({name.title() for name in HERO_PRESETS.keys()})
PLUGIN_SKILLS = sorted(
    [
        (sid, data.get("name", sid))
        for sid, data in SKILL_REGISTRY_GLOBAL.items()
        if data.get("type") == SkillType.PLUGIN_SKILL
    ],
    key=lambda item: item[1],
)
MOUNT_SKILLS = sorted(
    [
        (sid, data.get("name", sid))
        for sid, data in SKILL_REGISTRY_GLOBAL.items()
        if data.get("type") == SkillType.MOUNT_SKILL
    ],
    key=lambda item: item[1],
)
JEWEL_SKILLS = sorted(
    [
        (sid, data.get("name", sid))
        for sid, data in SKILL_REGISTRY_GLOBAL.items()
        if data.get("type") == SkillType.GEM_SKILL
    ],
    key=lambda item: item[1],
)
JEWEL_SLOTS = [
    ("friggs_agate", "Frigg's Agate"),
    ("tyrs_emerald", "Tyr's Emerald"),
    ("thors_ruby", "Thor's Ruby"),
    ("freyas_amethyst", "Freya's Amethyst"),
    ("odins_amber", "Odin's Amber"),
    ("heimdalls_sapphire", "Heimdall's Sapphire"),
]

GEAR_OPTIONS_BY_SLOT = {}
for slot_key, _ in GEAR_SLOT_ORDER:
    slot_items = [
        (gid, f"{gear.name} ({gear.rarity})")
        for gid, gear in GEAR_REGISTRY.items()
        if gear.slot == slot_key
    ]
    slot_items.sort(key=lambda x: x[1])
    GEAR_OPTIONS_BY_SLOT[slot_key] = slot_items


def _select_skill_id(label: str, options: list[tuple[str, str]], key: str, include_none: bool = True) -> str:
    ids = [sid for sid, _ in options]
    labels = [name for _, name in options]
    if include_none:
        ids = [""] + ids
        labels = ["None"] + labels
    selected_label = st.selectbox(label, labels, key=key)
    return ids[labels.index(selected_label)]


def _hero_block(side_key: str, hero_idx: int, hero_title: str) -> dict:
    st.markdown(f"**{hero_title}**")
    hero_name = st.selectbox(
        f"{hero_title} Hero",
        HERO_OPTIONS,
        key=f"{side_key}_h{hero_idx}_hero",
    )

    c1, c2 = st.columns(2)
    with c1:
        plugin_1 = _select_skill_id(
            "Plugin Skill 1",
            PLUGIN_SKILLS,
            key=f"{side_key}_h{hero_idx}_plugin1",
        )
    with c2:
        plugin_2 = _select_skill_id(
            "Plugin Skill 2",
            PLUGIN_SKILLS,
            key=f"{side_key}_h{hero_idx}_plugin2",
        )

    c3, c4 = st.columns(2)
    with c3:
        mount_1 = _select_skill_id(
            "Mount Skill 1",
            MOUNT_SKILLS,
            key=f"{side_key}_h{hero_idx}_mount1",
        )
    with c4:
        mount_2 = _select_skill_id(
            "Mount Skill 2",
            MOUNT_SKILLS,
            key=f"{side_key}_h{hero_idx}_mount2",
        )

    st.caption("Gear")
    gear_cfg = {}
    gear_cols = st.columns(len(GEAR_SLOT_ORDER))
    for col, (slot_key, slot_name) in zip(gear_cols, GEAR_SLOT_ORDER):
        with col:
            selected_gear = _select_skill_id(
                slot_name,
                GEAR_OPTIONS_BY_SLOT.get(slot_key, []),
                key=f"{side_key}_h{hero_idx}_gear_{slot_key}",
            )
            if selected_gear:
                gear_cfg[slot_key] = selected_gear

    preset = HERO_PRESETS.get(hero_name.lower(), {})
    return {
        "hero_name_or_preset": hero_name,
        "talent_ids": list(preset.get("talents", [])),
        "base_skill_ids": list(preset.get("base_skills", [])),
        "plugin_skill_ids": [sid for sid in [plugin_1, plugin_2] if sid],
        "mount_skill_ids": [sid for sid in [mount_1, mount_2] if sid],
        "gear_ids": gear_cfg,
    }


def _army_block(title: str, side_key: str, defaults: dict) -> dict:
    st.header(title)
    army_name = st.text_input("Army Name", value=defaults["army_name"], key=f"{side_key}_army_name")
    troop_count = st.number_input("Troop Count", value=defaults["count"], step=1000, key=f"{side_key}_count")
    troop_type = st.selectbox("Troop Type", ["archers", "infantry", "pikemen"], key=f"{side_key}_unit")

    s1, s2, s3 = st.columns(3)
    with s1:
        atk_mod = st.number_input("ATK Modifier", value=float(defaults["atk_mod"]), step=0.1, key=f"{side_key}_atk")
    with s2:
        def_mod = st.number_input("DEF Modifier", value=float(defaults["def_mod"]), step=0.1, key=f"{side_key}_def")
    with s3:
        hp_mod = st.number_input("HP Modifier", value=float(defaults["hp_mod"]), step=0.1, key=f"{side_key}_hp")

    st.markdown("**Bonus Stats**")
    b1, b2, b3, b4 = st.columns(4)
    with b1:
        bonus_damage = st.number_input("Damage Boost (All)", value=0.0, step=0.01, key=f"{side_key}_bonus_damage")
        bonus_heal = st.number_input("Heal Boost", value=0.0, step=0.01, key=f"{side_key}_bonus_heal")
    with b2:
        bonus_reduction = st.number_input("Damage Reduction (All)", value=0.0, step=0.01, key=f"{side_key}_bonus_reduction")
        bonus_shield = st.number_input("Shield Gain", value=0.0, step=0.01, key=f"{side_key}_bonus_shield")
    with b3:
        bonus_basic = st.number_input("Basic Boost", value=0.0, step=0.01, key=f"{side_key}_bonus_basic")
        bonus_counter = st.number_input("Counter Boost", value=0.0, step=0.01, key=f"{side_key}_bonus_counter")
    with b4:
        bonus_rage_skill = st.number_input("Rage Skill Boost", value=0.0, step=0.01, key=f"{side_key}_bonus_rage_skill")

    bonus_stats = {
        "damage_boost": {"all": bonus_damage},
        "damage_reduction": {"all": bonus_reduction},
        "heal_boost": bonus_heal,
        "shield_gain": bonus_shield,
        "basic_boost": bonus_basic,
        "counter_boost": bonus_counter,
        "rage_skill_boost": bonus_rage_skill,
    }

    with st.expander("Primary Hero", expanded=True):
        hero_1 = _hero_block(side_key, 1, "Primary")
    with st.expander("Secondary Hero", expanded=True):
        hero_2 = _hero_block(side_key, 2, "Secondary")

    with st.expander("Jewel Skills", expanded=False):
        gem_skills = {}
        for slot_key, slot_label in JEWEL_SLOTS:
            sid = _select_skill_id(
                slot_label,
                JEWEL_SKILLS,
                key=f"{side_key}_jewel_{slot_key}",
            )
            if sid:
                gem_skills[slot_key] = sid

    return {
        "army_name": army_name,
        "unit_type": troop_type,
        "tier": 7,
        "count": int(troop_count),
        "atk_mod": float(atk_mod),
        "def_mod": float(def_mod),
        "hp_mod": float(hp_mod),
        "is_rally": False,
        "unrevivable_ratio": 0.65,
        "use_dynamic_unrevivable_ratio": True,
        "heroes": [hero_1, hero_2],
        "gem_skills": gem_skills,
        "bonus_stats": bonus_stats,
    }


def _skill_rows_for_army(army) -> list[dict]:
    rows = []
    for skill_id, casts in sorted(army.skill_trigger_counts.items(), key=lambda x: x[0]):
        skill_name = SKILL_REGISTRY_GLOBAL.get(skill_id, {}).get("name", skill_id)
        rows.append(
            {
                "skill_name": skill_name,
                "casts": int(casts),
                "damage": int(round(army.skill_damage_totals.get(skill_id, 0.0))),
                "kills": int(round(army.skill_kill_totals.get(skill_id, 0.0))),
                "healing": int(round(army.skill_heal_totals.get(skill_id, 0.0))),
                "shield": int(round(army.skill_shield_totals.get(skill_id, 0.0))),
                "rage": int(round(army.skill_rage_totals.get(skill_id, 0.0))),
            }
        )
    return rows


def _build_overall_performance_html(sim: GameSimulator) -> str:
    army_data = []
    for army in [sim.army1, sim.army2]:
        army_data.append(
            {
                "name": army.name,
                "final_troops": int(round(army.current_troop_count)),
                "unrevivable": int(round(army.unrevivable_troops)),
                "skill_rows": _skill_rows_for_army(army),
            }
        )

    winner = "Draw"
    if sim.army1.current_troop_count > sim.army2.current_troop_count:
        winner = sim.army1.name
    elif sim.army2.current_troop_count > sim.army1.current_troop_count:
        winner = sim.army2.name

    def render_rows(rows: list[dict]) -> str:
        if not rows:
            return "<tr><td colspan='7'>No skill metrics recorded.</td></tr>"
        return "".join(
            "<tr>"
            f"<td>{html.escape(row['skill_name'])}</td>"
            f"<td>{row['casts']}</td>"
            f"<td>{row['damage']}</td>"
            f"<td>{row['kills']}</td>"
            f"<td>{row['healing']}</td>"
            f"<td>{row['shield']}</td>"
            f"<td>{row['rage']}</td>"
            "</tr>"
            for row in rows
            if row["casts"] > 0
            or row["damage"] > 0
            or row["kills"] > 0
            or row["healing"] > 0
            or row["shield"] > 0
            or row["rage"] > 0
        )

    cards = []
    for army in army_data:
        cards.append(
            "<section class='army-card'>"
            f"<h2>{html.escape(army['name'])}</h2>"
            f"<p><strong>Final Troops:</strong> {army['final_troops']:,} &nbsp;|&nbsp; <strong>Unrevivable:</strong> {army['unrevivable']:,}</p>"
            "<table><thead><tr>"
            "<th>Skill</th><th>Casts</th><th>Damage</th><th>Kills</th><th>Healing</th><th>Shield</th><th>Rage</th>"
            "</tr></thead><tbody>"
            f"{render_rows(army['skill_rows'])}"
            "</tbody></table></section>"
        )

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Overall Performance</title>
  <style>
    body {{ font-family: Arial, sans-serif; background:#0f172a; color:#e2e8f0; margin:0; padding:24px; }}
    h1 {{ margin-top:0; }}
    .summary {{ background:#1e293b; border-radius:10px; padding:16px; margin-bottom:20px; }}
    .army-card {{ background:#1e293b; border-radius:10px; padding:16px; margin-bottom:16px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th, td {{ border-bottom:1px solid #334155; padding:8px; text-align:left; font-size:14px; }}
    th {{ color:#93c5fd; }}
  </style>
</head>
<body>
  <h1>Overall Performance</h1>
  <div class=\"summary\">
    <p><strong>Winner:</strong> {html.escape(winner)}</p>
    <p><strong>Total Rounds:</strong> {int(sim.round)}</p>
  </div>
  {''.join(cards)}
</body>
</html>"""


col1, col2 = st.columns(2)
DEFAULTS = {
    "attacker": {"army_name": "Attacker", "count": 350000, "atk_mod": 3.8, "def_mod": 2.4, "hp_mod": 1.0},
    "defender": {"army_name": "Defender", "count": 350000, "atk_mod": 3.8, "def_mod": 2.4, "hp_mod": 1.0},
}

with col1:
    attacker_cfg = _army_block("Attacker", "att", DEFAULTS["attacker"])
with col2:
    defender_cfg = _army_block("Defender", "def", DEFAULTS["defender"])

st.divider()

if st.button("Run Simulation ⚔️", use_container_width=True):
    with st.spinner("The Vikings are fighting..."):
        try:
            setup_data = [attacker_cfg, defender_cfg]
            armies = create_armies_from_data(setup_data)
            sim = GameSimulator(armies[0], armies[1], track_stats=True)
            with contextlib.redirect_stdout(io.StringIO()):
                sim.simulate_battle()

            html_output = _build_overall_performance_html(sim)
            st.success("Simulation Complete!")
            st.subheader("Overall Performance HTML")
            components.html(html_output, height=700, scrolling=True)
            st.download_button(
                "Download Overall Performance HTML",
                data=html_output,
                file_name="overall_performance.html",
                mime="text/html",
                use_container_width=True,
            )
            st.code(json.dumps(setup_data, indent=2), language="json")
        except Exception as e:
            st.error(f"An error occurred: {e}")
