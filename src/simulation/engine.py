from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List, Any, Set

from .grid import Grid
from .rng import RNG
from .metrics import Metrics
from ..config import Config

from ..entities.base import Entity, Living, Pos
from ..entities.agents import Dek, ClanPredator, Elder, Thia, Tessa, BasicSynth
from ..entities.monsters import (
    ExplosiveSlug,
    MicroDragon,
    ShooterSpikePods,
    RazorGrass,
    AttackVines,
    GennaVulture,
    BoneBison,
    LunaBug,
    KaliskApex,
    ChildKalisk,
)
from ..entities.items import PlasmaSword, Shuriken, Mask

from ..utils.helpers import neighbours4, step_towards_wrap, manhattan_wrap


@dataclass
class WorldState:
    thia_met: bool = False
    thia_hint_ready: bool = False

    bud_found: bool = False

    kalisk_captured: bool = False
    tessa_dead: bool = False

    win: bool = False
    lose: bool = False
    end_reason: str = ""


class World:
    def __init__(self, cfg: Config, rng: RNG) -> None:
        self.cfg = cfg
        self.rng = rng
        self.size = cfg.grid_size
        self.grid = Grid(self.size)
        self.entities: Dict[str, Entity] = {}
        self.metrics = Metrics()
        self.state = WorldState()


    # entity management
    def add_entity(self, e: Entity) -> None:
        self.entities[e.eid] = e
        self.grid.add(e.eid, e.pos)

    def remove_entity(self, eid: str) -> None:
        e = self.entities.get(eid)
        if not e:
            return
        self.grid.remove(eid, e.pos)
        del self.entities[eid]

    def get_dek(self) -> Optional[Dek]:
        e = self.entities.get("dek")
        return e if isinstance(e, Dek) else None

    def get_thia(self) -> Optional[Thia]:
        e = self.entities.get("thia")
        return e if isinstance(e, Thia) else None

    def get_tessa(self) -> Optional[Tessa]:
        e = self.entities.get("tessa")
        return e if isinstance(e, Tessa) else None

    def get_kalisk(self) -> Optional[KaliskApex]:
        e = self.entities.get("kalisk")
        return e if isinstance(e, KaliskApex) else None

    def get_bud(self) -> Optional[ChildKalisk]:
        e = self.entities.get("bud")
        return e if isinstance(e, ChildKalisk) else None


    # placement helpers
    def random_empty_pos(self) -> Pos:
        for _ in range(12000):
            pos = (self.rng.randint(0, self.size - 1), self.rng.randint(0, self.size - 1))
            if not self.is_key_blocked(pos):
                return pos
        return (0, 0)

    def is_key_blocked(self, pos: Pos) -> bool:
        ids = self.grid.at(pos)
        for eid in ids:
            g = self.entities[eid].glyph
            if g in ("D", "K", "F", "B", "E", "T", "S", "C"):
                return True
        return False

    def is_hazard_cell(self, pos: Pos) -> bool:
        ids = self.grid.at(pos)
        for eid in ids:
            obj = self.entities.get(eid)
            if obj is None:
                continue
            if obj.glyph in ("~", "^", "V"):
                return True
        return False

    def random_empty_nonhazard_pos(self) -> Pos:
        for _ in range(16000):
            pos = (self.rng.randint(0, self.size - 1), self.rng.randint(0, self.size - 1))
            if self.is_key_blocked(pos):
                continue
            if self.is_hazard_cell(pos):
                continue
            return pos
        return self.random_empty_pos()

    def random_safe_pos_strict(self, avoid_glyphs: Set[str], min_dist: int) -> Pos:
        for _ in range(20000):
            pos = (self.rng.randint(0, self.size - 1), self.rng.randint(0, self.size - 1))
            if self.is_key_blocked(pos):
                continue
            if self.is_hazard_cell(pos):
                continue

            ok = True
            for e in self.entities.values():
                if getattr(e, "alive", True) is False:
                    continue
                if e.glyph in avoid_glyphs:
                    if manhattan_wrap(pos, e.pos, self.size) < min_dist:
                        ok = False
                        break
            if ok:
                return pos
        return self.random_empty_nonhazard_pos()


    # sensing helpers
    def can_see(self, a: Pos, b: Pos) -> bool:
        return manhattan_wrap(a, b, self.size) <= self.cfg.vision_radius

    def find_nearest_living_at_range(self, pos: Pos, r: int, ignore_glyphs: Set[str] | None = None) -> Optional[Living]:
        ignore_glyphs = ignore_glyphs or set()
        best = None
        bestd = 10**9
        for e in self.entities.values():
            if isinstance(e, Living) and e.alive and e.glyph not in ignore_glyphs:
                d = manhattan_wrap(pos, e.pos, self.size)
                if 0 < d <= r and d < bestd:
                    best, bestd = e, d
        return best

    def find_nearest_enemy(self, src: Living, max_dist: int) -> Optional[Living]:
        candidates: List[Living] = []
        for e in self.entities.values():
            if not isinstance(e, Living) or not e.alive:
                continue
            if e.eid == src.eid:
                continue
            if e.glyph in ("D", "F", "B", "E", "T", "C"):
                d = manhattan_wrap(src.pos, e.pos, self.size)
                if d <= max_dist:
                    candidates.append(e)
        if not candidates:
            return None
        candidates.sort(key=lambda x: manhattan_wrap(src.pos, x.pos, self.size))
        return candidates[0]

    def find_weakest_enemy(self, src: Living, max_dist: int) -> Optional[Living]:
        candidates: List[Living] = []
        for e in self.entities.values():
            if not isinstance(e, Living) or not e.alive:
                continue
            if e.eid == src.eid:
                continue
            if e.glyph in ("D", "F", "B", "E", "T", "C"):
                d = manhattan_wrap(src.pos, e.pos, self.size)
                if d <= max_dist:
                    candidates.append(e)
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x.health, manhattan_wrap(src.pos, x.pos, self.size)))
        return candidates[0]

    def find_nearest_hostile(self, pos: Pos, max_dist: int) -> Optional[Living]:
        hostile_glyphs = {"s", "S", "g", "b", "l", "K", "m"}
        best = None
        bestd = 10**9
        for e in self.entities.values():
            if isinstance(e, Living) and e.alive and e.glyph in hostile_glyphs:
                d = manhattan_wrap(pos, e.pos, self.size)
                if d <= max_dist and d < bestd:
                    best, bestd = e, d
        return best


    # movement
    def _cell_has_glyph(self, pos: Pos, glyph: str) -> bool:
        ids = self.grid.at(pos)
        for eid in ids:
            obj = self.entities.get(eid)
            if obj is not None and obj.glyph == glyph:
                return True
        return False

    def move_entity(self, e: Entity, new_pos: Pos) -> None:
        old = e.pos
        e.pos = new_pos
        self.grid.move(e.eid, old, new_pos)

    def random_move(self, e: Living, step: int = 1) -> None:
        for _ in range(step):
            options = neighbours4(e.pos, self.size)

            # Dek avoids razor grass if possible
            if isinstance(e, Dek):
                safe = [p for p in options if not self._cell_has_glyph(p, "~")]
                if safe:
                    options = safe

            nxt = self.rng.choice(options)
            self._move_costs(e, nxt)
            self.move_entity(e, nxt)
            self._resolve_cell(e)

    def move_towards(self, e: Living, target: Pos, step: int = 1) -> None:
        for _ in range(step):
            nxt = step_towards_wrap(e.pos, target, self.size)
            self._move_costs(e, nxt)
            self.move_entity(e, nxt)
            self._resolve_cell(e)

    def _move_costs(self, e: Living, nxt: Pos) -> None:
        cost = self.cfg.base_move_cost
        if self.grid.terrain_at(nxt) == "forest":
            cost += self.cfg.forest_move_extra_cost

        if isinstance(e, Dek):
            if e.carrying_thia:
                cost += self.cfg.carry_move_extra_cost
            e.spend_stamina(cost)
        else:
            e.spend_stamina(max(1, cost - 1))


    # protection rules (story)
    def _protect_story_targets(self, target: Living) -> None:
        """
        Enforce: Dek and Thia survive until Tessa is dead.
        Bud cannot be killed ever.
        """
        if target.eid == "bud":
            # Bud cannot die; clamp high enough
            if target.health <= 0:
                target.health = 9999
            target.alive = True
            return

        if not self.state.tessa_dead and target.eid in ("dek", "thia"):
            if target.health <= 0:
                target.health = 1
                target.alive = True


    # ranged hits
    def ranged_hit(self, source: str, target: Living, damage: int, kind: str, cryo: bool = False) -> None:
        if not target.alive:
            return

        # Tessa invulnerable until capture
        if target.eid == "tessa" and not self.state.kalisk_captured:
            self.metrics.note("ranged_hit", source=source, target=target.eid, dmg=0, attack_kind=kind, hp=target.health, blocked=True)
            return

        target.take_damage(damage)
        self._protect_story_targets(target)

        self.metrics.note("ranged_hit", source=source, target=target.eid, dmg=damage, attack_kind=kind, hp=target.health)

        if cryo:
            k = self.get_kalisk()
            if k and target.eid == k.eid:
                k.slowed_turns = max(k.slowed_turns, self.cfg.cryo_slow_turns)

        if not target.alive:
            self.metrics.note("death", who=target.eid, reason=kind)


    # cell resolution (hazards + items)
    def _resolve_cell(self, mover: Living) -> None:
        if not mover.alive:
            return

        ids_here = self.grid.at(mover.pos)
        for eid in list(ids_here):
            obj = self.entities.get(eid)
            if obj is None or obj.eid == mover.eid:
                continue

            # Razor grass damages on entry (but story-protect Dek/Thia)
            if isinstance(obj, RazorGrass):
                mover.take_damage(obj.damage)
                self._protect_story_targets(mover)
                self.metrics.note("hazard", hazard_kind="razor_grass", victim=mover.eid, dmg=obj.damage, hp=mover.health)
                if not mover.alive:
                    self.metrics.note("death", who=mover.eid, reason="razor_grass")
                    return

            # Dek pickups
            if isinstance(mover, Dek):
                if isinstance(obj, PlasmaSword) and not mover.plasma_sword:
                    mover.plasma_sword = True
                    mover.strength += obj.attack_bonus
                    mover.honour += 8
                    self.metrics.note("pickup", who=mover.eid, item="plasma_sword")
                    self.remove_entity(obj.eid)

                if isinstance(obj, Shuriken) and not mover.shuriken:
                    mover.shuriken = True
                    mover.strength += obj.ranged_bonus
                    mover.honour += 4
                    self.metrics.note("pickup", who=mover.eid, item="shuriken")
                    self.remove_entity(obj.eid)

                if isinstance(obj, Mask) and not mover.mask:
                    mover.mask = True
                    mover.health = min(110, mover.health + obj.health_bonus)
                    mover.honour += 3
                    self.metrics.note("pickup", who=mover.eid, item="mask")
                    self.remove_entity(obj.eid)


    # combat
    def combat(self, attacker: Living, defender: Living, tag: str, clan_duel: bool = False) -> None:
        if not attacker.alive or not defender.alive:
            return

        # Tessa cannot be killed until capture
        if defender.eid == "tessa" and not self.state.kalisk_captured:
            self.metrics.note("combat", tag=tag, attacker=attacker.eid, defender=defender.eid, hit=False, dmg=0, hp=defender.health, blocked=True)
            return

        atk_score = attacker.strength + (attacker.stamina / 10)
        def_score = defender.strength + (defender.stamina / 10)

        roll = self.rng.random()
        hit_prob = max(0.15, min(0.85, 0.5 + (atk_score - def_score) * 0.03))
        hit = roll < hit_prob

        dmg = 0
        if hit:
            dmg = int(self.cfg.base_melee_damage + attacker.strength * 0.55)
            defender.take_damage(dmg)

        attacker.spend_stamina(4)
        defender.spend_stamina(2)

        self._protect_story_targets(defender)

        self.metrics.note("combat", tag=tag, attacker=attacker.eid, defender=defender.eid, hit=hit, dmg=dmg, hp=defender.health)

        # provoke bison
        if isinstance(defender, BoneBison) and hit:
            defender.provoked = True

        # slug explosion on death
        if isinstance(defender, ExplosiveSlug) and defender.health <= 0:
            for e in self.entities.values():
                if isinstance(e, Living) and e.alive:
                    if manhattan_wrap(defender.pos, e.pos, self.size) <= 1:
                        e.take_damage(10)
                        self._protect_story_targets(e)
                        self.metrics.note("explosion", source=defender.eid, victim=e.eid, dmg=10, hp=e.health)

        # boss enrage
        k = self.get_kalisk()
        if k and defender.eid == k.eid and hit:
            k.enraged = min(10, k.enraged + 1)

        # death handling
        if not defender.alive:
            self.metrics.note("death", who=defender.eid, reason="combat")

            # Win condition: kill Tessa (only possible after capture)
            if defender.eid == "tessa":
                self.state.tessa_dead = True
                self.state.win = True
                self.state.end_reason = "tessa_killed"
                return

    # step loop
    def step(self) -> None:
        if self.state.win or self.state.lose:
            return

        self.metrics.steps += 1

        # Thia clue
        if self.state.thia_hint_ready:
            self.state.thia_hint_ready = False
            dek = self.get_dek()
            if dek and dek.alive:
                dek.honour += 2
                self.metrics.note("clue", who="thia", effect="honour_boost")

        # tick order
        for eid in ["dek", "father", "brother", "elder", "thia", "bud", "tessa"]:
            e = self.entities.get(eid)
            if e is not None:
                e.tick(self)

        # synth underlings
        for e in list(self.entities.values()):
            if isinstance(e, BasicSynth):
                e.tick(self)

        # plants
        for e in list(self.entities.values()):
            if isinstance(e, (ShooterSpikePods, AttackVines)):
                e.tick(self)

        # creatures
        for e in list(self.entities.values()):
            if isinstance(e, (ExplosiveSlug, MicroDragon, GennaVulture, BoneBison, LunaBug)):
                e.tick(self)

        # boss
        k = self.get_kalisk()
        if k:
            k.tick(self)

        # capture rule: Tessa captures Kalisk when she reaches his cell
        tessa = self.get_tessa()
        kalisk = self.get_kalisk()
        if tessa and kalisk and tessa.alive and kalisk.alive and not self.state.kalisk_captured:
            if tessa.pos == kalisk.pos:
                self.state.kalisk_captured = True
                kalisk.captured = True
                self.metrics.note("state", change="kalisk_captured", by="tessa", step=self.metrics.steps)

        # carry Thia
        dek = self.get_dek()
        thia = self.get_thia()
        if dek and thia and dek.alive and thia.alive and dek.carrying_thia:
            if thia.pos != dek.pos:
                self.move_entity(thia, dek.pos)

        # lose conditions (after story protection, Dek/Thia won't die before Tessa)
        if not dek or not dek.alive:
            self.state.lose = True
            self.state.end_reason = "dek_dead"
        elif self.metrics.steps >= self.cfg.max_steps:
            self.state.lose = True
            self.state.end_reason = "time_limit"

    # summary
    def summary(self) -> Dict[str, Any]:
        dek = self.get_dek()
        thia = self.get_thia()
        kalisk = self.get_kalisk()
        tessa = self.get_tessa()
        bud = self.get_bud()

        return {
            "win": self.state.win,
            "lose": self.state.lose,
            "end_reason": self.state.end_reason,
            "steps": self.metrics.steps,
            "state": {
                "thia_met": self.state.thia_met,
                "bud_found": self.state.bud_found,
                "kalisk_captured": self.state.kalisk_captured,
                "tessa_dead": self.state.tessa_dead,
            },
            "dek": {"alive": bool(dek and dek.alive), "health": dek.health if dek else None, "stamina": dek.stamina if dek else None},
            "thia": {"alive": bool(thia and thia.alive), "health": thia.health if thia else None, "incap": thia.incapacitated if thia else None},
            "bud": {"alive": bool(bud and bud.alive), "health": bud.health if bud else None, "met": bud.met_dek if bud else None},
            "tessa": {"alive": bool(tessa and tessa.alive), "health": tessa.health if tessa else None},
            "kalisk": {"alive": bool(kalisk and kalisk.alive), "health": kalisk.health if kalisk else None, "captured": kalisk.captured if kalisk else None},
            "actions": self.metrics.actions,
        }


