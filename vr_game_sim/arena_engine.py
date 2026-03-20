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
from math import hypot
from typing import Any, Dict, List, Mapping, Optional

from .battlefield_engine import BattlefieldEngine, ENGAGEMENT_DISTANCE


class ArenaEngine(BattlefieldEngine):
    """Specialised engine coordinating arena style battles."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialise the engine and prepare row fallback mappings."""
        kwargs.setdefault("mode", "arena")
        super().__init__(*args, **kwargs)
        self._row_fallbacks: Dict[str, List[str]] = {}
        # Default movement speed used when layouts do not specify a custom
        # formation.  ``start_arena_battle`` recalculates this based on slot
        # positions to satisfy timing expectations.
        self.default_speed: float = 50.0
        # Default targeting behaviour when no explicit preference is supplied
        # for a given arena battle.
        self.targeting_mode: str = "legacy"
        # Custom targeting configuration: dict mapping team ("red"/"blue") -> list of army names in order
        self._custom_targeting: Optional[Dict[str, List[str]]] = None
        # Custom targeting configuration: dict mapping team ("red"/"blue") -> list of army names in order
        self._custom_targeting: Optional[Dict[str, List[str]]] = None

    def start_arena_battle(
        self, layout_slots: Any, *, targeting_mode: Optional[str] = None, custom_targeting: Optional[Dict[str, List[str]]] = None
    ) -> None:
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
        team_entries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
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
            team_entries[team].append(entry)

        team_names = list(columns.keys())

        mode = (targeting_mode or self.targeting_mode or "legacy").lower()
        if mode not in {"legacy", "str", "frg", "custom"}:
            mode = "legacy"
        self.targeting_mode = mode
        self._custom_targeting = custom_targeting if mode == "custom" else None

        if mode == "legacy":
            # Derive default speeds for front and back rows so armies meet after
            # approximately 2 s (front vs. front) and 4 s (back vs. front).
            front_entries: List[Dict[str, Any]] = []
            back_entries: List[Dict[str, Any]] = []
            front_dists: List[float] = []
            back_dists: List[float] = []
            if len(team_names) == 2:
                t1, t2 = team_names
                all_cols = set(columns[t1].keys()) | set(columns[t2].keys())
                for col in all_cols:
                    col1 = columns[t1].get(col, {})
                    col2 = columns[t2].get(col, {})
                    f1 = col1.get("front")
                    f2 = col2.get("front")
                    b1 = col1.get("back")
                    b2 = col2.get("back")
                    if f1 and f2:
                        p1 = f1["position"]
                        p2 = f2["position"]
                        front_dists.append(hypot(p2[0] - p1[0], p2[1] - p1[1]))
                        front_entries.extend([f1, f2])
                    if b1 and f2:
                        p1 = b1["position"]
                        p2 = f2["position"]
                        back_dists.append(hypot(p2[0] - p1[0], p2[1] - p1[1]))
                        back_entries.append(b1)
                    if b2 and f1:
                        p1 = b2["position"]
                        p2 = f1["position"]
                        back_dists.append(hypot(p2[0] - p1[0], p2[1] - p1[1]))
                        back_entries.append(b2)

            if front_dists:
                front_speed = (
                    sum(d - ENGAGEMENT_DISTANCE for d in front_dists)
                    / (4.0 * len(front_dists))
                )
            else:
                front_speed = 50.0
            if back_dists:
                back_speed = (
                    sum(d - ENGAGEMENT_DISTANCE for d in back_dists)
                    / (8.0 * len(back_dists))
                )
            else:
                back_speed = front_speed

            if abs(front_speed - back_speed) < 1e-6:
                self.default_speed = front_speed
            else:
                self.default_speed = (front_speed + back_speed) / 2.0
            for e in front_entries:
                ctx = self._armies[e["army"].name]
                ctx.speed = ctx.base_speed = front_speed
            for e in back_entries:
                ctx = self._armies[e["army"].name]
                ctx.speed = ctx.base_speed = back_speed
        else:
            if entries:
                first_ctx = self._armies[entries[0]["army"].name]
                self.default_speed = first_ctx.base_speed
            else:
                self.default_speed = 50.0

        # Pair columns across teams to assign default targets and march orders
        self._row_fallbacks.clear()
        if len(team_names) == 2:
            t1, t2 = team_names
            if mode == "legacy":
                all_cols = set(columns[t1].keys()) | set(columns[t2].keys())
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
            else:
                def _has_explicit_target(entry: Dict[str, Any]) -> bool:
                    return bool(
                        entry.get("target_army")
                        or entry.get("target")
                        or entry.get("march_to")
                    )

                def _sorted_targets(team: str, opponent: str) -> List[str]:
                    enemies = [
                        e for e in team_entries[opponent] if not _has_explicit_target(e)
                    ]
                    if not enemies:
                        return []

                    if mode == "str":
                        enemies.sort(
                            key=lambda e: e["army"].unit.effective_attack(
                                e["army"].active_effects
                            ),
                            reverse=True,
                        )
                    else:  # mode == "frg"
                        enemies.sort(
                            key=lambda e: (
                                e["army"].unit.effective_defense(e["army"].active_effects)
                                + e["army"].unit.effective_hp_per_troop(
                                    e["army"].active_effects
                                )
                            )
                        )
                    return [e["army"].name for e in enemies]

                if mode == "custom" and self._custom_targeting:
                    # Use custom targeting order
                    for team, opponent in ((t1, t2), (t2, t1)):
                        # Get the team identifier (red/blue) from the first entry
                        team_id = None
                        for entry in team_entries[team]:
                            team_id = entry.get("team")
                            if team_id:
                                break
                        if not team_id:
                            # Fallback: try to infer from team name
                            team_id = "red" if team == t1 else "blue"
                        
                        # Get custom targeting order for this team
                        custom_order = self._custom_targeting.get(team_id, [])
                        if not custom_order:
                            # If no custom order specified, fall back to auto
                            for entry in team_entries[team]:
                                if _has_explicit_target(entry):
                                    continue
                                attacker = entry["army"].name
                                self._auto_select_closest_enemy(attacker)
                            continue
                        
                        # Filter custom order to only include armies that exist and are on the opponent team
                        valid_order: List[str] = []
                        opponent_army_names = {e["army"].name for e in team_entries[opponent]}
                        for army_name in custom_order:
                            if army_name in opponent_army_names:
                                valid_order.append(army_name)
                        
                        # Apply targeting order to all armies in this team
                        for entry in team_entries[team]:
                            if _has_explicit_target(entry):
                                continue
                            attacker = entry["army"].name
                            if valid_order:
                                self._row_fallbacks[attacker] = list(valid_order)
                                self.set_direct_target(attacker, valid_order[0])
                            else:
                                self._auto_select_closest_enemy(attacker)
                else:
                    # Use standard targeting modes (str/frg)
                    for team, opponent in ((t1, t2), (t2, t1)):
                        order = _sorted_targets(team, opponent)
                        for entry in team_entries[team]:
                            if _has_explicit_target(entry):
                                continue
                            attacker = entry["army"].name
                            if order:
                                self._row_fallbacks[attacker] = list(order)
                                self.set_direct_target(attacker, order[0])
                            else:
                                self._auto_select_closest_enemy(attacker)

        row_map = {e["army"].name: e.get("row") for e in entries}

        if mode == "legacy":
            # Temporarily boost speed for armies that must travel diagonally or
            # from the back row so engagements start at predictable times.
            def _legacy_back_row_speed_to_defender(
                sx: float,
                sy: float,
                tx: float,
                ty: float,
                defender_base: float,
            ) -> float:
                # Same geometry as legacy back-row closure toward a defender; pace
                # is caller-chosen (4 s window for back→front).
                dx, dy = tx - sx, ty - sy
                mv = 2 * defender_base
                dist_vec = hypot(dx, dy)
                if dist_vec > 1e-6:
                    dx -= mv * dx / dist_vec
                    dy -= mv * dy / dist_vec
                required_dist = hypot(dx, dy) - ENGAGEMENT_DISTANCE
                # Fudge 3.95 vs 4 s for discrete steps (back→front only).
                return required_dist / 3.95

            back_to_front_speeds: List[float] = []
            for entry in entries:
                ctx = self._armies[entry["army"].name]
                target_name = ctx.direct_target
                if target_name is None:
                    continue
                tgt_ctx = self._armies.get(target_name)
                if tgt_ctx is None:
                    continue
                if entry.get("row") != 1 or row_map.get(target_name) != 0:
                    continue
                sx, sy = ctx.position
                tx, ty = tgt_ctx.position
                back_to_front_speeds.append(
                    _legacy_back_row_speed_to_defender(
                        sx, sy, tx, ty, tgt_ctx.base_speed
                    )
                )

            nominal_back_row_speed = (
                sum(back_to_front_speeds) / len(back_to_front_speeds)
                if back_to_front_speeds
                else self.default_speed
            )

            for entry in entries:
                army = entry["army"]
                ctx = self._armies[army.name]
                target_name = ctx.direct_target
                if target_name is None:
                    continue
                tgt_ctx = self._armies.get(target_name)
                if tgt_ctx is None:
                    continue
                sx, sy = ctx.position
                tx, ty = tgt_ctx.position
                dist = hypot(tx - sx, ty - sy)
                attacker_row = entry.get("row")
                target_row = row_map.get(target_name)
                if attacker_row == 1 and target_row == 0:
                    # Back row vs front – boost to engage in ~4 s.  Uses the
                    # defender's base speed for a theoretical forward advance.
                    needed_speed = _legacy_back_row_speed_to_defender(
                        sx, sy, tx, ty, tgt_ctx.base_speed
                    )
                    if needed_speed > ctx.base_speed:
                        ctx.speed = needed_speed
                elif attacker_row == 1 and target_row == 1:
                    # Back vs back: match the general back→front march rate (mean
                    # across lanes) so peers no longer crawl, but do not scale
                    # speed up to close in ~4 s—longer separation ⇒ longer time.
                    if nominal_back_row_speed > ctx.base_speed:
                        ctx.speed = nominal_back_row_speed
                elif abs(sy - ty) > 1e-6:
                    # Diagonal engagement – ensure it completes in ~2 s.
                    # Diagonal attackers previously reached their target a full
                    # combat round later when another friendly was already
                    # engaging the defender.  Boost their speed so the combined
                    # travel time remains safely below the 2 s round boundary,
                    # accounting for the initial simulation step and float error.
                    required_sum = (dist - ENGAGEMENT_DISTANCE) / 1.87

                    # ``tgt_ctx`` may itself be marching towards a different
                    # opponent.  Only the component of its movement along the
                    # attacker's approach vector helps close the distance.  Project
                    # the defender's velocity onto the attack vector to obtain this
                    # contribution.
                    tgt_component = 0.0
                    if tgt_ctx.direct_target:
                        other = self._armies.get(tgt_ctx.direct_target)
                        if other is not None:
                            mx, my = other.position[0] - tx, other.position[1] - ty
                            mv_dist = hypot(mx, my)
                            if mv_dist > 1e-6:
                                ux, uy = mx / mv_dist, my / mv_dist
                                ax = (tx - sx) / dist
                                ay = (ty - sy) / dist
                                tgt_component = tgt_ctx.speed * (ax * ux + ay * uy)

                    needed_speed = required_sum + tgt_component
                    if needed_speed > ctx.base_speed:
                        ctx.speed = needed_speed

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
