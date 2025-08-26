"""Deterministic physics integration for the Murmuration simulation.

This module implements the core physics engine for agent movement, including
flocking behaviors, environmental forces, and semi-implicit Euler integration
with fixed 60Hz timesteps for deterministic behavior.

Performance target: O(N²) for flocking behaviors, capable of handling
300 agents @ 60Hz on development hardware.
"""

import logging
from typing import List, Tuple, Optional
import numpy as np

from .types import Position, Velocity, Positions, Velocities, Vector2D, RNG, create_vector2d
from .agent import Agent
from .environment import Environment

# Configure structured logging
logger = logging.getLogger(__name__)


# Physics constants
FIXED_TIMESTEP = 1.0 / 60.0  # Fixed timestep at 60Hz
MAX_SPEED = 8.0  # Maximum agent speed
MAX_ACCELERATION = 2.0  # Maximum acceleration magnitude
DRAG_COEFFICIENT = 0.98  # Velocity damping factor
MIN_SEPARATION = 2.0  # Minimum distance between agents
COHESION_RADIUS = 15.0  # Radius for cohesion behavior
ALIGNMENT_RADIUS = 12.0  # Radius for alignment behavior
SEPARATION_RADIUS = 8.0  # Radius for separation behavior

# Force weights for flocking behaviors
SEPARATION_WEIGHT = 2.0
ALIGNMENT_WEIGHT = 1.0
COHESION_WEIGHT = 0.8
BEACON_WEIGHT = 1.5
WIND_WEIGHT = 0.5
RISK_AVOIDANCE_WEIGHT = 3.0

# Energy and stress dynamics constants
ENERGY_COST_SPEED_FACTOR = 0.1
STRESS_CROWDING_FACTOR = 0.5
STRESS_RISK_FACTOR = 10.0
STRESS_DECAY_RATE = 1.0


def apply_flocking_forces(
    positions: Positions,
    velocities: Velocities,
    agent_idx: int,
    rng: RNG,
) -> Vector2D:
    """Apply Reynolds flocking forces (separation, alignment, cohesion) to an agent.
    
    Implements the classic three rules of flocking using optimized vectorized calculations:
    1. Separation - avoid crowding neighbors within separation radius
    2. Alignment - steer towards average heading of neighbors within alignment radius
    3. Cohesion - steer towards average position of neighbors within cohesion radius
    
    Args:
        positions: Array of all agent positions (N, 2)
        velocities: Array of all agent velocities (N, 2) 
        agent_idx: Index of the agent to compute forces for
        rng: Random number generator for deterministic behavior (unused but required)
        
    Returns:
        Combined flocking force vector to apply to the agent
        
    Performance:
        O(N) where N is number of agents - optimized with vectorized operations
    """
    position = positions[agent_idx]
    velocity = velocities[agent_idx]
    
    # Vectorized distance calculations
    diffs = position - positions  # Shape (N, 2)
    distances = np.linalg.norm(diffs, axis=1)  # Shape (N,)
    
    # Avoid self and zero-distance agents
    valid_mask = (distances > 0) & (np.arange(len(positions)) != agent_idx)
    
    if not np.any(valid_mask):
        return create_vector2d(0.0, 0.0)
    
    # Initialize force
    total_force = create_vector2d(0.0, 0.0)
    
    # Separation forces
    separation_mask = valid_mask & (distances < SEPARATION_RADIUS)
    if np.any(separation_mask):
        sep_diffs = diffs[separation_mask]
        sep_distances = distances[separation_mask, np.newaxis]  # Shape (n_sep, 1)
        separation_forces = sep_diffs / sep_distances  # Normalized directions
        separation_force = np.mean(separation_forces, axis=0)
        total_force += separation_force * SEPARATION_WEIGHT
    
    # Alignment forces  
    alignment_mask = valid_mask & (distances < ALIGNMENT_RADIUS)
    if np.any(alignment_mask):
        neighbor_velocities = velocities[alignment_mask]
        avg_velocity = np.mean(neighbor_velocities, axis=0)
        alignment_force = avg_velocity - velocity  # Steer toward average
        total_force += alignment_force * ALIGNMENT_WEIGHT
    
    # Cohesion forces
    cohesion_mask = valid_mask & (distances < COHESION_RADIUS)
    if np.any(cohesion_mask):
        neighbor_positions = positions[cohesion_mask]
        center_of_mass = np.mean(neighbor_positions, axis=0)
        cohesion_force = center_of_mass - position
        total_force += cohesion_force * COHESION_WEIGHT
    
    return total_force


