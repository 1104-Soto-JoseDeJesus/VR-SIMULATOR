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
import random
from dataclasses import dataclass, field
from math import atan2, cos, sin, hypot, pi, degrees, radians
from typing import Any, Callable, Dict, List, Optional, Tuple

from .army_composition import Army
from .game_simulator import GameSimulator
from .enums import SkillTriggerType
from .battlefield_report_builder import BattlefieldReportBuilder


# Minimum centre-to-centre separation at which armies begin fighting.  Using a
# module level constant allows tests and other modules to align their
# expectations with the engine's behaviour.
#
# Battlefield mode now operates on a wider engagement radius and allows
# attackers to circle around a defender.  ``ENGAGEMENT_DISTANCE`` therefore
# acts as the radius of the combat ring rather than a mere straight-line
# separation.
ENGAGEMENT_DISTANCE: float = 70.0
_ARC_PUSH_SPEED: float = 20.0  # speed in units/s when sliding around radius
_ENGAGE_EPS: float = 0.01  # small tolerance for floating point comparisons


@dataclass
class _ArmyContext:
    """Container storing metadata about an army within the battlefield."""

    army: Army
    team: str
    position: Tuple[float, float] = (0.0, 0.0)
    path: List[Tuple[float, float]] = field(default_factory=list)
    path_start: Optional[Tuple[float, float]] = None
    speed: float = 50.0
    # Name of the army this one is directly targeting.
    direct_target: Optional[str] = None
    # Whether the army should actively pursue its target.
    pursue_target: bool = False
    # Per-attacker round counter which tracks only when recently engaged.
    internal_round: int = 0
    # Timestamp of the last round this army actually fought in.
    last_engaged_time: float = field(default=float('-inf'))
    # Timestamp when this army entered its current engagement.  Used to order
    # attackers around the engagement radius.
    engaged_at: float = 0.0
    # When an army needs to slide along the engagement radius to make room for
    # others these fields describe the target angle and movement direction
    # (``+1`` for anti-clockwise, ``-1`` for clockwise).  A ``None`` target
    # indicates no pending repositioning.
    arc_target_angle: Optional[float] = None
    arc_direction: int = 0


