"""Predator hazards for the Murmuration simulation.

This module implements predator spawning and predation events using Poisson
processes in predefined hotspot polygons. Higher flock cohesion reduces
predation risk through the selfish herd effect.

Key features:
- Deterministic Poisson spawning in hotspot areas
- Cohesion-based survival probability (selfish herd effect)
- Time-of-day variation in predator activity 
- Separate tracking for protected zone deaths
- O(N) performance per simulation tick

Classes:
    PredatorHotspot: Defines area with elevated predation risk
    PredationEvent: Records predation event data

Functions:
    spawn_predators: Generate new predators using Poisson process
    add_predation_events: Process predation attempts on agents
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from numpy.typing import NDArray

from ..core.types import Position, RNG, EventData, Tick, create_vector2d
from ..core.agent import Agent
from ..core.environment import Environment
from ..core.physics import compute_flock_cohesion
from ..utils.logging import get_logger

logger = get_logger("predators")


@dataclass
class PredatorHotspot:
    """Defines a predator hotspot area with elevated predation risk.
    
    Hotspots are polygonal areas where predators spawn more frequently
    and have higher success rates. Examples include forest edges, water
    sources, and terrain features that provide ambush opportunities.
    
    Attributes:
        vertices: Polygon vertices defining the hotspot boundary
        base_spawn_rate: Base Poisson lambda for predator spawning per hour
        activity_multiplier: Multiplier based on time of day
        predation_efficiency: Base predation success rate [0.0, 1.0]
        name: Human-readable identifier for logging
        active: Whether this hotspot is currently active
    """
    vertices: NDArray[np.float64]  # Shape (n_vertices, 2)
    base_spawn_rate: float = 0.1   # Spawns per hour
    activity_multiplier: float = 1.0
    predation_efficiency: float = 0.3  # 30% base success rate
    name: str = "unnamed_hotspot"
    active: bool = True
    
    def __post_init__(self) -> None:
        """Validate hotspot parameters."""
        if len(self.vertices) < 3:
            raise ValueError("Hotspot must have at least 3 vertices")
        if not (0.0 <= self.predation_efficiency <= 1.0):
            raise ValueError("Predation efficiency must be in [0.0, 1.0]")
        if self.base_spawn_rate < 0.0:
            raise ValueError("Base spawn rate must be non-negative")
    
    def contains_point(self, position: Position) -> bool:
        """Check if a position is inside this hotspot polygon.
        
        Uses ray casting algorithm for point-in-polygon test.
        
        Args:
            position: Position to test
            
        Returns:
            True if position is inside the polygon
            
        Performance:
            O(V) where V is number of vertices
        """
        if not self.active:
            return False
            
        x, y = position[0], position[1]
        n = len(self.vertices)
        inside = False
        
        p1x, p1y = self.vertices[0]
        for i in range(1, n + 1):
            p2x, p2y = self.vertices[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def get_effective_spawn_rate(self, time_of_day: float) -> float:
        """Calculate effective spawn rate based on time of day.
        
        Predator activity varies throughout the day:
        - Dawn (5-7 AM): High activity (1.5x)
        - Day (7 AM - 5 PM): Low activity (0.3x)
        - Dusk (5-8 PM): Highest activity (2.0x) 
        - Night (8 PM - 5 AM): Moderate activity (0.8x)
        
        Args:
            time_of_day: Hour of day as float [0.0, 24.0)
            
        Returns:
            Effective spawn rate per hour
        """
        if not self.active:
            return 0.0
            
        # Time-based activity multipliers
        if 5.0 <= time_of_day < 7.0:  # Dawn
            time_multiplier = 1.5
        elif 7.0 <= time_of_day < 17.0:  # Day
            time_multiplier = 0.3
        elif 17.0 <= time_of_day < 20.0:  # Dusk
            time_multiplier = 2.0
        else:  # Night (20:00 - 05:00)
            time_multiplier = 0.8
        
        return self.base_spawn_rate * self.activity_multiplier * time_multiplier
    
    def get_center(self) -> Position:
        """Get the centroid of the hotspot polygon.
        
        Returns:
            Center position of the polygon
        """
        return create_vector2d(
            float(np.mean(self.vertices[:, 0])),
            float(np.mean(self.vertices[:, 1]))
        )


@dataclass
class PredationEvent:
    """Records the details of a predation event.
    
    Attributes:
        tick: Simulation tick when event occurred
        hotspot_name: Name of the hotspot where predation occurred
        target_agent_id: ID of the targeted agent
        flock_cohesion: Cohesion value at time of attack
        success: Whether the predation was successful
        survival_bonus: Cohesion-based survival bonus applied
        position: Where the predation attempt occurred
    """
    tick: Tick
    hotspot_name: str
    target_agent_id: int
    flock_cohesion: float
    success: bool
    survival_bonus: float
    position: Position


def create_default_hotspots(environment: Environment, rng: RNG) -> List[PredatorHotspot]:
    """Create a set of default predator hotspots for an environment.
    
    Places hotspots in strategic locations like corners and edges where
    predators would naturally ambush prey.
    
    Args:
        environment: Environment to place hotspots in
        rng: Random number generator for placement variation
        
    Returns:
        List of predator hotspots
    """
    hotspots = []
    w, h = environment.width, environment.height
    
    # Forest edge hotspot (northwest)
    forest_vertices = np.array([
        [0, h * 0.7],
        [w * 0.3, h],
        [0, h],
    ], dtype=np.float64)
    
    hotspots.append(PredatorHotspot(
        vertices=forest_vertices,
        base_spawn_rate=0.15,
        predation_efficiency=0.4,
        name="forest_edge"
    ))
    
    # Water source hotspot (southeast)
    water_center = create_vector2d(w * 0.8, h * 0.2)
    water_radius = min(w, h) * 0.15
    n_sides = 8
    angles = np.linspace(0, 2 * np.pi, n_sides, endpoint=False)
    water_vertices = np.array([
        [water_center[0] + water_radius * np.cos(angle),
         water_center[1] + water_radius * np.sin(angle)]
        for angle in angles
    ], dtype=np.float64)
    
    hotspots.append(PredatorHotspot(
        vertices=water_vertices,
        base_spawn_rate=0.08,
        predation_efficiency=0.25,
        name="water_source"
    ))
    
    # Rocky outcrop hotspot (center-east)
    rock_vertices = np.array([
        [w * 0.6, h * 0.4],
        [w * 0.9, h * 0.45], 
        [w * 0.85, h * 0.7],
        [w * 0.55, h * 0.65],
    ], dtype=np.float64)
    
    hotspots.append(PredatorHotspot(
        vertices=rock_vertices,
        base_spawn_rate=0.12,
        predation_efficiency=0.35,
        name="rocky_outcrop"
    ))
    
    logger.info(
        "Created default predator hotspots",
        extra={
            "hotspot_count": len(hotspots),
            "total_area": sum(_calculate_polygon_area(h.vertices) for h in hotspots),
            "environment_size": w * h,
        }
    )
    
    return hotspots


def _calculate_polygon_area(vertices: NDArray[np.float64]) -> float:
    """Calculate area of polygon using shoelace formula.
    
    Args:
        vertices: Array of polygon vertices shape (n, 2)
        
    Returns:
        Area of the polygon
    """
    n = len(vertices)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    return abs(area) / 2.0


def spawn_predators(
    hotspots: List[PredatorHotspot],
    current_tick: Tick,
    time_of_day: float,
    dt_hours: float,
    rng: RNG,
) -> List[EventData]:
    """Spawn predators in hotspots using Poisson process.
    
    Generates predator spawn events based on Poisson distribution with
    rates varying by hotspot and time of day. Each spawn event creates
    potential predation pressure for agents in that area.
    
    Args:
        hotspots: List of active predator hotspots
        current_tick: Current simulation tick
        time_of_day: Current time of day [0.0, 24.0)
        dt_hours: Time step in hours
        rng: Random number generator for deterministic spawning
        
    Returns:
        List of predator spawn events
        
    Performance:
        O(H) where H is the number of hotspots
        
    Example:
        >>> hotspots = create_default_hotspots(env, rng)
        >>> events = spawn_predators(hotspots, Tick(1000), 6.5, 1/60, rng)
        >>> print(f"Spawned predators: {len(events)}")
    """
    spawn_events: List[EventData] = []
    
    for hotspot in hotspots:
        if not hotspot.active:
            continue
        
        # Get time-adjusted spawn rate
        spawn_rate = hotspot.get_effective_spawn_rate(time_of_day)
        
        # Expected spawns this timestep
        lambda_dt = spawn_rate * dt_hours
        
        # Sample from Poisson distribution
        num_spawns = rng.poisson(lambda_dt) if lambda_dt > 0 else 0
        
        if num_spawns > 0:
            # Generate spawn positions within hotspot polygon
            hotspot_center = hotspot.get_center()
            
            for _ in range(num_spawns):
                # Simple method: sample near center with some spread
                # More sophisticated methods could uniformly sample polygon interior
                spawn_offset = create_vector2d(
                    rng.normal(0, 20.0),
                    rng.normal(0, 20.0)
                )
                spawn_position = hotspot_center + spawn_offset
                
                spawn_events.append({
                    "event_type": "predator_spawn",
                    "tick": int(current_tick),
                    "hotspot_name": hotspot.name,
                    "position": spawn_position.tolist(),
                    "time_of_day": time_of_day,
                    "spawn_rate": spawn_rate,
                    "efficiency": hotspot.predation_efficiency,
                })
        
        # Log spawn activity (throttled to avoid spam)
        if int(current_tick) % 3600 == 0:  # Once per hour (assuming 60 ticks/sec)
            logger.debug(
                "Predator spawn check",
                extra={
                    "hotspot": hotspot.name,
                    "spawn_rate": spawn_rate,
                    "lambda_dt": lambda_dt,
                    "spawns": num_spawns,
                    "time_of_day": time_of_day,
                }
            )
    
    if spawn_events:
        logger.info(
            "Predators spawned",
            extra={
                "total_spawns": len(spawn_events),
                "hotspots_active": sum(1 for h in hotspots if h.active),
                "time_of_day": time_of_day,
            }
        )
    
    return spawn_events


def add_predation_events(
    agents: List[Agent],
    environment: Environment,
    current_tick: Tick,
    time_of_day: float,
    protected_zones: Optional[List[Tuple[Position, float]]] = None,
    rng: Optional[RNG] = None,
    hotspots: Optional[List[PredatorHotspot]] = None,
) -> List[EventData]:
    """Process predation events affecting agents in the environment.
    
    Evaluates predation attempts on agents based on their positions relative
    to predator hotspots. Higher flock cohesion increases survival chances
    through the selfish herd effect.
    
    Args:
        agents: List of agents to check for predation (modified in-place)
        environment: Environment containing hazard state
        current_tick: Current simulation tick
        time_of_day: Current time of day [0.0, 24.0)
        protected_zones: List of (center, radius) for protected areas
        rng: Random number generator for deterministic predation
        hotspots: Predator hotspots (creates defaults if None)
        
    Returns:
        List of predation events (both successful and failed attempts)
        
    Performance:
        O(N*H) where N=agents, H=hotspots, typically O(N) since H is small
        
    Notes:
        Cohesion-based survival follows the selfish herd hypothesis:
        - High cohesion (>0.7): +50% survival bonus
        - Medium cohesion (0.4-0.7): +20% survival bonus  
        - Low cohesion (<0.4): No survival bonus
    """
    if rng is None:
        rng = np.random.default_rng()
    
    if protected_zones is None:
        protected_zones = []
    
    if hotspots is None:
        hotspots = create_default_hotspots(environment, rng)
    
    predation_events: List[EventData] = []
    alive_agents = [agent for agent in agents if agent.alive]
    
    if not alive_agents:
        return predation_events
    
    # Calculate current flock cohesion for survival bonus
    flock_cohesion = compute_flock_cohesion(agents)
    
    # Cohesion-based survival bonus (selfish herd effect)
    if flock_cohesion >= 0.7:
        cohesion_survival_bonus = 0.5  # 50% bonus
    elif flock_cohesion >= 0.4:
        cohesion_survival_bonus = 0.2  # 20% bonus
    else:
        cohesion_survival_bonus = 0.0  # No bonus
    
    logger.debug(
        "Evaluating predation risk", 
        extra={
            "alive_agents": len(alive_agents),
            "flock_cohesion": flock_cohesion,
            "survival_bonus": cohesion_survival_bonus,
            "active_hotspots": sum(1 for h in hotspots if h.active),
        }
    )
    
    # Check each agent against hotspots
    for agent in alive_agents:
        # Skip agents in protected zones
        in_protected_zone = False
        for zone_center, zone_radius in protected_zones:
            distance = np.linalg.norm(agent.position - np.array(zone_center))
            if distance <= zone_radius:
                in_protected_zone = True
                break
        
        if in_protected_zone:
            continue
        
        # Check if agent is in any active hotspot
        for hotspot in hotspots:
            if not hotspot.active:
                continue
                
            if hotspot.contains_point(agent.position):
                # Agent is at risk - roll for predation attempt
                base_risk = hotspot.predation_efficiency * hotspot.activity_multiplier
                
                # Time of day affects predation risk
                time_risk_multiplier = hotspot.get_effective_spawn_rate(time_of_day) / hotspot.base_spawn_rate
                
                # Calculate total predation probability
                predation_probability = base_risk * time_risk_multiplier
                
                # Apply cohesion survival bonus
                survival_probability = 1.0 - predation_probability + cohesion_survival_bonus
                survival_probability = np.clip(survival_probability, 0.0, 1.0)
                
                # Roll for survival
                survival_roll = rng.random()
                success = survival_roll >= survival_probability
                
                # Record predation event
                event_data = {
                    "event_type": "predation" if success else "predation_attempt",
                    "tick": int(current_tick),
                    "agent_id": int(agent.id),
                    "agent_position": agent.position.tolist(),
                    "hotspot_name": hotspot.name,
                    "flock_cohesion": flock_cohesion,
                    "base_risk": base_risk,
                    "time_multiplier": time_risk_multiplier,
                    "survival_bonus": cohesion_survival_bonus,
                    "survival_probability": survival_probability,
                    "survival_roll": survival_roll,
                    "success": success,
                    "deaths": 1 if success else 0,
                    "time_of_day": time_of_day,
                }
                
                predation_events.append(event_data)
                
                if success:
                    # Agent is killed
                    agent.alive = False
                    logger.warning(
                        "Agent killed by predator",
                        extra={
                            "agent_id": int(agent.id),
                            "hotspot": hotspot.name,
                            "cohesion": flock_cohesion,
                            "survival_prob": survival_probability,
                        }
                    )
                else:
                    # Agent survives but may suffer stress
                    stress_increase = rng.uniform(10.0, 25.0)
                    agent.update_stress(stress_increase)
                    
                    logger.debug(
                        "Agent survived predation attempt",
                        extra={
                            "agent_id": int(agent.id),
                            "stress_increase": stress_increase,
                            "survival_prob": survival_probability,
                        }
                    )
                
                # Only one predation attempt per agent per tick
                break
    
    # Spawn new predators for next tick
    dt_hours = 1.0 / 3600.0  # Assuming 60 FPS = 3600 ticks/hour
    spawn_events = spawn_predators(hotspots, current_tick, time_of_day, dt_hours, rng)
    predation_events.extend(spawn_events)
    
    if predation_events:
        successful_predations = sum(1 for event in predation_events if event.get("success", False))
        logger.info(
            "Predation events processed",
            extra={
                "total_events": len(predation_events),
                "successful_kills": successful_predations,
                "spawn_events": len(spawn_events),
                "flock_cohesion": flock_cohesion,
            }
        )
    
    return predation_events