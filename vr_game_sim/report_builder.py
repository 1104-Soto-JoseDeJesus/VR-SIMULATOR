from typing import List, Dict, Any
from tabulate import tabulate

class ReportBuilder:
    def __init__(self):
        self.lines: List[str] = []

    def log_active_effects(self, lines: List[str]):
        self.lines.extend(lines)

    def emit_round(self, round_num: int, combat_actions: List[Dict[str, Any]], skill_triggers: Dict[str, List[Dict[str, Any]]], active_effects: List[str] | None = None):
        self.lines.append(f"\n--- Round {round_num} ---")
        if active_effects:
            self.lines.extend(active_effects)
        if combat_actions:
            table = tabulate(
                [
                    [a['attacker_name'], a['defender_name'], a['action_type'],
                     f"{a['damage_potential_hp']:.0f}", f"{a['absorbed_hp']:.0f}",
                     f"{a['final_hp_damage']:.0f}", a['potential_kills']]
                    for a in combat_actions
                ],
                headers=["Attacker", "Defender", "Type", "DMG Pot", "Absorb", "Final DMG", "Kills"],
                tablefmt="grid"
            )
            self.lines.append(table)
        else:
            self.lines.append("No combat actions.")

        for army_name, triggers in skill_triggers.items():
            self.lines.append(f"{army_name} Skill Triggers:")
            if not triggers:
                self.lines.append("  None")
            else:
                rows = []
                for tr in triggers:
                    detail = ""
                    if 'damage_done_hp' in tr:
                        detail = f"DMG {tr['damage_done_hp']:.0f}"
                    elif 'shield_hp_gained' in tr:
                        detail = f"Shield {tr['shield_hp_gained']:.0f}"
                    rows.append([tr['skill_name'], tr['effect_description'], detail])
                self.lines.append(tabulate(rows, headers=["Skill", "Effect", "Details"], tablefmt="grid"))

    def emit_final(self, winner: str, rounds: int, army1_state: str, army2_state: str):
        self.lines.append("\n--- Battle Over ---")
        self.lines.append(f"Winner: {winner}")
        self.lines.append(f"Total Rounds: {rounds}")
        self.lines.append(army1_state)
        self.lines.append(army2_state)

    def print_report(self):
        print("\n".join(self.lines))
