"""Tkinter based graphical interface for configuring and running battles."""

from __future__ import annotations

import contextlib
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog

from PIL import Image, ImageTk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from vr_game_sim.hero_definition import HERO_PRESETS
from vr_game_sim.unit_definition import Unit
from vr_game_sim.game_simulator import GameSimulator
from vr_game_sim.report_builder import ReportBuilder
from vr_game_sim.main import (
    create_armies_from_data,
    run_additional_simulations,
    save_setup_to_file,
    load_setup_from_file,
)
from vr_game_sim.skill_definitions import SKILL_REGISTRY_GLOBAL, SkillType


class HeroEditDialog(tk.Toplevel):
    """Popup dialog to edit or create a hero configuration."""

    def __init__(self, master: tk.Misc, hero_config: dict | None = None):
        super().__init__(master)
        self.title("Edit Hero")
        self.resizable(False, False)
        self.result: dict | None = None

        self.hero_name_var = tk.StringVar(value="" if hero_config is None else hero_config.get("hero_name_or_preset", ""))

        def _skill_options(skill_type: SkillType, include_none: bool = True):
            options = ["None"] if include_none else []
            opts = sorted(
                ((sid, sdef["name"]) for sid, sdef in SKILL_REGISTRY_GLOBAL.items() if sdef["type"] == skill_type),
                key=lambda x: x[1],
            )
            options.extend(name for _, name in opts)
            mapping = {sdef["name"]: sid for sid, sdef in SKILL_REGISTRY_GLOBAL.items() if sdef["type"] == skill_type}
            mapping["None"] = "dummy_talent_empty" if skill_type == SkillType.TALENT else ""
            return options, mapping

        self.talent_vars: list[tk.StringVar] = []
        self.base_vars: list[tk.StringVar] = []
        self.plugin_vars: list[tk.StringVar] = []

        ttk.Label(self, text="Hero Name:").grid(row=0, column=0, sticky="e")
        ttk.Entry(self, textvariable=self.hero_name_var, width=20).grid(row=0, column=1, columnspan=2, pady=2, sticky="we")

        talent_options, self.talent_map = _skill_options(SkillType.TALENT)
        base_options, self.base_map = _skill_options(SkillType.BASE_SKILL)
        plugin_options, self.plugin_map = _skill_options(SkillType.PLUGIN_SKILL)

        row = 1
        ttk.Label(self, text="Talents:").grid(row=row, column=0, sticky="e")
        for i in range(3):
            var = tk.StringVar(value="None")
            if hero_config and i < len(hero_config.get("talent_ids", [])):
                sid = hero_config["talent_ids"][i]
                var.set(SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None"))
            self.talent_vars.append(var)
            ttk.OptionMenu(self, var, var.get(), *talent_options).grid(row=row, column=i + 1, sticky="we")
        row += 1

        ttk.Label(self, text="Base Skills:").grid(row=row, column=0, sticky="e")
        for i in range(2):
            var = tk.StringVar(value="None")
            if hero_config and i < len(hero_config.get("base_skill_ids", [])):
                sid = hero_config["base_skill_ids"][i]
                var.set(SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None"))
            self.base_vars.append(var)
            ttk.OptionMenu(self, var, var.get(), *base_options).grid(row=row, column=i + 1, sticky="we")
        row += 1

        ttk.Label(self, text="Plugin Skills:").grid(row=row, column=0, sticky="e")
        for i in range(2):
            var = tk.StringVar(value="None")
            if hero_config and i < len(hero_config.get("plugin_skill_ids", [])):
                sid = hero_config["plugin_skill_ids"][i]
                var.set(SKILL_REGISTRY_GLOBAL.get(sid, {}).get("name", "None"))
            self.plugin_vars.append(var)
            ttk.OptionMenu(self, var, var.get(), *plugin_options).grid(row=row, column=i + 1, sticky="we")

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=row + 1, column=0, columnspan=3, pady=5)
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

        self.grab_set()
        self.wait_window(self)

    def _on_ok(self):
        name = self.hero_name_var.get().strip()
        if not name:
            messagebox.showerror("Error", "Hero name required")
            return
        talents = [self.talent_map.get(var.get(), "") for var in self.talent_vars]
        base_skills = [self.base_map.get(var.get(), "") for var in self.base_vars if var.get() != "None"]
        plugin_skills = [self.plugin_map.get(var.get(), "") for var in self.plugin_vars if var.get() != "None"]
        self.result = {
            "hero_name_or_preset": name,
            "talent_ids": talents,
            "base_skill_ids": base_skills,
            "plugin_skill_ids": plugin_skills,
        }
        self.destroy()


class ArmyFrame(tk.LabelFrame):
    """GUI inputs for a single army."""

    def __init__(self, master: tk.Misc, index: int):
        super().__init__(master, text=f"Army {index}")
        self.index = index

        self.hero_options = ["None", "Custom"] + sorted(name.capitalize() for name in HERO_PRESETS.keys())

        self.name_var = tk.StringVar(value=f"Army {index}")
        self.unit_var = tk.StringVar(value="pikemen")
        self.tier_var = tk.StringVar(value="5")
        self.count_var = tk.StringVar(value="100000")
        self.atk_var = tk.StringVar(value="0")
        self.def_var = tk.StringVar(value="0")
        self.hp_var = tk.StringVar(value="0")
        self.hero1_var = tk.StringVar(value="None")
        self.hero2_var = tk.StringVar(value="None")

        self.custom_heroes: dict[int, dict] = {1: None, 2: None}

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
        self.hero1_menu = ttk.OptionMenu(self, self.hero1_var, self.hero1_var.get(), *self.hero_options, command=lambda val: self._hero_changed(1, val))
        self.hero1_menu.grid(row=row, column=1, sticky="we")
        ttk.Button(self, text="Edit", command=lambda: self.edit_hero(1)).grid(row=row, column=2, sticky="w")
        row += 1

        ttk.Label(self, text="Hero 2:").grid(row=row, column=0, sticky="e")
        self.hero2_menu = ttk.OptionMenu(self, self.hero2_var, self.hero2_var.get(), *self.hero_options, command=lambda val: self._hero_changed(2, val))
        self.hero2_menu.grid(row=row, column=1, sticky="we")
        ttk.Button(self, text="Edit", command=lambda: self.edit_hero(2)).grid(row=row, column=2, sticky="w")

        for child in self.winfo_children():
            child.grid_configure(padx=2, pady=2)

    def _add_custom_hero_option(self, name: str) -> None:
        if name not in self.hero_options:
            self.hero_options.append(name)
            for menu in [self.hero1_menu['menu'], self.hero2_menu['menu']]:
                menu.add_command(label=name, command=lambda v=name: None)

    def _hero_changed(self, slot: int, value: str) -> None:
        if value == "Custom":
            self.edit_hero(slot)
            return

        # Clear or set hero configuration when a different hero is selected so
        # the base skills and talents match the newly chosen hero.  This avoids
        # the previously selected hero's configuration becoming "locked" in
        # place when switching between heroes via the dropdown.
        if value in ("None", ""):
            self.custom_heroes[slot] = None
            return

        # If the selected name is one of the predefined presets, discard any
        # custom configuration so the preset values are used.
        if value.lower() in HERO_PRESETS:
            self.custom_heroes[slot] = None
        else:
            # Otherwise attempt to carry over an existing custom hero by name.
            cfg = self.custom_heroes.get(slot)
            if not (cfg and cfg.get("hero_name_or_preset") == value):
                self.custom_heroes[slot] = None

    def edit_hero(self, slot: int) -> None:
        current_cfg = self.custom_heroes.get(slot)
        if current_cfg is None:
            hero_name = self.hero1_var.get() if slot == 1 else self.hero2_var.get()
            preset = HERO_PRESETS.get(hero_name.lower())
            if preset:
                current_cfg = {
                    "hero_name_or_preset": hero_name,
                    "talent_ids": preset.get("talents", []),
                    "base_skill_ids": preset.get("base_skills", []),
                    "plugin_skill_ids": preset.get("plugin_skills", []),
                }
        dlg = HeroEditDialog(self, current_cfg)
        if dlg.result:
            self.custom_heroes[slot] = dlg.result
            name = dlg.result["hero_name_or_preset"]
            self._add_custom_hero_option(name)
            if slot == 1:
                self.hero1_var.set(name)
            else:
                self.hero2_var.set(name)

    def populate_from_config(self, cfg: dict) -> None:
        self.name_var.set(cfg.get("army_name", f"Army {self.index}"))
        self.unit_var.set(cfg.get("unit_type", "pikemen"))
        self.tier_var.set(str(cfg.get("tier", 5)))
        self.count_var.set(str(cfg.get("count", 100000)))
        self.atk_var.set(str(cfg.get("atk_mod", 0)))
        self.def_var.set(str(cfg.get("def_mod", 0)))
        self.hp_var.set(str(cfg.get("hp_mod", 0)))

        hero_vars = [self.hero1_var, self.hero2_var]
        for idx, hv in enumerate(hero_vars, start=1):
            hv.set("None")
            self.custom_heroes[idx] = None
        for idx, hero_cfg in enumerate(cfg.get("heroes", []), start=1):
            if idx > 2:
                break
            name = hero_cfg.get("hero_name_or_preset", "")
            preset = HERO_PRESETS.get(name.lower())
            if preset and preset.get("talents") == hero_cfg.get("talent_ids") and preset.get("base_skills") == hero_cfg.get("base_skill_ids") and preset.get("plugin_skills") == hero_cfg.get("plugin_skill_ids"):
                hero_name_display = name.capitalize()
            else:
                hero_name_display = name
                self.custom_heroes[idx] = hero_cfg
                self._add_custom_hero_option(name)
            hero_vars[idx - 1].set(hero_name_display)

    def build_config(self) -> dict:
        heroes_config = []
        for idx, hero_var in enumerate([self.hero1_var, self.hero2_var], start=1):
            hero_name = hero_var.get()
            if hero_name and hero_name != "None" and hero_name != "Custom":
                custom_cfg = self.custom_heroes.get(idx)
                if custom_cfg and custom_cfg.get("hero_name_or_preset") == hero_name:
                    heroes_config.append(custom_cfg)
                    continue
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


class ScrollableFrame(ttk.Frame):
    """A simple vertically scrollable frame."""

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.vscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        # Create the interior window and remember its id so we can resize it
        self._window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        # Ensure the interior frame always matches the canvas width
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._window_id, width=e.width),
        )

        self.canvas.configure(yscrollcommand=self.vscroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vscroll.pack(side="right", fill="y")


def run_simulation(
    army_frames: list[ArmyFrame],
    output_widget: tk.Text,
    histogram_frame: tk.Frame,
    status_var: tk.StringVar,
    progress: ttk.Progressbar,
) -> None:

    def task() -> None:
        setup_data = [af.build_config() for af in army_frames]
        try:
            armies = create_armies_from_data(setup_data)
            report_builder = ReportBuilder(use_color=False)
            sim = GameSimulator(armies[0], armies[1], report_builder)
            report_text = sim.simulate_battle()
            def progress_cb(done: int, total: int) -> None:
                output_widget.after(0, lambda: progress.configure(value=done, maximum=total))

            win_rate = run_additional_simulations(
                setup_data, verbose=False, progress_callback=progress_cb
            )
            result_text = (
                report_text
                + f"\nWin rate for {armies[0].name}: {win_rate*100:.1f}% over 200 runs.\n"
            )

            def update():
                output_widget.configure(state=tk.NORMAL)
                output_widget.delete("1.0", tk.END)
                output_widget.insert(tk.END, result_text)
                output_widget.see("1.0")
                output_widget.configure(state=tk.DISABLED)
                display_histograms(histogram_frame)
                progress.configure(value=0)
                status_var.set("Ready")

            output_widget.after(0, update)
        except Exception as exc:
            def show_err():
                progress.configure(value=0)
                status_var.set("Ready")
                messagebox.showerror("Error", str(exc))

            output_widget.after(0, show_err)

    status_var.set("Running simulation...")
    progress.configure(mode="determinate", value=0, maximum=200)
    threading.Thread(target=task, daemon=True).start()


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
    max_width = 300
    for idx, img_name in enumerate(image_files):
        path = os.path.join("histograms", img_name)
        if not os.path.exists(path):
            continue
        try:
            img = Image.open(path)
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
        except Exception:
            continue
        lbl = ttk.Label(frame, image=photo)
        lbl.image = photo
        # Display all histogram images in a single horizontal row
        lbl.grid(row=0, column=idx, padx=5, pady=5)


def main() -> None:
    """Launch the GUI application."""
    root = tk.Tk()
    root.title("Battle Simulator")

    # Try to use a modern looking ttk theme if available
    style = ttk.Style(root)
    with contextlib.suppress(tk.TclError):
        style.theme_use("clam")

    primary_bg = "#f0f0f0"
    style.configure("TFrame", background=primary_bg)
    style.configure("TLabel", background=primary_bg, font=("Segoe UI", 10))
    style.configure("Header.TLabel", background=primary_bg, font=("Segoe UI", 12, "bold"))
    style.configure("TButton", font=("Segoe UI", 10))
    style.configure("Custom.TLabelframe", background=primary_bg)
    style.configure("Custom.TLabelframe.Label", background=primary_bg, font=("Segoe UI", 12, "bold"))
    style.configure(
        "Success.Horizontal.TProgressbar",
        troughcolor="#ddd",
        background="#4caf50",
    )
    root.configure(background=primary_bg)

    # Configure grid to make widgets expand with the window
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    # Wrap the entire interface in a scrollable frame so the UI works on small screens
    scroll = ScrollableFrame(root)
    scroll.grid(row=0, column=0, sticky="nsew")
    main_frame = scroll.scrollable_frame
    main_frame.columnconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)
    main_frame.rowconfigure(2, weight=1)

    notebook = ttk.Notebook(main_frame)
    notebook.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    army1_tab = ttk.Frame(notebook)
    army2_tab = ttk.Frame(notebook)
    notebook.add(army1_tab, text="Army 1")
    notebook.add(army2_tab, text="Army 2")

    army1_frame = ArmyFrame(army1_tab, 1)
    army1_frame.pack(fill="both", expand=True, padx=5, pady=5)

    army2_frame = ArmyFrame(army2_tab, 2)
    army2_frame.pack(fill="both", expand=True, padx=5, pady=5)

    report_frame = ttk.LabelFrame(main_frame, text="Battle Report", style="Custom.TLabelframe")
    report_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
    report_frame.columnconfigure(0, weight=1)
    report_frame.rowconfigure(0, weight=1)

    output = scrolledtext.ScrolledText(report_frame, height=20, wrap=tk.NONE)
    output.grid(row=0, column=0, sticky="nsew")
    x_scroll = ttk.Scrollbar(report_frame, orient="horizontal", command=output.xview)
    x_scroll.grid(row=1, column=0, sticky="ew")
    output.configure(xscrollcommand=x_scroll.set)

    hist_scroll = ScrollableFrame(main_frame)
    hist_scroll.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
    hist_frame = hist_scroll.scrollable_frame

    status_var = tk.StringVar(value="Ready")
    status_label = ttk.Label(main_frame, textvariable=status_var)
    status_label.grid(row=3, column=0, pady=(0, 5))

    progress = ttk.Progressbar(
        main_frame,
        mode="indeterminate",
        style="Success.Horizontal.TProgressbar",
    )
    progress.grid(row=4, column=0, sticky="ew", padx=10)

    btn_frame = ttk.Frame(main_frame)
    btn_frame.grid(row=5, column=0, pady=10)

    def save_current_setup() -> None:
        file_path = filedialog.asksaveasfilename(initialdir="setups", defaultextension=".json")
        if file_path:
            save_setup_to_file([army1_frame.build_config(), army2_frame.build_config()], os.path.basename(file_path))
            status_var.set(f"Saved to {os.path.basename(file_path)}")

    def load_setup() -> None:
        file_path = filedialog.askopenfilename(initialdir="setups", filetypes=[("JSON files", "*.json")])
        if file_path:
            data = load_setup_from_file(file_path)
            if data and len(data) >= 2:
                army1_frame.populate_from_config(data[0])
                army2_frame.populate_from_config(data[1])
                status_var.set(f"Loaded {os.path.basename(file_path)}")

    save_btn = ttk.Button(btn_frame, text="Save Setup", command=save_current_setup)
    save_btn.pack(side="left", padx=5)

    load_btn = ttk.Button(btn_frame, text="Load Setup", command=load_setup)
    load_btn.pack(side="left", padx=5)

    run_btn = ttk.Button(
        btn_frame,
        text="Run Simulation",
        command=lambda: run_simulation(
            [army1_frame, army2_frame], output, hist_frame, status_var, progress
        ),
    )
    run_btn.pack(side="left", padx=5)

    root.mainloop()


if __name__ == "__main__":
    main()
