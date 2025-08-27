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
from typing import Any, Callable, Dict, List, Optional, Tuple

from .army_composition import Army
from .game_simulator import GameSimulator
from .enums import SkillTriggerType


@dataclass
class _ArmyContext:
    """Container storing metadata about an army within the battlefield."""

    army: Army
    team: str
    position: Tuple[float, float] = (0.0, 0.0)
    path: List[Tuple[float, float]] = field(default_factory=list)
    speed: float = 0.0
    # Name of the army this one is directly targeting.
    direct_target: Optional[str] = None
    # Per-attacker round counter which tracks only when recently engaged.
    internal_round: int = 0
    # Timestamp of the last round this army actually fought in.
    last_engaged_time: float = field(default=float('-inf'))


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

        # Pending engagements that should start on the next whole second.
        # Mapping of (attacker, defender) -> start_time
        self._pending_engagements: Dict[Tuple[str, str], float] = {}

        # Graph of direct engagements represented as an adjacency list.
        self._graph: Dict[str, set] = defaultdict(set)

        # Clock accumulators for 1 Hz and 1000 Hz ticks.
        self._round_accumulator = 0.0
        self._sub_accumulator = 0.0
        self.time_elapsed = 0.0

        # Centralised army state tracking for broadcasting between participants.
        # _state_cache stores a lightweight signature to detect changes while
        # _pending_state_updates keeps full snapshots to broadcast on the next
        # tick.  Listeners can subscribe via :meth:`add_state_listener`.
        self._state_cache: Dict[str, Tuple] = {}
        self._pending_state_updates: Dict[str, Dict[str, Any]] = {}
        self._state_listeners: List[Callable[[str, Dict[str, Any]], None]] = []

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
                           path=[], speed=speed)
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
        """Update the target waypoint for ``army_name``.

        This resets the army's path to a single waypoint.  For multi point
        paths :meth:`set_path` can be used directly.
        """
        self.set_path(army_name, [waypoint])

    def set_path(self, army_name: str, path: List[Tuple[float, float]]) -> None:
        """Assign a full waypoint ``path`` to ``army_name``."""
        if army_name in self._armies:
            self._armies[army_name].path = list(path)

    # ------------------------------------------------------------------
    # State broadcasting
    # ------------------------------------------------------------------
    def add_state_listener(self, listener: Callable[[str, Dict[str, Any]], None]) -> None:
        """Subscribe to state updates for armies.

        ``listener`` will be called with ``(army_name, state_dict)`` whenever an
        army's active effects, shield HP or rage changes.  The broadcast occurs
        before the next tick completes.
        """

        self._state_listeners.append(listener)

    def _snapshot_state(self, army: Army) -> Dict[str, Any]:
        return {
            'active_effects': list(army.active_effects),
            'shield_hp': army.get_current_shield_hp(),
            'rage': army.current_rage,
        }

    def _state_signature(self, army: Army) -> Tuple:
        effects_sig = tuple(sorted((str(e.id), round(e.magnitude, 3), e.duration)
                                   for e in army.active_effects))
        shield = round(army.get_current_shield_hp(), 3)
        rage = round(army.current_rage, 3)
        return effects_sig, shield, rage

    def _queue_state_update(self, army: Army) -> None:
        sig = self._state_signature(army)
        if self._state_cache.get(army.name) != sig:
            self._state_cache[army.name] = sig
            self._pending_state_updates[army.name] = self._snapshot_state(army)

    def _flush_state_updates(self) -> None:
        if not self._pending_state_updates:
            return
        for name, state in self._pending_state_updates.items():
            for listener in self._state_listeners:
                listener(name, state)
        self._pending_state_updates.clear()

    # ------------------------------------------------------------------
    # Engagement handling
    # ------------------------------------------------------------------
    def set_direct_target(self, attacker: str, defender: Optional[str]) -> None:
        """Assign ``defender`` as the direct target for ``attacker``.

        ``defender`` may be ``None`` to clear an existing target. Engagement
        simulators and graph links are updated to mirror this assignment.
        """

        if attacker not in self._armies:
            raise KeyError("Attacker must be registered before engagement")

        atk_ctx = self._armies[attacker]
        old_target = atk_ctx.direct_target
        if old_target:
            # Remove active engagement if one exists
            if (attacker, old_target) in self._engagements:
                self._engagements.pop((attacker, old_target), None)
                self._graph[attacker].discard(old_target)
                self._graph[old_target].discard(attacker)
            # Remove any pending engagement for the old target
            self._pending_engagements.pop((attacker, old_target), None)

        atk_ctx.direct_target = defender

        if defender is None:
            return

        if defender not in self._armies:
            raise KeyError("Defender must be registered before engagement")

        # Schedule the engagement to start on the next whole second
        start_time = int(self.time_elapsed) + 1
        self._pending_engagements[(attacker, defender)] = float(start_time)

    # Backwards compatible alias
    def engage(self, attacker: str, defender: str) -> None:
        self.set_direct_target(attacker, defender)

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

        # Push any queued defender state updates to listeners.
        self._flush_state_updates()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _step_movements(self, dt: float) -> None:
        """Interpolate movement towards the next waypoint in an army's path."""
        for ctx in self._armies.values():
            if ctx.speed <= 0 or not ctx.path:
                continue
            x, y = ctx.position
            wx, wy = ctx.path[0]
            dx, dy = wx - x, wy - y
            dist = hypot(dx, dy)
            if dist == 0:
                ctx.position = (wx, wy)
                ctx.path.pop(0)
                continue
            step = min(dist, ctx.speed * dt)
            if step == dist:
                ctx.position = (wx, wy)
                ctx.path.pop(0)
            else:
                ctx.position = (x + dx / dist * step, y + dy / dist * step)

        # Snap armies to their engaged opponents when sufficiently close.
        for (atk, dfd), _ in self._engagements.items():
            atk_ctx = self._armies[atk]
            dfd_ctx = self._armies[dfd]
            ax, ay = atk_ctx.position
            dx_, dy_ = dfd_ctx.position
            if hypot(ax - dx_, ay - dy_) <= 2:
                atk_ctx.position = dfd_ctx.position
                atk_ctx.path.clear()
                dfd_ctx.path.clear()

    def _commit_rounds(self) -> None:
        """Execute a single round for all direct engagements."""
        # Activate any pending engagements scheduled for this second.
        for (atk, dfd), start in list(self._pending_engagements.items()):
            if self.time_elapsed >= start and self._armies[atk].direct_target == dfd:
                atk_ctx = self._armies[atk]
                def_ctx = self._armies[dfd]
                simulator = GameSimulator(atk_ctx.army, def_ctx.army, track_stats=False)
                self._engagements[(atk, dfd)] = simulator
                self._graph[atk].add(dfd)
                self._graph[dfd].add(atk)
                self._pending_engagements.pop((atk, dfd), None)
            elif self.time_elapsed >= start:
                # Target changed before engagement started; discard
                self._pending_engagements.pop((atk, dfd), None)

        # Reset per-round skill and rage tracking to allow reactive skills to
        # fire once across all engagements.
        for ctx in self._armies.values():
            army = ctx.army
            army.triggered_skills_this_round.clear()
            army.pending_hp_damage_this_round = 0.0
            army.pending_hp_healing_this_round = 0.0
            army.rage_added_this_round = 0.0

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

        # Update internal rounds and grant base rage to armies that have
        # participated in combat recently (within the last 2 seconds).
        for ctx in self._armies.values():
            army = ctx.army
            time_since = self.time_elapsed - ctx.last_engaged_time
            if time_since <= 2:
                ctx.internal_round += 1
                army.current_rage += 100
                army.rage_added_this_round += 100
                army.rage_gained_history.append(army.rage_added_this_round)
            else:
                # No recent combat – reset round counter
                ctx.internal_round = 0

            self._queue_state_update(army)

    def _simulate_one_round(self, sim: GameSimulator) -> None:
        """Very small round simulation using :class:`GameSimulator` internals."""
        if sim.army1.current_troop_count <= 0 or sim.army2.current_troop_count <= 0:
            return
        sim.round += 1

        atk, dfd = sim.army1, sim.army2

        # Attacker basic attack
        sim._process_skill_triggers(atk, dfd, SkillTriggerType.ON_BASIC_ATTACK,
                                    event_data={'opponent_for_shield_calc': dfd})
        atk.activate_queued_effects()
        dfd.activate_queued_effects()
        sim._calculate_and_log_attack(atk, dfd, is_counter=False)

        if dfd.current_troop_count > 0:
            # Defender reacts to being hit and may counter attack
            sim._process_skill_triggers(dfd, atk, SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
                                        event_data={'opponent_for_shield_calc': atk})
            dfd.activate_queued_effects()
            atk.activate_queued_effects()
            sim._process_skill_triggers(dfd, atk, SkillTriggerType.ON_COUNTER_ATTACK,
                                        event_data={'opponent_for_shield_calc': atk})
            dfd.activate_queued_effects()
            atk.activate_queued_effects()
            sim._calculate_and_log_attack(dfd, atk, is_counter=True)

        atk.commit_pending_healing_and_damage()
        dfd.commit_pending_healing_and_damage()

        # Queue broadcasts for any state changes to either army.
        self._queue_state_update(atk)
        self._queue_state_update(dfd)

        # Record latest engagement time for both armies
        self._armies[atk.name].last_engaged_time = self.time_elapsed
        self._armies[dfd.name].last_engaged_time = self.time_elapsed

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
