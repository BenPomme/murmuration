"""Pulse system for temporary area-of-effect abilities.

This module implements the Festival Pulse and Scouting Ping systems that provide
temporary area-of-effect benefits with cooldown mechanics.

Key Features:
- Festival Pulse: +reward multiplier in area for 12 hours, 1 day cooldown
- Scouting Ping: Reveals fog in area for 24 hours, no cooldown
- Duration and cooldown tracking
- Area-of-effect calculations
- Limited uses per level

Design Doc Requirements:
- Festival Pulse: +reward multiplier in 220 radius for 12h, cooldown 1 day
- Scouting Ping: Reveals fog in 200 radius for 24h
"""

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
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

# Time conversion: 1 in-game day = 6000 ticks (100 seconds at 60Hz)
TICKS_PER_DAY = 6000
TICKS_PER_HOUR = TICKS_PER_DAY // 24  # 250 ticks per hour


class PulseType(Enum):
    """Types of pulse abilities available."""
    FESTIVAL = "festival"
    SCOUTING = "scouting"


@dataclass
class PulseSpec:
    """Specification for a pulse type."""
    radius: float
    duration_hours: float
    cooldown_hours: float
    max_uses: Optional[int] = None  # None = unlimited
    
    @property
    def duration_ticks(self) -> int:
        """Duration in simulation ticks."""
        return int(self.duration_hours * TICKS_PER_HOUR)
    
    @property
    def cooldown_ticks(self) -> int:
        """Cooldown period in simulation ticks."""
        return int(self.cooldown_hours * TICKS_PER_HOUR)


# Pulse specifications from design doc
PULSE_SPECS = {
    PulseType.FESTIVAL: PulseSpec(
        radius=220.0, 
        duration_hours=12.0, 
        cooldown_hours=24.0,
        max_uses=None  # Unlimited uses, limited by cooldown
    ),
    PulseType.SCOUTING: PulseSpec(
        radius=200.0,
        duration_hours=24.0,
        cooldown_hours=0.0,  # No cooldown
        max_uses=None  # Unlimited uses
    ),
}


@dataclass
class Pulse:
    """Base class for pulse effects.
    
    Represents an active pulse with position, timing, and type information.
    
    Attributes:
        pulse_type: Type of this pulse
        position: World position where pulse was triggered
        triggered_at_tick: Tick when pulse was activated
        pulse_id: Unique identifier for this pulse instance
    """
    
    pulse_type: PulseType
    position: Position
    triggered_at_tick: Tick
    pulse_id: int
    
    @property
    def spec(self) -> PulseSpec:
        """Get the specification for this pulse type."""
        return PULSE_SPECS[self.pulse_type]
    
    def is_active(self, current_tick: Tick) -> bool:
        """Check if pulse is currently active.
        
        Args:
            current_tick: Current simulation tick
            
        Returns:
            True if pulse effect is still active
        """
        elapsed_ticks = current_tick - self.triggered_at_tick
        return 0 <= elapsed_ticks <= self.spec.duration_ticks
    
    def is_expired(self, current_tick: Tick) -> bool:
        """Check if pulse has expired and should be removed.
        
        Args:
            current_tick: Current simulation tick
            
        Returns:
            True if pulse should be cleaned up
        """
        return not self.is_active(current_tick)
    
    def get_effect_strength(self, position: Position, current_tick: Tick) -> float:
        """Calculate pulse effect strength at position.
        
        Uses distance-based falloff within the pulse radius.
        Effect is binary - full strength within radius, zero outside.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            
        Returns:
            Effect strength (0.0 or 1.0)
        """
        if not self.is_active(current_tick):
            return 0.0
        
        distance = np.linalg.norm(position - self.position)
        return 1.0 if distance <= self.spec.radius else 0.0
    
    def get_time_remaining(self, current_tick: Tick) -> int:
        """Get remaining duration in ticks.
        
        Args:
            current_tick: Current simulation tick
            
        Returns:
            Remaining ticks, or 0 if expired
        """
        if not self.is_active(current_tick):
            return 0
        
        elapsed_ticks = current_tick - self.triggered_at_tick
        return max(0, self.spec.duration_ticks - elapsed_ticks)


class FestivalPulse(Pulse):
    """Festival Pulse that provides reward multiplier boost.
    
    Creates a temporary area where agents receive increased rewards,
    encouraging congregation and cooperative behavior.
    
    Radius: 220, Duration: 12 hours, Cooldown: 24 hours
    """
    
    def __init__(self, position: Position, triggered_at_tick: Tick, pulse_id: int):
        super().__init__(PulseType.FESTIVAL, position, triggered_at_tick, pulse_id)
    
    def get_reward_multiplier(self, position: Position, current_tick: Tick,
                            base_multiplier: float = 1.5) -> float:
        """Get reward multiplier at position.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            base_multiplier: Base reward multiplier to apply
            
        Returns:
            Reward multiplier (1.0 if outside effect, base_multiplier if inside)
        """
        effect_strength = self.get_effect_strength(position, current_tick)
        return 1.0 + (base_multiplier - 1.0) * effect_strength


