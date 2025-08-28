from __future__ import annotations

"""Aggregate battle reports for multiple engagements."""

from typing import Dict, List, Tuple, Any

from .report_builder import ReportBuilder


class BattlefieldReportBuilder:
    """Maintains :class:`ReportBuilder` instances for each engagement pair."""

    def __init__(self) -> None:
        self._builders: Dict[Tuple[str, str], ReportBuilder] = {}

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
        return {key: builder.get_rounds() for key, builder in self._builders.items()}
