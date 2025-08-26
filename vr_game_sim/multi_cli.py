"""Simple command line interface for the multi-army simulator."""
from __future__ import annotations

from typing import Dict
import math

from .unit_definition import Unit
from .army_composition import Army
from .battlefield import Battlefield
from .navmesh import NavMesh, Polygon
from .multi_army_simulator import MultiArmySimulator


def main() -> None:
    battlefield = Battlefield(10, 10)
    nav = NavMesh([Polygon(vertices=[(0, 0), (10, 0), (10, 10), (0, 10)], neighbors=[])])
    battlefield.load_navmesh(nav)
    red = Army("Red", Unit("infantry", 5, 100))
    blue = Army("Blue", Unit("archers", 5, 100))
    battlefield.place_army(red, 0, 0)
    battlefield.place_army(blue, 9, 9)
    simulator = MultiArmySimulator(battlefield, [red, blue])

    print("Commands: move <army> <x> <y>, step, show, quit")
    name_map: Dict[str, Army] = {a.name.lower(): a for a in simulator.armies}

    while True:
        cmd = input(">>> ").strip().split()
        if not cmd:
            continue
        action = cmd[0].lower()
        if action == "move" and len(cmd) == 4:
            army = name_map.get(cmd[1].lower())
            if not army:
                print("Unknown army")
                continue
            try:
                x, y = float(cmd[2]), float(cmd[3])
            except ValueError:
                print("Invalid coordinates")
                continue
            army.set_destination((x, y))
            occupant = None
            for other in simulator.armies:
                if other is army or other.current_troop_count <= 0:
                    continue
                if math.hypot(other.float_x - x, other.float_y - y) < 1.0:
                    occupant = other
                    break
            if not occupant or occupant.team == army.team:
                simulator.clear_targeting(army)
            else:
                simulator.set_targeting(army, occupant)
            print(f"{army.name} marching to {(x, y)}")
        elif action == "step":
            simulator.step()
            print(battlefield.render_with_coords(simulator.armies))
            name_map = {a.name.lower(): a for a in simulator.armies}
            if len(simulator.armies) <= 1:
                if simulator.armies:
                    print(f"{simulator.armies[0].name} wins!")
                break
        elif action == "show":
            print(battlefield.render_with_coords(simulator.armies))
        elif action == "quit":
            break
        else:
            print("Unknown command")


if __name__ == "__main__":  # pragma: no cover - simple manual CLI
    main()
