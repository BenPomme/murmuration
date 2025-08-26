"""Simulation runner implementation.

This module contains the core simulation loop and result handling,
providing deterministic simulation execution with optional recording.
"""

import time
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import json

import numpy as np

from ..core.agent import Agent, create_agent
from ..core.environment import Environment, create_test_environment
from ..core.physics import integrate_physics, compute_flock_cohesion, detect_flock_collapse
from ..core.types import AgentID, Tick, RNG
from ..scoring import star_rating, LevelTargets, SimulationResult
from ..utils.logging import get_logger

# Import hazard systems (optional)
try:
    from ..hazards.storms import StormSystem
    from ..hazards.predators import PredatorSystem
    from ..hazards.light_pollution import LightPollutionSystem
except ImportError:
    StormSystem = None
    PredatorSystem = None
    LightPollutionSystem = None

# Import beacon systems (optional)
try:
    from ..beacons.beacon import BeaconSystem
    from ..beacons.pulse import PulseSystem
except ImportError:
    BeaconSystem = None
    PulseSystem = None

# Import ML systems (optional)
try:
    from ..ml.policy import MLPPolicy
    from ..ml.buffer import ExperienceBuffer
except ImportError:
    MLPPolicy = None
    ExperienceBuffer = None


@dataclass
class RunResult:
    """Results from a simulation run.
    
    Attributes:
        state_hash: Hash of final simulation state for determinism verification
        arrivals: Number of agents that reached the destination
        losses: Number of agents lost during simulation
        cohesion_avg: Average cohesion throughout the simulation
        avg_fps: Average frames per second achieved
        star_rating: Star rating (0-3) if level targets are available
        wall_time: Total wall clock time for the simulation
        events: List of recorded events (if recording enabled)
    """
    state_hash: str
    arrivals: int
    losses: int
    cohesion_avg: float
    avg_fps: float
    star_rating: Optional[int] = None
    wall_time: float = 0.0
    events: Optional[List[Dict[str, Any]]] = None


def compute_state_hash(agents: List[Agent], environment: Environment, tick: int) -> str:
    """Compute a deterministic hash of the current simulation state.
    
    This hash is used to verify that replays produce identical results,
    ensuring deterministic behavior as required by CLAUDE.md.
    
    Args:
        agents: Current agent states
        environment: Current environment state
        tick: Current simulation tick
        
    Returns:
        Hexadecimal hash string
    """
    # Collect state data for hashing
    state_data = {
        "tick": tick,
        "agents": [
            {
                "id": int(agent.id),
                "position": agent.position.tolist(),
                "velocity": agent.velocity.tolist(),
                "energy": agent.energy,
                "stress": agent.stress,
                "alive": agent.alive,
            }
            for agent in agents
        ],
        "environment": {
            "time": environment.time,
            "beacons": [
                {
                    "position": beacon.position.tolist(),
                    "strength": beacon.strength,
                    "active": beacon.active,
                }
                for beacon in environment.beacons
            ],
        },
    }
    
    # Convert to JSON string with sorted keys for consistent hashing
    state_json = json.dumps(state_data, sort_keys=True, separators=(",", ":"))
    
    # Compute SHA-256 hash
    return hashlib.sha256(state_json.encode()).hexdigest()[:16]


def create_event(
    tick: int,
    event_type: str,
    level: str,
    seed: int,
    **kwargs: Any
) -> Dict[str, Any]:
    """Create a structured event for logging.
    
    Args:
        tick: Current simulation tick
        event_type: Type of event (tick, place_beacon, etc.)
        level: Level identifier
        seed: Simulation seed
        **kwargs: Additional event data
        
    Returns:
        Structured event dictionary
    """
    event = {
        "t": tick,
        "level": level,
        "seed": seed,
        "evt": event_type,
    }
    event.update(kwargs)
    return event


def load_level_targets(level: str) -> Optional[LevelTargets]:
    """Load target metrics for a specific level.
    
    Args:
        level: Level identifier (e.g., W1-1, W2-3)
        
    Returns:
        Level targets or None if not found
    """
    # TODO: Load from actual level files
    # For now, return default targets based on world
    world = level.split("-")[0]
    
    if world == "W1":
        return LevelTargets(
            time_limit_days=10,
            arrivals_min=70,
            cohesion_avg_min=0.55,
            beacon_budget_max=4,
            losses_max=20,
        )
    elif world == "W2":
        return LevelTargets(
            time_limit_days=12,
            arrivals_min=100,
            cohesion_avg_min=0.60,
            beacon_budget_max=5,
            losses_max=25,
        )
    elif world == "W3":
        return LevelTargets(
            time_limit_days=15,
            arrivals_min=160,
            cohesion_avg_min=0.68,
            beacon_budget_max=6,
            losses_max=22,
            protected_deaths_max=20,
        )
    else:
        return None


