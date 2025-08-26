"""Storm hazards for the Murmuration simulation.

This module implements weather systems including planned and random storm
events. Storms create wind shocks, reduce visibility, and can cause direct
agent deaths through exhaustion or wind shear.

Key features:
- Deterministic and random storm spawning 
- Wind field modifications during storm events
- Visibility reduction affecting agent behavior
- Energy drain and stress accumulation during storms
- Telegraph system integration for advance warnings

Classes:
    StormSystem: Represents an active storm with dynamics
    StormEvent: Records storm event data

Functions:
    spawn_storms: Create new storm systems
    apply_storm_effects: Apply storm forces and effects to agents
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from enum import Enum

from ..core.types import Position, RNG, EventData, Tick, create_vector2d, Vector2D
from ..core.agent import Agent
from ..core.environment import Environment, WindField
from ..utils.logging import get_logger

logger = get_logger("storms")


class StormSeverity(Enum):
    """Storm severity levels with associated parameters."""
    MILD = "mild"
    MODERATE = "moderate" 
    SEVERE = "severe"
    EXTREME = "extreme"


@dataclass
class StormCell:
    """Individual storm cell with localized effects.
    
    Attributes:
        center: Center position of the storm cell
        radius: Effective radius of storm influence
        intensity: Storm intensity [0.0, 1.0]
        wind_speed: Peak wind speed in m/s
        movement_vector: Direction and speed of storm movement
        rotation_speed: Angular velocity for rotation effects
    """
    center: Position
    radius: float
    intensity: float = 1.0
    wind_speed: float = 20.0  # m/s
    movement_vector: Vector2D = field(default_factory=lambda: create_vector2d(0.0, 0.0))
    rotation_speed: float = 0.1  # rad/s


@dataclass
class StormSystem:
    """Represents a complete storm system with multiple cells.
    
    Attributes:
        id: Unique identifier for this storm
        severity: Storm severity level
        cells: List of individual storm cells
        duration_remaining: Time remaining in hours
        spawn_tick: Tick when storm was created
        visibility_reduction: Visibility penalty [0.0, 1.0]
        energy_drain_rate: Additional energy cost per second
        stress_factor: Stress increase multiplier
        active: Whether storm is currently affecting the environment
        forecasted: Whether this storm was forecasted in advance
    """
    id: str
    severity: StormSeverity
    cells: List[StormCell]
    duration_remaining: float  # hours
    spawn_tick: Tick
    visibility_reduction: float = 0.5
    energy_drain_rate: float = 2.0  # energy/second
    stress_factor: float = 1.5
    active: bool = True
    forecasted: bool = False
    
    def __post_init__(self) -> None:
        """Initialize storm parameters based on severity."""
        severity_params = {
            StormSeverity.MILD: {
                "visibility_reduction": 0.2,
                "energy_drain_rate": 1.0,
                "stress_factor": 1.2,
                "wind_multiplier": 1.5,
            },
            StormSeverity.MODERATE: {
                "visibility_reduction": 0.4,
                "energy_drain_rate": 2.0,
                "stress_factor": 1.5,
                "wind_multiplier": 2.0,
            },
            StormSeverity.SEVERE: {
                "visibility_reduction": 0.7,
                "energy_drain_rate": 4.0,
                "stress_factor": 2.0,
                "wind_multiplier": 3.0,
            },
            StormSeverity.EXTREME: {
                "visibility_reduction": 0.9,
                "energy_drain_rate": 6.0,
                "stress_factor": 3.0,
                "wind_multiplier": 4.0,
            },
        }
        
        params = severity_params[self.severity]
        if self.visibility_reduction == 0.5:  # Default value, update it
            self.visibility_reduction = params["visibility_reduction"]
            self.energy_drain_rate = params["energy_drain_rate"]
            self.stress_factor = params["stress_factor"]
            
            # Update wind speeds for all cells
            wind_multiplier = params["wind_multiplier"]
            for cell in self.cells:
                cell.wind_speed *= wind_multiplier
    
    def update(self, dt_hours: float) -> bool:
        """Update storm state over time.
        
        Args:
            dt_hours: Time step in hours
            
        Returns:
            True if storm is still active
        """
        if not self.active:
            return False
            
        # Update duration
        self.duration_remaining -= dt_hours
        
        if self.duration_remaining <= 0:
            self.active = False
            return False
        
        # Move storm cells
        for cell in self.cells:
            cell.center += cell.movement_vector * dt_hours
            
            # Update intensity based on remaining duration
            age_factor = 1.0 - (self.duration_remaining / self.get_total_duration())
            if age_factor > 0.8:  # Storm weakening in final 20%
                cell.intensity *= 0.95
        
        return True
    
    def get_total_duration(self) -> float:
        """Get original storm duration in hours."""
        duration_by_severity = {
            StormSeverity.MILD: 2.0,
            StormSeverity.MODERATE: 4.0,
            StormSeverity.SEVERE: 6.0,
            StormSeverity.EXTREME: 8.0,
        }
        return duration_by_severity[self.severity]
    
    def get_wind_at(self, position: Position) -> Vector2D:
        """Calculate wind velocity at a given position.
        
        Args:
            position: Position to calculate wind for
            
        Returns:
            Wind velocity vector
        """
        if not self.active:
            return create_vector2d(0.0, 0.0)
        
        total_wind = create_vector2d(0.0, 0.0)
        
        for cell in self.cells:
            distance = np.linalg.norm(position - cell.center)
            
            if distance < cell.radius:
                # Distance-based intensity falloff
                influence = (1.0 - distance / cell.radius) ** 2
                influence *= cell.intensity
                
                # Calculate wind direction (radial + tangential components)
                if distance > 0.1:  # Avoid division by zero
                    # Radial component (outward from center)
                    radial_dir = (position - cell.center) / distance
                    radial_wind = radial_dir * cell.wind_speed * 0.3
                    
                    # Tangential component (circulation)
                    tangent_dir = create_vector2d(-radial_dir[1], radial_dir[0])
                    tangent_wind = tangent_dir * cell.wind_speed * cell.rotation_speed
                    
                    cell_wind = (radial_wind + tangent_wind) * influence
                    total_wind += cell_wind
        
        return total_wind
    
    def affects_position(self, position: Position) -> bool:
        """Check if storm affects a given position.
        
        Args:
            position: Position to check
            
        Returns:
            True if position is within storm influence
        """
        if not self.active:
            return False
            
        for cell in self.cells:
            distance = np.linalg.norm(position - cell.center)
            if distance <= cell.radius:
                return True
        
        return False


@dataclass
class StormEvent:
    """Records a storm-related event.
    
    Attributes:
        tick: When the event occurred
        event_type: Type of storm event
        storm_id: ID of associated storm system
        agent_id: Affected agent (if applicable)
        position: Where event occurred
        severity: Storm severity at time of event
        details: Additional event-specific data
    """
    tick: Tick
    event_type: str  # "storm_spawn", "wind_shock", "exhaustion", etc.
    storm_id: str
    agent_id: Optional[int] = None
    position: Optional[Position] = None
    severity: Optional[StormSeverity] = None
    details: Dict[str, Any] = field(default_factory=dict)


def create_storm_system(
    storm_id: str,
    severity: StormSeverity,
    spawn_position: Position,
    environment: Environment,
    rng: RNG,
    current_tick: Tick,
    forecasted: bool = False,
) -> StormSystem:
    """Create a new storm system with realistic parameters.
    
    Args:
        storm_id: Unique identifier for the storm
        severity: Storm severity level
        spawn_position: Where to center the initial storm cell
        environment: Environment for boundary checking
        rng: Random number generator
        current_tick: Current simulation tick
        forecasted: Whether this storm was forecasted
        
    Returns:
        New StormSystem instance
    """
    # Create initial storm cell
    base_radius = {
        StormSeverity.MILD: 30.0,
        StormSeverity.MODERATE: 50.0,
        StormSeverity.SEVERE: 70.0,
        StormSeverity.EXTREME: 100.0,
    }[severity]
    
    base_wind_speed = {
        StormSeverity.MILD: 15.0,
        StormSeverity.MODERATE: 25.0,
        StormSeverity.SEVERE: 40.0,
        StormSeverity.EXTREME: 60.0,
    }[severity]
    
    # Add some randomization
    radius_variation = rng.uniform(0.8, 1.2)
    wind_variation = rng.uniform(0.9, 1.1)
    
    # Storm movement direction and speed
    movement_angle = rng.uniform(0, 2 * np.pi)
    movement_speed = rng.uniform(5.0, 20.0)  # km/h
    movement_vector = create_vector2d(
        movement_speed * np.cos(movement_angle),
        movement_speed * np.sin(movement_angle)
    )
    
    primary_cell = StormCell(
        center=spawn_position.copy(),
        radius=base_radius * radius_variation,
        intensity=1.0,
        wind_speed=base_wind_speed * wind_variation,
        movement_vector=movement_vector,
        rotation_speed=rng.uniform(0.05, 0.2)
    )
    
    cells = [primary_cell]
    
    # Add additional cells for severe storms
    if severity in [StormSeverity.SEVERE, StormSeverity.EXTREME]:
        n_additional = 1 if severity == StormSeverity.SEVERE else 2
        
        for i in range(n_additional):
            # Place secondary cells nearby
            offset_angle = rng.uniform(0, 2 * np.pi)
            offset_distance = rng.uniform(20.0, 60.0)
            
            secondary_center = spawn_position + create_vector2d(
                offset_distance * np.cos(offset_angle),
                offset_distance * np.sin(offset_angle)
            )
            
            secondary_cell = StormCell(
                center=secondary_center,
                radius=base_radius * 0.7 * radius_variation,
                intensity=rng.uniform(0.6, 0.9),
                wind_speed=base_wind_speed * 0.8 * wind_variation,
                movement_vector=movement_vector * rng.uniform(0.8, 1.2),
                rotation_speed=rng.uniform(0.03, 0.15)
            )
            cells.append(secondary_cell)
    
    duration = {
        StormSeverity.MILD: rng.uniform(1.0, 3.0),
        StormSeverity.MODERATE: rng.uniform(2.0, 5.0),
        StormSeverity.SEVERE: rng.uniform(3.0, 7.0),
        StormSeverity.EXTREME: rng.uniform(4.0, 10.0),
    }[severity]
    
    storm = StormSystem(
        id=storm_id,
        severity=severity,
        cells=cells,
        duration_remaining=duration,
        spawn_tick=current_tick,
        forecasted=forecasted,
    )
    
    logger.info(
        "Storm system created",
        extra={
            "storm_id": storm_id,
            "severity": severity.value,
            "cells": len(cells),
            "duration_h": duration,
            "forecasted": forecasted,
            "spawn_position": spawn_position.tolist(),
        }
    )
    
    return storm


def spawn_storms(
    active_storms: List[StormSystem],
    current_tick: Tick,
    time_of_day: float,
    environment: Environment,
    planned_storms: Optional[List[Dict[str, Any]]] = None,
    rng: Optional[RNG] = None,
) -> List[EventData]:
    """Spawn new storm systems based on weather patterns.
    
    Creates both planned (deterministic) storms and random weather events.
    Random storms must be telegraphed ≥12h in advance per CLAUDE.md.
    
    Args:
        active_storms: Currently active storm systems
        current_tick: Current simulation tick
        time_of_day: Current time of day [0.0, 24.0)
        environment: Environment to spawn storms in
        planned_storms: Predetermined storm events
        rng: Random number generator
        
    Returns:
        List of storm spawn events
        
    Note:
        This function only spawns planned storms. Random storms should be
        generated by the telegraph_hazards system and spawned when their
        scheduled time arrives.
    """
    if rng is None:
        rng = np.random.default_rng()
    
    if planned_storms is None:
        planned_storms = []
    
    spawn_events: List[EventData] = []
    
    # Process planned storm spawns
    for planned_storm in planned_storms:
        if planned_storm.get("spawn_tick", 0) == int(current_tick):
            # Time to spawn this planned storm
            severity_str = planned_storm.get("severity", "mild")
            try:
                severity = StormSeverity(severity_str)
            except ValueError:
                logger.warning(
                    "Invalid storm severity in planned storm",
                    extra={"severity": severity_str, "defaulting_to": "mild"}
                )
                severity = StormSeverity.MILD
            
            # Determine spawn position
            if "spawn_position" in planned_storm:
                spawn_pos = create_vector2d(*planned_storm["spawn_position"])
            else:
                # Random position within environment
                spawn_pos = create_vector2d(
                    rng.uniform(0, environment.width),
                    rng.uniform(0, environment.height)
                )
            
            storm_id = f"planned_storm_{current_tick}"
            new_storm = create_storm_system(
                storm_id=storm_id,
                severity=severity,
                spawn_position=spawn_pos,
                environment=environment,
                rng=rng,
                current_tick=current_tick,
                forecasted=True,  # Planned storms are always forecasted
            )
            
            active_storms.append(new_storm)
            
            spawn_events.append({
                "event_type": "storm_spawn",
                "tick": int(current_tick),
                "storm_id": storm_id,
                "severity": severity.value,
                "position": spawn_pos.tolist(),
                "planned": True,
                "duration_h": new_storm.duration_remaining,
                "cells": len(new_storm.cells),
            })
    
    # Note: Random storm generation is handled by telegraph_hazards()
    # This ensures ≥12h advance warning requirement is met
    
    return spawn_events


def apply_storm_effects(
    agents: List[Agent],
    environment: Environment,
    current_tick: Tick,
    active_storms: Optional[List[StormSystem]] = None,
    dt_hours: float = 1.0 / 3600.0,  # 1/60 second default
    rng: Optional[RNG] = None,
) -> List[EventData]:
    """Apply storm effects to agents and environment.
    
    Processes wind forces, energy drain, stress accumulation, and potential
    deaths from storm exposure. Updates wind fields and visibility.
    
    Args:
        agents: List of agents to affect (modified in-place)
        environment: Environment to modify
        current_tick: Current simulation tick
        active_storms: List of active storm systems
        dt_hours: Time step in hours
        rng: Random number generator
        
    Returns:
        List of storm effect events
        
    Performance:
        O(N*S) where N=agents, S=storm cells, typically O(N) since S is small
    """
    if rng is None:
        rng = np.random.default_rng()
    
    if active_storms is None:
        active_storms = []
    
    storm_events: List[EventData] = []
    alive_agents = [agent for agent in agents if agent.alive]
    
    if not alive_agents or not active_storms:
        return storm_events
    
    # Update all active storms
    storms_to_remove = []
    for storm in active_storms:
        still_active = storm.update(dt_hours)
        if not still_active:
            storms_to_remove.append(storm)
            storm_events.append({
                "event_type": "storm_dissipated",
                "tick": int(current_tick),
                "storm_id": storm.id,
                "duration_h": storm.get_total_duration(),
            })
    
    # Remove dissipated storms
    for storm in storms_to_remove:
        active_storms.remove(storm)
    
    # Apply effects to agents
    for agent in alive_agents:
        storm_effects_applied = False
        total_wind_force = create_vector2d(0.0, 0.0)
        max_visibility_reduction = 0.0
        max_stress_factor = 1.0
        total_energy_drain = 0.0
        
        # Check which storms affect this agent
        affecting_storms = []
        for storm in active_storms:
            if storm.affects_position(agent.position):
                affecting_storms.append(storm)
                
                # Accumulate storm effects
                storm_wind = storm.get_wind_at(agent.position)
                total_wind_force += storm_wind
                
                max_visibility_reduction = max(max_visibility_reduction, storm.visibility_reduction)
                max_stress_factor = max(max_stress_factor, storm.stress_factor)
                total_energy_drain += storm.energy_drain_rate
                
                storm_effects_applied = True
        
        if storm_effects_applied:
            # Apply wind shock to velocity (immediate effect)
            wind_shock_strength = np.linalg.norm(total_wind_force) * 0.1
            if wind_shock_strength > 0.1:
                # Add some randomness to wind direction for turbulence
                wind_turbulence = create_vector2d(
                    rng.normal(0, wind_shock_strength * 0.3),
                    rng.normal(0, wind_shock_strength * 0.3)
                )
                agent.velocity += (total_wind_force + wind_turbulence) * dt_hours
            
            # Apply energy drain
            energy_cost = total_energy_drain * dt_hours * 3600  # Convert back to seconds
            agent.update_energy(-energy_cost)
            
            # Apply stress increase
            stress_increase = (max_stress_factor - 1.0) * 10.0 * dt_hours * 3600
            agent.update_stress(stress_increase)
            
            # Check for storm-related death
            death_risk = 0.0
            
            # Energy exhaustion risk
            if agent.energy < 20.0:
                death_risk += 0.01 * dt_hours  # 1% per hour when low energy
            
            # Extreme wind risk  
            wind_speed = np.linalg.norm(total_wind_force)
            if wind_speed > 50.0:  # Extreme winds
                death_risk += 0.005 * dt_hours  # 0.5% per hour in extreme winds
            
            # Apply death risk
            if death_risk > 0 and rng.random() < death_risk:
                agent.alive = False
                
                storm_events.append({
                    "event_type": "storm_death",
                    "tick": int(current_tick),
                    "agent_id": int(agent.id),
                    "agent_position": agent.position.tolist(),
                    "cause": "exhaustion" if agent.energy <= 0 else "wind_shear",
                    "wind_speed": wind_speed,
                    "energy_remaining": agent.energy,
                    "affecting_storms": [s.id for s in affecting_storms],
                    "deaths": 1,
                })
                
                logger.warning(
                    "Agent killed by storm",
                    extra={
                        "agent_id": int(agent.id),
                        "cause": "exhaustion" if agent.energy <= 0 else "wind_shear",
                        "wind_speed": wind_speed,
                        "storms": len(affecting_storms),
                    }
                )
            else:
                # Record storm effect (non-lethal)
                if int(current_tick) % 600 == 0:  # Throttle logging (every 10 seconds at 60 FPS)
                    storm_events.append({
                        "event_type": "storm_effect",
                        "tick": int(current_tick),
                        "agent_id": int(agent.id),
                        "wind_force": np.linalg.norm(total_wind_force),
                        "energy_drain": energy_cost,
                        "stress_increase": stress_increase,
                        "visibility_reduction": max_visibility_reduction,
                        "affecting_storms": [s.id for s in affecting_storms],
                        "deaths": 0,
                    })
    
    # Modify environment wind field if storms are active
    if active_storms and hasattr(environment, 'wind'):
        _modify_wind_field(environment.wind, active_storms)
    
    if storm_events:
        deaths = sum(event.get("deaths", 0) for event in storm_events)
        logger.info(
            "Storm effects applied",
            extra={
                "total_events": len(storm_events),
                "deaths": deaths,
                "active_storms": len(active_storms),
                "affected_agents": len(alive_agents),
            }
        )
    
    return storm_events


def _modify_wind_field(wind_field: WindField, active_storms: List[StormSystem]) -> None:
    """Modify environment wind field based on active storms.
    
    Args:
        wind_field: Wind field to modify (modified in-place)
        active_storms: List of active storm systems
    """
    if not active_storms:
        return
    
    height, width = wind_field.strength_field.shape
    
    # Sample wind effects at grid points
    for y in range(height):
        for x in range(width):
            # Convert grid coordinates to world coordinates
            world_x = (x / width) * 100.0  # Assuming 100x100 world
            world_y = (y / height) * 100.0
            world_pos = create_vector2d(world_x, world_y)
            
            storm_wind = create_vector2d(0.0, 0.0)
            max_intensity = 0.0
            
            # Accumulate wind from all storms
            for storm in active_storms:
                if storm.affects_position(world_pos):
                    storm_wind += storm.get_wind_at(world_pos)
                    
                    # Find closest storm cell for intensity
                    for cell in storm.cells:
                        distance = np.linalg.norm(world_pos - cell.center)
                        if distance < cell.radius:
                            influence = (1.0 - distance / cell.radius) * cell.intensity
                            max_intensity = max(max_intensity, influence)
            
            # Apply storm effects to wind field
            if max_intensity > 0:
                # Increase base wind strength
                wind_field.strength_field[y, x] *= (1.0 + max_intensity * 2.0)
                
                # Modify wind direction
                if len(wind_field.velocity_field.shape) == 3:
                    current_wind = wind_field.velocity_field[y, x, :]
                    combined_wind = current_wind + storm_wind * 0.1
                    wind_field.velocity_field[y, x, :] = combined_wind
                
                # Increase turbulence
                wind_field.turbulence = max(wind_field.turbulence, max_intensity * 0.5)