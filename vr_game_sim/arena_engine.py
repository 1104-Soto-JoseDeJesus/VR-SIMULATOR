from __future__ import annotations

"""Arena specific engine utilities.

This module provides :class:`ArenaEngine` which extends the base
:class:`BattlefieldEngine` with a convenience routine for the simplified
"arena" mode used in the project.  The arena works with fixed deployment
slots.  ``start_arena_battle`` takes a description of armies placed in
these slots, registers the armies with the underlying battlefield engine
and schedules their initial movement commands.
"""

from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional

from .battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE


class ArenaEngine(BattlefieldEngine):
    """Specialised engine coordinating arena style battles."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the engine and prepare row fallback mappings."""
        kwargs.setdefault("mode", "arena")
        super().__init__(*args, **kwargs)
        self._row_fallbacks: Dict[str, List[str]] = {}

    def start_arena_battle(self, layout_slots: Any) -> None:
        """Register armies in ``layout_slots`` and queue march orders.

        Parameters
        ----------
        layout_slots:
            Description of slot assignments.  The function accepts a wide
            range of structures to keep the interface convenient for GUI
            and tests.  The object may either be an iterable of slot
            descriptions or a mapping of ``team`` -> iterable.  Individual
            slot descriptions can be simple :class:`Army` instances or
            dictionaries with at least the keys ``army`` and ``position``.
            Optional keys:

            ``team``
                Team identifier for the army.  If omitted when a mapping is
                supplied, the mapping key is used.
            ``speed``
                Movement speed for the army.  Defaults to ``50.0``.
            ``target`` / ``march_to``
                Waypoint the army should march towards.
            ``target_army``
                Another :class:`Army` object that should be engaged.  Both
                armies will march towards each other until within combat
                distance.
        """

        entries: List[Dict[str, Any]] = []
        columns: Dict[str, Dict[int, Dict[str, Dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(dict)
        )

        def _add_entry(item: Any, default_team: Optional[str] = None) -> None:
            if item is None:
                return
            if isinstance(item, dict):
                entry = dict(item)
                if default_team is not None:
                    entry.setdefault("team", default_team)
            else:
                entry = {"army": item, "team": default_team}
            if "army" not in entry or entry.get("team") is None:
                # insufficient data; ignore
                return
            entries.append(entry)

        if isinstance(layout_slots, Mapping):
            for team, slots in layout_slots.items():
                if isinstance(slots, Mapping):
                    for data in slots.values():
                        _add_entry(data, team)
                else:
                    for data in slots:
                        _add_entry(data, team)
        else:
            for data in layout_slots:  # type: ignore[arg-type]
                _add_entry(data, None)

        # Register all armies with their positions and track slot columns
        for entry in entries:
            army = entry["army"]
            team = entry["team"]
            position = entry.get("position")
            if position is None:
                idx = entry.get("index")
                coords = entry.get("slot_coords")
                if coords is not None and idx is not None:
                    position = coords[idx]
            if position is None:
                raise ValueError("Each slot entry must define a position")
            speed = entry.get("speed", 50.0)
            self.add_army(army, team, position=position, speed=speed)
            entry["position"] = position

            # Normalise column/row information for later pairing
            col = entry.get("column")
            row = entry.get("row")
            if col is None or row is None:
                idx = entry.get("index")
                if idx is not None:
                    col = idx % 4
                    row = 0 if idx < 4 else 1
            if col is not None and row is not None:
                entry["column"] = col
                entry["row"] = row
                columns[team][col]["front" if row == 0 else "back"] = entry

        # Pair columns across teams to assign default targets and march orders
        self._row_fallbacks.clear()
        team_names = list(columns.keys())
        if len(team_names) == 2:
            t1, t2 = team_names
            all_cols = set(columns[t1].keys()) | set(columns[t2].keys())

            def _time_based_destinations(e1: Dict[str, Any], e2: Dict[str, Any], time: float):
                p1 = e1["position"]
                p2 = e2["position"]
                ctx1 = self._armies[e1["army"].name]
                ctx2 = self._armies[e2["army"].name]
                dist_init = abs(p1[1] - p2[1])
                if dist_init <= ENGAGEMENT_DISTANCE:
                    return p1, p2
                total_speed = ctx1.speed + ctx2.speed
                required_total_distance = dist_init - ENGAGEMENT_DISTANCE
                required_total_speed = required_total_distance / time
                if total_speed != required_total_speed:
                    scale = required_total_speed / total_speed
                    ctx1.speed *= scale
                    ctx2.speed *= scale
                dist1 = ctx1.speed * time
                dist2 = ctx2.speed * time
                direction = 1.0 if p1[1] < p2[1] else -1.0
                dest1 = (p1[0], p1[1] + direction * dist1)
                dest2 = (p2[0], p2[1] - direction * dist2)
                return dest1, dest2

            for col in all_cols:
                col1 = columns[t1].get(col, {})
                col2 = columns[t2].get(col, {})

                # Determine target priority for each team: front opponent then back
                targets1: List[str] = []
                opp_front = col2.get("front")
                opp_back = col2.get("back")
                if opp_front:
                    targets1.append(opp_front["army"].name)
                if opp_back:
                    targets1.append(opp_back["army"].name)

                targets2: List[str] = []
                opp_front = col1.get("front")
                opp_back = col1.get("back")
                if opp_front:
                    targets2.append(opp_front["army"].name)
                if opp_back:
                    targets2.append(opp_back["army"].name)

                for row_key in ("front", "back"):
                    e1 = col1.get(row_key)
                    if e1 and not (
                        e1.get("target_army")
                        or e1.get("target")
                        or e1.get("march_to")
                    ):
                        if targets1:
                            self.set_direct_target(e1["army"].name, targets1[0])
                            self._row_fallbacks[e1["army"].name] = list(targets1)
                        else:
                            self._auto_select_closest_enemy(e1["army"].name)

                    e2 = col2.get(row_key)
                    if e2 and not (
                        e2.get("target_army")
                        or e2.get("target")
                        or e2.get("march_to")
                    ):
                        if targets2:
                            self.set_direct_target(e2["army"].name, targets2[0])
                            self._row_fallbacks[e2["army"].name] = list(targets2)
                        else:
                            self._auto_select_closest_enemy(e2["army"].name)

                front1 = col1.get("front")
                front2 = col2.get("front")
                if front1 and front2:
                    dest1, dest2 = _time_based_destinations(front1, front2, 2.0)
                    if not (
                        front1.get("target_army")
                        or front1.get("target")
                        or front1.get("march_to")
                    ):
                        self.set_waypoint(front1["army"].name, dest1)
                    if not (
                        front2.get("target_army")
                        or front2.get("target")
                        or front2.get("march_to")
                    ):
                        self.set_waypoint(front2["army"].name, dest2)

                back1 = col1.get("back")
                back2 = col2.get("back")
                if back1 and back2:
                    dest1, dest2 = _time_based_destinations(back1, back2, 4.0)
                    if not (
                        back1.get("target_army")
                        or back1.get("target")
                        or back1.get("march_to")
                    ):
                        self.set_waypoint(back1["army"].name, dest1)
                    if not (
                        back2.get("target_army")
                        or back2.get("target")
                        or back2.get("march_to")
                    ):
                        self.set_waypoint(back2["army"].name, dest2)

        # Queue march orders (either waypoints or direct engagements)
        for entry in entries:
            army = entry["army"]
            target_army = entry.get("target_army")
            if target_army is not None:
                self.engage(army.name, target_army.name)
                continue
            target = entry.get("target") or entry.get("march_to")
            if target is not None:
                self.set_waypoint(army.name, target)

    def _remove_army(self, name: str) -> None:
        """Override removal to apply row-based fallbacks before auto retargeting."""
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

        self._row_fallbacks.pop(name, None)
        for attacker in lost:
            targets = [t for t in self._row_fallbacks.get(attacker, []) if t != name]
            while targets and targets[0] not in self._armies:
                targets.pop(0)
            if targets:
                self._row_fallbacks[attacker] = targets
                self.set_direct_target(attacker, targets[0])
            else:
                self._row_fallbacks.pop(attacker, None)
                self._auto_select_closest_enemy(attacker)
