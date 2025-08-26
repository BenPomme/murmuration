"""Environment modeling for the Murmuration simulation.

This module defines the Environment class representing the simulation world,
including wind fields, food sources, risk zones, and beacon placements.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
import numpy as np

from .types import Position, Vector2D, Field2D, create_vector2d


@dataclass
class Beacon:
    """Represents a beacon placed by the player to guide the flock.
    
    Attributes:
        position: Location of the beacon in 2D space
        strength: Influence strength of the beacon (0.0 to 1.0)
        active: Whether the beacon is currently active
        decay_rate: Rate at which beacon strength decreases over time
    """
    position: Position
    strength: float = 1.0
    active: bool = True
    decay_rate: float = 0.005
    
    def update(self, dt: float) -> None:
        """Update beacon state over time.
        
        Args:
            dt: Time step duration
        """
        if self.active:
            self.strength = max(0.0, self.strength - self.decay_rate * dt)
            if self.strength <= 0.0:
                self.active = False


@dataclass
class WindField:
    """Represents wind patterns in the environment.
    
    Attributes:
        velocity_field: 2D field of wind velocity vectors
        strength_field: 2D field of wind strength scalars
        turbulence: Amount of random turbulence to add
    """
    velocity_field: Field2D  # Shape (height, width, 2)
    strength_field: Field2D  # Shape (height, width)
    turbulence: float = 0.1
    
    def get_wind_at(self, position: Position) -> Vector2D:
        """Get wind velocity at a specific position.
        
        Args:
            position: Position to sample wind at
            
        Returns:
            Wind velocity vector at the position
        """
        # Convert world coordinates to field indices
        height, width = self.strength_field.shape
        x_idx = int(np.clip(position[0] / 100.0 * width, 0, width - 1))
        y_idx = int(np.clip(position[1] / 100.0 * height, 0, height - 1))
        
        # Sample velocity and strength
        if len(self.velocity_field.shape) == 3:
            velocity = self.velocity_field[y_idx, x_idx, :]
        else:
            # If velocity_field is 2D, assume it's magnitude only
            magnitude = self.velocity_field[y_idx, x_idx]
            # Default wind direction (eastward)
            velocity = np.array([magnitude, 0.0])
        
        strength = self.strength_field[y_idx, x_idx]
        
        return velocity * strength


@dataclass
class FoodSource:
    """Represents a food source in the environment.
    
    Attributes:
        position: Location of the food source
        energy_value: Amount of energy this source provides
        radius: Effective radius for feeding
        depletion_rate: Rate at which food is consumed
    """
    position: Position
    energy_value: float = 10.0
    radius: float = 5.0
    depletion_rate: float = 0.1
    
    def is_accessible(self, agent_position: Position) -> bool:
        """Check if an agent can access this food source.
        
        Args:
            agent_position: Position of the agent
            
        Returns:
            True if agent is within feeding radius
        """
        distance = np.linalg.norm(agent_position - self.position)
        return distance <= self.radius
    
    def consume(self, amount: float) -> float:
        """Consume food from this source.
        
        Args:
            amount: Amount of energy to consume
            
        Returns:
            Actual amount consumed (limited by availability)
        """
        consumed = min(amount, self.energy_value)
        self.energy_value = max(0.0, self.energy_value - consumed)
        return consumed


@dataclass
class Environment:
    """Represents the simulation environment with all spatial fields.
    
    This includes wind patterns, food sources, risk zones, and player-placed beacons
    that influence flock behavior.
    
    Attributes:
        width: Environment width in world units
        height: Environment height in world units
        wind: Wind field affecting agent movement
        food_sources: List of available food sources
        risk_field: 2D field representing danger levels
        beacons: List of player-placed beacons
        time: Current simulation time
    """
    
    width: float = 100.0
    height: float = 100.0
    wind: Optional[WindField] = None
    food_sources: List[FoodSource] = field(default_factory=list)
    risk_field: Field2D = field(default_factory=lambda: np.zeros((64, 64), dtype=np.float64))
    beacons: List[Beacon] = field(default_factory=list)
    time: float = 0.0
    
    def __post_init__(self) -> None:
        """Initialize default wind field if none provided."""
        if self.wind is None:
            # Create default wind field with gentle eastward wind
            height, width = self.risk_field.shape
            velocity_field = np.zeros((height, width, 2), dtype=np.float64)
            velocity_field[:, :, 0] = 0.5  # Eastward wind
            strength_field = np.ones((height, width), dtype=np.float64) * 0.3
            
            self.wind = WindField(
                velocity_field=velocity_field,
                strength_field=strength_field,
                turbulence=0.1,
            )
    
    def update(self, dt: float) -> None:
        """Update environment state over time.
        
        Args:
            dt: Time step duration
        """
        self.time += dt
        
        # Update beacon decay
        for beacon in self.beacons:
            beacon.update(dt)
        
        # Remove inactive beacons
        self.beacons = [b for b in self.beacons if b.active]
    
    def add_beacon(self, position: Position, strength: float = 1.0) -> None:
        """Add a new beacon to the environment.
        
        Args:
            position: Where to place the beacon
            strength: Initial strength of the beacon
        """
        beacon = Beacon(position=position.copy(), strength=strength)
        self.beacons.append(beacon)
    
    def remove_beacon_at(self, position: Position, tolerance: float = 2.0) -> bool:
        """Remove beacon near the specified position.
        
        Args:
            position: Position to search near
            tolerance: Maximum distance for beacon removal
            
        Returns:
            True if a beacon was removed
        """
        for i, beacon in enumerate(self.beacons):
            distance = np.linalg.norm(beacon.position - position)
            if distance <= tolerance:
                self.beacons.pop(i)
                return True
        return False
    
    def get_risk_at(self, position: Position) -> float:
        """Get risk level at a specific position.
        
        Args:
            position: Position to sample risk at
            
        Returns:
            Risk level (0.0 to 1.0)
        """
        height, width = self.risk_field.shape
        x_idx = int(np.clip(position[0] / self.width * width, 0, width - 1))
        y_idx = int(np.clip(position[1] / self.height * height, 0, height - 1))
        
        return float(self.risk_field[y_idx, x_idx])
    
    def set_risk_at(self, position: Position, risk: float, radius: float = 5.0) -> None:
        """Set risk level in a circular area.
        
        Args:
            position: Center of the risk area
            risk: Risk level to set (0.0 to 1.0)
            radius: Radius of the affected area
        """
        height, width = self.risk_field.shape
        center_x = position[0] / self.width * width
        center_y = position[1] / self.height * height
        
        y_indices, x_indices = np.ogrid[:height, :width]
        distances = np.sqrt((x_indices - center_x) ** 2 + (y_indices - center_y) ** 2)
        
        # Apply risk with falloff
        mask = distances <= radius
        self.risk_field[mask] = np.maximum(
            self.risk_field[mask],
            risk * np.exp(-distances[mask] / radius)
        )
    
    def get_nearest_food(self, position: Position) -> Optional[FoodSource]:
        """Find the nearest accessible food source.
        
        Args:
            position: Position to search from
            
        Returns:
            Nearest food source or None if none accessible
        """
        accessible_sources = [
            source for source in self.food_sources
            if source.energy_value > 0 and source.is_accessible(position)
        ]
        
        if not accessible_sources:
            return None
        
        # Find closest source
        distances = [
            np.linalg.norm(position - source.position)
            for source in accessible_sources
        ]
        min_idx = np.argmin(distances)
        return accessible_sources[min_idx]
    
    def get_beacon_influence(self, position: Position) -> Vector2D:
        """Calculate combined beacon influence at a position.
        
        Args:
            position: Position to calculate influence at
            
        Returns:
            Combined influence vector from all active beacons
        """
        if not self.beacons:
            return create_vector2d(0.0, 0.0)
        
        total_influence = create_vector2d(0.0, 0.0)
        
        for beacon in self.beacons:
            if not beacon.active or beacon.strength <= 0:
                continue
            
            # Direction from position to beacon
            direction = beacon.position - position
            distance = np.linalg.norm(direction)
            
            if distance > 0:
                # Normalize direction and apply strength with distance falloff
                direction_norm = direction / distance
                influence_strength = beacon.strength / (1.0 + distance * 0.01)
                total_influence += direction_norm * influence_strength
        
        return total_influence
    
    def add_food_source(self, position: Position, energy_value: float = 10.0) -> None:
        """Add a new food source to the environment.
        
        Args:
            position: Where to place the food source
            energy_value: Amount of energy the source provides
        """
        food_source = FoodSource(position=position.copy(), energy_value=energy_value)
        self.food_sources.append(food_source)
    
    def cleanup_depleted_food(self) -> None:
        """Remove food sources that have been completely consumed."""
        self.food_sources = [
            source for source in self.food_sources
            if source.energy_value > 0
        ]


def create_test_environment(rng: np.random.Generator) -> Environment:
    """Create a test environment with random features.
    
    Args:
        rng: Random number generator for initialization
        
    Returns:
        Environment with random wind, food, and risk patterns
    """
    env = Environment(width=100.0, height=100.0)
    
    # Add some random food sources
    for _ in range(5):
        position = create_vector2d(
            rng.uniform(10, 90),
            rng.uniform(10, 90)
        )
        energy = rng.uniform(5.0, 20.0)
        env.add_food_source(position, energy)
    
    # Add some risk areas
    for _ in range(3):
        position = create_vector2d(
            rng.uniform(10, 90),
            rng.uniform(10, 90)
        )
        risk_level = rng.uniform(0.3, 0.8)
        radius = rng.uniform(8.0, 15.0)
        env.set_risk_at(position, risk_level, radius)
    
    return env