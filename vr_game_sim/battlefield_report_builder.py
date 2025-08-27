from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple


class BattlefieldReportBuilder:
    """Aggregate round reports for each engagement on the battlefield.

    Each attacker/defender pair is identified by a tuple of their names. The
    builder stores a list of reports for every pair and exposes helpers to
    retrieve individual or all engagements.
    """

    def __init__(self) -> None:
        self._reports: Dict[Tuple[str, str], List[Any]] = defaultdict(list)

    def log_round(self, attacker: str, defender: str, report: Any) -> None:
        """Record a round ``report`` for the given engagement."""
        self._reports[(attacker, defender)].append(report)

    def get_engagement(self, attacker: str, defender: str) -> List[Any]:
        """Return the list of reports for ``attacker`` vs ``defender``."""
        return list(self._reports.get((attacker, defender), []))

    def get_all_engagements(self) -> Dict[Tuple[str, str], List[Any]]:
        """Return a mapping of all engagements to their reports."""
        return {pair: list(reports) for pair, reports in self._reports.items()}

    def remove_engagement(self, attacker: str, defender: str) -> None:
        """Remove all stored reports for the given engagement."""
        self._reports.pop((attacker, defender), None)
