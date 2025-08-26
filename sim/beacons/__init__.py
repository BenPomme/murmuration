"""Beacon system for Murmuration simulation.

This module provides environmental signals that players can place to influence
bird behavior through potential fields and area-of-effect pulses.

Key Components:
- BeaconManager: Manages placement, removal, and field calculations
- Beacon types: Light, Sound, Food Scent, Wind Lure beacons
- Pulses: Festival Pulse and Scouting Ping temporary effects
- Field calculations with exponential decay and stacking

Following CLAUDE.md standards:
- Deterministic behavior (no RNG dependency for beacons themselves)
- Type hints and structured logging
- Performance optimized for O(N*B) complexity
- Half-life decay mechanics
"""

from .beacon import (
    Beacon,
    LightBeacon,
    SoundBeacon,
    FoodScentBeacon,
    WindLureBeacon,
    BeaconType,
    BeaconManager,
)

from .pulse import (
    Pulse,
    FestivalPulse,
    ScoutingPing,
    PulseType,
    PulseManager,
)

__all__ = [
    "Beacon",
    "LightBeacon", 
    "SoundBeacon",
    "FoodScentBeacon",
    "WindLureBeacon",
    "BeaconType",
    "BeaconManager",
    "Pulse",
    "FestivalPulse",
    "ScoutingPing", 
    "PulseType",
    "PulseManager",
]