class ScoutingPing(Pulse):
    """Scouting Ping that reveals fog of war.
    
    Temporarily reveals hidden environmental information in an area,
    helping players plan migration routes.
    
    Radius: 200, Duration: 24 hours, No cooldown
    """
    
    def __init__(self, position: Position, triggered_at_tick: Tick, pulse_id: int):
        super().__init__(PulseType.SCOUTING, position, triggered_at_tick, pulse_id)
    
    def reveals_fog_at(self, position: Position, current_tick: Tick) -> bool:
        """Check if fog is revealed at position.
        
        Args:
            position: Position to check
            current_tick: Current simulation tick
            
        Returns:
            True if fog should be revealed at this position
        """
        return self.get_effect_strength(position, current_tick) > 0


class PulseManager:
    """Manages all active pulses and cooldown tracking.
    
    Handles pulse activation, effect calculations, cooldown management,
    and automatic cleanup of expired pulses.
    
    Attributes:
        active_pulses: List of currently active pulse effects
        last_used: Tracking of last use time for each pulse type
        use_counts: Number of times each pulse type has been used
        next_pulse_id: Counter for unique pulse IDs
    """
    
    def __init__(self):
        """Initialize pulse manager."""
        self.active_pulses: List[Pulse] = []
        self.last_used: Dict[PulseType, Tick] = {}
        self.use_counts: Dict[PulseType, int] = {pt: 0 for pt in PulseType}
        self.next_pulse_id: int = 1
        
        _get_logger().info("PulseManager initialized")
    
    def can_use_pulse(self, pulse_type: PulseType, current_tick: Tick) -> bool:
        """Check if a pulse can be activated.
        
        Considers cooldown time and maximum uses constraints.
        
        Args:
            pulse_type: Type of pulse to check
            current_tick: Current simulation tick
            
        Returns:
            True if pulse can be activated
        """
        spec = PULSE_SPECS[pulse_type]
        
        # Check maximum uses limit
        if spec.max_uses is not None:
            if self.use_counts[pulse_type] >= spec.max_uses:
                return False
        
        # Check cooldown
        if pulse_type in self.last_used:
            ticks_since_last_use = current_tick - self.last_used[pulse_type]
            if ticks_since_last_use < spec.cooldown_ticks:
                return False
        
        return True
    
    def get_cooldown_remaining(self, pulse_type: PulseType, 
                              current_tick: Tick) -> int:
        """Get remaining cooldown time in ticks.
        
        Args:
            pulse_type: Type of pulse to check
            current_tick: Current simulation tick
            
        Returns:
            Remaining cooldown ticks, or 0 if ready
        """
        if pulse_type not in self.last_used:
            return 0
        
        spec = PULSE_SPECS[pulse_type]
        ticks_since_last_use = current_tick - self.last_used[pulse_type]
        cooldown_remaining = spec.cooldown_ticks - ticks_since_last_use
        
        return max(0, cooldown_remaining)
    
    def activate_pulse(self, pulse_type: PulseType, position: Position,
                      current_tick: Tick) -> Optional[Pulse]:
        """Activate a pulse at the specified position.
        
        Args:
            pulse_type: Type of pulse to activate
            position: World position for pulse center
            current_tick: Current simulation tick
            
        Returns:
            The activated pulse, or None if activation failed
        """
        if not self.can_use_pulse(pulse_type, current_tick):
            cooldown_remaining = self.get_cooldown_remaining(pulse_type, current_tick)
            _get_logger().warning(
                "Pulse activation failed - not ready",
                extra={
                    "pulse_type": pulse_type.value,
                    "cooldown_remaining_ticks": cooldown_remaining,
                    "use_count": self.use_counts[pulse_type],
                    "max_uses": PULSE_SPECS[pulse_type].max_uses
                }
            )
            return None
        
        pulse_id = self.next_pulse_id
        self.next_pulse_id += 1
        
        # Create pulse instance based on type
        if pulse_type == PulseType.FESTIVAL:
            pulse = FestivalPulse(position, current_tick, pulse_id)
        elif pulse_type == PulseType.SCOUTING:
            pulse = ScoutingPing(position, current_tick, pulse_id)
        else:
            _get_logger().error(
                "Unknown pulse type",
                extra={"pulse_type": pulse_type}
            )
            return None
        
        self.active_pulses.append(pulse)
        self.last_used[pulse_type] = current_tick
        self.use_counts[pulse_type] += 1
        
        _get_logger().info(
            "Pulse activated",
            extra={
                "pulse_id": pulse_id,
                "pulse_type": pulse_type.value,
                "position": position.tolist(),
                "tick": current_tick,
                "duration_ticks": pulse.spec.duration_ticks,
                "use_count": self.use_counts[pulse_type]
            }
        )
        
        return pulse
    
    def cleanup_expired_pulses(self, current_tick: Tick) -> int:
        """Remove expired pulses.
        
        Args:
            current_tick: Current simulation tick
            
        Returns:
            Number of pulses removed
        """
        initial_count = len(self.active_pulses)
        
        self.active_pulses = [
            pulse for pulse in self.active_pulses
            if not pulse.is_expired(current_tick)
        ]
        
        removed_count = initial_count - len(self.active_pulses)
        if removed_count > 0:
            _get_logger().info(
                "Expired pulses cleaned up",
                extra={
                    "removed_count": removed_count,
                    "remaining_pulses": len(self.active_pulses),
                    "tick": current_tick
                }
            )
        
        return removed_count
    
    def get_festival_multiplier(self, position: Position, 
                               current_tick: Tick) -> float:
        """Get combined festival reward multiplier at position.
        
        Combines effects of all active festival pulses.
        Multiple festival pulses stack additively.
        
        Args:
            position: Position to evaluate
            current_tick: Current simulation tick
            
        Returns:
            Total reward multiplier
        """
        total_multiplier = 1.0
        
        for pulse in self.active_pulses:
            if isinstance(pulse, FestivalPulse) and pulse.is_active(current_tick):
                multiplier = pulse.get_reward_multiplier(position, current_tick)
                total_multiplier += (multiplier - 1.0)  # Additive stacking
        
        return total_multiplier
    
    def is_fog_revealed(self, position: Position, current_tick: Tick) -> bool:
        """Check if fog is revealed at position by any scouting ping.
        
        Args:
            position: Position to check
            current_tick: Current simulation tick
            
        Returns:
            True if fog should be revealed
        """
        for pulse in self.active_pulses:
            if isinstance(pulse, ScoutingPing) and pulse.is_active(current_tick):
                if pulse.reveals_fog_at(position, current_tick):
                    return True
        
        return False
    
    def get_active_pulses_at(self, position: Position, 
                            current_tick: Tick) -> List[Pulse]:
        """Get all active pulses affecting a position.
        
        Args:
            position: Position to check
            current_tick: Current simulation tick
            
        Returns:
            List of pulses affecting the position
        """
        affecting_pulses = []
        
        for pulse in self.active_pulses:
            if pulse.is_active(current_tick):
                if pulse.get_effect_strength(position, current_tick) > 0:
                    affecting_pulses.append(pulse)
        
        return affecting_pulses
    
    def get_pulse_count(self, pulse_type: Optional[PulseType] = None) -> int:
        """Get count of active pulses.
        
        Args:
            pulse_type: Specific type to count, or None for total
            
        Returns:
            Number of active pulses
        """
        if pulse_type is None:
            return len(self.active_pulses)
        else:
            return sum(1 for pulse in self.active_pulses 
                      if pulse.pulse_type == pulse_type)
    
    def get_pulse_status(self, current_tick: Tick) -> Dict[str, dict]:
        """Get status of all pulse types.
        
        Args:
            current_tick: Current simulation tick
            
        Returns:
            Status information for each pulse type
        """
        status = {}
        
        for pulse_type in PulseType:
            cooldown_remaining = self.get_cooldown_remaining(pulse_type, current_tick)
            active_count = self.get_pulse_count(pulse_type)
            
            status[pulse_type.value] = {
                "can_use": self.can_use_pulse(pulse_type, current_tick),
                "cooldown_remaining_ticks": cooldown_remaining,
                "use_count": self.use_counts[pulse_type],
                "max_uses": PULSE_SPECS[pulse_type].max_uses,
                "active_count": active_count,
                "spec": {
                    "radius": PULSE_SPECS[pulse_type].radius,
                    "duration_hours": PULSE_SPECS[pulse_type].duration_hours,
                    "cooldown_hours": PULSE_SPECS[pulse_type].cooldown_hours,
                }
            }
        
        return status
    
    def get_active_pulses(self) -> List[Pulse]:
        """Get list of all active pulses.
        
        Returns:
            Copy of active pulses list
        """
        return self.active_pulses.copy()