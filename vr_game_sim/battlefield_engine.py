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
from .constants import EFFECT_NAME_DISARM_DEBUFF


# Minimum centre-to-centre separation at which armies begin fighting.  Using a
# module level constant allows tests and other modules to align their
# expectations with the engine's behaviour.
#
# Battlefield mode now operates on a wider engagement radius and allows
# attackers to circle around a defender.  ``ENGAGEMENT_DISTANCE`` therefore
# acts as the radius of the combat ring rather than a mere straight-line
# separation.
ENGAGEMENT_DISTANCE: float = 60.0
_ARC_PUSH_SPEED: float = 25.0  # speed in units/s when sliding around radius
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
    # Original movement speed used to restore after temporary boosts.
    base_speed: float = 50.0
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
    # Flag indicating whether passive effects have been reset during the
    # current idle period.  Prevents repeated reapplication of passive skills
    # while an army remains out of combat.
    idle_reset_done: bool = False


class BattlefieldEngine:
    """Coordinates multiple :class:`Army` objects on a battlefield.

    The engine focuses on orchestration rather than on the intricate combat
    mechanics which continue to be handled by :class:`GameSimulator` instances.
    Each direct engagement between two armies spawns one simulator.  Because
    the same :class:`Army` objects are passed to simulators any state changes of
    a defender are automatically visible to all attackers.
    """

    def __init__(
        self,
        report_builder: Optional[BattlefieldReportBuilder] = None,
        mode: str = "battlefield",
    ) -> None:
        # Registry of armies keyed by name.
        self._armies: Dict[str, _ArmyContext] = {}

        # Team level shared effects.  Every army joining a team receives these
        # effects immediately.
        self._team_effects: Dict[str, List] = defaultdict(list)

        # Mapping of (attacker, defender) -> GameSimulator
        self._engagements: Dict[Tuple[str, str], GameSimulator] = {}
        self.mode = mode

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

    def get_engaged_enemies(self, army_name: str) -> List[Army]:
        """Return list of armies currently engaged with ``army_name``."""
        return [self._armies[nm].army for nm in self._graph.get(army_name, set()) if nm in self._armies]

    def get_direct_attackers(self, army_name: str) -> List[Army]:
        """Return armies whose direct target is ``army_name``."""
        return [ctx.army for ctx in self._armies.values() if ctx.direct_target == army_name]

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
                           path=[], speed=speed, base_speed=speed)
        self._armies[army.name] = ctx

        # Apply existing team effects and append new shared effects if supplied.
        if shared_effects:
            self._team_effects[team].extend(shared_effects)
        for eff in self._team_effects.get(team, []):
            # Effects are shared by reference which is acceptable for the simple
            # scenarios in the tests.  More elaborate systems would want to copy
            # them instead.
            army.active_effects.append(eff)

        # Ensure passive skills are present even before the first combat round.
        # If the army already has an associated simulator, apply the passive
        # skills immediately.  Otherwise, when exactly two armies are present we
        # create a temporary simulator so that passive effects are initialised
        # for simple 1v1 setups.
        if army.simulator:
            army._apply_initial_passive_skills()
        elif len(self._armies) == 2 and not self._engagements:
            other_name, other_ctx = next(
                (n, c) for n, c in self._armies.items() if n != army.name
            )
            rb = None
            if self._report_builder is not None:
                rb = self._report_builder.get_builder(other_name, army.name)
            sim = GameSimulator(other_ctx.army, ctx.army, rb, track_stats=False, mode=self.mode)
            sim.parent_engine = self
            # Detach the temporary simulator; passive skills remain applied.
            for a in (other_ctx.army, ctx.army):
                if sim in a.simulators:
                    a.simulators.remove(sim)
                if a.simulator is sim:
                    a.simulator = a.simulators[-1] if a.simulators else None

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
        if (
            self.mode == "arena"
            and defender is not None
            and atk_ctx.direct_target is not None
            and atk_ctx.direct_target != defender
            and atk_ctx.direct_target in self._armies
        ):
            # In arena mode retain the first direct target until it is defeated.
            return
        old_target = atk_ctx.direct_target
        if old_target:
            # Remove active engagement if one exists
            if (attacker, old_target) in self._engagements:
                self._engagements.pop((attacker, old_target), None)
                self._graph[attacker].discard(old_target)
                self._graph[old_target].discard(attacker)
                if self._report_builder is not None:
                    self._report_builder.clear_builder(attacker, old_target)
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
                    if self._report_builder is not None:
                        self._report_builder.clear_builder(old_target, attacker)
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

        reverse_key = (defender, attacker)
        if (
            reverse_key not in self._pending_engagements
            and reverse_key not in self._engagements
        ):
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

        # Reset rage and round based counters for armies out of combat.
        self._reset_idle_armies()

        # Push any queued defender state updates to listeners.
        self._flush_state_updates()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _army_in_combat(self, name: str) -> bool:
        return any(name == atk or name == dfd for atk, dfd in self._engagements)

    def _reset_idle_armies(self) -> None:
        for nm, ctx in self._armies.items():
            if self._army_in_combat(nm):
                continue
            if self.time_elapsed > ctx.last_engaged_time:
                ctx.internal_round = 0
                army = ctx.army
                army.current_rage = 0.0
                army.skill_last_triggered_round.clear()
                # Do not clear cumulative skill trigger counts here so that
                # total cast numbers persist across engagements.  Only
                # per-round counters are reset below.
                # army.skill_trigger_counts.clear()
                army.triggered_skills_this_round.clear()
                army.skill_trigger_counts_this_round.clear()
                army.skill_triggers_against_this_round.clear()
                if ctx.last_engaged_time > 0 and not ctx.idle_reset_done:
                    army.active_effects.clear()
                    army.upcoming_effects.clear()
                    army.effects_to_activate_next_round.clear()
                    # Reapply passive skills without resetting troop counts.
                    # Remove existing passive skill trigger counts so they
                    # apply their effects again for this idle army.
                    passive_ids = {
                        skill_def.get("id")
                        for hero in army.heroes
                        for skill_def in hero.skills
                        if skill_def.get("trigger") == SkillTriggerType.PASSIVE
                    }
                    prev_counts: Dict[str, int] = {}
                    for sid in passive_ids:
                        prev_counts[sid] = army.skill_trigger_counts.pop(sid, 0)
                    army._apply_initial_passive_skills()
                    for sid, prev in prev_counts.items():
                        army.skill_trigger_counts[sid] = prev + army.skill_trigger_counts.get(sid, 0)
                    ctx.idle_reset_done = True
                army.hero1_rage_skill_used_round = None
                army.hero1_rage_skill_scheduled_round = None
                army.hero1_rage_skill_queued_this_round = False
                army.hero1_rage_skill_cast_blocked_by_silence_this_round = False
                army.army_used_rage_skill_this_round_for_rage_gain_block = False
                self._queue_state_update(army)

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
            if not ctx.path:
                if ctx.speed != ctx.base_speed:
                    ctx.speed = ctx.base_speed
                continue
            if ctx.speed <= 0:
                continue
            x, y = ctx.position
            wx, wy = ctx.path[0]
            dx, dy = wx - x, wy - y
            dist = hypot(dx, dy)
            if dist == 0:
                ctx.position = (wx, wy)
                ctx.path.pop(0)
                if ctx.speed != ctx.base_speed and not ctx.path:
                    ctx.speed = ctx.base_speed
                continue
            step = min(dist, ctx.speed * dt)
            if step == dist:
                ctx.position = (wx, wy)
                ctx.path.pop(0)
                if ctx.speed != ctx.base_speed and not ctx.path:
                    ctx.speed = ctx.base_speed
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
        groups: Dict[str, List[_ArmyContext]] = defaultdict(list)
        for (atk, dfd), _ in self._engagements.items():
            groups[dfd].append(self._armies[atk])
            groups[atk].append(self._armies[dfd])

        for centre, neighbours in groups.items():
            if len(neighbours) < 2:
                continue
            centre_ctx = self._armies[centre]
            cx, cy = centre_ctx.position
            neighbours.sort(key=lambda c: c.engaged_at)
            angles = {
                id(n): (degrees(atan2(n.position[1] - cy, n.position[0] - cx)) + 360) % 360
                for n in neighbours
            }
            for idx in range(1, len(neighbours)):
                ctx = neighbours[idx]
                if ctx.arc_target_angle is not None:
                    continue
                curr_angle = angles[id(ctx)]
                for j in range(idx):
                    other = neighbours[j]
                    other_angle = angles[id(other)]
                    diff = (curr_angle - other_angle + 180) % 360 - 180
                    # ``diff`` represents how many degrees ``ctx`` sits
                    # clockwise (negative) or anti-clockwise (positive) from
                    # ``other`` based on their current centre positions. Late
                    # arrivals 5° anti-clockwise to 25° clockwise slide 45°
                    # clockwise to make room; those 5.1–25° anti-clockwise
                    # instead slide 45° anti-clockwise.  When the target
                    # direction is already occupied we may flip to the opposite
                    # side or push existing armies further around the circle.

                    direction = 0
                    if -25 < diff <= 5:
                        direction = -1
                    elif 5 < diff < 25:
                        direction = 1
                    if not direction:
                        continue

                    def find_chain(start_angle: float, dir_: int, step_angle: float) -> List[_ArmyContext]:
                        chain: List[_ArmyContext] = []
                        angle = (start_angle + dir_ * step_angle) % 360
                        while True:
                            found = None
                            for n in neighbours:
                                if n is ctx:
                                    continue
                                ang = angles[id(n)]
                                if abs((ang - angle + 180) % 360 - 180) <= 5:
                                    found = n
                                    break
                            if found is None:
                                break
                            chain.append(found)
                            angle = (angle + dir_ * step_angle) % 360
                        return chain

                    chain = find_chain(other_angle, direction, 45)
                    opp_chain = find_chain(other_angle, -direction, 45)

                    if chain and abs(diff) <= 10 and not opp_chain:
                        # Target blocked but opposite free and we are very
                        # close to ``other`` – flip direction.
                        direction *= -1
                        chain = []

                    chain_full = [ctx] + chain
                    step_angle = 45
                    if len(chain_full) > 2:
                        step_angle = 25

                    for i, army in enumerate(chain_full):
                        target = (other_angle + direction * step_angle * (i + 1)) % 360
                        curr = angles[id(army)]
                        cw = (curr - target + 360) % 360
                        ccw = (target - curr + 360) % 360
                        army.arc_target_angle = target
                        army.arc_direction = 1 if ccw <= cw else -1
                        army.path.clear()
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
                simulator = GameSimulator(atk_ctx.army, def_ctx.army, rb, track_stats=False, mode=self.mode)
                simulator.parent_engine = self
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
            engaged_with_target = (
                def_ctx.direct_target is not None
                and (
                    (def_ctx.direct_target, dfd) in self._engagements
                    or (dfd, def_ctx.direct_target) in self._engagements
                )
            )
            if def_ctx.direct_target is None or not engaged_with_target:
                self.set_direct_target(dfd, attackers[0], pursue=False)

        # Reset per-round bookkeeping so reactive/round based skills only
        # fire once across all engagements and rage gain can be tracked.
        for ctx in self._armies.values():
            army = ctx.army
            army.triggered_skills_this_round.clear()
            army.skill_trigger_counts_this_round.clear()
            army.skill_triggers_against_this_round.clear()
            army.healing_hymn_triggered_this_round = False
            army.pending_hp_damage_this_round = 0.0
            army.pending_hp_healing_this_round = 0.0
            army.rage_added_this_round = 0.0
            army.base_rage_awarded_this_round = False
            army.army_used_rage_skill_this_round_for_rage_gain_block = False
            army.hero1_rage_skill_cast_blocked_by_silence_this_round = False
            army.kills_dealt_this_round = 0.0
            army.damage_contributors_this_round = {}
            army.damage_contributors_by_skill_this_round = {}
            army.heal_contributors_this_round = {}

        unique_armies: List[Army] = []
        start_processed: set[str] = set()
        end_processed: set[str] = set()
        engagement_items = list(self._engagements.items())
        random.shuffle(engagement_items)
        for key, sim in engagement_items:
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
            sim = self._engagements.pop(key, None)
            self._graph[atk].discard(dfd)
            self._graph[dfd].discard(atk)
            if sim:
                for army in (sim.army1, sim.army2):
                    if sim in army.simulators:
                        army.simulators.remove(sim)
                    if army.simulator is sim:
                        army.simulator = army.simulators[-1] if army.simulators else None

        defeated = [name for name, ctx in list(self._armies.items())
                     if ctx.army.current_troop_count <= 0]
        for name in defeated:
            self._remove_army(name)

        # Update internal round counters for armies that fought this round.
        for ctx in self._armies.values():
            army = ctx.army
            if abs(self.time_elapsed - ctx.last_engaged_time) < 1e-6:
                ctx.internal_round += 1
                army.rage_gained_history.append(army.rage_added_this_round)
                army.kills_dealt_history.append(army.kills_dealt_this_round)
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
        atk.register_simulator(sim)
        dfd.register_simulator(sim)

        # Fetch contexts for both armies once so we can use their internal
        # round counters throughout the routine.  This keeps all engagements
        # in sync when an army is involved in multiple simulators.
        atk_ctx = self._armies.get(atk.name)
        dfd_ctx = self._armies.get(dfd.name)

        # Determine if any rage skills were scheduled for this round
        for army, ctx in ((atk, atk_ctx), (dfd, dfd_ctx)):
            if ctx is None:
                army.hero1_rage_skill_queued_this_round = False
            else:
                army.hero1_rage_skill_queued_this_round = (
                    army.hero1_rage_skill_scheduled_round == ctx.internal_round
                )

        # Activate any effects queued from the previous round and decrement durations
        processed_now: List[Army] = []
        for army in (atk, dfd):
            if army.name in start_processed:
                continue
            start_processed.add(army.name)
            processed_now.append(army)
            if army.effects_to_activate_next_round:
                army.upcoming_effects.extend(army.effects_to_activate_next_round)
                army.effects_to_activate_next_round.clear()
            army.activate_queued_effects()
            army.decrement_effect_durations()

        atk.started_last_round_with_active_shield = atk.started_round_with_active_shield
        dfd.started_last_round_with_active_shield = dfd.started_round_with_active_shield
        atk.started_round_with_active_shield = atk.get_current_shield_hp() > 0
        dfd.started_round_with_active_shield = dfd.get_current_shield_hp() > 0

        # --- Start of round housekeeping & round based skill triggers ---
        for army in processed_now:
            opponent = dfd if army is atk else atk
            ctx = atk_ctx if army is atk else dfd_ctx

            if army.current_troop_count <= 0:
                continue
            army.activate_queued_effects()
            army.apply_start_of_round_rage_deductions()
            # Determine the primary opponent for non-reactive skills –
            # defenders should only aim such skills at their direct target.
            primary_opponent = opponent
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

        # Schedule rage skills if the threshold has been reached after start of round
        for army, ctx in ((atk, atk_ctx), (dfd, dfd_ctx)):
            if (
                army.current_troop_count > 0
                and army.hero1_rage_skill_id
                and army.hero1_rage_skill_scheduled_round is None
                and (
                    army.hero2_rage_skill_primed_for_round is None
                    or army.hero2_rage_skill_primed_for_round != ctx.internal_round + 1
                )
            ):
                skill_def = army.hero1_rage_skill_def
                if skill_def is not None and army.current_rage >= skill_def.get("rage_cost", 1000):
                    army.hero1_rage_skill_scheduled_round = ctx.internal_round + 1
                    army.army_used_rage_skill_this_round_for_rage_gain_block = True

        # Execute any queued rage skills.
        if atk.current_troop_count > 0 and dfd.current_troop_count > 0:
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
                atk.hero2_rage_skill_primed_for_round == (atk_ctx.internal_round if atk_ctx else None)
                and atk_ctx
                and atk_ctx.direct_target == dfd.name
            ):
                sim._execute_rage_skills(atk, dfd, is_hero2_delayed_trigger=True)
            if (
                dfd.hero2_rage_skill_primed_for_round == (dfd_ctx.internal_round if dfd_ctx else None)
                and dfd_ctx
                and dfd_ctx.direct_target == atk.name
            ):
                sim._execute_rage_skills(dfd, atk, is_hero2_delayed_trigger=True)

        # --- Basic attack sequences ---
        atk_disarmed = any(
            eff.name == EFFECT_NAME_DISARM_DEBUFF or eff.config.get("prevents_basic_attack")
            for eff in atk.active_effects
        )
        if not atk_disarmed:
            sim._process_skill_triggers(
                atk, dfd, SkillTriggerType.ON_BASIC_ATTACK,
                event_data={'opponent_for_shield_calc': dfd, 'direct_target_army': dfd}
            )
            atk.activate_queued_effects()
            dfd.activate_queued_effects()
        sim._calculate_and_log_attack(atk, dfd, is_counter=False)

        if dfd.current_troop_count > 0:
            dfd_ctx = self._armies.get(dfd.name)
            reactive_target = atk
            if dfd_ctx and dfd_ctx.direct_target and dfd_ctx.direct_target in self._armies:
                reactive_target = self._armies[dfd_ctx.direct_target].army
            if not atk_disarmed:
                sim._process_skill_triggers(
                    dfd,
                    atk,
                    SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
                    event_data={
                        'opponent_for_shield_calc': atk,
                        'attacking_army_for_tit_for_tat': atk,
                        'direct_target_army': reactive_target,
                    }
                )
                dfd.activate_queued_effects()
                atk.activate_queued_effects()
            sim._process_skill_triggers(
                dfd,
                atk,
                SkillTriggerType.ON_COUNTER_ATTACK,
                event_data={
                    'opponent_for_shield_calc': atk,
                    'attacking_army_for_tit_for_tat': atk,
                    'direct_target_army': reactive_target,
                }
            )
            dfd.activate_queued_effects()
            atk.activate_queued_effects()
            sim._calculate_and_log_attack(dfd, atk, is_counter=True)

        if (
            atk.current_troop_count > 0
            and dfd.current_troop_count > 0
            and self._armies[dfd.name].direct_target == atk.name
        ):
            dfd_disarmed = any(
                eff.name == EFFECT_NAME_DISARM_DEBUFF or eff.config.get("prevents_basic_attack")
                for eff in dfd.active_effects
            )
            if not dfd_disarmed:
                sim._process_skill_triggers(
                    dfd, atk, SkillTriggerType.ON_BASIC_ATTACK,
                    event_data={'opponent_for_shield_calc': atk, 'direct_target_army': atk},
                )
                dfd.activate_queued_effects()
                atk.activate_queued_effects()
            sim._calculate_and_log_attack(dfd, atk, is_counter=False)

            if atk.current_troop_count > 0:
                atk_ctx = self._armies.get(atk.name)
                reactive_target2 = dfd
                if atk_ctx and atk_ctx.direct_target and atk_ctx.direct_target in self._armies:
                    reactive_target2 = self._armies[atk_ctx.direct_target].army
                if not dfd_disarmed:
                    sim._process_skill_triggers(
                        atk,
                        dfd,
                        SkillTriggerType.ON_HIT_BY_BASIC_ATTACK,
                        event_data={
                            'opponent_for_shield_calc': dfd,
                            'attacking_army_for_tit_for_tat': dfd,
                            'direct_target_army': reactive_target2,
                        },
                    )
                    atk.activate_queued_effects()
                    dfd.activate_queued_effects()
                sim._process_skill_triggers(
                    atk,
                    dfd,
                    SkillTriggerType.ON_COUNTER_ATTACK,
                    event_data={
                        'opponent_for_shield_calc': dfd,
                        'attacking_army_for_tit_for_tat': dfd,
                        'direct_target_army': reactive_target2,
                    },
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
                # Capture currently active effects so that newly applied
                # effects during the end-of-round phase retain their
                # ``applied_this_round`` flag until the next start-of-round.
                pre_existing = {id(eff) for eff in army.active_effects}
                army.process_periodic_effects("end_of_round", opponent=opponent)
                army.activate_queued_effects()
                for eff in army.active_effects:
                    if id(eff) in pre_existing:
                        eff.applied_this_round = False

        sim._apply_base_rage_gain()

        # Schedule primary hero rage skills for the next round if threshold met
        for army, ctx in ((atk, atk_ctx), (dfd, dfd_ctx)):
            if (
                army.current_troop_count > 0
                and army.hero1_rage_skill_id
                and army.hero1_rage_skill_scheduled_round is None
                and (
                    army.hero2_rage_skill_primed_for_round is None
                    or army.hero2_rage_skill_primed_for_round != ctx.internal_round + 1
                )
            ):
                skill_def = army.hero1_rage_skill_def
                if skill_def is not None and army.current_rage >= skill_def.get("rage_cost", 1000):
                    army.hero1_rage_skill_scheduled_round = ctx.internal_round + 1

        # Record latest engagement time for both armies
        self._armies[atk.name].last_engaged_time = self.time_elapsed
        self._armies[atk.name].idle_reset_done = False
        self._armies[dfd.name].last_engaged_time = self.time_elapsed
        self._armies[dfd.name].idle_reset_done = False


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