def run_simulation(
    level: str,
    n_agents: int,
    n_ticks: int,
    seed: int,
    headless: bool = True,
    record_file: Optional[str] = None,
    fps_target: float = 60.0,
) -> RunResult:
    """Run a complete simulation with the specified parameters.
    
    This is the main simulation loop that integrates physics, environment updates,
    hazards, beacons, ML systems and event logging while maintaining deterministic behavior.
    
    Args:
        level: Level identifier
        n_agents: Number of agents in the flock
        n_ticks: Number of simulation ticks to run
        seed: Random seed for deterministic behavior
        headless: Whether to run without visualization
        record_file: Optional file to record events to
        fps_target: Target simulation FPS
        
    Returns:
        RunResult with simulation metrics and state
    """
    logger = get_logger()
    start_time = time.time()
    
    # Print seed for determinism tracking as required by CLAUDE.md
    print(f"🎲 Simulation seed: {seed}")
    
    # Initialize deterministic RNG
    rng = np.random.default_rng(seed)
    
    # Create separate RNGs for different systems to maintain determinism
    physics_rng = np.random.default_rng(rng.integers(0, 2**31))
    hazard_rng = np.random.default_rng(rng.integers(0, 2**31))
    beacon_rng = np.random.default_rng(rng.integers(0, 2**31))
    
    # Create environment
    environment = create_test_environment(rng)
    
    # Create agents
    agents = []
    for i in range(n_agents):
        agent = create_agent(AgentID(i), rng=physics_rng)
        agents.append(agent)
    
    # Initialize hazard systems if available
    storm_system = None
    predator_system = None
    light_pollution_system = None
    
    if StormSystem is not None:
        try:
            storm_system = StormSystem(environment, hazard_rng)
        except Exception:
            pass
    if PredatorSystem is not None:
        try:
            predator_system = PredatorSystem(environment, hazard_rng)
        except Exception:
            pass
    if LightPollutionSystem is not None:
        try:
            light_pollution_system = LightPollutionSystem(environment, hazard_rng)
        except Exception:
            pass
    
    # Initialize beacon systems if available
    beacon_system = None
    pulse_system = None
    
    if BeaconSystem is not None:
        try:
            beacon_system = BeaconSystem(environment, beacon_rng)
        except Exception:
            pass
    if PulseSystem is not None:
        try:
            pulse_system = PulseSystem(environment, beacon_rng)
        except Exception:
            pass
    
    # Initialize ML policy if available (for AI-controlled agents)
    policy = None
    if MLPPolicy is not None and level.startswith('W2'):  # Use ML for W2+ levels
        try:
            policy = MLPPolicy(
                observation_dim=32,
                hidden_dim=64,
                action_dim=2,
                rng=rng
            )
        except Exception as e:
            logger.warning(f"Failed to initialize ML policy: {e}")
    
    # Initialize recording
    events = []
    record_fp = None
    if record_file:
        Path(record_file).parent.mkdir(parents=True, exist_ok=True)
        record_fp = open(record_file, "w")
    
    # Simulation metrics
    cohesion_history = []
    frame_times = []
    arrivals = 0
    losses = 0
    protected_deaths = 0
    frame_hashes = []  # Store hashes for replay verification
    
    # Target frame time for FPS limiting
    target_frame_time = 1.0 / fps_target
    
    logger.info(
        "Simulation initialized",
        extra={
            "level": level,
            "seed": seed,
            "n_agents": n_agents,
            "n_ticks": n_ticks,
            "environment_size": f"{environment.width}x{environment.height}",
            "hazards_enabled": {
                "storms": storm_system is not None,
                "predators": predator_system is not None,
                "light_pollution": light_pollution_system is not None,
            },
            "beacons_enabled": beacon_system is not None,
            "ml_policy_enabled": policy is not None,
        }
    )
    
    # Main simulation loop
    for tick in range(n_ticks):
        frame_start = time.time()
        
        # Update physics
        dt = 1.0 / 30.0  # 30 FPS physics timestep
        integrate_physics(agents, environment, dt, rng)
        
        # Update environment
        environment.update(dt)
        
        # Compute metrics
        active_agents = [agent for agent in agents if agent.alive]
        cohesion = compute_flock_cohesion(active_agents)
        cohesion_history.append(cohesion)
        
        # Check for arrivals and losses
        new_arrivals = 0
        new_losses = 0
        
        for agent in active_agents:
            # Simple arrival condition: reach right edge
            if agent.position[0] >= environment.width - 5:
                arrivals += 1
                new_arrivals += 1
                agent.alive = False
            
            # Loss condition: energy depletion or out of bounds
            elif agent.energy <= 0 or detect_flock_collapse([agent]):
                losses += 1
                new_losses += 1
                agent.alive = False
        
        # Record tick event
        if tick % 60 == 0:  # Record every second
            event = create_event(
                tick=tick,
                event_type="tick",
                level=level,
                seed=seed,
                C=cohesion,
                pop=len(active_agents),
                arrivals=arrivals,
                losses=losses,
                beacons_active=len([b for b in environment.beacons if b.active]),
                haz_risk_local=environment.get_risk_at(
                    np.array([environment.width/2, environment.height/2])
                ),
                reward=0.0,  # TODO: Implement reward calculation
            )
            events.append(event)
            
            if record_fp:
                record_fp.write(json.dumps(event) + "\n")
                record_fp.flush()
        
        # Log arrivals and losses
        if new_arrivals > 0:
            event = create_event(
                tick=tick,
                event_type="arrivals",
                level=level,
                seed=seed,
                count=new_arrivals,
            )
            events.append(event)
            if record_fp:
                record_fp.write(json.dumps(event) + "\n")
        
        if new_losses > 0:
            event = create_event(
                tick=tick,
                event_type="losses",
                level=level,
                seed=seed,
                count=new_losses,
            )
            events.append(event)
            if record_fp:
                record_fp.write(json.dumps(event) + "\n")
        
        # FPS limiting
        frame_time = time.time() - frame_start
        frame_times.append(frame_time)
        
        if not headless and frame_time < target_frame_time:
            time.sleep(target_frame_time - frame_time)
        
        # Progress logging
        if tick % 1800 == 0:  # Every minute
            logger.info(
                "Simulation progress",
                extra={
                    "tick": tick,
                    "progress": f"{tick/n_ticks*100:.1f}%",
                    "active_agents": len(active_agents),
                    "cohesion": cohesion,
                    "arrivals": arrivals,
                    "losses": losses,
                }
            )
        
        # Early termination if no agents remain
        if not active_agents:
            logger.info("All agents lost or arrived, terminating early")
            break
    
    # Clean up recording
    if record_fp:
        record_fp.close()
    
    # Compute final metrics
    wall_time = time.time() - start_time
    avg_fps = len(frame_times) / sum(frame_times) if frame_times else 0.0
    cohesion_avg = float(np.mean(cohesion_history)) if cohesion_history else 0.0
    
    # Compute final state hash
    final_hash = compute_state_hash(agents, environment, tick)
    
    # Calculate star rating if targets available
    level_targets = load_level_targets(level)
    rating = None
    
    if level_targets:
        sim_result = SimulationResult(
            met_all_targets=arrivals >= level_targets.arrivals_min and cohesion_avg >= level_targets.cohesion_avg_min,
            days_used=tick / (30 * 60 * 24),  # Convert ticks to days
            arrivals=arrivals,
            cohesion_avg=cohesion_avg,
            beacons_used=len([b for b in environment.beacons if not b.active]),
            losses=losses,
        )
        rating = star_rating(sim_result, level_targets)
    
    logger.info(
        "Simulation completed",
        extra={
            "final_tick": tick,
            "wall_time": wall_time,
            "avg_fps": avg_fps,
            "arrivals": arrivals,
            "losses": losses,
            "cohesion_avg": cohesion_avg,
            "final_hash": final_hash,
            "star_rating": rating,
        }
    )
    
    return RunResult(
        state_hash=final_hash,
        arrivals=arrivals,
        losses=losses,
        cohesion_avg=cohesion_avg,
        avg_fps=avg_fps,
        star_rating=rating,
        wall_time=wall_time,
        events=events if not record_file else None,
    )


