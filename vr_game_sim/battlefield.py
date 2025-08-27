from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple

from .game_simulator import GameSimulator


class Battlefield:
    """Orchestrates engagements between armies.

    The battlefield maintains a global clock and a registry of participating
    armies grouped by team.  Engagements are represented by ``GameSimulator``
    objects which are advanced one round per call to :meth:`tick`.
    """

    def __init__(self) -> None:
        self.global_time: int = 0
        self.armies: Dict[str, Any] = {}
        self.teams: Dict[str, set[str]] = defaultdict(set)
        self.engagements: Dict[Tuple[str, str], GameSimulator] = {}
        self._combat_reports: Dict[Tuple[str, str], List[Any]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Army management
    # ------------------------------------------------------------------
    def add_army(self, army: Any, team: str) -> None:
        """Register ``army`` to ``team`` on the battlefield."""
        self.armies[army.name] = army
        self.teams[team].add(army.name)

    def remove_army(self, army_name: str) -> None:
        """Remove an army from the battlefield and clear related engagements."""
        if army_name in self.armies:
            del self.armies[army_name]
        for members in self.teams.values():
            members.discard(army_name)

        to_remove = [pair for pair in self.engagements if army_name in pair]
        for pair in to_remove:
            del self.engagements[pair]
            self._combat_reports.pop(pair, None)

    # ------------------------------------------------------------------
    # Engagement management
    # ------------------------------------------------------------------
    def register_engagement(self, attacker_name: str, defender_name: str) -> None:
        """Create a ``GameSimulator`` for ``attacker`` vs ``defender``."""
        attacker = self.armies[attacker_name]
        defender = self.armies[defender_name]
        self.engagements[(attacker_name, defender_name)] = GameSimulator(attacker, defender)

    # ------------------------------------------------------------------
    # Simulation control
    # ------------------------------------------------------------------
    def tick(self) -> None:
        """Advance the global clock and trigger one round for each engagement."""
        self.global_time += 1

        engagements_by_defender: Dict[str, List[Tuple[str, GameSimulator]]] = defaultdict(list)
        for (attacker_name, defender_name), sim in self.engagements.items():
            engagements_by_defender[defender_name].append((attacker_name, sim))

        for defender_name, sims in engagements_by_defender.items():
            for attacker_name, sim in sims:
                report = sim.simulate_round()
                self._combat_reports[(attacker_name, defender_name)].append(report)

    # ------------------------------------------------------------------
    # Query APIs
    # ------------------------------------------------------------------
    def get_combat_report(self, attacker_name: str, defender_name: str) -> List[Any]:
        """Return the list of round reports for the attacker/defender pair."""
        return list(self._combat_reports.get((attacker_name, defender_name), []))
