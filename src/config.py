from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    grid_size: int = 20
    max_steps: int = 400
    seed: int = 42

    # terrain generation
    forest_ratio: float = 0.55  # rest becomes grasslands

    # population (not counting key characters)
    explosive_slugs: int = 8
    micro_dragons: int = 8
    genna_vultures: int = 6
    bone_bisons: int = 5
    luna_bugs: int = 2  # very high danger

    shooter_spike_pods: int = 10
    razor_grass: int = 12
    attack_vines: int = 5

    # items for Dek (pickups)
    plasma_swords: int = 1
    shurikens: int = 2
    masks: int = 1

    # visibility / sensing
    vision_radius: int = 4

    # stamina/health tuning
    base_move_cost: int = 2
    carry_move_extra_cost: int = 2
    rest_gain: int = 6

    # terrain costs
    forest_move_extra_cost: int = 1  # forest slightly harder than grassland

    # combat tuning
    base_melee_damage: int = 12
    ranged_damage: int = 10

    # special effects
    cryo_slow_turns: int = 2
    shoulder_laser_charge: int = 5  # turns

    # victory/defeat
    honour_target: int = 80
