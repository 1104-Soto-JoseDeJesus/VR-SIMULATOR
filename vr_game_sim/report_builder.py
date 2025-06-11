from typing import List, Dict, Any
from tabulate import tabulate
from colorama import Fore, Style, init
import sys

try:
    from rich.table import Table
    from rich.console import Console
    from rich.text import Text
    _RICH_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    Table = None
    Console = None
    Text = None
    _RICH_AVAILABLE = False

# Track whether colorama has been initialized to avoid repeated global wrapping
_COLORAMA_INITIALIZED = False

class ReportBuilder:
    def __init__(self, use_color: bool = True, use_rich: bool = True):
        global _COLORAMA_INITIALIZED
        self.use_rich = use_rich and _RICH_AVAILABLE
        self.use_color = use_color and sys.stdout.isatty()
        if self.use_color and not _COLORAMA_INITIALIZED:
            init(autoreset=True)
            _COLORAMA_INITIALIZED = True
        self.lines: List[Any] = []

    def _c(self, text: str, color: str):
        if self.use_rich:
            if Text is not None:
                color_map = {
                    Fore.RED: "red",
                    Fore.GREEN: "green",
                    Fore.CYAN: "cyan",
                    Fore.MAGENTA: "magenta",
                    Fore.YELLOW: "yellow",
                }
                style = color_map.get(color, "")
                return Text(text, style=style)
            return text
        if self.use_color:
            return color + text + Style.RESET_ALL
        return text

    def log_active_effects(self, lines: List[str]):
        self.lines.extend(lines)

    def emit_round(self, round_num: int, combat_actions: List[Dict[str, Any]], skill_triggers: Dict[str, List[Dict[str, Any]]], active_effects: List[str] | None = None):
        self.lines.append("\n" + "=" * 40)
        self.lines.append(self._c(f"Round {round_num}", Fore.CYAN))
        if active_effects:
            self.lines.extend(active_effects)
        if combat_actions:
            if self.use_rich and Table is not None:
                table = Table()
                for h in ["Attacker", "Defender", "Type", "DMG Pot", "Absorb", "Final DMG", "Kills"]:
                    table.add_column(h)
                for a in combat_actions:
                    table.add_row(
                        a['attacker_name'],
                        a['defender_name'],
                        a['action_type'],
                        f"{a['damage_potential_hp']:.0f}",
                        f"{a['absorbed_hp']:.0f}",
                        f"{a['final_hp_damage']:.0f}",
                        str(a['potential_kills']),
                    )
                self.lines.append(table)
            else:
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
            self.lines.append(self._c(f"{army_name} Skill Triggers:", Fore.MAGENTA))
            if not triggers:
                self.lines.append("  None")
            else:
                rows = []
                for tr in triggers:
                    detail = ""
                    if 'damage_done_hp' in tr:
                        detail = self._c(f"DMG {tr['damage_done_hp']:.0f}", Fore.RED)
                    elif 'shield_hp_gained' in tr:
                        detail = self._c(f"Shield {tr['shield_hp_gained']:.0f}", Fore.GREEN)
                    rows.append([tr['skill_name'], tr['effect_description'], detail])
                if self.use_rich and Table is not None:
                    t = Table()
                    for h in ["Skill", "Effect", "Details"]:
                        t.add_column(h)
                    for r in rows:
                        t.add_row(*[str(x) for x in r])
                    self.lines.append(t)
                else:
                    self.lines.append(tabulate(rows, headers=["Skill", "Effect", "Details"], tablefmt="grid"))

    def emit_final(self, winner: str, rounds: int, army1_state: str, army2_state: str):
        self.lines.append("\n" + "=" * 40)
        self.lines.append(self._c("Battle Over", Fore.YELLOW))
        self.lines.append(self._c(f"Winner: {winner}", Fore.GREEN))
        self.lines.append(f"Total Rounds: {rounds}")
        self.lines.append(army1_state)
        self.lines.append(army2_state)

    def print_report(self):
        if self.use_rich and Console is not None:
            console = Console()
            for line in self.lines:
                console.print(line)
        else:
            print(self.get_report_text())

    def get_report_text(self) -> str:
        """Returns the full report text without printing."""
        if not self.use_rich or Console is None:
            return "\n".join(self.lines).lstrip()
        console = Console(record=True)
        for line in self.lines:
            console.print(line)
        return console.export_text().lstrip()
