"""Light pollution hazards for the Murmuration simulation.

This module implements urban light pollution effects that disrupt natural
navigation during nighttime migration. Birds can become trapped by artificial
lights, leading to exhaustion, collisions, and predation.

Key features:
- Urban light source modeling with intensity gradients
- Night-time navigation disruption effects
- Circadian rhythm disruption and stress accumulation
- Energy drain from disorientation and extended flight
- Collision risk with illuminated structures

Classes:
    LightPollutionTrap: Represents an urban light source
    LightPollutionEvent: Records light pollution event data

Functions:
    check_light_pollution: Apply light pollution effects to agents
    create_urban_lighting: Generate realistic urban light patterns
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from enum import Enum

from ..core.types import Position, RNG, EventData, Tick, create_vector2d, Vector2D
from ..core.agent import Agent
from ..core.environment import Environment
from ..utils.logging import get_logger

logger = get_logger("light_pollution")


class LightType(Enum):
    """Types of artificial light sources."""
    STREET_LIGHT = "street_light"
    BUILDING = "building"
    STADIUM = "stadium"
    TOWER = "tower"
    BILLBOARD = "billboard"


@dataclass
class LightPollutionTrap:
    """Represents an artificial light source causing navigation disruption.
    
    Urban lights create zones of navigation confusion for migrating birds,
    especially during night hours. The effect varies by light type, intensity,
    and spectral characteristics.
    
    Attributes:
        position: Center position of the light source
        light_type: Type of light source affecting behavior patterns
        intensity: Light intensity [0.0, 1.0] where 1.0 is blinding
        radius: Effective radius of light influence
        trap_strength: Probability of trapping agents per hour
        spectral_disruption: Blue light content affecting circadian rhythm
        collision_risk: Base collision probability with structures
        active_hours: Hours when light is active (24-hour format)
        seasonal_variation: Intensity variation by season
    """
    position: Position
    light_type: LightType
    intensity: float = 0.5
    radius: float = 50.0
    trap_strength: float = 0.1  # 10% chance per hour
    spectral_disruption: float = 0.3  # Blue light content
    collision_risk: float = 0.05  # 5% base collision risk
    active_hours: Tuple[float, float] = (18.0, 6.0)  # 6 PM to 6 AM
    seasonal_variation: float = 0.1
    
    def __post_init__(self) -> None:
        """Initialize light parameters based on type."""
        type_params = {
            LightType.STREET_LIGHT: {
                "intensity": 0.3,
                "radius": 25.0,
                "trap_strength": 0.05,
                "spectral_disruption": 0.4,
                "collision_risk": 0.02,
            },
            LightType.BUILDING: {
                "intensity": 0.6,
                "radius": 80.0,
                "trap_strength": 0.15,
                "spectral_disruption": 0.5,
                "collision_risk": 0.08,
            },
            LightType.STADIUM: {
                "intensity": 0.9,
                "radius": 200.0,
                "trap_strength": 0.3,
                "spectral_disruption": 0.2,
                "collision_risk": 0.03,
            },
            LightType.TOWER: {
                "intensity": 0.8,
                "radius": 150.0,
                "trap_strength": 0.25,
                "spectral_disruption": 0.6,
                "collision_risk": 0.12,
            },
            LightType.BILLBOARD: {
                "intensity": 0.7,
                "radius": 60.0,
                "trap_strength": 0.2,
                "spectral_disruption": 0.7,
                "collision_risk": 0.04,
            },
        }
        
        if self.intensity == 0.5:  # Default value, update based on type
            params = type_params[self.light_type]
            self.intensity = params["intensity"]
            self.radius = params["radius"]
            self.trap_strength = params["trap_strength"]
            self.spectral_disruption = params["spectral_disruption"]
            self.collision_risk = params["collision_risk"]
    
    def is_active(self, time_of_day: float) -> bool:
        """Check if light source is active at given time.
        
        Args:
            time_of_day: Hour of day [0.0, 24.0)
            
        Returns:
            True if light is currently active
        """
        start_hour, end_hour = self.active_hours
        
        if start_hour <= end_hour:  # Same day (e.g., 9 AM to 5 PM)
            return start_hour <= time_of_day <= end_hour
        else:  # Crosses midnight (e.g., 6 PM to 6 AM)
            return time_of_day >= start_hour or time_of_day <= end_hour
    
    def get_intensity_at(self, position: Position, time_of_day: float) -> float:
        """Calculate light intensity at a given position and time.
        
        Args:
            position: Position to calculate intensity for
            time_of_day: Current time of day [0.0, 24.0)
            
        Returns:
            Light intensity at position [0.0, 1.0]
        """
        if not self.is_active(time_of_day):
            return 0.0
        
        distance = np.linalg.norm(position - self.position)
        
        if distance >= self.radius:
            return 0.0
        
        # Distance-based intensity falloff (inverse square law with minimum)
        distance_factor = max(0.1, 1.0 - (distance / self.radius) ** 2)
        
        # Time-based intensity variation (dimmer in late night)
        if 2.0 <= time_of_day <= 5.0:  # Late night dimming
            time_factor = 0.7
        elif 5.0 < time_of_day <= 6.0:  # Early morning dimming
            time_factor = 0.5
        else:
            time_factor = 1.0
        
        return self.intensity * distance_factor * time_factor
    
    def get_trap_probability(self, position: Position, time_of_day: float, dt_hours: float) -> float:
        """Calculate probability of trapping an agent at given position.
        
        Args:
            position: Agent position
            time_of_day: Current time of day
            dt_hours: Time step in hours
            
        Returns:
            Trap probability for this time step
        """
        intensity = self.get_intensity_at(position, time_of_day)
        
        if intensity <= 0.01:
            return 0.0
        
        # Base trap probability scaled by intensity and time step
        base_prob = self.trap_strength * intensity * dt_hours
        
        # Peak trapping hours (migration times)
        if 20.0 <= time_of_day <= 2.0:  # Peak migration hours
            time_multiplier = 2.0
        elif 2.0 < time_of_day <= 6.0:  # Late night
            time_multiplier = 1.5
        else:
            time_multiplier = 1.0
        
        return min(base_prob * time_multiplier, 0.95)  # Cap at 95%


@dataclass
class LightPollutionEvent:
    """Records a light pollution event affecting agents.
    
    Attributes:
        tick: When the event occurred
        event_type: Type of light pollution event
        agent_id: Affected agent ID
        position: Where event occurred
        light_source: Associated light pollution source
        intensity: Light intensity at agent position
        duration_hours: How long agent was affected
        outcome: Result of the interaction
    """
    tick: Tick
    event_type: str  # "navigation_disruption", "collision", "exhaustion", etc.
    agent_id: int
    position: Position
    light_source: str
    intensity: float
    duration_hours: float
    outcome: str  # "trapped", "escaped", "collision", "death"


def create_urban_lighting(
    environment: Environment,
    city_centers: List[Position],
    rng: RNG,
    density_factor: float = 1.0,
) -> List[LightPollutionTrap]:
    """Create realistic urban light pollution sources.
    
    Generates a network of artificial light sources around urban centers
    with realistic distributions of different light types.
    
    Args:
        environment: Environment to place lights in
        city_centers: Positions of urban centers
        rng: Random number generator for placement
        density_factor: Multiplier for light source density
        
    Returns:
        List of light pollution sources
    """
    light_sources = []
    
    for i, city_center in enumerate(city_centers):
        city_id = f"city_{i}"
        city_radius = rng.uniform(30.0, 80.0)  # City size variation
        
        # Calculate number of lights based on city size and density
        base_lights = int(city_radius / 10.0 * density_factor)
        n_lights = rng.poisson(base_lights)
        
        logger.debug(
            "Generating urban lighting",
            extra={
                "city_id": city_id,
                "center": city_center.tolist(),
                "radius": city_radius,
                "n_lights": n_lights,
            }
        )
        
        # Generate different types of light sources
        for j in range(n_lights):
            # Light type distribution (realistic urban mix)
            light_type_probs = [0.4, 0.3, 0.05, 0.15, 0.1]  # street, building, stadium, tower, billboard
            light_type = rng.choice(list(LightType), p=light_type_probs)
            
            # Position within city boundaries (clustered around center)
            if light_type == LightType.STADIUM:
                # Stadiums on city edges
                angle = rng.uniform(0, 2 * np.pi)
                distance = rng.uniform(city_radius * 0.7, city_radius)
            elif light_type == LightType.TOWER:
                # Towers scattered throughout
                angle = rng.uniform(0, 2 * np.pi)
                distance = rng.uniform(0, city_radius)
            else:
                # Other lights concentrated in center
                angle = rng.uniform(0, 2 * np.pi)
                distance = rng.exponential(city_radius * 0.3)
                distance = min(distance, city_radius)
            
            light_position = city_center + create_vector2d(
                distance * np.cos(angle),
                distance * np.sin(angle)
            )
            
            # Ensure lights are within environment bounds
            light_position[0] = np.clip(light_position[0], 0, environment.width)
            light_position[1] = np.clip(light_position[1], 0, environment.height)
            
            # Create light source with some parameter variation
            intensity_var = rng.uniform(0.8, 1.2)
            radius_var = rng.uniform(0.9, 1.1)
            
            light_source = LightPollutionTrap(
                position=light_position,
                light_type=light_type,
            )
            
            # Apply variation
            light_source.intensity *= intensity_var
            light_source.radius *= radius_var
            
            light_sources.append(light_source)
    
    logger.info(
        "Urban lighting created",
        extra={
            "total_lights": len(light_sources),
            "cities": len(city_centers),
            "types": {lt.value: sum(1 for ls in light_sources if ls.light_type == lt) for lt in LightType},
        }
    )
    
    return light_sources


def check_light_pollution(
    agents: List[Agent],
    environment: Environment,
    current_tick: Tick,
    light_intensity: float = 1.0,
    light_sources: Optional[List[LightPollutionTrap]] = None,
    time_of_day: Optional[float] = None,
    dt_hours: float = 1.0 / 3600.0,
    rng: Optional[RNG] = None,
) -> List[EventData]:
    """Check and apply light pollution effects to agents.
    
    Evaluates navigation disruption, collision risk, and energy drain from
    artificial lighting during night hours. Effects are strongest during
    peak migration times (8 PM - 2 AM).
    
    Args:
        agents: List of agents to check (modified in-place)
        environment: Environment containing light sources
        current_tick: Current simulation tick
        light_intensity: Global light intensity multiplier
        light_sources: List of light pollution sources (creates defaults if None)
        time_of_day: Current time of day [0.0, 24.0) (estimated if None)
        dt_hours: Time step in hours
        rng: Random number generator
        
    Returns:
        List of light pollution events
        
    Performance:
        O(N*L) where N=agents, L=light sources, typically O(N) since L is small
        
    Notes:
        Light pollution effects are minimal during daytime hours and peak
        during nighttime migration periods. Young or inexperienced agents
        are more susceptible to light traps.
    """
    if rng is None:
        rng = np.random.default_rng()
    
    if time_of_day is None:
        # Estimate time from tick (assuming 60 FPS and 1 tick = 1 second)
        hours_per_tick = 1.0 / 3600.0  # 1 hour = 3600 ticks
        time_of_day = (float(current_tick) * hours_per_tick) % 24.0
    
    # Only significant effects during night hours
    if not (19.0 <= time_of_day <= 6.0):  # 7 PM to 6 AM
        return []
    
    if light_sources is None:
        # Create default urban lighting if none provided
        city_centers = [
            create_vector2d(environment.width * 0.2, environment.height * 0.3),
            create_vector2d(environment.width * 0.8, environment.height * 0.7),
        ]
        light_sources = create_urban_lighting(environment, city_centers, rng)
    
    light_events: List[EventData] = []
    alive_agents = [agent for agent in agents if agent.alive]
    
    if not alive_agents or not light_sources:
        return light_events
    
    logger.debug(
        "Checking light pollution effects",
        extra={
            "agents": len(alive_agents),
            "light_sources": len(light_sources),
            "time_of_day": time_of_day,
            "light_intensity": light_intensity,
        }
    )
    
    for agent in alive_agents:
        total_light_exposure = 0.0
        max_trap_probability = 0.0
        affecting_lights = []
        
        # Check exposure to all light sources
        for light_source in light_sources:
            if not light_source.is_active(time_of_day):
                continue
            
            intensity_at_agent = light_source.get_intensity_at(agent.position, time_of_day)
            
            if intensity_at_agent > 0.01:  # Minimum threshold
                total_light_exposure += intensity_at_agent
                affecting_lights.append(light_source)
                
                # Track highest trap probability
                trap_prob = light_source.get_trap_probability(agent.position, time_of_day, dt_hours)
                max_trap_probability = max(max_trap_probability, trap_prob)
        
        if total_light_exposure <= 0.01:
            continue  # No significant light exposure
        
        # Apply global light intensity modifier
        total_light_exposure *= light_intensity
        max_trap_probability *= light_intensity
        
        # Navigation disruption effects
        if total_light_exposure > 0.1:
            # Disorientation causes erratic movement
            disorientation_strength = min(total_light_exposure, 1.0)
            
            # Add random velocity component (navigation confusion)
            confusion_velocity = create_vector2d(
                rng.normal(0, disorientation_strength * 2.0),
                rng.normal(0, disorientation_strength * 2.0)
            )
            agent.velocity += confusion_velocity * dt_hours
            
            # Increased energy drain from inefficient flight
            energy_drain = disorientation_strength * 5.0 * dt_hours * 3600
            agent.update_energy(-energy_drain)
            
            # Circadian rhythm disruption increases stress
            stress_increase = total_light_exposure * 15.0 * dt_hours * 3600
            agent.update_stress(stress_increase)
        
        # Trapping effects (agent becomes attracted to light)
        if max_trap_probability > 0.01:
            trap_roll = rng.random()
            
            if trap_roll < max_trap_probability:
                # Agent becomes trapped/attracted to light
                
                # Find strongest light source
                strongest_light = max(affecting_lights, 
                                    key=lambda ls: ls.get_intensity_at(agent.position, time_of_day))
                
                # Attract agent toward light source
                attraction_vector = strongest_light.position - agent.position
                attraction_distance = np.linalg.norm(attraction_vector)
                
                if attraction_distance > 1.0:  # Avoid division by zero
                    attraction_force = (attraction_vector / attraction_distance) * strongest_light.trap_strength
                    agent.velocity += attraction_force * dt_hours
                
                # Check for collision with structures
                collision_risk = strongest_light.collision_risk * total_light_exposure
                collision_roll = rng.random()
                
                if collision_roll < collision_risk * dt_hours:
                    # Collision death
                    agent.alive = False
                    
                    light_events.append({
                        "event_type": "light_trap_death",
                        "tick": int(current_tick),
                        "agent_id": int(agent.id),
                        "agent_position": agent.position.tolist(),
                        "light_type": strongest_light.light_type.value,
                        "light_position": strongest_light.position.tolist(),
                        "cause": "collision",
                        "light_intensity": total_light_exposure,
                        "trap_probability": max_trap_probability,
                        "deaths": 1,
                        "time_of_day": time_of_day,
                    })
                    
                    logger.warning(
                        "Agent killed by light pollution collision",
                        extra={
                            "agent_id": int(agent.id),
                            "light_type": strongest_light.light_type.value,
                            "intensity": total_light_exposure,
                            "collision_risk": collision_risk,
                        }
                    )
                else:
                    # Trapped but alive
                    light_events.append({
                        "event_type": "navigation_disruption",
                        "tick": int(current_tick),
                        "agent_id": int(agent.id),
                        "agent_position": agent.position.tolist(),
                        "light_type": strongest_light.light_type.value,
                        "light_position": strongest_light.position.tolist(),
                        "outcome": "trapped",
                        "light_intensity": total_light_exposure,
                        "energy_drain": energy_drain,
                        "stress_increase": stress_increase,
                        "deaths": 0,
                        "time_of_day": time_of_day,
                    })
        
        # Check for death from exhaustion (separate from collision)
        if agent.alive and agent.energy <= 0.0:
            agent.alive = False
            
            light_events.append({
                "event_type": "light_trap_death",
                "tick": int(current_tick),
                "agent_id": int(agent.id),
                "agent_position": agent.position.tolist(),
                "cause": "exhaustion",
                "light_intensity": total_light_exposure,
                "affecting_lights": len(affecting_lights),
                "deaths": 1,
                "time_of_day": time_of_day,
            })
            
            logger.warning(
                "Agent died from exhaustion due to light pollution",
                extra={
                    "agent_id": int(agent.id),
                    "light_exposure": total_light_exposure,
                    "affecting_lights": len(affecting_lights),
                }
            )
    
    if light_events:
        deaths = sum(event.get("deaths", 0) for event in light_events)
        disruptions = sum(1 for event in light_events if "disruption" in event["event_type"])
        
        logger.info(
            "Light pollution effects processed",
            extra={
                "total_events": len(light_events),
                "deaths": deaths,
                "disruptions": disruptions,
                "affected_agents": len([e for e in light_events if e.get("agent_id")]),
                "active_lights": len([ls for ls in light_sources if ls.is_active(time_of_day)]),
            }
        )
    
    return light_events