def apply_beacon_forces(
    position: Position,
    environment: Environment,
    rng: RNG,
) -> Vector2D:
    """Apply attraction forces from player-placed beacons.
    
    Beacons provide guidance forces that attract agents toward their positions
    with strength proportional to beacon strength and inverse distance.
    
    Args:
        position: Agent position to calculate beacon forces for
        environment: Environment containing active beacons
        rng: Random number generator for deterministic behavior (unused but required)
        
    Returns:
        Combined beacon attraction force vector
    """
    beacon_influence = environment.get_beacon_influence(position)
    return beacon_influence * BEACON_WEIGHT


def apply_environmental_forces(
    position: Position,
    velocity: Velocity,
    environment: Environment,
    rng: RNG,
) -> Vector2D:
    """Apply environmental forces including wind and obstacle avoidance.
    
    Environmental forces include:
    - Wind forces from the wind field with turbulence
    - Risk avoidance forces to steer away from dangerous areas
    
    Args:
        position: Agent position to calculate forces for
        velocity: Agent velocity (currently unused but may be needed for advanced wind models)
        environment: Environment containing wind field and risk zones
        rng: Random number generator for deterministic turbulence
        
    Returns:
        Combined environmental force vector
    """
    total_force = create_vector2d(0.0, 0.0)
    
    # Wind force
    if environment.wind is not None:
        wind_velocity = environment.wind.get_wind_at(position)
        wind_force = wind_velocity * 0.5
        total_force += wind_force
        
        # Add turbulence
        turbulence_strength = environment.wind.turbulence
        turbulence = create_vector2d(
            rng.normal(0, turbulence_strength),
            rng.normal(0, turbulence_strength)
        )
        total_force += turbulence
    
    # Risk avoidance
    risk_level = environment.get_risk_at(position)
    if risk_level > 0.1:
        # Sample risk gradient to determine avoidance direction
        gradient_step = 1.0
        risk_gradient = create_vector2d(0.0, 0.0)
        
        # Sample neighboring positions
        for dx, dy in [(gradient_step, 0), (-gradient_step, 0), (0, gradient_step), (0, -gradient_step)]:
            sample_pos = position + create_vector2d(dx, dy)
            sample_risk = environment.get_risk_at(sample_pos)
            direction = create_vector2d(-dx, -dy)  # Opposite direction
            risk_gradient += direction * (sample_risk - risk_level)
        
        # Apply avoidance force proportional to risk level
        avoidance_force = risk_gradient * risk_level * 3.0
        total_force += avoidance_force
    
    # Removed debug logging for performance
    
    return total_force


def integrate_semi_implicit_euler(
    position: Position,
    velocity: Velocity,
    acceleration: Vector2D,
    dt: float,
) -> Tuple[Position, Velocity]:
    """Integrate agent motion using semi-implicit Euler method.
    
    Semi-implicit Euler provides better stability than explicit Euler
    while being more computationally efficient than Velocity-Verlet.
    This ensures deterministic physics integration.
    
    Args:
        position: Current position
        velocity: Current velocity
        acceleration: Current acceleration
        dt: Time step (should be FIXED_TIMESTEP for determinism)
        
    Returns:
        Tuple of (new_position, new_velocity)
        
    Note:
        Semi-implicit Euler updates velocity first, then position:
        v(t+dt) = v(t) + a(t) * dt
        x(t+dt) = x(t) + v(t+dt) * dt
    """
    # Semi-implicit Euler integration: update velocity first, then position
    new_velocity = velocity + acceleration * dt
    
    # Apply drag to velocity
    new_velocity = new_velocity * DRAG_COEFFICIENT
    
    # Apply speed limit
    speed = np.linalg.norm(new_velocity)
    if speed > MAX_SPEED:
        new_velocity = (new_velocity / speed) * MAX_SPEED
    
    # Update position using new velocity
    new_position = position + new_velocity * dt
    
    return new_position, new_velocity


def apply_boundary_conditions(
    position: Position,
    velocity: Velocity,
    environment: Environment,
) -> Tuple[Position, Velocity]:
    """Apply boundary conditions to keep agents within the environment.
    
    Uses soft boundary forces rather than hard walls for more natural behavior.
    
    Args:
        position: Agent position
        velocity: Agent velocity  
        environment: Environment with boundary information
        
    Returns:
        Tuple of (constrained_position, adjusted_velocity)
    """
    boundary_force = create_vector2d(0.0, 0.0)
    boundary_strength = 5.0
    boundary_margin = 10.0
    
    # Left boundary
    if position[0] < boundary_margin:
        boundary_force[0] += boundary_strength * (boundary_margin - position[0])
    
    # Right boundary
    if position[0] > environment.width - boundary_margin:
        boundary_force[0] -= boundary_strength * (position[0] - (environment.width - boundary_margin))
    
    # Bottom boundary
    if position[1] < boundary_margin:
        boundary_force[1] += boundary_strength * (boundary_margin - position[1])
    
    # Top boundary
    if position[1] > environment.height - boundary_margin:
        boundary_force[1] -= boundary_strength * (position[1] - (environment.height - boundary_margin))
    
    # Apply boundary force to velocity (more gentle)
    adjusted_velocity = velocity + boundary_force * 0.05  # Reduced multiplier
    
    # Hard clamp position to environment bounds
    clamped_position = np.array([
        np.clip(position[0], 0, environment.width),
        np.clip(position[1], 0, environment.height)
    ])
    
    # Note: Speed limiting is applied after this in the main integration loop
    return clamped_position, adjusted_velocity


