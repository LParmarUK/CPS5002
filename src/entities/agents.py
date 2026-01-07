from __future__ import annotations
from dataclasses import dataclass

from .base import Living
from ..utils.helpers import manhattan_wrap


@dataclass
class Predator(Living):
    honour: int = 0
    trophies: int = 0
    carrying_thia: bool = False

    def rest(self, cfg) -> None:
        self.gain_stamina(cfg.rest_gain)


@dataclass
class Dek(Predator):
    plasma_sword: bool = False
    shuriken: bool = False
    mask: bool = False

    def tick(self, world: "World") -> None:
        if not self.alive:
            return
        cfg = world.cfg

        if self.is_exhausted():
            self.rest(cfg)
            world.metrics.note_action(self.eid, "rest")
            return

        thia = world.get_thia()
        kalisk = world.get_kalisk()

        # 1) Find Thia early
        if thia and thia.alive and not world.state.thia_met:
            if world.can_see(self.pos, thia.pos):
                world.move_towards(self, thia.pos)
                world.metrics.note_action(self.eid, "seek_thia")
            else:
                world.random_move(self)
                world.metrics.note_action(self.eid, "explore")
            return

        # 2) Pick up Thia if incapacitated and in same cell
        if thia and thia.alive and thia.incapacitated and self.pos == thia.pos and not self.carrying_thia:
            self.carrying_thia = True
            world.metrics.note_action(self.eid, "carry_thia")
            return

        # 3) If strong enough, go for Kalisk
        if kalisk and kalisk.alive and (self.honour >= 45 or self.strength >= 20):
            world.move_towards(self, kalisk.pos)
            world.metrics.note_action(self.eid, "towards_kalisk")
            if self.pos == kalisk.pos:
                world.combat(attacker=self, defender=kalisk, tag="dek_vs_kalisk")
            return

        # 4) Otherwise hunt nearest hostile
        prey = world.find_nearest_hostile(self.pos, max_dist=cfg.vision_radius)
        if prey:
            world.move_towards(self, prey.pos)
            world.metrics.note_action(self.eid, "hunt")
            if self.pos == prey.pos:
                world.combat(attacker=self, defender=prey, tag="dek_hunt")
            return

        world.random_move(self)
        world.metrics.note_action(self.eid, "explore")


@dataclass
class ClanPredator(Predator):
    role: str = "clan"

    def tick(self, world: "World") -> None:
        if not self.alive:
            return

        cfg = world.cfg
        dek = world.get_dek()
        if not dek or not dek.alive:
            world.random_move(self)
            world.metrics.note_action(self.eid, "patrol")
            return

        # Father/Brother: challenge Dek if honour is low and nearby
        dist = manhattan_wrap(self.pos, dek.pos, world.size)
        if dist <= 3 and dek.honour < 20:
            world.move_towards(self, dek.pos)
            world.metrics.note_action(self.eid, "challenge_dek")
            if self.pos == dek.pos:
                world.combat(attacker=self, defender=dek, tag="clan_duel", clan_duel=True)
            return

        if self.is_exhausted():
            self.rest(cfg)
            world.metrics.note_action(self.eid, "rest")
        else:
            world.random_move(self)
            world.metrics.note_action(self.eid, "patrol")


@dataclass
class Elder(ClanPredator):
    """
    Very Strong clan member.
    """
    def tick(self, world: "World") -> None:
        if not self.alive:
            return

        dek = world.get_dek()
        if not dek or not dek.alive:
            world.random_move(self)
            world.metrics.note_action(self.eid, "patrol")
            return

        if dek.honour < 10 and manhattan_wrap(self.pos, dek.pos, world.size) <= 4:
            world.move_towards(self, dek.pos)
            world.metrics.note_action(self.eid, "elder_judgement")
            if self.pos == dek.pos:
                world.combat(attacker=self, defender=dek, tag="elder_duel", clan_duel=True)
            return

        world.random_move(self)
        world.metrics.note_action(self.eid, "patrol")


@dataclass
class Thia(Living):
    incapacitated: bool = True
    knowledge_given: bool = False

    def tick(self, world: "World") -> None:
        if not self.alive:
            return
        dek = world.get_dek()
        if dek and dek.alive and dek.pos == self.pos:
            world.state.thia_met = True
            if not self.knowledge_given:
                self.knowledge_given = True
                world.state.thia_hint_ready = True
                world.metrics.note_action(self.eid, "give_clue")


@dataclass
class BasicSynth(Living):
    """
    Underlings of Tessa.
    """
    def tick(self, world: "World") -> None:
        if not self.alive:
            return
        dek = world.get_dek()
        if dek and dek.alive and manhattan_wrap(self.pos, dek.pos, world.size) <= 4:
            world.move_towards(self, dek.pos)
            if self.pos == dek.pos:
                world.combat(attacker=self, defender=dek, tag="basic_synth")
        else:
            world.random_move(self)


@dataclass
class Tessa(Living):
    """
    Evil strong synth:
    - Cryo Grenade: medium-high damage, slows Kalisk if it hits Kalisk (via ranged_hit cryo=True)
    - Shoulder Laser: high damage, fires after charge delay
    """
    laser_charge: int = 0

    def tick(self, world: "World") -> None:
        if not self.alive:
            return

        cfg = world.cfg
        dek = world.get_dek()
        if not dek or not dek.alive:
            world.random_move(self)
            return

        dist = manhattan_wrap(self.pos, dek.pos, world.size)

        # charge shoulder laser
        self.laser_charge += 1
        if dist <= 6 and self.laser_charge >= cfg.shoulder_laser_charge:
            self.laser_charge = 0
            world.ranged_hit(
                source=self.eid,
                target=dek,
                damage=cfg.ranged_damage + 14,
                kind="shoulder_laser",
                cryo=False,
            )
            world.metrics.note_action(self.eid, "laser_fire")
            return

        # cryo grenade
        if dist <= 3 and self.stamina >= 10:
            self.spend_stamina(6)
            world.ranged_hit(
                source=self.eid,
                target=dek,
                damage=cfg.ranged_damage + 6,
                kind="cryo_grenade",
                cryo=True,
            )
            world.metrics.note_action(self.eid, "cryo_grenade")
            return

        world.move_towards(self, dek.pos)
        world.metrics.note_action(self.eid, "pursue")