class BattlefieldEngine:
    """Coordinates multiple :class:`Army` objects on a battlefield.

    The engine focuses on orchestration rather than on the intricate combat
    mechanics which continue to be handled by :class:`GameSimulator` instances.
    Each direct engagement between two armies spawns one simulator.  Because
    the same :class:`Army` objects are passed to simulators any state changes of
    a defender are automatically visible to all attackers.
    """

    def __init__(self, report_builder: Optional[BattlefieldReportBuilder] = None) -> None:
        # Registry of armies keyed by name.
        self._armies: Dict[str, _ArmyContext] = {}

        # Team level shared effects.  Every army joining a team receives these
        # effects immediately.
        self._team_effects: Dict[str, List] = defaultdict(list)

        # Mapping of (attacker, defender) -> GameSimulator
        self._engagements: Dict[Tuple[str, str], GameSimulator] = {}

        # Optional report builder aggregating per-engagement logs
        self._report_builder = report_builder

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
    # Reset
    # ------------------------------------------------------------------
    def reset(self, report_builder: Optional[BattlefieldReportBuilder] = None) -> None:
        """Reset the engine state and global clock.

        Parameters
        ----------
        report_builder:
            Optional new :class:`BattlefieldReportBuilder` to associate with the
            engine.  If omitted the existing builder is cleared.
        """

        self._armies.clear()
        self._team_effects.clear()
        self._engagements.clear()
        self._pending_engagements.clear()
        self._graph.clear()
        self._round_accumulator = 0.0
        self._sub_accumulator = 0.0
        self.time_elapsed = 0.0
        self._state_cache.clear()
        self._pending_state_updates.clear()
        self._report_builder = report_builder

    # ------------------------------------------------------------------
    # Army management
    # ------------------------------------------------------------------
    def add_army(self, army: Army, team: str, *, position: Tuple[float, float] = (0.0, 0.0),
                 speed: float = 50.0, shared_effects: Optional[List] = None) -> None:
        """Register ``army`` on the battlefield.

        ``shared_effects`` – if provided – are added to the team's shared effect
        pool and applied to all current members of the team.
        """
        # Armies are keyed by their name inside the engine.  Previously adding
        # a second army with an identical name would silently overwrite the
        # existing entry which effectively "removed" the first army.  This made
        # it appear as if only a single army could be registered per team when
        # default names were used.  To prevent this confusing behaviour we now
        # explicitly guard against duplicate names and raise a ``ValueError``
        # instead of overwriting existing entries.

        if army.name in self._armies:
            raise ValueError(f"Army with name '{army.name}' already exists")

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
            ctx = self._armies[army_name]
            ctx.path = list(path)
            ctx.path_start = ctx.position

    def _auto_select_closest_enemy(self, army_name: str) -> None:
        """Retarget ``army_name`` to the closest enemy if available."""
        ctx = self._armies.get(army_name)
        if ctx is None:
            return
        ax, ay = ctx.position
        attackers: List[str] = []
        enemies: List[Tuple[float, str]] = []
        for name, other in self._armies.items():
            if other.team == ctx.team or other.army.current_troop_count <= 0:
                continue
            if other.direct_target == army_name:
                attackers.append(name)
            dist = hypot(other.position[0] - ax, other.position[1] - ay)
            enemies.append((dist, name))
        target: Optional[str]
        if attackers:
            target = random.choice(attackers)
        elif enemies:
            min_dist = min(d for d, _ in enemies)
            candidates = [n for d, n in enemies if abs(d - min_dist) <= _ENGAGE_EPS]
            target = candidates[0]
        else:
            return
        self.set_direct_target(army_name, target)

    def _remove_army(self, name: str) -> None:
        """Remove ``name`` from the engine and clean up references."""
        ctx = self._armies.pop(name, None)
        if ctx is None:
            return
        self._graph.pop(name, None)
        for neighbours in self._graph.values():
            neighbours.discard(name)
        for key in list(self._pending_engagements.keys()):
            if name in key:
                self._pending_engagements.pop(key, None)
        lost: List[str] = []
        for other_name, other in self._armies.items():
            if other.direct_target == name:
                other.direct_target = None
                other.pursue_target = False
                other.path.clear()
                lost.append(other_name)
        self._state_cache.pop(name, None)
        self._pending_state_updates.pop(name, None)

        for other_name in lost:
            self._auto_select_closest_enemy(other_name)

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
    def set_direct_target(self, attacker: str, defender: Optional[str], *, pursue: bool = True) -> None:
        """Assign ``defender`` as the direct target for ``attacker``.

        ``defender`` may be ``None`` to clear an existing target.  Engagement
        simulators and graph links are updated to mirror this assignment.  A
        :class:`ValueError` is raised when attempting to target an army on the
        same team as the attacker.  When a defender has no current target they
        will automatically target the attacker in response.
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

        if defender is None:
            if old_target:
                rev_ctx = self._armies.get(old_target)
                if rev_ctx and rev_ctx.direct_target == attacker:
                    self._engagements.pop((old_target, attacker), None)
                    self._pending_engagements.pop((old_target, attacker), None)
                    self._graph[old_target].discard(attacker)
                    self._graph[attacker].discard(old_target)
                    rev_ctx.direct_target = None
            atk_ctx.direct_target = None
            atk_ctx.pursue_target = False
            atk_ctx.arc_target_angle = None
            atk_ctx.arc_direction = 0
            atk_ctx.engaged_at = 0.0
            return

        if defender not in self._armies:
            raise KeyError("Defender must be registered before engagement")

        def_ctx = self._armies[defender]
        if def_ctx.team == atk_ctx.team:
            raise ValueError("Cannot engage armies on the same team")

        atk_ctx.direct_target = defender
        atk_ctx.pursue_target = pursue
        atk_ctx.arc_target_angle = None
        atk_ctx.arc_direction = 0
        atk_ctx.engaged_at = 0.0

        # Compute initial path that stops ``ENGAGEMENT_DISTANCE`` units short of
        # the defender when pursuing.
        if pursue:
            ax, ay = atk_ctx.position
            dx_, dy_ = def_ctx.position
            vec_x, vec_y = dx_ - ax, dy_ - ay
            dist = hypot(vec_x, vec_y)
            if dist > 0:
                norm_x, norm_y = vec_x / dist, vec_y / dist
                target_x = dx_ - norm_x * ENGAGEMENT_DISTANCE
                target_y = dy_ - norm_y * ENGAGEMENT_DISTANCE
                if dist > ENGAGEMENT_DISTANCE:
                    atk_ctx.path = [(target_x, target_y)]
                    atk_ctx.path_start = atk_ctx.position
                else:
                    # Already within the desired distance; reposition immediately
                    atk_ctx.position = (target_x, target_y)
                    atk_ctx.path.clear()
                    atk_ctx.path_start = atk_ctx.position
            else:
                # Overlapping positions; choose arbitrary offset
                atk_ctx.position = (dx_ - ENGAGEMENT_DISTANCE, dy_)
                atk_ctx.path.clear()
                atk_ctx.path_start = atk_ctx.position
        else:
            atk_ctx.path.clear()
            atk_ctx.path_start = None

        start_time = int(self.time_elapsed) + 1
        self._pending_engagements[(attacker, defender)] = float(start_time)

        # If the defender is idle, keep them stationary until combat begins but
        # do not preemptively assign a direct target.  The first attacker to
        # actually arrive and engage will become the defender's target.
        #
        # Previously this block ran even when the defender was already moving
        # along a waypoint path which caused them to immediately stop once an
        # enemy targeted them.  By additionally checking that the defender has
        # no active path we ensure only truly idle armies are frozen in place
        # while moving armies continue towards their destination.
        if def_ctx.direct_target is None and def_ctx.team != atk_ctx.team and not def_ctx.path:
            def_ctx.pursue_target = False
            def_ctx.path.clear()

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
            self._refresh_target_waypoints()
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
    def _refresh_target_waypoints(self) -> None:
        """Update paths for armies that have a direct target.

        This recomputes the waypoint leading to the defender's current
        position minus ``ENGAGEMENT_DISTANCE`` units.  By running every
        sub‑tick attackers will continuously follow moving defenders.
        """
        for ctx in self._armies.values():
            if not ctx.direct_target or not ctx.pursue_target:
                continue
            def_ctx = self._armies.get(ctx.direct_target)
            if def_ctx is None:
                continue
            ax, ay = ctx.position
            dx, dy = def_ctx.position
            vec_x, vec_y = dx - ax, dy - ay
            dist = hypot(vec_x, vec_y)
            if dist > 0:
                norm_x, norm_y = vec_x / dist, vec_y / dist
                target_x = dx - norm_x * ENGAGEMENT_DISTANCE
                target_y = dy - norm_y * ENGAGEMENT_DISTANCE
                if dist > ENGAGEMENT_DISTANCE:
                    ctx.path = [(target_x, target_y)]
                else:
                    ctx.position = (target_x, target_y)
                    ctx.path.clear()
            else:
                ctx.position = (dx - ENGAGEMENT_DISTANCE, dy)
                ctx.path.clear()

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

        # Maintain a minimum distance of ``ENGAGEMENT_DISTANCE`` units between
        # engaged armies.
        for (atk, dfd), _ in self._engagements.items():
            atk_ctx = self._armies[atk]
            dfd_ctx = self._armies[dfd]
            ax, ay = atk_ctx.position
            dx_, dy_ = dfd_ctx.position
            vec_x, vec_y = ax - dx_, ay - dy_
            dist = hypot(vec_x, vec_y)
            if dist < ENGAGEMENT_DISTANCE:
                if dist > 0:
                    norm_x, norm_y = vec_x / dist, vec_y / dist
                else:
                    norm_x, norm_y = 1.0, 0.0
                atk_ctx.position = (
                    dx_ + norm_x * ENGAGEMENT_DISTANCE,
                    dy_ + norm_y * ENGAGEMENT_DISTANCE,
                )
                atk_ctx.path.clear()
                dfd_ctx.path.clear()

        # Reposition attackers on the engagement radius if they cluster too
        # closely in angle around their defender.  Later arrivals slide along
        # the circle to maintain at least 20 degrees separation and end up 45
        # degrees away from the unit they were crowding.
        defenders: Dict[str, List[_ArmyContext]] = defaultdict(list)
        for (atk, dfd), _ in self._engagements.items():
            defenders[dfd].append(self._armies[atk])

        for dfd, attackers in defenders.items():
            if len(attackers) < 2:
                continue
            def_ctx = self._armies[dfd]
            dx, dy = def_ctx.position
            attackers.sort(key=lambda c: c.engaged_at)
            for idx in range(1, len(attackers)):
                ctx = attackers[idx]
                if ctx.arc_target_angle is not None:
                    continue
                ax, ay = ctx.position
                curr_angle = degrees(atan2(ay - dy, ax - dx))
                curr_angle = (curr_angle + 360) % 360
                for j in range(idx):
                    other = attackers[j]
                    ox, oy = other.position
                    other_angle = degrees(atan2(oy - dy, ox - dx))
                    other_angle = (other_angle + 360) % 360
                    diff = (curr_angle - other_angle + 180) % 360 - 180
                    # ``diff`` represents how many degrees ``ctx`` sits
                    # clockwise (negative) or anti-clockwise (positive) from
                    # ``other`` based on their current centre positions. Late
                    # arrivals 5° anti-clockwise to 25° clockwise slide 45°
                    # clockwise to make room; those 5.1–25° anti-clockwise
                    # instead slide 45° anti-clockwise.

                    if -25 <= diff <= 5:
                        ctx.arc_target_angle = (other_angle - 45) % 360
                        ctx.arc_direction = -1
                        ctx.path.clear()
                        break
                    elif 5 < diff <= 25:
                        ctx.arc_target_angle = (other_angle + 45) % 360
                        ctx.arc_direction = 1
                        ctx.path.clear()
                        break

        # Progress any pending angular repositioning along the engagement
        # radius.  Combat continues while armies slide along the circle.
        angular_speed = _ARC_PUSH_SPEED / ENGAGEMENT_DISTANCE * (180 / pi)
        for ctx in self._armies.values():
            if ctx.arc_target_angle is None or not ctx.direct_target:
                continue
            def_ctx = self._armies.get(ctx.direct_target)
            if def_ctx is None:
                ctx.arc_target_angle = None
                ctx.arc_direction = 0
                continue
            dx, dy = def_ctx.position
            ax, ay = ctx.position
            curr_angle = degrees(atan2(ay - dy, ax - dx))
            curr_angle = (curr_angle + 360) % 360
            target = ctx.arc_target_angle % 360
            if ctx.arc_direction == 1:
                remaining = (target - curr_angle + 360) % 360
                if remaining == 0:
                    ctx.arc_target_angle = None
                    ctx.arc_direction = 0
                    continue
                step = min(remaining, angular_speed * dt)
                new_angle = curr_angle + step
            else:
                remaining = (curr_angle - target + 360) % 360
                if remaining == 0:
                    ctx.arc_target_angle = None
                    ctx.arc_direction = 0
                    continue
                step = min(remaining, angular_speed * dt)
                new_angle = curr_angle - step
            rad = radians(new_angle)
            ctx.position = (
                dx + cos(rad) * ENGAGEMENT_DISTANCE,
                dy + sin(rad) * ENGAGEMENT_DISTANCE,
            )
            if step == remaining:
                ctx.arc_target_angle = None
                ctx.arc_direction = 0
                ctx.path_start = ctx.position

    def _commit_rounds(self) -> None:
        """Execute a single round for all direct engagements."""
        # Retarget armies whose current target vanished before resolution.
        for name, ctx in list(self._armies.items()):
            tgt = ctx.direct_target
            if tgt and tgt not in self._armies:
                ctx.direct_target = None
                ctx.pursue_target = False
                ctx.path.clear()
                self._auto_select_closest_enemy(name)

        # Activate any pending engagements scheduled for this second.
        new_engagements: Dict[str, List[str]] = defaultdict(list)
        for (atk, dfd), start in list(self._pending_engagements.items()):
            if self.time_elapsed >= start:
                atk_ctx = self._armies.get(atk)
                if not atk_ctx or atk_ctx.direct_target != dfd:
                    # Target changed before engagement started; discard
                    self._pending_engagements.pop((atk, dfd), None)
                    continue
                def_ctx = self._armies[dfd]
                ax, ay = atk_ctx.position
                dx_, dy_ = def_ctx.position
                if hypot(ax - dx_, ay - dy_) > ENGAGEMENT_DISTANCE + _ENGAGE_EPS:
                    # Still too far away; keep engagement pending
                    continue
                rb = None
                if self._report_builder is not None:
                    rb = self._report_builder.get_builder(atk, dfd)
                simulator = GameSimulator(atk_ctx.army, def_ctx.army, rb, track_stats=False)
                self._engagements[(atk, dfd)] = simulator
                self._graph[atk].add(dfd)
                self._graph[dfd].add(atk)
                self._pending_engagements.pop((atk, dfd), None)
                atk_ctx.engaged_at = self.time_elapsed
                if def_ctx.engaged_at == 0.0:
                    def_ctx.engaged_at = self.time_elapsed
                new_engagements[dfd].append(atk)

        for dfd, attackers in new_engagements.items():
            def_ctx = self._armies[dfd]
            if def_ctx.direct_target is None or (def_ctx.direct_target, dfd) not in self._engagements:
                chosen = attackers[0]
                def_ctx.direct_target = chosen
                def_ctx.pursue_target = False
                def_ctx.path.clear()

        # Reset per-round bookkeeping so reactive/round based skills only
        # fire once across all engagements and rage gain can be tracked.
        for ctx in self._armies.values():
            army = ctx.army
            army.triggered_skills_this_round.clear()
            army.pending_hp_damage_this_round = 0.0
            army.pending_hp_healing_this_round = 0.0
            army.rage_added_this_round = 0.0
            army.base_rage_awarded_this_round = False

        unique_armies: List[Army] = []
        start_processed: set[str] = set()
        end_processed: set[str] = set()
        for key, sim in self._engagements.items():
            self._simulate_one_round(sim, start_processed, end_processed)
            atk, dfd = key
            if (
                self._report_builder is not None
                and sim.report_builder is not None
                and dfd in self._armies
            ):
                self._report_builder.record_defender_round(
                    atk,
                    dfd,
                    sim.round,
                    self._armies[dfd].internal_round + 1,
                )
            for army in (sim.army1, sim.army2):
                if army not in unique_armies:
                    unique_armies.append(army)

        for army in unique_armies:
            army.commit_pending_healing_and_damage()
            self._queue_state_update(army)

        # Emit round reports after committing damage/healing so that
        # "Damage Commitment" entries appear in the same round they belong to.
        for sim in self._engagements.values():
            if sim.report_builder:
                active_lines = sim._log_active_effects_for_report()
                sim.report_builder.emit_round(
                    sim.round,
                    sim.round_combat_actions_log,
                    sim.round_skill_triggers_log,
                    active_effects=active_lines,
                )
                sim.round_combat_actions_log.clear()
                sim.round_skill_triggers_log = {
                    sim.army1.name: [],
                    sim.army2.name: [],
                }

        to_remove: List[Tuple[str, str]] = []
        for key, sim in self._engagements.items():
            a1 = sim.army1.current_troop_count
            a2 = sim.army2.current_troop_count
            if a1 <= 0 or a2 <= 0:
                to_remove.append(key)
        for key in to_remove:
            atk, dfd = key
            self._graph[atk].discard(dfd)
            self._graph[dfd].discard(atk)
            self._engagements.pop(key, None)

        defeated = [name for name, ctx in list(self._armies.items())
                     if ctx.army.current_troop_count <= 0]
        for name in defeated:
            self._remove_army(name)

        # Update internal round counters for armies that fought recently.  The
        # actual rage gain is handled within ``_simulate_one_round`` via the
        # simulator's internal logic which mirrors the behaviour of the full
        # duel simulator.  Armies that have been idle for more than two seconds
        # lose their round progress and rage.
        for ctx in self._armies.values():
            army = ctx.army
            time_since = self.time_elapsed - ctx.last_engaged_time
            if time_since <= 2:
                ctx.internal_round += 1
                # Armies that were idle this round (no simulator processed
                # combat for them) still receive base rage during the two second
                # grace period after leaving combat.  ``last_engaged_time`` is
                # only updated when a round is actually simulated, so a smaller
                # value indicates we didn't fight this tick.
                if army.rage_added_this_round == 0 and ctx.last_engaged_time < self.time_elapsed:
                    army.current_rage += 100
                    army.rage_added_this_round += 100
                army.rage_gained_history.append(army.rage_added_this_round)
            else:
                ctx.internal_round = 0
                army.current_rage = 0.0

            self._queue_state_update(army)

    def _simulate_one_round(
        self,
        sim: GameSimulator,
        start_processed: set[str],
        end_processed: set[str],
    ) -> None:
        """Very small round simulation using :class:`GameSimulator` internals.

        ``start_processed`` and ``end_processed`` track armies that already had
        their start- or end-of-round housekeeping executed this global round.
        This ensures effects such as DoTs are only evaluated once per round even
        when an army is involved in multiple engagements simultaneously.
        """

        if sim.army1.current_troop_count <= 0 or sim.army2.current_troop_count <= 0:
            return
        sim.round += 1

        atk, dfd = sim.army1, sim.army2

        # Activate any effects queued from the previous round and decrement durations
        for army in (atk, dfd):
            if army.effects_to_activate_next_round:
                army.upcoming_effects.extend(army.effects_to_activate_next_round)
                army.effects_to_activate_next_round.clear()
            army.activate_queued_effects()
            army.decrement_effect_durations()

        # --- Start of round housekeeping & round based skill triggers ---
        for army, opponent in ((atk, dfd), (dfd, atk)):
            if army.name in start_processed:
                continue
            start_processed.add(army.name)

            if army.current_troop_count <= 0:
                continue
            army.activate_queued_effects()
            army.apply_start_of_round_rage_deductions()
            # Determine the primary opponent for non-reactive skills –
            # defenders should only aim such skills at their direct target.
            primary_opponent = opponent
            ctx = self._armies.get(army.name)
            if ctx and ctx.direct_target and ctx.direct_target in self._armies:
                primary_opponent = self._armies[ctx.direct_target].army
            army.process_periodic_effects(
                "start_of_round", opponent=primary_opponent, skip_dot_at_start=True
            )
            army.activate_queued_effects()
            sim._process_skill_triggers(
                army,
                primary_opponent,
                SkillTriggerType.CHANCE_PER_ROUND,
                event_data={"opponent_for_shield_calc": primary_opponent},
            )
            army.activate_queued_effects()

        # Queue rage skills if the threshold has been reached after start of round
        for army in (atk, dfd):
            if (
                army.current_troop_count > 0
                and army.hero1_rage_skill_id
                and not army.hero1_rage_skill_queued_this_round
                and (
                    army.hero2_rage_skill_primed_for_round is None
                    or army.hero2_rage_skill_primed_for_round != sim.round
                )
            ):
                skill_def = sim.SKILL_REGISTRY_GLOBAL.get(army.hero1_rage_skill_id)
                if skill_def and army.current_rage >= skill_def.get("rage_cost", 1000):
                    army.hero1_rage_skill_queued_this_round = True

        # Execute any queued rage skills.
        if atk.current_troop_count > 0 and dfd.current_troop_count > 0:
            atk_ctx = self._armies.get(atk.name)
            dfd_ctx = self._armies.get(dfd.name)
            if (
                atk.hero1_rage_skill_queued_this_round
                and atk_ctx
                and atk_ctx.direct_target == dfd.name
            ):
                sim._execute_rage_skills(atk, dfd, is_hero2_delayed_trigger=False)
            if (
                dfd.hero1_rage_skill_queued_this_round
                and dfd_ctx
                and dfd_ctx.direct_target == atk.name
            ):
                sim._execute_rage_skills(dfd, atk, is_hero2_delayed_trigger=False)
            if (
                atk.hero2_rage_skill_primed_for_round == sim.round
                and atk_ctx
                and atk_ctx.direct_target == dfd.name
            ):
                sim._execute_rage_skills(atk, dfd, is_hero2_delayed_trigger=True)
            if (
                dfd.hero2_rage_skill_primed_for_round == sim.round
                and dfd_ctx
                and dfd_ctx.direct_target == atk.name
            ):
                sim._execute_rage_skills(dfd, atk, is_hero2_delayed_trigger=True)

        # --- Basic attack sequences ---
        sim._process_skill_triggers(
            atk, dfd, SkillTriggerType.ON_BASIC_ATTACK,
            event_data={'opponent_for_shield_calc': dfd}
        )
        atk.activate_queued_effects()
        dfd.activate_queued_effects()
        sim._calculate_and_log_attack(atk, dfd, is_counter=False)

        if dfd.current_troop_count > 0:
            sim._process_skill_triggers(
                dfd, atk, SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
                event_data={'opponent_for_shield_calc': atk}
            )
            dfd.activate_queued_effects()
            atk.activate_queued_effects()
            sim._process_skill_triggers(
                dfd, atk, SkillTriggerType.ON_COUNTER_ATTACK,
                event_data={'opponent_for_shield_calc': atk}
            )
            dfd.activate_queued_effects()
            atk.activate_queued_effects()
            sim._calculate_and_log_attack(dfd, atk, is_counter=True)

        if (
            atk.current_troop_count > 0
            and dfd.current_troop_count > 0
            and self._armies[dfd.name].direct_target == atk.name
        ):
            sim._process_skill_triggers(
                dfd, atk, SkillTriggerType.ON_BASIC_ATTACK,
                event_data={'opponent_for_shield_calc': atk},
            )
            dfd.activate_queued_effects()
            atk.activate_queued_effects()
            sim._calculate_and_log_attack(dfd, atk, is_counter=False)

            if atk.current_troop_count > 0:
                sim._process_skill_triggers(
                    atk, dfd, SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
                    event_data={'opponent_for_shield_calc': dfd},
                )
                atk.activate_queued_effects()
                dfd.activate_queued_effects()
                sim._process_skill_triggers(
                    atk, dfd, SkillTriggerType.ON_COUNTER_ATTACK,
                    event_data={'opponent_for_shield_calc': dfd},
                )
                atk.activate_queued_effects()
                dfd.activate_queued_effects()
                sim._calculate_and_log_attack(atk, dfd, is_counter=True)


        # End of round processing and base rage gain
        for army, opponent in ((atk, dfd), (dfd, atk)):
            if army.name in end_processed:
                continue
            end_processed.add(army.name)
            if army.current_troop_count > 0:
                army.process_periodic_effects("end_of_round", opponent=opponent)
                army.activate_queued_effects()
                for eff in army.active_effects:
                    eff.applied_this_round = False

        sim._apply_base_rage_gain()
        for army in (atk, dfd):
            army.army_used_rage_skill_this_round_for_rage_gain_block = False
            army.hero1_rage_skill_cast_blocked_by_silence_this_round = False

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