def update_energy_stress(
    agents: List[Agent],
    environment: Environment,
    dt: float,
    positions: Positions,
    velocities: Velocities,
    rng: RNG,
) -> None:
    """Update agent energy and stress levels based on current state.
    
    Energy decreases based on movement speed and increases from food sources.
    Stress increases from crowding, risk exposure, and decreases over time.
    
    Args:
        agents: List of agents to update (only alive agents)
        environment: Environment containing food sources and risk fields
        dt: Time step duration
        positions: Current agent positions
        velocities: Current agent velocities
        rng: Random number generator for deterministic behavior
    """
    if not agents:
        return
        
    n_agents = len(agents)
    
    # Vectorized speed calculations
    speeds = np.linalg.norm(velocities, axis=1)
    energy_costs = speeds * ENERGY_COST_SPEED_FACTOR * dt
    
    # Vectorized crowding calculations
    for i in range(n_agents):
        agent = agents[i]
        
        # Update energy
        agent.update_energy(-energy_costs[i])
        
        # Check for food sources (keep individual for now, could be optimized further)
        food_source = environment.get_nearest_food(positions[i])
        if food_source is not None:
            energy_gained = food_source.consume(5.0 * dt)
            agent.update_energy(energy_gained)
        
        # Compute crowding stress efficiently
        position_diffs = positions - positions[i]
        distances = np.linalg.norm(position_diffs, axis=1)
        nearby_count = np.sum((distances < MIN_SEPARATION * 2) & (distances > 0))  # Exclude self
        
        crowding_stress = nearby_count * STRESS_CROWDING_FACTOR * dt
        risk_stress = environment.get_risk_at(positions[i]) * STRESS_RISK_FACTOR * dt
        
        agent.update_stress(crowding_stress + risk_stress - STRESS_DECAY_RATE * dt)
        
        # Decay social memory
        agent.decay_social_memory()
        
        # Check for agent death due to exhaustion
        if agent.energy <= 0.0:
            agent.alive = False


