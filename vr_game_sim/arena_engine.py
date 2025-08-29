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

from .battlefield_engine import BattlefieldEngine


class ArenaEngine(BattlefieldEngine):
    """Specialised engine coordinating arena style battles."""

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
                    col = idx % 3
                    row = 0 if idx < 3 else 1
            if col is not None and row is not None:
                entry["column"] = col
                entry["row"] = row
                columns[team][col]["front" if row == 0 else "back"] = entry

        # Pair columns across teams to assign default targets and march orders
        team_names = list(columns.keys())
        if len(team_names) == 2:
            t1, t2 = team_names
            all_cols = set(columns[t1].keys()) | set(columns[t2].keys())
            for col in all_cols:
                col1 = columns[t1].get(col, {})
                col2 = columns[t2].get(col, {})

                def _pick_target(col_data: Dict[str, Dict[str, Any]]) -> Optional[str]:
                    target_entry = col_data.get("front") or col_data.get("back")
                    if target_entry is None:
                        return None
                    return target_entry["army"].name

                target1 = _pick_target(col2)
                target2 = _pick_target(col1)

                for row_key in ("front", "back"):
                    e1 = col1.get(row_key)
                    if (
                        e1
                        and not (
                            e1.get("target_army")
                            or e1.get("target")
                            or e1.get("march_to")
                        )
                        and target1
                    ):
                        self.set_direct_target(e1["army"].name, target1)
                    e2 = col2.get(row_key)
                    if (
                        e2
                        and not (
                            e2.get("target_army")
                            or e2.get("target")
                            or e2.get("march_to")
                        )
                        and target2
                    ):
                        self.set_direct_target(e2["army"].name, target2)

                front1 = col1.get("front")
                front2 = col2.get("front")
                if front1 and front2:
                    p1 = front1["position"]
                    p2 = front2["position"]
                    midpoint = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
                    if not (
                        front1.get("target_army")
                        or front1.get("target")
                        or front1.get("march_to")
                    ):
                        self.set_waypoint(front1["army"].name, midpoint)
                    if not (
                        front2.get("target_army")
                        or front2.get("target")
                        or front2.get("march_to")
                    ):
                        self.set_waypoint(front2["army"].name, midpoint)

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
