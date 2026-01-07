from __future__ import annotations
from typing import Dict

from ..entities.base import Entity


def render_ascii(size: int, entities: Dict[str, Entity], terrain_at=None) -> str:
    """
    If terrain_at is provided (callable pos->"forest"/"grassland"),
    empty cells show:
      forest = 'f'
      grassland = 'g'
    otherwise empty = '.'
    """
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
        "b": 50,  # bison
        "g": 48,  # genna vulture
        "m": 45,  # small monsters
        "V": 40,  # attack vines
        "^": 35,  # spike pods
        "~": 30,  # razor grass
        "P": 25,  # plasma sword
        "U": 25,  # shuriken
        "M": 25,  # mask
        ".": 0,
        "f": 0,
        "g0": 0,
    }

    grid = [["." for _ in range(size)] for _ in range(size)]

    # terrain background
    if terrain_at is not None:
        for y in range(size):
            for x in range(size):
                t = terrain_at((x, y))
                grid[y][x] = "f" if t == "forest" else "g"

    # overlay entities by priority
    for e in entities.values():
        if hasattr(e, "alive") and not getattr(e, "alive"):
            continue
        x, y = e.pos
        g = e.glyph
        if priority.get(g, 0) >= priority.get(grid[y][x], 0):
            grid[y][x] = g

    return "\n".join("".join(row) for row in grid)
