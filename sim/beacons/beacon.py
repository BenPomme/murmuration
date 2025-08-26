"""Beacon classes and field calculation system.

This module implements the various beacon types that players can place to influence
bird behavior through environmental potential fields. Each beacon type has specific
radius, cost, half-life, and effect characteristics.

Key Features:
- Exponential distance decay: φ(r) = exp(-r/ρ) where ρ is the radius
- Temporal decay: e^(-t/τ) where τ is derived from half-life  
- Stacking with diminishing returns
- Budget tracking and validation
- O(N*B) performance for field contribution calculations

Design Doc Requirements:
- Light Beacon: draws birds at night, radius 150, cost 1, half-life 1.5 days
- Sound Beacon: increases cohesion locally, radius 180, cost 1, half-life 1.0 day
- Food Scent: biases foraging, radius 120, cost 2, half-life 0.8 day
- Wind Lure: boosts tailwind, radius 200, cost 2, half-life 1.0 day
"""

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set
import numpy as np

from sim.core.types import Position, Vector2D, Tick, create_vector2d
# Resilient logging setup with fallback
logger = None

def _get_logger():
    """Get logger instance, with fallback for testing."""
    global logger
    if logger is None:
        try:
            from sim.utils.logging import get_logger
            logger = get_logger(__name__)
        except (ImportError, RuntimeError, ModuleNotFoundError):
            # Fallback for testing without full logging setup
            import logging
            logger = logging.getLogger(__name__)
            if not logger.handlers:
                logger.addHandler(logging.NullHandler())
    return logger


class BeaconType(Enum):
    """Types of beacons available for placement."""
    LIGHT = "light"
    SOUND = "sound" 
    FOOD_SCENT = "food_scent"
    WIND_LURE = "wind_lure"


@dataclass
class BeaconSpec:
    """Specification for a beacon type."""
    radius: float
    cost: int
    half_life_days: float
    
    @property
    def decay_constant(self) -> float:
        """Calculate decay constant τ from half-life.
        
        Half-life formula: t_half = τ * ln(2)
        Therefore: τ = t_half / ln(2)
        
        Returns:
            Decay constant for exponential decay calculation
        """
        return self.half_life_days / math.log(2)


# Beacon specifications from design doc
BEACON_SPECS = {
    BeaconType.LIGHT: BeaconSpec(radius=150.0, cost=1, half_life_days=1.5),
    BeaconType.SOUND: BeaconSpec(radius=180.0, cost=1, half_life_days=1.0),
    BeaconType.FOOD_SCENT: BeaconSpec(radius=120.0, cost=2, half_life_days=0.8),
    BeaconType.WIND_LURE: BeaconSpec(radius=200.0, cost=2, half_life_days=1.0),
}

# Time conversion: 1 in-game day = 6000 ticks (100 seconds at 60Hz)
TICKS_PER_DAY = 6000


@dataclass
class Beacon:
    """Base class for all beacon types.
    
    Represents a placed beacon with position, placement time, and type.
    Handles temporal decay calculations and field strength computation.
    
    Attributes:
        beacon_type: Type of this beacon
        position: World position where beacon was placed
        placed_at_tick: Tick when beacon was placed
        beacon_id: Unique identifier for this beacon instance
    """
    
    beacon_type: BeaconType
    position: Position
    placed_at_tick: Tick
    beacon_id: int
    
    @property
    def spec(self) -> BeaconSpec:
        """Get the specification for this beacon type."""
        return BEACON_SPECS[self.beacon_type]
    
    def get_temporal_decay(self, current_tick: Tick) -> float:
        """Calculate temporal decay factor based on time since placement.
        
        Uses exponential decay: e^(-t/τ) where:
        - t is time elapsed in days
        - τ is the decay constant derived from half-life
        
        Args:
            current_tick: Current simulation tick
            
        Returns:
            Decay factor between 0 and 1
        """
        ticks_elapsed = current_tick - self.placed_at_tick
        days_elapsed = ticks_elapsed / TICKS_PER_DAY
        
        if days_elapsed < 0:
            _get_logger().warning(
                "Beacon temporal decay calculation with negative time",
                extra={
                    "beacon_id": self.beacon_id,
                    "beacon_type": self.beacon_type.value,
                    "current_tick": current_tick,
                    "placed_at_tick": self.placed_at_tick,
                    "days_elapsed": days_elapsed
                }
            )
            return 1.0
            
        return math.exp(-days_elapsed / self.spec.decay_constant)
    
    def get_distance_decay(self, position: Position) -> float:
        """Calculate distance-based field strength at a position.
        
        Uses exponential decay: exp(-r/ρ) where:
        - r is distance from beacon
        - ρ is the beacon's effective radius
        
        Args:
            position: Position to evaluate field strength
            
        Returns:
            Field strength between 0 and 1
        """
        distance = np.linalg.norm(position - self.position)
        return math.exp(-distance / self.spec.radius)
    
    def get_field_strength(self, position: Position, current_tick: Tick) -> float:
        """Calculate total field strength at position including both decays.
        
        Combines temporal and distance decay factors.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            
        Returns:
            Combined field strength between 0 and 1
        """
        temporal = self.get_temporal_decay(current_tick)
        distance = self.get_distance_decay(position)
        return temporal * distance
    
    def is_expired(self, current_tick: Tick, threshold: float = 0.01) -> bool:
        """Check if beacon has decayed below useful threshold.
        
        Args:
            current_tick: Current simulation tick
            threshold: Minimum useful field strength
            
        Returns:
            True if beacon should be considered expired
        """
        return self.get_temporal_decay(current_tick) < threshold


