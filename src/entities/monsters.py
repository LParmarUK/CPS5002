from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .base import Living, Entity
from ..utils.helpers import manhattan_wrap


# Normal adversaries

@dataclass
class ExplosiveSlug(Living):
    """
    Low-medium danger. If killed, it can explode and damage nearby agents.
    """
    def tick(self, world: "World") -> None:
        if not self.alive:
            return
        target = world.find_nearest_enemy(self, max_dist=3)
        if target:
            world.move_towards(self, target.pos)
            if self.pos == target.pos:
                world.combat(attacker=self, defender=target, tag="slug_melee")
        else:
            world.random_move(self)


@dataclass
class MicroDragon(Living):
    def tick(self, world: "World") -> None:
        if not self.alive:
            return
        target = world.find_nearest_enemy(self, max_dist=4)
        if target:
            world.move_towards(self, target.pos)
            if self.pos == target.pos:
                world.combat(attacker=self, defender=target, tag="micro_dragon")
        else:
            world.random_move(self)


@dataclass
class GennaVulture(Living):
    def tick(self, world: "World") -> None:
        if not self.alive:
            return
        # flying scavenger: prefers weaker targets
        target = world.find_weakest_enemy(self, max_dist=5)
        if target:
            world.move_towards(self, target.pos)
            if self.pos == target.pos:
                world.combat(attacker=self, defender=target, tag="vulture")
        else:
            world.random_move(self)


@dataclass
class BoneBison(Living):
    provoked: bool = False

    def tick(self, world: "World") -> None:
        if not self.alive:
            return
        # only attack if provoked, otherwise roam slowly
        if self.provoked:
            target = world.find_nearest_enemy(self, max_dist=4)
            if target:
                world.move_towards(self, target.pos)
                if self.pos == target.pos:
                    world.combat(attacker=self, defender=target, tag="bison_charge")
                return
        # peaceful roam
        world.random_move(self)


@dataclass
class LunaBug(Living):
    """
    Very high danger.
    """
    def tick(self, world: "World") -> None:
        if not self.alive:
            return
        target = world.find_nearest_enemy(self, max_dist=6)
        if target:
            world.move_towards(self, target.pos, step=2)
            if self.pos == target.pos:
                world.combat(attacker=self, defender=target, tag="lunabug")
        else:
            world.random_move(self)


# Plant hazards

@dataclass
class ShooterSpikePods(Entity):
    """
    Stationary plant: shoots nearby targets (low damage).
    """
    range: int = 3
    damage: int = 6

    def tick(self, world: "World") -> None:
        target = world.find_nearest_living_at_range(self.pos, self.range)
        if target:
            world.ranged_hit(source=self.eid, target=target, damage=self.damage, kind="spike_pods")


@dataclass
class RazorGrass(Entity):
    """
    Stationary hazard: damages anything entering its cell (low-medium).
    """
    damage: int = 8


@dataclass
class AttackVines(Entity):
    """
    Ambush plant predator: if something enters its cell or adjacent, it strikes hard.
    """
    range: int = 1
    damage: int = 14

    def tick(self, world: "World") -> None:
        target = world.find_nearest_living_at_range(self.pos, self.range)
        if target:
            world.ranged_hit(source=self.eid, target=target, damage=self.damage, kind="attack_vines")


# Ultimate adversary (Boss)

@dataclass
class KaliskApex(Living):
    """
    Boss Monster: Kalisk (Apex Monster) - Mammoth size, extreme danger.
    Habitat: Forest & Grasslands
    """
    enraged: int = 0
    slowed_turns: int = 0  # from cryo

    def tick(self, world: "World") -> None:
        if not self.alive:
            return

        dek = world.get_dek()
        if not dek or not dek.alive:
            return

        step = 1 if self.slowed_turns > 0 else 2
        if self.slowed_turns > 0:
            self.slowed_turns -= 1

        dist = manhattan_wrap(self.pos, dek.pos, world.size)
        if dist <= 7 or self.enraged > 0:
            world.move_towards(self, dek.pos, step=step)
            if self.pos == dek.pos:
                world.combat(attacker=self, defender=dek, tag="kalisk_smash")
        else:
            world.random_move(self, step=1)

from dataclasses import dataclass
from .base import Living
from ..utils.helpers import manhattan_wrap

@dataclass
class ChildKalisk(Living):
    """
    Friendly monster. Cannot be killed.
    Nickname: Bud
    Glyph: C
    """
    met_dek: bool = False

    def tick(self, world: "World") -> None:
        if not self.alive:
            return

        dek = world.get_dek()
        if not dek:
            return

        # meet/bond
        if self.pos == dek.pos:
            self.met_dek = True
            world.state.bud_found = True
            world.metrics.note_action(self.eid, "bond_with_dek")

        # follow once met
        if self.met_dek and manhattan_wrap(self.pos, dek.pos, world.size) > 1:
            world.move_towards(self, dek.pos)
            world.metrics.note_action(self.eid, "follow_dek")

        # defend: attack nearby hostile (medium power)
        hostile = world.find_nearest_hostile(self.pos, max_dist=2)
        if hostile:
            world.move_towards(self, hostile.pos)
            if self.pos == hostile.pos:
                world.combat(attacker=self, defender=hostile, tag="bud_defend")