def integrate_physics(
    agents: List[Agent],
    environment: Environment,
    dt: Optional[float] = None,
    rng: Optional[RNG] = None,
) -> None:
    """Main physics integration step for all agents.
    
    This is the primary physics function that coordinates all force calculations,
    motion integration, and agent state updates for a single simulation step.
    Uses deterministic semi-implicit Euler integration at fixed timestep.
    
    Args:
        agents: List of agents to update physics for
        environment: Environment containing forces and constraints
        dt: Time step duration (defaults to FIXED_TIMESTEP for determinism)
        rng: Random number generator for deterministic physics calculations
        
    Performance:
        O(N²) complexity due to flocking force calculations where N is agent count.
        Optimized for handling 300 agents @ 60Hz on development hardware.
    """
    if dt is None:
        dt = FIXED_TIMESTEP
    
    if rng is None:
        rng = np.random.default_rng()
    
    if not agents:
        logger.debug("No agents to update physics for")
        return
    
    # Filter out dead agents for physics calculations
    alive_agents = [agent for agent in agents if agent.alive]
    if not alive_agents:
        return
    
    n_alive = len(alive_agents)
    
    # Extract positions and velocities for vectorized computation
    positions = np.array([agent.position for agent in alive_agents])
    velocities = np.array([agent.velocity for agent in alive_agents])
    
    # Pre-allocate acceleration array
    accelerations = np.zeros((n_alive, 2))
    
    # Compute forces for each agent (this is the O(N²) bottleneck)
    for i in range(n_alive):
        agent = alive_agents[i]
        
        # Apply flocking forces (separation, alignment, cohesion)
        flocking_force = apply_flocking_forces(positions, velocities, i, rng)
        
        # Apply beacon attraction forces
        beacon_force = apply_beacon_forces(positions[i], environment, rng)
        
        # Apply environmental forces (wind, risk avoidance)
        env_force = apply_environmental_forces(
            positions[i], velocities[i], environment, rng
        )
        
        # Combine all forces to get acceleration
        total_force = flocking_force + beacon_force + env_force
        
        # Limit acceleration magnitude for stability
        force_magnitude = np.linalg.norm(total_force)
        if force_magnitude > MAX_ACCELERATION:
            total_force = (total_force / force_magnitude) * MAX_ACCELERATION
        
        accelerations[i] = total_force
    
    # Vectorized integration for all agents
    new_velocities = velocities + accelerations * dt
    new_velocities *= DRAG_COEFFICIENT  # Apply drag
    
    # Apply speed limits vectorized
    speeds = np.linalg.norm(new_velocities, axis=1)
    speed_mask = speeds > MAX_SPEED
    if np.any(speed_mask):
        new_velocities[speed_mask] = (new_velocities[speed_mask].T / speeds[speed_mask] * MAX_SPEED).T
    
    # Update positions using new velocities
    new_positions = positions + new_velocities * dt
    
    # Apply boundary conditions to all agents
    for i in range(n_alive):
        new_positions[i], new_velocities[i] = apply_boundary_conditions(
            new_positions[i], new_velocities[i], environment
        )
    
    # Re-apply speed limits after boundary conditions (which can modify velocity)
    speeds = np.linalg.norm(new_velocities, axis=1)
    speed_mask = speeds > MAX_SPEED
    if np.any(speed_mask):
        new_velocities[speed_mask] = (new_velocities[speed_mask].T / speeds[speed_mask] * MAX_SPEED).T
    
    # Update agent states
    for i, agent in enumerate(alive_agents):
        agent.position = new_positions[i]
        agent.velocity = new_velocities[i]
    
    # Update energy and stress levels for all alive agents
    update_energy_stress(alive_agents, environment, dt, new_positions, new_velocities, rng)
    
    # Update environment state
    environment.update(dt)
    
    # Clean up depleted food sources
    environment.cleanup_depleted_food()
    
    # Update environment and cleanup (minimal logging for performance)
    environment.update(dt)
    environment.cleanup_depleted_food()


def compute_flock_cohesion(agents: List[Agent]) -> float:
    """Compute the cohesion metric for the entire flock.
    
    Cohesion is measured as the inverse of the average distance between agents,
    normalized to a [0, 1] range where 1 indicates perfect cohesion.
    This metric is used for scoring and analysis.
    
    Args:
        agents: List of agents to analyze (includes both alive and dead)
        
    Returns:
        Cohesion value between 0.0 and 1.0
        
    Performance:
        O(N²) where N is the number of alive agents
    """
    active_agents = [agent for agent in agents if agent.alive]
    
    if len(active_agents) < 2:
        logger.debug(
            "Computing cohesion with insufficient agents",
            extra={"active_agents": len(active_agents)}
        )
        return 1.0  # Perfect cohesion for single agent or no agents
    
    positions = np.array([agent.position for agent in active_agents])
    n_agents = len(positions)
    
    # Compute all pairwise distances efficiently
    total_distance = 0.0
    pair_count = 0
    
    for i in range(n_agents):
        for j in range(i + 1, n_agents):
            distance = np.linalg.norm(positions[i] - positions[j])
            total_distance += distance
            pair_count += 1
    
    if pair_count == 0:
        return 1.0
    
    # Average distance between agents
    avg_distance = total_distance / pair_count
    
    # Convert to cohesion metric (0 = spread out, 1 = tightly packed)
    # Use exponential decay to map distance to [0, 1] range
    cohesion = np.exp(-avg_distance / 30.0)  # 30.0 is the reference distance
    
    cohesion_value = float(np.clip(cohesion, 0.0, 1.0))
    
    logger.debug(
        "Computed flock cohesion",
        extra={
            "active_agents": n_agents,
            "avg_distance": avg_distance,
            "cohesion": cohesion_value
        }
    )
    
    return cohesion_value


def detect_flock_collapse(agents: List[Agent], threshold: float = 0.2) -> bool:
    """Detect if the flock has collapsed (lost cohesion).
    
    A collapsed flock indicates the agents have spread out too much
    and are no longer exhibiting coordinated behavior.
    
    Args:
        agents: List of agents to analyze
        threshold: Cohesion threshold below which collapse is detected
        
    Returns:
        True if flock has collapsed (cohesion below threshold)
    """
    cohesion = compute_flock_cohesion(agents)
    collapsed = cohesion < threshold
    
    if collapsed:
        logger.warning(
            "Flock collapse detected",
            extra={
                "cohesion": cohesion,
                "threshold": threshold,
                "active_agents": len([a for a in agents if a.alive])
            }
        )
    
    return collapsed