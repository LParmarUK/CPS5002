from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ..simulation.engine import World


class TkGridView(ttk.Frame):
    """
    Tkinter grid viewer:
    - Cell background shows terrain: forest (dark green), grassland (light green)
    - Entities render as glyphs on top
    - Plant hazards have distinct glyphs and colours
    """

    FOREST = "#0B3D0B"
    GRASS = "#7CFC90"

    def __init__(
        self,
        master: tk.Tk,
        world: World,
        cell_px: int = 26,
        padding: int = 10,
    ) -> None:
        super().__init__(master, padding=padding)
        self.world = world
        self.size = world.size
        self.cell_px = cell_px

        self.canvas = tk.Canvas(
            self,
            width=self.size * cell_px,
            height=self.size * cell_px,
            highlightthickness=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.side = ttk.Frame(self)
        self.side.grid(row=0, column=1, padx=(12, 0), sticky="n")

        self.lbl_title = ttk.Label(self.side, text="Predator: Badlands", font=("Segoe UI", 14, "bold"))
        self.lbl_title.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.stats = tk.StringVar(value="")
        self.lbl_stats = ttk.Label(self.side, textvariable=self.stats, justify="left")
        self.lbl_stats.grid(row=1, column=0, sticky="w")

        self.legend = tk.StringVar(value="")
        self.lbl_legend = ttk.Label(self.side, textvariable=self.legend, justify="left")
        self.lbl_legend.grid(row=2, column=0, sticky="w", pady=(10, 0))

        self.log = tk.StringVar(value="")
        self.lbl_log = ttk.Label(self.side, textvariable=self.log, justify="left")
        self.lbl_log.grid(row=3, column=0, sticky="w", pady=(10, 0))

        self.controls = ttk.Frame(self)
        self.controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.btn_play = ttk.Button(self.controls, text="Play", command=self.play)
        self.btn_pause = ttk.Button(self.controls, text="Pause", command=self.pause)
        self.btn_step = ttk.Button(self.controls, text="Step", command=self.step_once)
        self.speed = tk.IntVar(value=120)  # ms

        self.btn_play.grid(row=0, column=0, padx=(0, 6))
        self.btn_pause.grid(row=0, column=1, padx=(0, 6))
        self.btn_step.grid(row=0, column=2, padx=(0, 12))

        ttk.Label(self.controls, text="Speed (ms):").grid(row=0, column=3, sticky="w")
        self.scale = ttk.Scale(self.controls, from_=30, to=400, variable=self.speed, orient="horizontal", length=220)
        self.scale.grid(row=0, column=4, sticky="ew")

        self.controls.columnconfigure(4, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._running = False
        self._after_id: Optional[str] = None

        self._rect_ids = [[None] * self.size for _ in range(self.size)]
        self._text_ids = [[None] * self.size for _ in range(self.size)]
        self._init_canvas_items()

        self._set_legend()
        self.draw()

    def _init_canvas_items(self) -> None:
        px = self.cell_px
        for y in range(self.size):
            for x in range(self.size):
                x0, y0 = x * px, y * px
                x1, y1 = x0 + px, y0 + px
                rid = self.canvas.create_rectangle(x0, y0, x1, y1, outline="#1f1f1f", width=1, fill=self.GRASS)
                tid = self.canvas.create_text(x0 + px / 2, y0 + px / 2, text="", fill="#000000", font=("Consolas", 12, "bold"))
                self._rect_ids[y][x] = rid
                self._text_ids[y][x] = tid

    def _set_legend(self) -> None:
        self.legend.set(
            "Legend\n"
            "Characters:\n"
            "  D = Dek\n"
            "  T = Thia\n"
            "  S = Tessa\n"
            "  K = Kalisk (Apex)\n"
            "  C = Bud (Child Kalisk, friendly)\n"
            "  F = Father  B = Brother  E = Elder\n\n"
            "Terrain:\n"
            "  Forest = dark green\n"
            "  Grasslands = light green\n\n"
            "Plants:\n"
            "  ^ = Spike Pods (ranged)\n"
            "  ~ = Razor Grass (on-step dmg)\n"
            "  V = Attack Vines (ambush)\n"
        )


    def _glyph_for_cell(self, x: int, y: int) -> str:
        priority = {
            "K": 95,  # Kalisk
            "S": 90,  # Tessa
            "D": 85,  # Dek
            "E": 80,  # Elder
            "F": 75,  # Father
            "B": 75,  # Brother
            "T": 70,  # Thia
            "s": 60,  # basic synth
            "l": 55,  # luna bug
            "b": 50,  # bone bison
            "g": 48,  # genna vulture
            "m": 45,  # slug / micro dragon etc.
            "V": 40,  # attack vines
            "^": 35,  # spike pods
            "~": 30,  # razor grass
            "P": 25,  # plasma sword
            "U": 25,  # shuriken
            "M": 25,  # mask
            "": 0,
        }

        best_g = ""
        best_p = 0
        ids = self.world.grid.at((x, y))
        for eid in ids:
            e = self.world.entities.get(eid)
            if e is None:
                continue
            if hasattr(e, "alive") and getattr(e, "alive") is False:
                continue
            g = e.glyph
            p = priority.get(g, 0)
            if p >= best_p:
                best_p = p
                best_g = g
        return best_g

    def _fg_for_glyph(self, g: str) -> str:
        # Terrain is background; glyph colours focus on readability.
        if g == "D":
            return "#00FFF7"
        if g == "T":
            return "#FFFFFF"
        if g == "C":
            return "#FFFFFF"
        if g == "S":
            return "#FF3B3B"
        if g == "K":
            return "#FFD1DC"
        if g in ("F", "B", "E"):
            return "#FFFFFF"
        if g == "s":
            return "#FFB86B"
        if g in ("m", "g", "b", "l"):
            return "#000000"
        # Plant hazards
        if g == "^":
            return "#7A1FFF"
        if g == "~":
            return "#0047FF"
        if g == "V":
            return "#00FF3B"
        # Items
        if g == "P":
            return "#FFEA00"
        if g == "U":
            return "#FFEA00"
        if g == "M":
            return "#FFEA00"
        return "#000000"

    def draw(self) -> None:
        # paint terrain first
        for y in range(self.size):
            for x in range(self.size):
                t = self.world.grid.terrain_at((x, y))
                fill = self.FOREST if t == "forest" else self.GRASS
                self.canvas.itemconfigure(self._rect_ids[y][x], fill=fill)

        # overlay entities as glyphs
        for y in range(self.size):
            for x in range(self.size):
                g = self._glyph_for_cell(x, y)
                fg = self._fg_for_glyph(g)
                self.canvas.itemconfigure(self._text_ids[y][x], text=g, fill=fg)

        # stats panel
        dek = self.world.get_dek()
        thia = self.world.get_thia()
        kalisk = self.world.get_kalisk()
        tessa = self.world.get_tessa()

        lines = [f"Step: {self.world.metrics.steps}", ""]
        if dek:
            lines += [
                "DEK",
                f"  HP: {dek.health}   STA: {dek.stamina}",
                f"  STR: {dek.strength}  HON: {dek.honour}",
                f"  TRO: {dek.trophies}  Carry: {dek.carrying_thia}",
                f"  Items: Plasma={dek.plasma_sword} Shuriken={dek.shuriken} Mask={dek.mask}",
                "",
            ]
        if thia:
            lines += ["THIA", f"  HP: {thia.health}   Incap: {thia.incapacitated}", ""]
        if tessa:
            lines += ["TESSA", f"  HP: {tessa.health}   LaserCharge: {tessa.laser_charge}", ""]
        if kalisk:
            lines += ["KALISK", f"  HP: {kalisk.health}   Enrage: {kalisk.enraged}   Slow: {kalisk.slowed_turns}", ""]

        lines += ["STATE", f"  Win: {self.world.state.win}", f"  Lose: {self.world.state.lose}"]
        if self.world.state.end_reason:
            lines.append(f"  End: {self.world.state.end_reason}")

        self.stats.set("\n".join(lines))

        if self.world.state.win or self.world.state.lose:
            self.log.set(f"Simulation ended: {self.world.state.end_reason}")
            self.pause()

    def step_once(self) -> None:
        if self.world.state.win or self.world.state.lose:
            self.draw()
            return
        self.world.step()
        self.draw()

    def _loop(self) -> None:
        if not self._running:
            return
        self.step_once()
        delay = int(self.speed.get())
        self._after_id = self.after(delay, self._loop)

    def play(self) -> None:
        if self._running:
            return
        self._running = True
        self._loop()

    def pause(self) -> None:
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
