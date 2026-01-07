from __future__ import annotations
from typing import Dict, Tuple, List
from ..entities.base import Entity


def render_ascii(size: int, entities: Dict[str, Entity]) -> str:
    # draw top-most glyph in cell by priority
    priority = {
        "A": 90,  # Adversary
        "D": 80,  # Dek
        "F": 70,  # Father
        "B": 70,  # Brother
        "T": 60,  # Thia
        "m": 50,  # minor monster
        "U": 30,  # weapon upgrade
        "R": 30,  # repair kit
        "X": 20,  # trap
        ".": 0,
    }

    grid = [["." for _ in range(size)] for _ in range(size)]
    for e in entities.values():
        if hasattr(e, "alive") and not getattr(e, "alive"):
            continue
        x, y = e.pos
        g = e.glyph
        if priority.get(g, 0) >= priority.get(grid[y][x], 0):
            grid[y][x] = g

    lines = ["".join(row) for row in grid]
    return "\n".join(lines)
