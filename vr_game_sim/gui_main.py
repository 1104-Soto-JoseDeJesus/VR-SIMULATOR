"""Tkinter based graphical interface for configuring and running battles."""

from __future__ import annotations

import contextlib
import io
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .hero_definition import HERO_PRESETS
from .unit_definition import Unit
from .game_simulator import GameSimulator
from .main import create_armies_from_data, run_additional_simulations


class ArmyFrame(tk.LabelFrame):
    """GUI inputs for a single army."""

    def __init__(self, master: tk.Misc, index: int):
        super().__init__(master, text=f"Army {index}")
        self.index = index

        hero_options = ["None"] + sorted(name.capitalize() for name in HERO_PRESETS.keys())

        self.name_var = tk.StringVar(value=f"Army {index}")
        self.unit_var = tk.StringVar(value="pikemen")
        self.tier_var = tk.StringVar(value="5")
        self.count_var = tk.StringVar(value="100000")
        self.atk_var = tk.StringVar(value="0")
        self.def_var = tk.StringVar(value="0")
        self.hp_var = tk.StringVar(value="0")
        self.hero1_var = tk.StringVar(value="None")
        self.hero2_var = tk.StringVar(value="None")

        row = 0
        ttk.Label(self, text="Name:").grid(row=row, column=0, sticky="e")
        ttk.Entry(self, textvariable=self.name_var, width=15).grid(row=row, column=1)
        row += 1

        ttk.Label(self, text="Unit type:").grid(row=row, column=0, sticky="e")
        ttk.OptionMenu(self, self.unit_var, self.unit_var.get(), *sorted(Unit.ALLOWED_TYPES)).grid(row=row, column=1, sticky="we")
        row += 1

        ttk.Label(self, text="Tier:").grid(row=row, column=0, sticky="e")
        ttk.OptionMenu(self, self.tier_var, self.tier_var.get(), *sorted(Unit.ALLOWED_TIERS)).grid(row=row, column=1, sticky="we")
        row += 1

        ttk.Label(self, text="Troops:").grid(row=row, column=0, sticky="e")
        ttk.Entry(self, textvariable=self.count_var, width=10).grid(row=row, column=1)
        row += 1

        ttk.Label(self, text="Atk mod:").grid(row=row, column=0, sticky="e")
        ttk.Entry(self, textvariable=self.atk_var, width=10).grid(row=row, column=1)
        row += 1

        ttk.Label(self, text="Def mod:").grid(row=row, column=0, sticky="e")
        ttk.Entry(self, textvariable=self.def_var, width=10).grid(row=row, column=1)
        row += 1

        ttk.Label(self, text="HP mod:").grid(row=row, column=0, sticky="e")
        ttk.Entry(self, textvariable=self.hp_var, width=10).grid(row=row, column=1)
        row += 1

        ttk.Label(self, text="Hero 1:").grid(row=row, column=0, sticky="e")
        ttk.OptionMenu(self, self.hero1_var, self.hero1_var.get(), *hero_options).grid(row=row, column=1, sticky="we")
        row += 1

        ttk.Label(self, text="Hero 2:").grid(row=row, column=0, sticky="e")
        ttk.OptionMenu(self, self.hero2_var, self.hero2_var.get(), *hero_options).grid(row=row, column=1, sticky="we")

        for child in self.winfo_children():
            child.grid_configure(padx=2, pady=2)

    def build_config(self) -> dict:
        heroes_config = []
        for hero_var in [self.hero1_var, self.hero2_var]:
            hero_name = hero_var.get()
            if hero_name and hero_name != "None":
                preset = HERO_PRESETS.get(hero_name.lower())
                if preset:
                    heroes_config.append(
                        {
                            "hero_name_or_preset": hero_name,
                            "talent_ids": preset.get("talents", []),
                            "base_skill_ids": preset.get("base_skills", []),
                            "plugin_skill_ids": preset.get("plugin_skills", []),
                        }
                    )
        return {
            "army_name": self.name_var.get() or f"Army {self.index}",
            "unit_type": self.unit_var.get(),
            "tier": int(self.tier_var.get()),
            "count": int(self.count_var.get()),
            "atk_mod": float(self.atk_var.get() or 0),
            "def_mod": float(self.def_var.get() or 0),
            "hp_mod": float(self.hp_var.get() or 0),
            "heroes": heroes_config,
        }


def run_simulation(army_frames: list[ArmyFrame], output_widget: tk.Text, histogram_frame: tk.Frame) -> None:
    setup_data = [af.build_config() for af in army_frames]
    try:
        armies = create_armies_from_data(setup_data)
        sim = GameSimulator(armies[0], armies[1])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sim.simulate_battle()
        output_widget.delete("1.0", tk.END)
        output_widget.insert(tk.END, buf.getvalue())
        win_rate = run_additional_simulations(setup_data, verbose=False)
        output_widget.insert(tk.END, f"\nWin rate for {armies[0].name}: {win_rate*100:.1f}% over 200 runs.\n")
        display_histograms(histogram_frame)
    except Exception as exc:
        messagebox.showerror("Error", str(exc))


def display_histograms(frame: tk.Frame) -> None:
    """Load histogram images saved by run_additional_simulations and show them."""
    for child in frame.winfo_children():
        child.destroy()

    image_files = [
        "own_remaining_troops.png",
        "enemy_remaining_troops.png",
        "rounds_to_battle_end.png",
        "victory_distribution.png",
    ]
    for idx, img_name in enumerate(image_files):
        path = os.path.join("histograms", img_name)
        if not os.path.exists(path):
            continue
        try:
            photo = tk.PhotoImage(file=path)
        except Exception:
            continue
        lbl = ttk.Label(frame, image=photo)
        lbl.image = photo
        lbl.grid(row=0, column=idx, padx=5, pady=5)


def main() -> None:
    """Launch the GUI application."""
    root = tk.Tk()
    root.title("Battle Simulator")

    # Try to use a modern looking ttk theme if available
    style = ttk.Style(root)
    with contextlib.suppress(tk.TclError):
        style.theme_use("clam")

    # Configure grid to make widgets expand with the window
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    notebook = ttk.Notebook(root)
    notebook.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    army1_tab = ttk.Frame(notebook)
    army2_tab = ttk.Frame(notebook)
    notebook.add(army1_tab, text="Army 1")
    notebook.add(army2_tab, text="Army 2")

    army1_frame = ArmyFrame(army1_tab, 1)
    army1_frame.pack(fill="both", expand=True, padx=5, pady=5)

    army2_frame = ArmyFrame(army2_tab, 2)
    army2_frame.pack(fill="both", expand=True, padx=5, pady=5)

    output = scrolledtext.ScrolledText(root, width=90, height=20, wrap=tk.WORD)
    output.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

    hist_frame = ttk.Frame(root)
    hist_frame.grid(row=2, column=0, padx=10, pady=10)

    run_btn = ttk.Button(
        root,
        text="Run Simulation",
        command=lambda: run_simulation([army1_frame, army2_frame], output, hist_frame),
    )
    run_btn.grid(row=3, column=0, pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
