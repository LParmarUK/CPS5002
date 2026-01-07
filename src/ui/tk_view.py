from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ..simulation.engine import World
from ..entities.base import Entity


class TkGridView(ttk.Frame):
    """
    Simple Tkinter grid viewer for the simulation.
    Draws each cell as a colored rectangle with a glyph character.
    """

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

        # Layout: canvas left, stats right, controls bottom
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

        self.log = tk.StringVar(value="")
        self.lbl_log = ttk.Label(self.side, textvariable=self.log, justify="left", foreground="#666666")
        self.lbl_log.grid(row=2, column=0, sticky="w", pady=(10, 0))

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

        # Animation state
        self._running = False
        self._after_id: Optional[str] = None

        # Pre-create grid rects + text items for speed
        self._rect_ids = [[None] * self.size for _ in range(self.size)]
        self._text_ids = [[None] * self.size for _ in range(self.size)]
        self._init_canvas_items()

        self.draw()

    def _init_canvas_items(self) -> None:
        px = self.cell_px
        for y in range(self.size):
            for x in range(self.size):
                x0, y0 = x * px, y * px
                x1, y1 = x0 + px, y0 + px
                rid = self.canvas.create_rectangle(x0, y0, x1, y1, outline="#2b2b2b", width=1, fill="#101010")
                tid = self.canvas.create_text(x0 + px / 2, y0 + px / 2, text=".", fill="#bbbbbb", font=("Consolas", 12, "bold"))
                self._rect_ids[y][x] = rid
                self._text_ids[y][x] = tid

    def _glyph_for_cell(self, x: int, y: int) -> str:
        # priority draw similar to ASCII renderer
        priority = {
            "A": 90,
            "D": 80,
            "F": 70,
            "B": 70,
            "T": 60,
            "m": 50,
            "U": 30,
            "R": 30,
            "X": 20,
            "P": 10,
            ".": 0,
        }

        best_g = "."
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

    def _style_for_glyph(self, g: str) -> tuple[str, str]:
        """
        Returns (cell_fill, text_color). Keep it simple and readable.
        """
        # Dark background palette + accent for key actors
        if g == "D":
            return ("#003b39", "#00fff7")
        if g == "T":
            return ("#1f2a44", "#e6f0ff")
        if g == "A":
            return ("#3b0010", "#ffd1dc")
        if g in ("F", "B"):
            return ("#2c2c2c", "#ffffff")
        if g == "m":
            return ("#2a1f00", "#ffe29a")
        if g == "X":
            return ("#2a0000", "#ff9c9c")
        if g == "P":
            return ("#0f1f2a", "#b8e6ff")
        if g == "U":
            return ("#003a1a", "#baffc9")
        if g == "R":
            return ("#2a0033", "#f4c2ff")
        return ("#101010", "#bbbbbb")

    def draw(self) -> None:
        # Update all cells
        for y in range(self.size):
            for x in range(self.size):
                g = self._glyph_for_cell(x, y)
                fill, fg = self._style_for_glyph(g)

                self.canvas.itemconfigure(self._rect_ids[y][x], fill=fill)
                self.canvas.itemconfigure(self._text_ids[y][x], text=g, fill=fg)

        # Stats panel
        dek = self.world.get_dek()
        thia = self.world.get_thia()
        adv = self.world.get_adversary()

        s = []
        s.append(f"Step: {self.world.metrics.steps}")
        s.append("")
        if dek:
            s.append("DEK")
            s.append(f"  HP: {dek.health}   STA: {dek.stamina}")
            s.append(f"  STR: {dek.strength}  HON: {dek.honour}")
            s.append(f"  TRO: {dek.trophies}  Carry: {dek.carrying_thia}")
            s.append("")
        if thia:
            s.append("THIA")
            s.append(f"  HP: {thia.health}   Incap: {thia.incapacitated}")
            s.append("")
        if adv:
            s.append("ADVERSARY")
            s.append(f"  HP: {adv.health}   Enrage: {adv.enraged}")
            s.append("")

        s.append("STATE")
        s.append(f"  Win: {self.world.state.win}")
        s.append(f"  Lose: {self.world.state.lose}")
        if self.world.state.end_reason:
            s.append(f"  End: {self.world.state.end_reason}")

        self.stats.set("\n".join(s))

        # End condition message
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
