"""Simulate battles between multiple armies on a battlefield."""
from __future__ import annotations

from typing import List
import random
import math

from .army_composition import Army
from .battlefield import Battlefield
from .duel import Duel
from .constants import ENGAGEMENT_RADIUS, DISENGAGE_DISTANCE


class MultiArmySimulator:
    """Advance armies on a battlefield and resolve clashes."""

    def __init__(self, battlefield: Battlefield, armies: List[Army], *, min_spacing: float = 2.0):
        """Create a simulator for the given armies.

        Parameters
        ----------
        battlefield:
            The battlefield on which the armies fight.
        armies:
            The armies taking part in the simulation.
        min_spacing:
            Minimum distance maintained between engaged armies.  Defaults to
            ``2.0`` units.
        """
        self.battlefield = battlefield
        self.armies = armies
        self.active_duels: List[Duel] = []
        self.min_spacing = float(min_spacing)

    # ------------------------------------------------------------------
    def _clear_targeting(self, army: Army) -> None:
        if army.direct_target and army in army.direct_target.attackers:
            army.direct_target.attackers.remove(army)
        for atk in list(army.attackers):
            atk.direct_target = None
        army.direct_target = None
        army.attackers.clear()

    # Public wrappers used by external callers (e.g. CLI/GUI)
    def clear_targeting(self, army: Army) -> None:
        self._clear_targeting(army)

    def _retarget(self, army: Army) -> None:
        if army.direct_target and army.direct_target.current_troop_count <= 0:
            if army in army.direct_target.attackers:
                army.direct_target.attackers.remove(army)
            army.direct_target = None
        if not army.direct_target and army.attackers:
            army.direct_target = random.choice(army.attackers)

    def _set_targeting(self, attacker: Army, defender: Army) -> None:
        if attacker.team == defender.team or attacker.direct_target is defender:
            return
        self._clear_targeting(attacker)
        attacker.direct_target = defender
        if attacker not in defender.attackers:
            defender.attackers.append(attacker)
        if defender.direct_target is None:
            defender.direct_target = attacker

    def set_targeting(self, attacker: Army, defender: Army) -> None:
        self._set_targeting(attacker, defender)

    def step(self, dt: float = 1.0) -> None:
        """Advance the simulation by ``dt`` seconds."""
        # Reset per-round skill trigger tracking so reactive skills only fire
        # once per second even under multiple attackers.
        for army in self.armies:
            army.triggered_skills_this_round.clear()
            army.healing_hymn_triggered_this_round = False
            army.base_rage_awarded_this_round = False

        finished_duels: List[Duel] = []
        engaged: List[Army] = []
        duels = list(self.active_duels)
        random.shuffle(duels)
        for duel in duels:
            duel.time_acc += dt
            while duel.time_acc >= 1.0:
                duel.time_acc -= 1.0
                duel.sync_from_armies()
                duel.allow_b_attack = duel.army_b.direct_target is duel.army_a
                result = duel.simulate_round(reset_triggers=False)
                if not result:
                    finished_duels.append(duel)
                    break
                if duel.army_a not in engaged:
                    engaged.append(duel.army_a)
                if duel.army_b not in engaged:
                    engaged.append(duel.army_b)
                log = result["log"]
                for army, d_troops, d_unrev in result["deltas"]:
                    army.apply_round_results(d_troops, d_unrev)
                    army.battle_reports.append(log)
                if result["battle_over"]:
                    finished_duels.append(duel)
                    break

        for duel in finished_duels:
            self.active_duels.remove(duel)
            for army in (duel.army_a, duel.army_b):
                if duel in army.active_duels:
                    army.active_duels.remove(duel)
                if army.current_troop_count <= 0:
                    self._clear_targeting(army)

        # Track continuous engagement rounds with a 2s reset window
        for army in self.armies:
            if army in engaged:
                army.continuous_rounds += 1
                army.time_since_last_battle = 0.0
            else:
                army.time_since_last_battle += dt
                if army.time_since_last_battle > 2.0:
                    army.continuous_rounds = 0
                    army.current_rage = 0.0

        # Remove any dead armies while preserving the shared list reference
        # ``BattlefieldTab`` and other callers retain a reference to
        # ``self.armies``.  Reassigning ``self.armies`` to a new list would
        # sever that link, meaning armies added later (e.g. via the GUI) would
        # never be seen by the simulator.  Instead mutate the list in place so
        # all holders see the updated contents.
        self.armies[:] = [a for a in self.armies if a.current_troop_count > 0]

        # Retarget surviving armies
        for army in self.armies:
            self._retarget(army)

        # Track positions before movement so we can detect which army moved
        prev_pos = {id(a): (a.float_x, a.float_y) for a in self.armies}

        # Move armies not currently in any duel
        for army in self.armies:
            if army.current_troop_count <= 0:
                continue
            if army.active_duels and army.destination is None:
                continue
            army.update_position(self.battlefield, dt)
            # Do not allow the moving army to end up closer than min_spacing
            # to any enemy.  If it does, push only this army back to the
            # allowed distance so armies do not appear to bounce apart.
            prev_x, prev_y = prev_pos[id(army)]
            for other in self.armies:
                if other is army or other.current_troop_count <= 0:
                    continue
                if other.team == army.team:
                    continue
                dist = math.hypot(army.float_x - other.float_x, army.float_y - other.float_y)
                if dist < self.min_spacing:
                    pdx = prev_x - other.float_x
                    pdy = prev_y - other.float_y
                    pdist = math.hypot(pdx, pdy)
                    if pdist == 0.0:
                        dx, dy = 1.0, 0.0
                    else:
                        dx, dy = pdx / pdist, pdy / pdist
                    nx = max(
                        0.0,
                        min(self.battlefield.width - 1e-3, other.float_x + dx * self.min_spacing),
                    )
                    ny = max(
                        0.0,
                        min(self.battlefield.height - 1e-3, other.float_y + dy * self.min_spacing),
                    )
                    self.battlefield.place_army(army, nx, ny)

        # Break duels if participants separate beyond the disengage distance
        for duel in list(self.active_duels):
            dist = math.hypot(
                duel.army_a.float_x - duel.army_b.float_x,
                duel.army_a.float_y - duel.army_b.float_y,
            )
            if dist > DISENGAGE_DISTANCE:
                self.active_duels.remove(duel)
                for army in (duel.army_a, duel.army_b):
                    if duel in army.active_duels:
                        army.active_duels.remove(duel)
                self._clear_targeting(duel.army_a)
                self._clear_targeting(duel.army_b)

        # Ensure armies in active duels maintain minimum spacing each tick
        for duel in self.active_duels:
            a1, a2 = duel.army_a, duel.army_b
            dist = math.hypot(a1.float_x - a2.float_x, a1.float_y - a2.float_y)
            if dist < self.min_spacing:
                if dist == 0.0:
                    dx, dy = 1.0, 0.0
                else:
                    dx = (a1.float_x - a2.float_x) / dist
                    dy = (a1.float_y - a2.float_y) / dist
                nx = max(
                    0.0,
                    min(self.battlefield.width - 1e-3, a2.float_x + dx * self.min_spacing),
                )
                ny = max(
                    0.0,
                    min(self.battlefield.height - 1e-3, a2.float_y + dy * self.min_spacing),
                )
                # Push only army_a (the initiator) back to the required spacing
                self.battlefield.place_army(a1, nx, ny)

        # Check for clashes based on proximity
        engage_radius = max(ENGAGEMENT_RADIUS, self.min_spacing)
        for i, a1 in enumerate(self.armies):
            if a1.current_troop_count <= 0:
                continue
            for a2 in self.armies[i + 1 :]:
                if a2.current_troop_count <= 0 or a1.team == a2.team:
                    continue
                if a1.active_duels and a2.active_duels:
                    continue
                dist = math.hypot(a1.float_x - a2.float_x, a1.float_y - a2.float_y)
                if dist <= engage_radius:
                    if dist < self.min_spacing:
                        # Push back only the army that moved closer this tick
                        move1 = math.hypot(a1.float_x - prev_pos[id(a1)][0], a1.float_y - prev_pos[id(a1)][1])
                        move2 = math.hypot(a2.float_x - prev_pos[id(a2)][0], a2.float_y - prev_pos[id(a2)][1])
                        mover, other = (a1, a2) if move1 >= move2 else (a2, a1)
                        prev_x, prev_y = prev_pos[id(mover)]
                        pdx = prev_x - other.float_x
                        pdy = prev_y - other.float_y
                        pdist = math.hypot(pdx, pdy)
                        if pdist == 0.0:
                            dx, dy = 1.0, 0.0
                        else:
                            dx, dy = pdx / pdist, pdy / pdist
                        nx = max(
                            0.0,
                            min(self.battlefield.width - 1e-3, other.float_x + dx * self.min_spacing),
                        )
                        ny = max(
                            0.0,
                            min(self.battlefield.height - 1e-3, other.float_y + dy * self.min_spacing),
                        )
                        self.battlefield.place_army(mover, nx, ny)
                        dist = self.min_spacing
                    if a1.direct_target is None:
                        self._set_targeting(a1, a2)
                    if a2.direct_target is None:
                        self._set_targeting(a2, a1)
                    attacker: Army | None = None
                    defender: Army | None = None
                    if a1.direct_target is a2:
                        attacker, defender = a1, a2
                    elif a2.direct_target is a1:
                        attacker, defender = a2, a1
                    if attacker and defender:
                        allow = defender.direct_target is attacker or defender.direct_target is None
                        duel = Duel(attacker, defender, allow_b_attack=allow)
                        self.active_duels.append(duel)
                        attacker.active_duels.append(duel)
                        defender.active_duels.append(duel)

        # Final cleanup of dead armies; again, mutate the list in place to keep
        # the simulator and GUI in sync.
        self.armies[:] = [a for a in self.armies if a.current_troop_count > 0]

    def _resolve_battle(self, army1: Army, army2: Army) -> None:
        """Start a duel between two armies."""
        if army1.team == army2.team:
            return
        full = True
        duel = Duel(army1, army2, allow_b_attack=full)
        self.active_duels.append(duel)
        army1.active_duels.append(duel)
        army2.active_duels.append(duel)

    def run(self, max_rounds: int = 100) -> List[Army]:
        """Run until only one army remains or max rounds reached."""
        for _ in range(max_rounds):
            if len(self.armies) <= 1:
                break
            self.step()
        return self.armies

    def render_battlefield(self) -> str:
        """Return a textual representation of the battlefield."""
        return self.battlefield.render(self.armies)
