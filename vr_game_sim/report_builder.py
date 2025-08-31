from typing import List, Dict, Any
from tabulate import tabulate
from colorama import Fore, Style, init
import sys
import copy

# Track whether colorama has been initialized to avoid repeated global wrapping
_COLORAMA_INITIALIZED = False

class ReportBuilder:
    def __init__(self, use_color: bool = True):
        global _COLORAMA_INITIALIZED
        self.use_color = use_color and sys.stdout.isatty()
        if self.use_color and not _COLORAMA_INITIALIZED:
            init(autoreset=True)
            _COLORAMA_INITIALIZED = True
        self.lines: List[str] = []
        self.rounds: List[Dict[str, Any]] = []

    def _c(self, text: str, color: str) -> str:
        if self.use_color:
            return color + text + Style.RESET_ALL
        return text

    def log_active_effects(self, lines: List[str]):
        self.lines.extend(lines)

    def emit_round(
        self,
        round_num: int,
        combat_actions: List[Dict[str, Any]],
        skill_triggers: Dict[str, List[Dict[str, Any]]],
        active_effects: List[str] | None = None,
    ) -> None:
        filtered_actions = [
            a for a in combat_actions
            if a.get("action_type") in ("Basic Attack", "Counter Attack")
        ]
        self.rounds.append(
            {
                "round": round_num,
                "combat_actions": copy.deepcopy(filtered_actions),
                "skill_triggers": copy.deepcopy(skill_triggers),
                "active_effects": list(active_effects) if active_effects else [],
            }
        )
        self.lines.append("\n" + "=" * 40)
        self.lines.append(self._c(f"Round {round_num}", Fore.CYAN))
        if active_effects:
            self.lines.extend(active_effects)
        if filtered_actions:
            table = tabulate(
                [
                    [
                        a['attacker_name'],
                        a['defender_name'],
                        a['action_type'],
                        f"{a['damage_potential_hp']:.0f}",
                        f"{a['absorbed_hp']:.0f}",
                        f"{a['final_hp_damage']:.0f}",
                        a['potential_kills'],
                    ]
                    for a in filtered_actions
                ],
                headers=[
                    "Attacker",
                    "Defender",
                    "Type",
                    "DMG Pot",
                    "Absorb",
                    "Final DMG",
                    "Kills",
                ],
                tablefmt="grid",
            )
            self.lines.append(table)
        else:
            self.lines.append("No combat actions.")

        for army_name, triggers in skill_triggers.items():
            self.lines.append(self._c(f"{army_name} Skill Triggers:", Fore.MAGENTA))
            if not triggers:
                self.lines.append("  None")
            else:
                rows = []
                for tr in triggers:
                    detail_parts: List[str] = []
                    if 'damage_done_hp' in tr:
                        detail_parts.append(self._c(f"DMG {tr['damage_done_hp']:.0f}", Fore.RED))
                    elif 'shield_hp_gained' in tr:
                        detail_parts.append(
                            self._c(f"Shield {tr['shield_hp_gained']:.0f}", Fore.GREEN)
                        )
                    kills = tr.get('potential_kills')
                    if kills:
                        detail_parts.append(self._c(f"Kills {kills}", Fore.YELLOW))
                    detail = ", ".join(detail_parts)
                    rows.append([tr['skill_name'], tr['effect_description'], detail])
                self.lines.append(
                    tabulate(rows, headers=["Skill", "Effect", "Details"], tablefmt="grid")
                )

    def emit_final(self, winner: str, rounds: int, army1_state: str, army2_state: str):
        self.lines.append("\n" + "=" * 40)
        self.lines.append(self._c("Battle Over", Fore.YELLOW))
        self.lines.append(self._c(f"Winner: {winner}", Fore.GREEN))
        self.lines.append(f"Total Rounds: {rounds}")
        self.lines.append(army1_state)
        self.lines.append(army2_state)

    def print_report(self):
        print(self.get_report_text())

    def get_report_text(self) -> str:
        """Returns the full report text without printing."""
        return "\n".join(self.lines).lstrip()

    def get_rounds(self) -> List[Dict[str, Any]]:
        """Return structured data for each round."""
        return self.rounds
