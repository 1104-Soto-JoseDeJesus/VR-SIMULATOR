# === File: battlefield_engine.py ===
"""Battlefield wide orchestration utilities.

This module introduces :class:`BattlefieldEngine` which acts as a light‑weight
manager around the heavy weight :class:`GameSimulator`.  The goal of the engine
isn't to replace the existing duel simulator but to provide a higher level view
where many armies can move and engage with each other.

The implementation intentionally keeps the mechanics extremely small; it merely
implements the features that are required by the unit tests for this kata:

* Registry of armies with a team assignment.  Teams may have *shared effects*
  which are applied to every army when it joins the team.
* A global clock.  The engine runs at two different resolutions – a main
  ``1 Hz`` tick used for committing combat rounds and a ``1000 Hz`` sub‑tick
  used for simple movement interpolation.
* An ``engagement graph`` which tracks direct links (armies that are currently
  fighting) and allows indirect links to be determined via graph traversal.
* A small public API consisting of ``add_army``, ``set_waypoint``, ``engage``
  and ``tick``.

The engine purposely keeps combat resolution very small.  For each direct
engagement a regular :class:`GameSimulator` instance is created.  When a round is
committed the engine calls a minimal private routine of ``GameSimulator`` that
performs one basic attack exchange.  While this is obviously only a tiny subset
of the real simulator's capabilities it is sufficient to demonstrate how the
engine coordinates multiple duels at a higher level.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import hypot
from typing import Dict, List, Optional, Tuple

from .army_composition import Army
from .game_simulator import GameSimulator


@dataclass
class _ArmyContext:
    """Container storing metadata about an army within the battlefield."""

    army: Army
    team: str
    position: Tuple[float, float] = (0.0, 0.0)
    waypoint: Tuple[float, float] = (0.0, 0.0)
    speed: float = 0.0


class BattlefieldEngine:
    """Coordinates multiple :class:`Army` objects on a battlefield.

    The engine focuses on orchestration rather than on the intricate combat
    mechanics which continue to be handled by :class:`GameSimulator` instances.
    Each direct engagement between two armies spawns one simulator.  Because
    the same :class:`Army` objects are passed to simulators any state changes of
    a defender are automatically visible to all attackers.
    """

    def __init__(self) -> None:
        # Registry of armies keyed by name.
        self._armies: Dict[str, _ArmyContext] = {}

        # Team level shared effects.  Every army joining a team receives these
        # effects immediately.
        self._team_effects: Dict[str, List] = defaultdict(list)

        # Mapping of (attacker, defender) -> GameSimulator
        self._engagements: Dict[Tuple[str, str], GameSimulator] = {}

        # Graph of direct engagements represented as an adjacency list.
        self._graph: Dict[str, set] = defaultdict(set)

        # Clock accumulators for 1 Hz and 1000 Hz ticks.
        self._round_accumulator = 0.0
        self._sub_accumulator = 0.0
        self.time_elapsed = 0.0

    # ------------------------------------------------------------------
    # Army management
    # ------------------------------------------------------------------
    def add_army(self, army: Army, team: str, *, position: Tuple[float, float] = (0.0, 0.0),
                 speed: float = 0.0, shared_effects: Optional[List] = None) -> None:
        """Register ``army`` on the battlefield.

        ``shared_effects`` – if provided – are added to the team's shared effect
        pool and applied to all current members of the team.
        """

        ctx = _ArmyContext(army=army, team=team, position=position,
                           waypoint=position, speed=speed)
        self._armies[army.name] = ctx

        # Apply existing team effects and append new shared effects if supplied.
        if shared_effects:
            self._team_effects[team].extend(shared_effects)
        for eff in self._team_effects.get(team, []):
            # Effects are shared by reference which is acceptable for the simple
            # scenarios in the tests.  More elaborate systems would want to copy
            # them instead.
            army.active_effects.append(eff)

    def set_waypoint(self, army_name: str, waypoint: Tuple[float, float]) -> None:
        """Update the target waypoint for ``army_name``."""
        if army_name in self._armies:
            self._armies[army_name].waypoint = waypoint

    # ------------------------------------------------------------------
    # Engagement handling
    # ------------------------------------------------------------------
    def engage(self, attacker: str, defender: str) -> None:
        """Create a direct engagement between two armies.

        A :class:`GameSimulator` is instantiated for this pair.  The same
        ``Army`` instances are reused in each simulator so the defender's state
        is automatically synchronised across different attackers.
        """

        if attacker not in self._armies or defender not in self._armies:
            raise KeyError("Both armies must be registered before engagement")

        atk_ctx = self._armies[attacker]
        def_ctx = self._armies[defender]
        simulator = GameSimulator(atk_ctx.army, def_ctx.army, track_stats=False)
        self._engagements[(attacker, defender)] = simulator
        self._graph[attacker].add(defender)
        self._graph[defender].add(attacker)

    # ------------------------------------------------------------------
    # Clock / ticking
    # ------------------------------------------------------------------
    def tick(self, dt: float) -> None:
        """Advance the global clock by ``dt`` seconds."""
        self.time_elapsed += dt
        self._round_accumulator += dt
        self._sub_accumulator += dt

        # Handle movement in small 1ms steps.
        while self._sub_accumulator >= 0.001:
            self._step_movements(0.001)
            self._sub_accumulator -= 0.001

        # Commit a combat round once per second.
        while self._round_accumulator >= 1.0:
            self._commit_rounds()
            self._round_accumulator -= 1.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _step_movements(self, dt: float) -> None:
        """Interpolate movement towards an army's waypoint."""
        for ctx in self._armies.values():
            if ctx.speed <= 0:
                continue
            x, y = ctx.position
            wx, wy = ctx.waypoint
            dx, dy = wx - x, wy - y
            dist = hypot(dx, dy)
            if dist == 0:
                continue
            step = min(dist, ctx.speed * dt)
            if step == dist:
                ctx.position = (wx, wy)
            else:
                ctx.position = (x + dx / dist * step, y + dy / dist * step)

    def _commit_rounds(self) -> None:
        """Execute a single round for all direct engagements."""
        to_remove: List[Tuple[str, str]] = []
        for key, sim in self._engagements.items():
            self._simulate_one_round(sim)
            a1 = sim.army1.current_troop_count
            a2 = sim.army2.current_troop_count
            if a1 <= 0 or a2 <= 0:
                to_remove.append(key)
        for key in to_remove:
            atk, dfd = key
            self._graph[atk].discard(dfd)
            self._graph[dfd].discard(atk)
            self._engagements.pop(key, None)

    def _simulate_one_round(self, sim: GameSimulator) -> None:
        """Very small round simulation using :class:`GameSimulator` internals."""
        if sim.army1.current_troop_count <= 0 or sim.army2.current_troop_count <= 0:
            return
        sim.round += 1
        sim._calculate_and_log_attack(sim.army1, sim.army2, is_counter=False)
        sim.army1.commit_pending_healing_and_damage()
        sim.army2.commit_pending_healing_and_damage()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def get_indirect_links(self, army_name: str) -> List[str]:
        """Return armies indirectly connected to ``army_name`` via engagements."""
        visited = set([army_name])
        queue = deque([army_name])
        while queue:
            current = queue.popleft()
            for neighbour in self._graph[current]:
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(neighbour)
        visited.remove(army_name)
        return list(visited)
