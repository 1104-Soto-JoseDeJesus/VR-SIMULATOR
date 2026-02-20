import contextlib
import copy
import html
import io
import json
import os
import tempfile
import time

import streamlit as st

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


DEBUG_OPTION_DEFAULTS = {
    "cooldowns_enabled": True,
    "hero_cooldowns_enabled": True,
    "plugin_cooldowns_enabled": True,
    "gem_cooldowns_enabled": True,
    "mount_cooldowns_enabled": True,
    "damage_reduction_affects_dots": True,
    "multi_heal_trig_enabled": False,
    "interval_active_cast_cooldowns_enabled": True,
    "fairness_rage_enabled": True,
    "advantage_mode": "multiplicative",
    "per_skill_cooldown_overrides": {},
    "max_rounds": None,
}


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

    with st.expander("Bonus Stats", expanded=False):
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            st.caption("Damage Boost")
            damage_all = st.number_input("Damage Boost (All)", value=0.0, step=0.01, key=f"{side_key}_damage_boost_all")
            damage_vs_archers = st.number_input("Damage Boost vs Archers", value=0.0, step=0.01, key=f"{side_key}_damage_boost_vs_archers")
            damage_vs_infantry = st.number_input("Damage Boost vs Infantry", value=0.0, step=0.01, key=f"{side_key}_damage_boost_vs_infantry")
            damage_vs_pikemen = st.number_input("Damage Boost vs Pikemen", value=0.0, step=0.01, key=f"{side_key}_damage_boost_vs_pikemen")
            damage_reactive = st.number_input("Damage Boost vs Reactive Skills", value=0.0, step=0.01, key=f"{side_key}_damage_boost_reactive")
            damage_cooperation = st.number_input("Damage Boost vs Cooperation Skills", value=0.0, step=0.01, key=f"{side_key}_damage_boost_cooperation")
            damage_command = st.number_input("Damage Boost vs Command Skills", value=0.0, step=0.01, key=f"{side_key}_damage_boost_command")
            reactive_crit_rate = st.number_input("Reactive Skill Crit Rate", value=0.0, step=0.01, key=f"{side_key}_damage_boost_reactive_crit_rate")
            cooperation_crit_rate = st.number_input("Cooperation Skill Crit Rate", value=0.0, step=0.01, key=f"{side_key}_damage_boost_cooperation_crit_rate")
            command_crit_rate = st.number_input("Command Skill Crit Rate", value=0.0, step=0.01, key=f"{side_key}_damage_boost_command_crit_rate")
        with dcol2:
            st.caption("Damage Reduction")
            reduction_all = st.number_input("Damage Reduction (All)", value=0.0, step=0.01, key=f"{side_key}_damage_reduction_all")
            reduction_vs_archers = st.number_input("Damage Reduction vs Archers", value=0.0, step=0.01, key=f"{side_key}_damage_reduction_vs_archers")
            reduction_vs_infantry = st.number_input("Damage Reduction vs Infantry", value=0.0, step=0.01, key=f"{side_key}_damage_reduction_vs_infantry")
            reduction_vs_pikemen = st.number_input("Damage Reduction vs Pikemen", value=0.0, step=0.01, key=f"{side_key}_damage_reduction_vs_pikemen")
            reduction_reactive = st.number_input("Damage Reduction vs Reactive Skills", value=0.0, step=0.01, key=f"{side_key}_damage_reduction_reactive")
            reduction_cooperation = st.number_input("Damage Reduction vs Cooperation Skills", value=0.0, step=0.01, key=f"{side_key}_damage_reduction_cooperation")
            reduction_command = st.number_input("Damage Reduction vs Command Skills", value=0.0, step=0.01, key=f"{side_key}_damage_reduction_command")

        ecol1, ecol2, ecol3 = st.columns(3)
        with ecol1:
            shield_gain = st.number_input("Shield Gain", value=0.0, step=0.01, key=f"{side_key}_shield_gain")
            heal_boost = st.number_input("Heal Boost", value=0.0, step=0.01, key=f"{side_key}_heal_boost")
            basic_boost = st.number_input("Basic Boost", value=0.0, step=0.01, key=f"{side_key}_basic_boost")
            counter_boost = st.number_input("Counter Boost", value=0.0, step=0.01, key=f"{side_key}_counter_boost")
            reactive_skill_boost = st.number_input("Reactive Skill Boost", value=0.0, step=0.01, key=f"{side_key}_reactive_skill_boost")
        with ecol2:
            burn_boost = st.number_input("Burn Boost", value=0.0, step=0.01, key=f"{side_key}_burn_boost")
            poison_boost = st.number_input("Poison Boost", value=0.0, step=0.01, key=f"{side_key}_poison_boost")
            lacerate_boost = st.number_input("Lacerate Boost", value=0.0, step=0.01, key=f"{side_key}_lacerate_boost")
            bleed_boost = st.number_input("Bleed Boost", value=0.0, step=0.01, key=f"{side_key}_bleed_boost")
        with ecol3:
            rage_skill_boost = st.number_input("Rage Skill Boost", value=0.0, step=0.01, key=f"{side_key}_rage_skill_boost")
            hero1_rage_skill_boost = st.number_input("Main Hero Rage Skill Boost", value=0.0, step=0.01, key=f"{side_key}_hero1_rage_skill_boost")
            hero2_rage_skill_boost = st.number_input("Secondary Hero Rage Skill Boost", value=0.0, step=0.01, key=f"{side_key}_hero2_rage_skill_boost")
            cooperation_skill_boost = st.number_input("Cooperation Skill Boost", value=0.0, step=0.01, key=f"{side_key}_cooperation_skill_boost")
            command_skill_boost = st.number_input("Command Skill Boost", value=0.0, step=0.01, key=f"{side_key}_command_skill_boost")

    bonus_stats = {
        "damage_boost": {
            "all": damage_all,
            "vs_archers": damage_vs_archers,
            "vs_infantry": damage_vs_infantry,
            "vs_pikemen": damage_vs_pikemen,
            "reactive": damage_reactive,
            "cooperation": damage_cooperation,
            "command": damage_command,
            "reactive_crit_rate": reactive_crit_rate,
            "cooperation_crit_rate": cooperation_crit_rate,
            "command_crit_rate": command_crit_rate,
        },
        "damage_reduction": {
            "all": reduction_all,
            "vs_archers": reduction_vs_archers,
            "vs_infantry": reduction_vs_infantry,
            "vs_pikemen": reduction_vs_pikemen,
            "reactive": reduction_reactive,
            "cooperation": reduction_cooperation,
            "command": reduction_command,
        },
        "shield_gain": shield_gain,
        "burn_boost": burn_boost,
        "poison_boost": poison_boost,
        "lacerate_boost": lacerate_boost,
        "bleed_boost": bleed_boost,
        "heal_boost": heal_boost,
        "basic_boost": basic_boost,
        "counter_boost": counter_boost,
        "reactive_skill_boost": reactive_skill_boost,
        "rage_skill_boost": rage_skill_boost,
        "hero1_rage_skill_boost": hero1_rage_skill_boost,
        "hero2_rage_skill_boost": hero2_rage_skill_boost,
        "cooperation_skill_boost": cooperation_skill_boost,
        "command_skill_boost": command_skill_boost,
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
    damage_map = getattr(army, "skill_damage_totals", {}) or {}
    rows = []
    for skill_id, casts in sorted(army.skill_trigger_counts.items(), key=lambda x: x[0]):
        skill_name = SKILL_REGISTRY_GLOBAL.get(skill_id, {}).get("name", skill_id)
        rows.append(
            {
                "skill_name": skill_name,
                "casts": int(casts),
                "damage": int(round(damage_map.get(skill_id, 0.0))),
                "kills": int(round(army.skill_kill_totals.get(skill_id, 0.0))),
                "healing": int(round(army.skill_heal_totals.get(skill_id, 0.0))),
                "shield": int(round(army.skill_shield_totals.get(skill_id, 0.0))),
                "rage": int(round(army.skill_rage_totals.get(skill_id, 0.0))),
            }
        )
    return rows


def _build_overall_performance_html(sim: GameSimulator) -> str:
    setup_data = getattr(st.session_state, "_latest_setup_data", None) or []
    if setup_data:
        try:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            from PyQt6 import QtWidgets
            from vr_game_sim.gui_main import MainWindow, build_skill_summaries

            _app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
            window = MainWindow()
            summary = build_skill_summaries([sim.army1, sim.army2], setup_data)
            winner = 0
            if sim.army1.current_troop_count > sim.army2.current_troop_count:
                winner = 1
            elif sim.army2.current_troop_count > sim.army1.current_troop_count:
                winner = 2

            hist_dir = os.path.join(os.path.dirname(__file__), "vr_game_sim", "histograms")
            histograms = []
            if os.path.isdir(hist_dir):
                histograms = [
                    os.path.join(hist_dir, name)
                    for name in sorted(os.listdir(hist_dir))
                    if name.lower().endswith(".png")
                ]

            window._last_simulation_payload = {
                "report_text": getattr(getattr(sim, "report_builder", None), "get_report_text", lambda: "")(),
                "rounds": copy.deepcopy(getattr(getattr(sim, "report_builder", None), "get_rounds", lambda: [])()),
                "summary": copy.deepcopy(summary),
                "win_rate": 1.0 if winner == 1 else 0.0,
                "runs": 1,
                "best_match": {"winner": winner, "summary": copy.deepcopy(summary)},
                "setup": [copy.deepcopy(cfg) for cfg in setup_data],
                "histograms": histograms,
                "generated_at": time.time(),
                "army_names": [sim.army1.name or "Army 1", sim.army2.name or "Army 2"],
                "cooldown_settings": {"hero": True, "plugin": True, "gem": True, "mount": True},
            }

            with tempfile.TemporaryDirectory(prefix="vr_web_export_") as tmp_dir:
                out_path = os.path.join(tmp_dir, "overall_performance.html")
                original_get_save = QtWidgets.QFileDialog.getSaveFileName
                try:
                    QtWidgets.QFileDialog.getSaveFileName = staticmethod(
                        lambda *args, **kwargs: (out_path, "HTML Files (*.html)")
                    )
                    window._export_summary_html(
                        include_sample_details=True,
                        include_sample_log=True,
                        dialog_title="Export Overall Performance & Sample Battle HTML",
                        filename_suffix="overall_performance_sample",
                        debug_mode=False,
                    )
                finally:
                    QtWidgets.QFileDialog.getSaveFileName = original_get_save
                if os.path.exists(out_path):
                    return open(out_path, "r", encoding="utf-8").read()
            window.close()
        except Exception:
            pass

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

st.subheader("Simulation Debug Options (1v1 / Duel parity)")
d1, d2, d3 = st.columns(3)
with d1:
    hero_cooldowns_enabled = st.checkbox("Hero Cooldowns Enabled", value=DEBUG_OPTION_DEFAULTS["hero_cooldowns_enabled"])
    plugin_cooldowns_enabled = st.checkbox("Plugin Cooldowns Enabled", value=DEBUG_OPTION_DEFAULTS["plugin_cooldowns_enabled"])
    gem_cooldowns_enabled = st.checkbox("Gem Cooldowns Enabled", value=DEBUG_OPTION_DEFAULTS["gem_cooldowns_enabled"])
    mount_cooldowns_enabled = st.checkbox("Mount Cooldowns Enabled", value=DEBUG_OPTION_DEFAULTS["mount_cooldowns_enabled"])
with d2:
    damage_reduction_affects_dots = st.checkbox(
        "Damage Reduction Affects DoTs",
        value=DEBUG_OPTION_DEFAULTS["damage_reduction_affects_dots"],
    )
    multi_heal_trig_enabled = st.checkbox("Multi-Heal Trigger Enabled", value=DEBUG_OPTION_DEFAULTS["multi_heal_trig_enabled"])
    interval_active_cast_cooldowns_enabled = st.checkbox(
        "Interval Active Cast Cooldowns Enabled",
        value=DEBUG_OPTION_DEFAULTS["interval_active_cast_cooldowns_enabled"],
    )
    fairness_rage_enabled = st.checkbox("Fairness Rage Enabled", value=DEBUG_OPTION_DEFAULTS["fairness_rage_enabled"])
with d3:
    advantage_mode = st.selectbox("Troop Advantage Mode", ["multiplicative", "additive", "off"], index=0)
    limit_rounds = st.checkbox("Set Max Rounds", value=False)
    max_rounds = st.number_input("Max Rounds", min_value=1, value=120, step=1, disabled=not limit_rounds)

per_skill_overrides_text = st.text_area(
    "Per-Skill Cooldown Overrides (JSON map of skill_id -> true/false)",
    value="{}",
    height=110,
)

per_skill_cooldown_overrides: dict[str, bool] = {}
if per_skill_overrides_text.strip():
    try:
        parsed_overrides = json.loads(per_skill_overrides_text)
        if isinstance(parsed_overrides, dict):
            per_skill_cooldown_overrides = {
                str(k): bool(v)
                for k, v in parsed_overrides.items()
            }
        else:
            st.warning("Per-skill cooldown overrides must be a JSON object. Falling back to empty map.")
    except json.JSONDecodeError:
        st.warning("Invalid JSON in per-skill overrides. Falling back to empty map.")

sim_debug_settings = {
    "cooldowns_enabled": hero_cooldowns_enabled,
    "hero_cooldowns_enabled": hero_cooldowns_enabled,
    "plugin_cooldowns_enabled": plugin_cooldowns_enabled,
    "gem_cooldowns_enabled": gem_cooldowns_enabled,
    "mount_cooldowns_enabled": mount_cooldowns_enabled,
    "damage_reduction_affects_dots": damage_reduction_affects_dots,
    "multi_heal_trig_enabled": multi_heal_trig_enabled,
    "interval_active_cast_cooldowns_enabled": interval_active_cast_cooldowns_enabled,
    "fairness_rage_enabled": fairness_rage_enabled,
    "advantage_mode": advantage_mode,
    "per_skill_cooldown_overrides": per_skill_cooldown_overrides,
}

battle_count = st.number_input("Battle Count", min_value=1, value=300, step=1)


if st.button("Run Simulation ⚔️", use_container_width=True):
    with st.spinner("The Vikings are fighting..."):
        try:
            setup_data = [attacker_cfg, defender_cfg]
            st.session_state["_latest_setup_data"] = setup_data
            attacker_wins = 0
            defender_wins = 0
            sim = None

            for _ in range(int(battle_count)):
                armies = create_armies_from_data(setup_data)
                sim = GameSimulator(armies[0], armies[1], track_stats=True, **sim_debug_settings)
                with contextlib.redirect_stdout(io.StringIO()):
                    sim.simulate_battle(max_rounds=int(max_rounds) if limit_rounds else None)

                if sim.army1.current_troop_count > sim.army2.current_troop_count:
                    attacker_wins += 1
                elif sim.army2.current_troop_count > sim.army1.current_troop_count:
                    defender_wins += 1

            if sim is None:
                raise RuntimeError("Simulation failed to produce results")

            html_output = _build_overall_performance_html(sim)
            st.subheader("Win Rates")
            st.write(f"{attacker_cfg['army_name']}: {(attacker_wins / battle_count) * 100:.2f}%")
            st.write(f"{defender_cfg['army_name']}: {(defender_wins / battle_count) * 100:.2f}%")
            st.download_button(
                "Download Overall Performance HTML",
                data=html_output,
                file_name="overall_performance.html",
                mime="text/html",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"An error occurred: {e}")
