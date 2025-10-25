"""Minimal HTML renderer for the in-game battle log export."""

from __future__ import annotations

import html
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .log_events import LogEvent
from .number_format import NumberFormat, fmt_damage, fmt_int


@dataclass
class _RoundBucket:
    number: int
    lines: List[str] = field(default_factory=list)
    header_text: Optional[str] = None


class HtmlRenderer:
    """Collects canonical log events and renders the in-game log HTML."""

    def __init__(self, assets_dir: str, number_format: NumberFormat | None = None):
        strings_path = os.path.join(assets_dir, "strings", "ingame_log_strings.en.json")
        with open(strings_path, "r", encoding="utf-8") as handle:
            self.strings: Dict[str, Any] = json.load(handle)

        tmpl_dir = os.path.join(assets_dir, "templates")
        self.template_path = os.path.join(tmpl_dir, "ingame_log_block.html")
        self.css_path = os.path.join(tmpl_dir, "ingame_log_styles.css")

        self.rounds: Dict[int, _RoundBucket] = {}
        self.nf = number_format or NumberFormat()

    def reset(self) -> None:
        """Clear any accumulated log events."""

        self.rounds.clear()

    # ------------------------------------------------------------------
    # Helpers
    def _visible(self, key: str) -> bool:
        entry = self.strings.get(key)
        return bool(entry and entry.get("visible", True))

    def _fmt(self, key: str, **kwargs: Any) -> str:
        entry = self.strings.get(key) or {}
        text = entry.get("text", "")
        return text.format(**kwargs)

    def _bucket(self, number: int, *, header_text: Optional[str] = None) -> _RoundBucket:
        bucket = self.rounds.get(number)
        if bucket is None:
            bucket = self.rounds[number] = _RoundBucket(number=number)
        if header_text is not None:
            bucket.header_text = header_text
        return bucket

    # ------------------------------------------------------------------
    def add(self, event: LogEvent) -> None:
        round_number = event.round if event.round is not None else 0
        bucket = self._bucket(round_number)

        def append_line(key: str, **kwargs: Any) -> None:
            if not self._visible(key):
                return
            rendered = html.escape(self._fmt(key, **kwargs))
            bucket.lines.append(rendered)

        if event.type == "ROUND_START":
            append_line("ROUND_START", n=round_number)
        elif event.type == "BASIC_ATTACK":
            damage = fmt_damage(event.damage or 0, self.nf)
            kills = fmt_int(int(event.kills or 0), self.nf)
            append_line(
                "BASIC_ATTACK",
                attacker=event.attacker_name,
                defender=event.defender_name,
                damage=damage,
                kills=kills,
            )
        elif event.type == "COUNTER_ATTACK":
            damage = fmt_damage(event.damage or 0, self.nf)
            append_line(
                "COUNTER_ATTACK",
                attacker=event.attacker_name,
                defender=event.defender_name,
                damage=damage,
            )
        elif event.type == "SKILL_CAST":
            damage = fmt_damage(event.damage or 0, self.nf)
            kills = fmt_int(int(event.kills or 0), self.nf)
            append_line(
                "SKILL_CAST",
                attacker=event.attacker_name,
                defender=event.defender_name,
                skill=event.skill_name,
                damage=damage,
                kills=kills,
            )
        elif event.type == "DOT_TICK":
            damage = fmt_damage(event.damage or 0, self.nf)
            append_line("DOT_TICK", defender=event.defender_name, damage=damage)
        elif event.type == "HOT_TICK":
            healed = fmt_damage(event.damage or 0, self.nf)
            append_line("HOT_TICK", target=event.target_name, damage=healed)
        elif event.type == "SHIELD_APPLIED":
            append_line("SHIELD_APPLIED", target=event.target_name, skill=event.skill_name)
        elif event.type == "SHIELD_ABSORB":
            absorbed = fmt_damage(event.absorbed or 0, self.nf)
            append_line("SHIELD_ABSORB", defender=event.defender_name, absorbed=absorbed)
        elif event.type == "EFFECT_GAINED":
            effect = event.skill_name or (event.notes or {}).get("effect")
            append_line("EFFECT_GAINED", target=event.target_name, effect=effect)
        elif event.type == "EFFECT_EXPIRED":
            effect = event.skill_name or (event.notes or {}).get("effect")
            append_line("EFFECT_EXPIRED", target=event.target_name, effect=effect)
        elif event.type == "QUEUE_PRIMARY_RAGE":
            append_line("QUEUE_PRIMARY_RAGE", attacker=event.attacker_name)
        elif event.type == "RAGE_CLEARED":
            append_line("RAGE_CLEARED")
        elif event.type == "KILLS_APPLIED":
            kills = fmt_int(int(event.kills or 0), self.nf)
            append_line("KILLS_APPLIED", defender=event.defender_name, kills=kills)
        elif event.type == "ROUND_END":
            append_line("ROUND_END", n=round_number)
        elif event.type == "BATTLE_END":
            if self._visible("BATTLE_END"):
                summary_bucket = self._bucket(10_000_000, header_text="Battle Summary")
                rendered = html.escape(
                    self._fmt(
                        "BATTLE_END",
                        winner=event.winner,
                        rounds=event.rounds_total,
                    )
                )
                summary_bucket.lines.append(rendered)
        elif event.type == "BATTLE_START":
            append_line("BATTLE_START")
        else:  # pragma: no cover - defensive path
            return

    # ------------------------------------------------------------------
    def _iter_rounds(self) -> Iterable[_RoundBucket]:
        for key in sorted(self.rounds.keys()):
            if key == 0:
                continue
            yield self.rounds[key]

    def render(self) -> str:
        lines: List[str] = ["<div class=\"ingame-log\" data-version=\"1\">"]
        for bucket in self._iter_rounds():
            lines.append("  <div class=\"round\">")
            header = bucket.header_text or f"Round {bucket.number}"
            lines.append(f"      <div class=\"round-header\">{header}</div>")
            lines.append("      <ul class=\"round-lines\">")
            for entry in bucket.lines:
                lines.append(f"        <li class=\"log-line\">{entry}</li>")
            lines.append("      </ul>")
            lines.append("    </div>")
        lines.append("</div>")
        return "\n".join(lines)

    def render_styles(self) -> str:
        with open(self.css_path, "r", encoding="utf-8") as handle:
            return handle.read()
