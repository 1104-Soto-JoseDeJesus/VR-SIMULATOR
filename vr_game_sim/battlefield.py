from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple, Set

from .game_simulator import GameSimulator


class Battlefield:
    """Orchestrates engagements between armies.

    The battlefield maintains a global clock and a registry of participating
    armies grouped by team.  Engagements are represented by ``GameSimulator``
    objects which are advanced one round per call to :meth:`tick`.

    In addition to the old global round counter the battlefield now tracks a
    ``current_time`` expressed in seconds.  Armies accumulate a ``local_round``
    counter whenever they participate in combat which resets after two seconds
    of inactivity.  This is used by rage/round based skills which depend on how
    long a particular army has been continuously fighting.
    """

    def __init__(self) -> None:
        # ``current_time`` replaces the previous ``global_time`` attribute and
        # represents the number of elapsed seconds in the battle.
        self.current_time: int = 0
        self.armies: Dict[str, Any] = {}
        self.teams: Dict[str, set[str]] = defaultdict(set)
        self.engagements: Dict[Tuple[str, str], GameSimulator] = {}
        self._combat_reports: Dict[Tuple[str, str], List[Any]] = defaultdict(list)

        # Track when an engagement becomes active so that newly registered
        # fights only trigger on the *next* tick boundary.
        self._engagement_start_time: Dict[Tuple[str, str], int] = {}

        # Per army bookkeeping for local rounds and the last time the army was
        # involved in combat.
        self._local_rounds: Dict[str, int] = defaultdict(int)
        self._last_engaged_time: Dict[str, int] = {}

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
            self._engagement_start_time.pop(pair, None)

    # ------------------------------------------------------------------
    # Engagement management
    # ------------------------------------------------------------------
    def register_engagement(self, attacker_name: str, defender_name: str) -> None:
        """Create a ``GameSimulator`` for ``attacker`` vs ``defender``."""
        attacker = self.armies[attacker_name]
        defender = self.armies[defender_name]
        key = (attacker_name, defender_name)
        self.engagements[key] = GameSimulator(attacker, defender)
        # The engagement only becomes active on the next tick so that an army's
        # first action is aligned with the tick boundary.
        self._engagement_start_time[key] = self.current_time + 1

    # ------------------------------------------------------------------
    # Simulation control
    # ------------------------------------------------------------------
    def tick(self) -> None:
        """Advance ``current_time`` by one second and process engagements."""
        # Move the global clock forward.
        self.current_time += 1

        # Reset local round counters for armies that have not fought for at
        # least two seconds.
        for army_name, last_time in list(self._last_engaged_time.items()):
            if self.current_time - last_time >= 2:
                self._local_rounds[army_name] = 0

        engagements_by_defender: Dict[str, List[Tuple[str, GameSimulator]]] = defaultdict(list)
        for key, sim in self.engagements.items():
            attacker_name, defender_name = key
            start_time = self._engagement_start_time.get(key, 0)
            if self.current_time >= start_time:
                engagements_by_defender[defender_name].append((attacker_name, sim))

        engaged_this_tick: Set[str] = set()
        for defender_name, sims in engagements_by_defender.items():
            engaged_this_tick.add(defender_name)
            for attacker_name, sim in sims:
                engaged_this_tick.add(attacker_name)
                report = sim.simulate_round()
                self._combat_reports[(attacker_name, defender_name)].append(report)

        for army_name in engaged_this_tick:
            self._local_rounds[army_name] += 1
            self._last_engaged_time[army_name] = self.current_time

    # ------------------------------------------------------------------
    # Query APIs
    # ------------------------------------------------------------------
    def get_combat_report(self, attacker_name: str, defender_name: str) -> List[Any]:
        """Return the list of round reports for the attacker/defender pair."""
        return list(self._combat_reports.get((attacker_name, defender_name), []))

    def get_local_round(self, army_name: str) -> int:
        """Return the current local round counter for ``army_name``."""
        return self._local_rounds.get(army_name, 0)
