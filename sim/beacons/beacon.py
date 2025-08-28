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
    WIND_UP = "wind_up"      # Pushes birds upward
    WIND_DOWN = "wind_down"  # Pushes birds downward


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


# Enhanced beacon specifications for strategic gameplay
# Increased radius and longer half-life to make beacons more influential
BEACON_SPECS = {
    BeaconType.WIND_UP: BeaconSpec(radius=80.0, cost=1, half_life_days=1.5),    # Upward wind push - smaller direct contact area
    BeaconType.WIND_DOWN: BeaconSpec(radius=80.0, cost=1, half_life_days=1.5),  # Downward wind push - smaller direct contact area
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
        
        Uses exponential decay: exp(-r/(ρ*1.5)) where:
        - r is distance from beacon
        - ρ is the beacon's effective radius
        - 1.5 multiplier makes the field decay slower for stronger influence
        
        Args:
            position: Position to evaluate field strength
            
        Returns:
            Field strength between 0 and 1
        """
        distance = np.linalg.norm(position - self.position)
        # Enhanced influence: slower decay rate makes beacons more effective at distance
        effective_radius = self.spec.radius * 1.5
        return math.exp(-distance / effective_radius)
    
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


class WindUpBeacon(Beacon):
    """Wind beacon that pushes birds upward (negative Y direction)."""
    
    def __init__(self, position: Position, placed_at_tick: Tick, beacon_id: int):
        super().__init__(BeaconType.WIND_UP, position, placed_at_tick, beacon_id)
    
    def get_wind_force(self, position: Position, current_tick: Tick) -> Vector2D:
        """Get upward wind force at position.
        
        Returns force vector pushing birds upward.
        """
        strength = self.get_field_strength(position, current_tick)
        return create_vector2d(0.0, -strength * 15.0)  # Negative Y = upward


class WindDownBeacon(Beacon):
    """Wind beacon that pushes birds downward (positive Y direction)."""
    
    def __init__(self, position: Position, placed_at_tick: Tick, beacon_id: int):
        super().__init__(BeaconType.WIND_DOWN, position, placed_at_tick, beacon_id)
    
    def get_wind_force(self, position: Position, current_tick: Tick) -> Vector2D:
        """Get downward wind force at position.
        
        Returns force vector pushing birds downward.
        """
        strength = self.get_field_strength(position, current_tick)
        return create_vector2d(0.0, strength * 15.0)  # Positive Y = downward


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
        if beacon_type == BeaconType.WIND_UP:
            beacon = WindUpBeacon(position, current_tick, beacon_id)
        elif beacon_type == BeaconType.WIND_DOWN:
            beacon = WindDownBeacon(position, current_tick, beacon_id)
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
            if beacon.beacon_type == BeaconType.WIND_UP:
                strength = beacon.get_field_strength(position, current_tick)
                type_contributions[BeaconType.WIND_UP].append(strength)
            elif beacon.beacon_type == BeaconType.WIND_DOWN:
                strength = beacon.get_field_strength(position, current_tick)
                type_contributions[BeaconType.WIND_DOWN].append(strength)
        
        # Apply diminishing returns to stacked beacons of same type
        wind_up = type_contributions.get(BeaconType.WIND_UP, [])
        wind_down = type_contributions.get(BeaconType.WIND_DOWN, [])
        
        contributions["wind_up_force"] = self._apply_diminishing_returns(wind_up)
        contributions["wind_down_force"] = self._apply_diminishing_returns(wind_down)
        
        # Keep legacy fields for compatibility but set to 0
        contributions["light_attraction"] = 0.0
        contributions["cohesion_boost"] = 0.0
        contributions["foraging_bias"] = 0.0
        contributions["wind_boost"] = 0.0
        
        return contributions
    
    def _apply_diminishing_returns(self, strengths: List[float]) -> float:
        """Apply diminishing returns to multiple beacon contributions.
        
        Uses formula: total = Σ(s_i * (0.85)^i) where s_i are strengths
        sorted in descending order and i is the stack index.
        Enhanced to be less punishing for strategic beacon placement.
        
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
            # Less aggressive diminishing returns (0.85 instead of 0.7)
            # This encourages strategic placement of multiple beacons
            diminishing_factor = 0.85 ** i
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