def build_world(cfg: Config) -> World:
    rng = RNG(cfg.seed)
    w = World(cfg, rng)

    # terrain
    for y in range(w.size):
        for x in range(w.size):
            t = "forest" if rng.random() < cfg.forest_ratio else "grassland"
            w.grid.set_terrain((x, y), t)

    # hazards first
    for i in range(cfg.shooter_spike_pods):
        pos = w.random_empty_pos()
        w.grid.set_terrain(pos, "grassland")
        w.add_entity(ShooterSpikePods(eid=f"spike{i}", name="Shooter Spike Pods", pos=pos, glyph="^", range=3, damage=6))

    for i in range(cfg.razor_grass):
        pos = w.random_empty_pos()
        w.grid.set_terrain(pos, "grassland")
        w.add_entity(RazorGrass(eid=f"razor{i}", name="Razor Grass", pos=pos, glyph="~", damage=8))

    for i in range(cfg.attack_vines):
        pos = w.random_empty_pos()
        w.grid.set_terrain(pos, "forest")
        w.add_entity(AttackVines(eid=f"vines{i}", name="Attack Vines", pos=pos, glyph="V", range=1, damage=14))

    # Dek + Thia + Bud should survive, so spawn them safely
    dek_pos = w.random_empty_nonhazard_pos()
    w.add_entity(Dek(eid="dek", name="Dek", pos=dek_pos, glyph="D", health=110, stamina=80, strength=14, honour=0))

    w.add_entity(Thia(eid="thia", name="Thia", pos=w.random_safe_pos_strict({"D", "S", "K"}, 7), glyph="T", health=60, stamina=35, strength=6, alive=True, incapacitated=True))

    # Bud: grasslands spawn
    bud_pos = w.random_safe_pos_strict({"D", "S", "K"}, 7)
    w.grid.set_terrain(bud_pos, "grassland")
    w.add_entity(ChildKalisk(eid="bud", name="Child Kalisk (Bud)", pos=bud_pos, glyph="C", health=9999, stamina=80, strength=14))

    # clan
    w.add_entity(ClanPredator(eid="father", name="Father", pos=w.random_safe_pos_strict({"D"}, 7), glyph="F", health=130, stamina=75, strength=17, honour=30, role="father"))
    w.add_entity(ClanPredator(eid="brother", name="Brother", pos=w.random_safe_pos_strict({"D"}, 7), glyph="B", health=120, stamina=75, strength=16, honour=20, role="brother"))
    w.add_entity(Elder(eid="elder", name="Elder", pos=w.random_safe_pos_strict({"D"}, 8), glyph="E", health=160, stamina=85, strength=22, honour=45, role="elder"))

    # boss far away
    w.add_entity(KaliskApex(eid="kalisk", name="Kalisk", pos=w.random_safe_pos_strict({"D", "T", "C"}, 11), glyph="K", health=260, stamina=120, strength=26))

    # Tessa hunts Kalisk first (far from Dek/Thia/Bud)
    w.add_entity(Tessa(eid="tessa", name="Tessa", pos=w.random_safe_pos_strict({"D", "T", "C", "K"}, 9), glyph="S", health=120, stamina=90, strength=18))

    # synth underlings
    for i in range(6):
        w.add_entity(BasicSynth(eid=f"synth{i}", name="BasicSynth", pos=w.random_safe_pos_strict({"D", "T", "C"}, 7), glyph="s", health=55, stamina=60, strength=12))

    # adversaries
    for i in range(cfg.explosive_slugs):
        w.add_entity(ExplosiveSlug(eid=f"slug{i}", name="Explosive Slug", pos=w.random_safe_pos_strict({"D", "T", "C"}, 6), glyph="m", health=25, stamina=35, strength=8))
    for i in range(cfg.micro_dragons):
        w.add_entity(MicroDragon(eid=f"md{i}", name="Micro Dragon", pos=w.random_safe_pos_strict({"D", "T", "C"}, 6), glyph="m", health=30, stamina=40, strength=9))
    for i in range(cfg.genna_vultures):
        w.add_entity(GennaVulture(eid=f"gv{i}", name="Genna Vulture", pos=w.random_safe_pos_strict({"D", "T", "C"}, 6), glyph="g", health=45, stamina=55, strength=12))
    for i in range(cfg.bone_bisons):
        w.add_entity(BoneBison(eid=f"bb{i}", name="Bone Bison", pos=w.random_safe_pos_strict({"D", "T", "C"}, 6), glyph="b", health=90, stamina=60, strength=15))
    for i in range(cfg.luna_bugs):
        w.add_entity(LunaBug(eid=f"lb{i}", name="Luna Bug", pos=w.random_safe_pos_strict({"D", "T", "C"}, 9), glyph="l", health=140, stamina=90, strength=20))

    # Dek items (optional pickups)
    for i in range(cfg.plasma_swords):
        w.add_entity(PlasmaSword(eid=f"ps{i}", name="Plasma Sword", pos=w.random_empty_nonhazard_pos(), glyph="P", attack_bonus=10))
    for i in range(cfg.shurikens):
        w.add_entity(Shuriken(eid=f"sh{i}", name="2-Bladed Shuriken", pos=w.random_empty_nonhazard_pos(), glyph="U", ranged_bonus=4))
    for i in range(cfg.masks):
        w.add_entity(Mask(eid=f"mk{i}", name="Mask", pos=w.random_empty_nonhazard_pos(), glyph="M", health_bonus=10))

    return w
