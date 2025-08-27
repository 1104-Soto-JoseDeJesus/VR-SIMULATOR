from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Tuple, Set, Optional

from .game_simulator import GameSimulator
from .battlefield_report_builder import BattlefieldReportBuilder


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
        self._report_builder = BattlefieldReportBuilder()
        # Track targeting relationships and reactive skill timing.
        self.direct_targets: Dict[str, Optional[str]] = {}
        self.indirect_attackers: Dict[str, Set[str]] = defaultdict(set)
        self._last_reactive_time: Dict[str, int] = {}

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
        # initialise tracking structures for the army
        self.direct_targets.setdefault(army.name, None)
        self.indirect_attackers.setdefault(army.name, set())

    def remove_army(self, army_name: str) -> None:
        """Remove an army from the battlefield and clear related engagements."""
        if army_name in self.armies:
            del self.armies[army_name]
        for members in self.teams.values():
            members.discard(army_name)

        to_remove = [pair for pair in self.engagements if army_name in pair]
        for pair in to_remove:
            del self.engagements[pair]
            self._report_builder.remove_engagement(*pair)
            self._engagement_start_time.pop(pair, None)

        # clean up targeting information
        self.direct_targets.pop(army_name, None)
        for k, v in list(self.direct_targets.items()):
            if v == army_name:
                self.direct_targets[k] = None
        self.indirect_attackers.pop(army_name, None)
        for attackers in self.indirect_attackers.values():
            attackers.discard(army_name)
        self._last_reactive_time.pop(army_name, None)

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
        # update targeting relationships
        if self.direct_targets.get(attacker_name) is None:
            self.direct_targets[attacker_name] = defender_name
        if self.direct_targets.get(defender_name) is None:
            self.direct_targets[defender_name] = attacker_name
        elif self.direct_targets.get(defender_name) != attacker_name:
            self.indirect_attackers[defender_name].add(attacker_name)

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
            direct_attacker = self.direct_targets.get(defender_name)
            reactive_triggered = self._last_reactive_time.get(defender_name) == self.current_time
            for attacker_name, sim in sims:
                engaged_this_tick.add(attacker_name)
                if attacker_name == direct_attacker or direct_attacker is None:
                    report = sim.simulate_round()
                    self.direct_targets.setdefault(defender_name, attacker_name)
                else:
                    self.indirect_attackers[defender_name].add(attacker_name)
                    if not reactive_triggered:
                        if hasattr(sim, "simulate_reactive_round"):
                            report = sim.simulate_reactive_round()
                        else:
                            report = {}
                        self._last_reactive_time[defender_name] = self.current_time
                        reactive_triggered = True
                    else:
                        report = {}
                self._report_builder.log_round(attacker_name, defender_name, report)

        for army_name in engaged_this_tick:
            self._local_rounds[army_name] += 1
            self._last_engaged_time[army_name] = self.current_time

    # ------------------------------------------------------------------
    # Query APIs
    # ------------------------------------------------------------------
    def get_combat_report(self, attacker_name: str, defender_name: str) -> List[Any]:
        """Return the list of round reports for the attacker/defender pair."""
        return self._report_builder.get_engagement(attacker_name, defender_name)

    def get_all_combat_reports(self) -> Dict[Tuple[str, str], List[Any]]:
        """Return a mapping of all engagements to their reports."""
        return self._report_builder.get_all_engagements()

    def get_local_round(self, army_name: str) -> int:
        """Return the current local round counter for ``army_name``."""
        return self._local_rounds.get(army_name, 0)