class LightBeacon(Beacon):
    """Light beacon that draws birds at night.
    
    Provides attraction field that is stronger during night hours.
    Radius: 150, Cost: 1, Half-life: 1.5 days
    """
    
    def __init__(self, position: Position, placed_at_tick: Tick, beacon_id: int):
        super().__init__(BeaconType.LIGHT, position, placed_at_tick, beacon_id)
    
    def get_attraction_strength(self, position: Position, current_tick: Tick, 
                              is_night: bool = False) -> float:
        """Get attraction strength with night bonus.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            is_night: Whether it's currently night time
            
        Returns:
            Attraction strength (stronger at night)
        """
        base_strength = self.get_field_strength(position, current_tick)
        night_multiplier = 1.5 if is_night else 0.7
        return base_strength * night_multiplier


class SoundBeacon(Beacon):
    """Sound beacon that increases local cohesion.
    
    Provides cohesion boost field that helps birds stay together.
    Radius: 180, Cost: 1, Half-life: 1.0 day
    """
    
    def __init__(self, position: Position, placed_at_tick: Tick, beacon_id: int):
        super().__init__(BeaconType.SOUND, position, placed_at_tick, beacon_id)
    
    def get_cohesion_boost(self, position: Position, current_tick: Tick) -> float:
        """Get cohesion boost strength at position.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            
        Returns:
            Cohesion boost factor
        """
        return self.get_field_strength(position, current_tick)


class FoodScentBeacon(Beacon):
    """Food scent beacon that biases foraging behavior.
    
    Creates attractive scent field that influences foraging decisions.
    Radius: 120, Cost: 2, Half-life: 0.8 day
    """
    
    def __init__(self, position: Position, placed_at_tick: Tick, beacon_id: int):
        super().__init__(BeaconType.FOOD_SCENT, position, placed_at_tick, beacon_id)
    
    def get_foraging_bias(self, position: Position, current_tick: Tick) -> float:
        """Get foraging bias strength at position.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            
        Returns:
            Foraging bias factor
        """
        return self.get_field_strength(position, current_tick)


class WindLureBeacon(Beacon):
    """Wind lure beacon that provides tailwind boost.
    
    Enhances effective tailwind in the beacon's area.
    Radius: 200, Cost: 2, Half-life: 1.0 day
    """
    
    def __init__(self, position: Position, placed_at_tick: Tick, beacon_id: int):
        super().__init__(BeaconType.WIND_LURE, position, placed_at_tick, beacon_id)
    
    def get_wind_boost(self, position: Position, current_tick: Tick) -> float:
        """Get wind boost strength at position.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            
        Returns:
            Wind boost factor
        """
        return self.get_field_strength(position, current_tick)