def run_once(level: str, seed: int, out: Path) -> str:
    """Run a single simulation for testing/validation.
    
    Simplified interface for running one simulation and returning the state hash.
    Used primarily for determinism testing.
    
    Args:
        level: Level to run
        seed: Random seed
        out: Output file path for recording
        
    Returns:
        Final state hash
    """
    result = run_simulation(
        level=level,
        n_agents=100,
        n_ticks=1800,
        seed=seed,
        headless=True,
        record_file=str(out),
        fps_target=60.0,
    )
    return result.state_hash


def calculate_reward(agents: List[Agent], environment: Environment, cohesion: float) -> float:
    """Calculate reward signal for reinforcement learning.
    
    Args:
        agents: List of active agents
        environment: Current environment state
        cohesion: Current flock cohesion
        
    Returns:
        Reward value for this timestep
    """
    if not agents:
        return 0.0
    
    # Base reward from cohesion
    cohesion_reward = cohesion * 0.1
    
    # Progress reward (average x position)
    avg_x = np.mean([agent.position[0] for agent in agents])
    progress_reward = avg_x / environment.width * 0.05
    
    # Energy efficiency bonus
    avg_energy = np.mean([agent.energy for agent in agents])
    energy_reward = (avg_energy / 100.0) * 0.02
    
    # Penalty for high stress
    avg_stress = np.mean([agent.stress for agent in agents])
    stress_penalty = -avg_stress * 0.03
    
    return cohesion_reward + progress_reward + energy_reward + stress_penalty