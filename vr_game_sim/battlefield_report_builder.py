from __future__ import annotations

"""Aggregate battle reports for multiple engagements."""

from typing import Dict, List, Tuple, Any
from collections import defaultdict

from .report_builder import ReportBuilder


class BattlefieldReportBuilder:
    """Maintains :class:`ReportBuilder` instances for each engagement pair."""

    def __init__(self) -> None:
        self._builders: Dict[Tuple[str, str], ReportBuilder] = {}
        self._defender_rounds: Dict[Tuple[str, str], Dict[int, int]] = defaultdict(dict)

    def get_builder(self, attacker: str, defender: str) -> ReportBuilder:
        """Return a :class:`ReportBuilder` for ``attacker`` vs ``defender``."""
        key = (attacker, defender)
        if key not in self._builders:
            # GUI rendering prefers plain text; disable colour by default
            self._builders[key] = ReportBuilder(use_color=False)
        return self._builders[key]

    def get_reports(self) -> Dict[Tuple[str, str], str]:
        """Return aggregated text reports keyed by engagement pair."""
        return {key: builder.get_report_text() for key, builder in self._builders.items()}

    def get_rounds(self) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
        """Return structured round data keyed by engagement pair."""
        return {
            key: [
                {
                    **round_data,
                    "defender_global_round": self._defender_rounds.get(key, {}).get(
                        round_data.get("round")
                    ),
                }
                for round_data in builder.get_rounds()
            ]
            for key, builder in self._builders.items()
        }

    def record_defender_round(
        self, attacker: str, defender: str, local_round: int, defender_round: int
    ) -> None:
        """Record mapping of local round to defender's global round."""
        key = (attacker, defender)
        self._defender_rounds[key][local_round] = defender_round