class BeaconManager:
    """Manages all placed beacons and calculates combined field effects.
    
    Handles beacon placement, removal, budget tracking, field calculations,
    and automatic cleanup of expired beacons. Optimized for O(N*B) performance
    where N is number of agents and B is number of active beacons.
    
    Attributes:
        beacons: List of currently active beacons
        budget_used: Current budget consumption
        budget_limit: Maximum allowed budget
        next_beacon_id: Counter for unique beacon IDs
    """
    
    def __init__(self, budget_limit: int = 10):
        """Initialize beacon manager.
        
        Args:
            budget_limit: Maximum beacon budget allowed
        """
        self.beacons: List[Beacon] = []
        self.budget_used: int = 0
        self.budget_limit: int = budget_limit
        self.next_beacon_id: int = 1
        self._beacon_type_counts: Dict[BeaconType, int] = {
            bt: 0 for bt in BeaconType
        }
        
        _get_logger().info(
            "BeaconManager initialized",
            extra={"budget_limit": budget_limit}
        )
    
    def can_place_beacon(self, beacon_type: BeaconType) -> bool:
        """Check if a beacon of the given type can be placed.
        
        Args:
            beacon_type: Type of beacon to check
            
        Returns:
            True if beacon can be placed within budget
        """
        spec = BEACON_SPECS[beacon_type]
        return self.budget_used + spec.cost <= self.budget_limit
    
    def place_beacon(self, beacon_type: BeaconType, position: Position, 
                    current_tick: Tick) -> Optional[Beacon]:
        """Place a new beacon at the specified position.
        
        Args:
            beacon_type: Type of beacon to place
            position: World position for placement
            current_tick: Current simulation tick
            
        Returns:
            The placed beacon, or None if placement failed
        """
        if not self.can_place_beacon(beacon_type):
            _get_logger().warning(
                "Beacon placement failed - budget exceeded",
                extra={
                    "beacon_type": beacon_type.value,
                    "budget_used": self.budget_used,
                    "budget_limit": self.budget_limit,
                    "cost": BEACON_SPECS[beacon_type].cost
                }
            )
            return None
        
        beacon_id = self.next_beacon_id
        self.next_beacon_id += 1
        
        # Create beacon instance based on type
        if beacon_type == BeaconType.LIGHT:
            beacon = LightBeacon(position, current_tick, beacon_id)
        elif beacon_type == BeaconType.SOUND:
            beacon = SoundBeacon(position, current_tick, beacon_id)
        elif beacon_type == BeaconType.FOOD_SCENT:
            beacon = FoodScentBeacon(position, current_tick, beacon_id)
        elif beacon_type == BeaconType.WIND_LURE:
            beacon = WindLureBeacon(position, current_tick, beacon_id)
        else:
            _get_logger().error(
                "Unknown beacon type",
                extra={"beacon_type": beacon_type}
            )
            return None
        
        self.beacons.append(beacon)
        self.budget_used += beacon.spec.cost
        self._beacon_type_counts[beacon_type] += 1
        
        _get_logger().info(
            "Beacon placed",
            extra={
                "beacon_id": beacon_id,
                "beacon_type": beacon_type.value,
                "position": position.tolist(),
                "tick": current_tick,
                "budget_used": self.budget_used,
                "remaining_budget": self.budget_limit - self.budget_used
            }
        )
        
        return beacon
    
    def remove_beacon(self, beacon_id: int) -> bool:
        """Remove a beacon by ID.
        
        Args:
            beacon_id: ID of beacon to remove
            
        Returns:
            True if beacon was found and removed
        """
        for i, beacon in enumerate(self.beacons):
            if beacon.beacon_id == beacon_id:
                removed_beacon = self.beacons.pop(i)
                self.budget_used -= removed_beacon.spec.cost
                self._beacon_type_counts[removed_beacon.beacon_type] -= 1
                
                _get_logger().info(
                    "Beacon removed",
                    extra={
                        "beacon_id": beacon_id,
                        "beacon_type": removed_beacon.beacon_type.value,
                        "budget_freed": removed_beacon.spec.cost,
                        "budget_used": self.budget_used
                    }
                )
                return True
        
        _get_logger().warning(
            "Attempted to remove non-existent beacon",
            extra={"beacon_id": beacon_id}
        )
        return False
    
    def cleanup_expired_beacons(self, current_tick: Tick, 
                               threshold: float = 0.01) -> int:
        """Remove beacons that have decayed below threshold.
        
        Args:
            current_tick: Current simulation tick
            threshold: Minimum field strength to keep beacon
            
        Returns:
            Number of beacons removed
        """
        initial_count = len(self.beacons)
        expired_beacons = []
        
        for beacon in self.beacons:
            if beacon.is_expired(current_tick, threshold):
                expired_beacons.append(beacon)
        
        for beacon in expired_beacons:
            self.remove_beacon(beacon.beacon_id)
        
        removed_count = len(expired_beacons)
        if removed_count > 0:
            _get_logger().info(
                "Expired beacons cleaned up",
                extra={
                    "removed_count": removed_count,
                    "remaining_beacons": len(self.beacons),
                    "tick": current_tick
                }
            )
        
        return removed_count
    
    def get_combined_field_contribution(self, position: Position, 
                                      current_tick: Tick,
                                      is_night: bool = False) -> Dict[str, float]:
        """Calculate combined field contributions at a position.
        
        Computes the total effect of all active beacons at the given position,
        including stacking effects with diminishing returns.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            is_night: Whether it's night time (affects light beacons)
            
        Returns:
            Dictionary with field contribution values:
            - light_attraction: Combined light beacon attraction
            - cohesion_boost: Combined cohesion boost from sound beacons
            - foraging_bias: Combined foraging bias from food scent
            - wind_boost: Combined wind enhancement
        """
        contributions = {
            "light_attraction": 0.0,
            "cohesion_boost": 0.0, 
            "foraging_bias": 0.0,
            "wind_boost": 0.0
        }
        
        # Track contributions by type for diminishing returns
        type_contributions: Dict[BeaconType, List[float]] = {
            bt: [] for bt in BeaconType
        }
        
        for beacon in self.beacons:
            if beacon.beacon_type == BeaconType.LIGHT:
                strength = beacon.get_attraction_strength(position, current_tick, is_night)
                type_contributions[BeaconType.LIGHT].append(strength)
            elif beacon.beacon_type == BeaconType.SOUND:
                strength = beacon.get_cohesion_boost(position, current_tick)
                type_contributions[BeaconType.SOUND].append(strength)
            elif beacon.beacon_type == BeaconType.FOOD_SCENT:
                strength = beacon.get_foraging_bias(position, current_tick)
                type_contributions[BeaconType.FOOD_SCENT].append(strength)
            elif beacon.beacon_type == BeaconType.WIND_LURE:
                strength = beacon.get_wind_boost(position, current_tick)
                type_contributions[BeaconType.WIND_LURE].append(strength)
        
        # Apply diminishing returns to stacked beacons of same type
        contributions["light_attraction"] = self._apply_diminishing_returns(
            type_contributions[BeaconType.LIGHT]
        )
        contributions["cohesion_boost"] = self._apply_diminishing_returns(
            type_contributions[BeaconType.SOUND]
        )
        contributions["foraging_bias"] = self._apply_diminishing_returns(
            type_contributions[BeaconType.FOOD_SCENT]
        )
        contributions["wind_boost"] = self._apply_diminishing_returns(
            type_contributions[BeaconType.WIND_LURE]
        )
        
        return contributions
    
    def _apply_diminishing_returns(self, strengths: List[float]) -> float:
        """Apply diminishing returns to multiple beacon contributions.
        
        Uses formula: total = Σ(s_i * (0.7)^i) where s_i are strengths
        sorted in descending order and i is the stack index.
        
        Args:
            strengths: List of individual beacon strengths
            
        Returns:
            Combined strength with diminishing returns
        """
        if not strengths:
            return 0.0
        
        # Sort in descending order for diminishing returns calculation
        sorted_strengths = sorted(strengths, reverse=True)
        
        total = 0.0
        for i, strength in enumerate(sorted_strengths):
            diminishing_factor = 0.7 ** i
            total += strength * diminishing_factor
        
        return total
    
    def get_beacon_count(self, beacon_type: Optional[BeaconType] = None) -> int:
        """Get count of active beacons.
        
        Args:
            beacon_type: Specific type to count, or None for total
            
        Returns:
            Number of active beacons
        """
        if beacon_type is None:
            return len(self.beacons)
        else:
            return self._beacon_type_counts[beacon_type]
    
    def get_budget_info(self) -> Dict[str, int]:
        """Get current budget information.
        
        Returns:
            Dictionary with budget_used, budget_limit, budget_remaining
        """
        return {
            "budget_used": self.budget_used,
            "budget_limit": self.budget_limit,
            "budget_remaining": self.budget_limit - self.budget_used
        }
    
    def get_active_beacons(self) -> List[Beacon]:
        """Get list of all active beacons.
        
        Returns:
            Copy of active beacons list
        """
        return self.beacons.copy()