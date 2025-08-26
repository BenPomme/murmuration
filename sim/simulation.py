"""Main simulation engine integrating all Murmuration systems.

This module provides the high-level simulation interface that coordinates
physics, environment, hazards, beacons, and ML systems as specified in CLAUDE.md.
"""

import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path

import numpy as np

from .core.agent import Agent, create_agent
from .core.environment import Environment, create_test_environment
from .core.physics import integrate_physics, compute_flock_cohesion, detect_flock_collapse
from .core.types import AgentID, RNG
from .scoring import star_rating, LevelTargets, SimulationResult
from .utils.logging import get_logger

# Import optional systems
try:
    from .hazards.storms import StormSystem
    from .hazards.predators import PredatorSystem
    from .hazards.light_pollution import LightPollutionSystem
except ImportError:
    StormSystem = None
    PredatorSystem = None
    LightPollutionSystem = None

try:
    from .beacons.beacon import BeaconSystem
    from .beacons.pulse import PulseSystem
except ImportError:
    BeaconSystem = None
    PulseSystem = None

try:
    from .ml.policy import MLPPolicy, create_observation_vector
    from .ml.buffer import ExperienceBuffer, Experience
    from .ml.ppo import PPOTrainer
except ImportError:
    MLPPolicy = None
    ExperienceBuffer = None
    PPOTrainer = None
    create_observation_vector = None
    Experience = None


@dataclass
class SimulationConfig:
    """Configuration for a simulation run.
    
    Attributes:
        level: Level identifier (e.g., W1-1, W2-3)
        n_agents: Number of agents in the flock
        n_ticks: Total simulation ticks to run
        seed: Random seed for deterministic behavior
        fps_target: Target simulation FPS
        enable_hazards: Whether to enable hazard systems
        enable_beacons: Whether to enable beacon systems
        enable_ml: Whether to use ML-controlled agents
        record_events: Whether to record events for replay
        headless: Whether to run without visualization
    """
    level: str
    n_agents: int
    n_ticks: int
    seed: int
    fps_target: float = 60.0
    enable_hazards: bool = True
    enable_beacons: bool = True
    enable_ml: bool = True
    record_events: bool = False
    headless: bool = True


@dataclass
class SimulationState:
    """Current state of the simulation.
    
    Attributes:
        tick: Current simulation tick
        environment: Environment instance
        agents: List of all agents
        active_agents: List of currently active (alive) agents
        systems: Dictionary of active systems
        metrics: Current simulation metrics
    """
    tick: int
    environment: Environment
    agents: List[Agent]
    active_agents: List[Agent]
    systems: Dict[str, Any]
    metrics: Dict[str, float]


class SimulationEngine:
    """Main simulation engine coordinating all systems.
    
    This class manages the integration of physics, environment, hazards,
    beacons, and ML systems in a unified simulation loop.
    """
    
    def __init__(self, config: SimulationConfig) -> None:
        """Initialize the simulation engine.
        
        Args:
            config: Simulation configuration
        """
        self.config = config
        self.logger = get_logger()
        
        # Print seed for determinism tracking
        print(f"🎲 Simulation seed: {config.seed}")
        
        # Initialize RNGs for different systems
        main_rng = np.random.default_rng(config.seed)
        self.rng_physics = np.random.default_rng(main_rng.integers(0, 2**31))
        self.rng_hazards = np.random.default_rng(main_rng.integers(0, 2**31))
        self.rng_beacons = np.random.default_rng(main_rng.integers(0, 2**31))
        self.rng_ml = np.random.default_rng(main_rng.integers(0, 2**31))
        
        # Initialize environment
        self.environment = create_test_environment(main_rng)
        
        # Initialize agents
        self.agents = []
        for i in range(config.n_agents):
            agent = create_agent(AgentID(i), rng=self.rng_physics)
            self.agents.append(agent)
        
        # Initialize systems
        self.systems = self._initialize_systems()
        
        # Simulation state
        self.current_tick = 0
        self.start_time = 0.0
        self.events: List[Dict[str, Any]] = []
        
        # Metrics tracking
        self.cohesion_history: List[float] = []
        self.frame_times: List[float] = []
        self.arrivals = 0
        self.losses = 0
        self.protected_deaths = 0
        
        self.logger.info(
            "Simulation engine initialized",
            extra={
                "config": {
                    "level": config.level,
                    "n_agents": config.n_agents,
                    "n_ticks": config.n_ticks,
                    "seed": config.seed,
                },
                "systems_active": list(self.systems.keys()),
            }
        )
    
    def _initialize_systems(self) -> Dict[str, Any]:
        """Initialize all enabled systems.
        
        Returns:
            Dictionary of initialized systems
        """
        systems = {}
        
        # Initialize hazard systems
        if self.config.enable_hazards:
            if StormSystem is not None:
                try:
                    systems['storms'] = StormSystem(self.environment, self.rng_hazards)
                except Exception as e:
                    self.logger.warning(f"Failed to initialize storm system: {e}")
            
            if PredatorSystem is not None:
                try:
                    systems['predators'] = PredatorSystem(self.environment, self.rng_hazards)
                except Exception as e:
                    self.logger.warning(f"Failed to initialize predator system: {e}")
            
            if LightPollutionSystem is not None:
                try:
                    systems['light_pollution'] = LightPollutionSystem(self.environment, self.rng_hazards)
                except Exception as e:
                    self.logger.warning(f"Failed to initialize light pollution system: {e}")
        
        # Initialize beacon systems
        if self.config.enable_beacons:
            if BeaconSystem is not None:
                try:
                    systems['beacons'] = BeaconSystem(self.environment, self.rng_beacons)
                except Exception as e:
                    self.logger.warning(f"Failed to initialize beacon system: {e}")
            
            if PulseSystem is not None:
                try:
                    systems['pulses'] = PulseSystem(self.environment, self.rng_beacons)
                except Exception as e:
                    self.logger.warning(f"Failed to initialize pulse system: {e}")
        
        # Initialize ML systems
        if self.config.enable_ml and MLPPolicy is not None:
            try:
                policy = MLPPolicy(
                    observation_dim=32,
                    hidden_dim=64,
                    action_dim=2,
                    rng=self.rng_ml
                )
                systems['ml_policy'] = policy
                
                # Initialize experience buffer if available
                if ExperienceBuffer is not None:
                    systems['experience_buffer'] = ExperienceBuffer(
                        capacity=10000,
                        gamma=0.98,
                        gae_lambda=0.95
                    )
                
            except Exception as e:
                self.logger.warning(f"Failed to initialize ML systems: {e}")
        
        return systems
    
    def get_current_state(self) -> SimulationState:
        """Get the current simulation state.
        
        Returns:
            Current simulation state
        """
        active_agents = [agent for agent in self.agents if agent.alive]
        
        metrics = {
            'cohesion': compute_flock_cohesion(active_agents) if active_agents else 0.0,
            'population': len(active_agents),
            'arrivals': self.arrivals,
            'losses': self.losses,
            'protected_deaths': self.protected_deaths,
        }
        
        return SimulationState(
            tick=self.current_tick,
            environment=self.environment,
            agents=self.agents,
            active_agents=active_agents,
            systems=self.systems,
            metrics=metrics,
        )
    
    def step(self) -> SimulationState:
        """Execute one simulation step.
        
        Returns:
            Updated simulation state
        """
        frame_start = time.time()
        dt = 1.0 / 30.0  # 30 FPS physics timestep
        
        # Update hazard systems
        hazard_events = []
        total_hazard_risk = 0.0
        
        for system_name, system in self.systems.items():
            if system_name in ['storms', 'predators', 'light_pollution']:
                try:
                    events = system.update(dt, self.agents)
                    hazard_events.extend(events)
                    total_hazard_risk += system.get_current_risk()
                except (AttributeError, Exception) as e:
                    self.logger.debug(f"System {system_name} update failed: {e}")
        
        # Update beacon systems
        beacon_events = []
        for system_name, system in self.systems.items():
            if system_name in ['beacons', 'pulses']:
                try:
                    events = system.update(dt)
                    beacon_events.extend(events)
                except (AttributeError, Exception) as e:
                    self.logger.debug(f"System {system_name} update failed: {e}")
        
        # Apply ML policy actions if available
        if 'ml_policy' in self.systems and self.current_tick % 10 == 0:
            self._apply_ml_actions(total_hazard_risk)
        
        # Update physics
        active_agents = [agent for agent in self.agents if agent.alive]
        if active_agents:
            integrate_physics(active_agents, self.environment, dt, self.rng_physics)
        
        # Update environment
        self.environment.update(dt)
        
        # Process agent state changes
        new_arrivals, new_losses, new_protected_deaths = self._process_agent_states()
        
        # Update metrics
        cohesion = compute_flock_cohesion(active_agents) if active_agents else 0.0
        self.cohesion_history.append(cohesion)
        
        # Record events if enabled
        if self.config.record_events:
            self._record_events(hazard_events, beacon_events, cohesion, total_hazard_risk)
        
        # Update timing
        frame_time = time.time() - frame_start
        self.frame_times.append(frame_time)
        self.current_tick += 1
        
        return self.get_current_state()
    
    def _apply_ml_actions(self, total_hazard_risk: float) -> None:
        """Apply ML policy actions to agents.
        
        Args:
            total_hazard_risk: Current total hazard risk level
        """
        policy = self.systems.get('ml_policy')
        experience_buffer = self.systems.get('experience_buffer')
        
        if not policy or not create_observation_vector:
            return
        
        active_agents = [agent for agent in self.agents if agent.alive]
        
        for agent in active_agents:
            try:
                # Create observation for agent
                obs = create_observation_vector(
                    agent_velocity=agent.velocity,
                    raycast_distances=np.ones(8) * 30.0,  # Simplified raycast
                    neighbor_count=min(len(active_agents) - 1, 10),
                    neighbor_avg_distance=15.0,  # Simplified
                    neighbor_cohesion=compute_flock_cohesion(active_agents),
                    signal_gradient_x=self.environment.get_beacon_influence(agent.position)[0],
                    signal_gradient_y=self.environment.get_beacon_influence(agent.position)[1],
                    time_of_day=(self.current_tick / (30 * 60 * 24)) % 1.0,
                    energy_level=agent.energy / 100.0,
                    social_stress=agent.stress,
                    risk_level=min(total_hazard_risk, 1.0),
                )
                
                # Get action from policy
                action, value, log_prob, _ = policy.get_action_and_value(obs)
                
                # Apply action as influence on velocity
                agent.velocity += action * 0.1
                
                # Store experience if buffer is available
                if experience_buffer and Experience:
                    # Calculate reward (simplified)
                    reward = self._calculate_agent_reward(agent, total_hazard_risk)
                    
                    experience = Experience(
                        observation=obs,
                        action=action,
                        reward=reward,
                        value=value,
                        log_prob=log_prob,
                        done=not agent.alive,
                    )
                    
                    experience_buffer.add(experience)
                
            except Exception as e:
                self.logger.debug(f"ML action application failed for agent {agent.id}: {e}")
    
    def _calculate_agent_reward(self, agent: Agent, hazard_risk: float) -> float:
        """Calculate reward for an individual agent.
        
        Args:
            agent: Agent to calculate reward for
            hazard_risk: Current hazard risk level
            
        Returns:
            Reward value for the agent
        """
        # Base survival reward
        reward = 0.1 if agent.alive else -1.0
        
        # Energy efficiency
        reward += (agent.energy / 100.0) * 0.05
        
        # Progress toward goal (eastward movement)
        if agent.position[0] > 50:  # Past halfway point
            reward += 0.1
        
        # Penalty for high risk exposure
        local_risk = self.environment.get_risk_at(agent.position)
        reward -= (local_risk + hazard_risk) * 0.05
        
        # Social cohesion bonus (simplified)
        reward += min(agent.stress, 0.5) * 0.02  # Lower stress is better
        
        return reward
    
    def _process_agent_states(self) -> tuple[int, int, int]:
        """Process agent state changes (arrivals, losses, etc.).
        
        Returns:
            Tuple of (new_arrivals, new_losses, new_protected_deaths)
        """
        new_arrivals = 0
        new_losses = 0
        new_protected_deaths = 0
        
        for agent in [a for a in self.agents if a.alive]:
            # Check for arrival
            if agent.position[0] >= self.environment.width - 5:
                self.arrivals += 1
                new_arrivals += 1
                agent.alive = False
                
                if self.config.record_events:
                    self.events.append({
                        't': self.current_tick,
                        'evt': 'arrival',
                        'level': self.config.level,
                        'seed': self.config.seed,
                        'agent_id': int(agent.id),
                        'final_energy': agent.energy,
                    })
            
            # Check for energy loss
            elif agent.energy <= 0:
                self.losses += 1
                new_losses += 1
                agent.alive = False
                
                if self.config.record_events:
                    self.events.append({
                        't': self.current_tick,
                        'evt': 'energy_loss',
                        'level': self.config.level,
                        'seed': self.config.seed,
                        'agent_id': int(agent.id),
                    })
            
            # Check for flock collapse
            elif detect_flock_collapse([agent]):
                self.losses += 1
                new_losses += 1
                agent.alive = False
                
                if self.config.record_events:
                    self.events.append({
                        't': self.current_tick,
                        'evt': 'flock_collapse',
                        'level': self.config.level,
                        'seed': self.config.seed,
                        'agent_id': int(agent.id),
                    })
        
        return new_arrivals, new_losses, new_protected_deaths
    
    def _record_events(
        self,
        hazard_events: List[Dict[str, Any]],
        beacon_events: List[Dict[str, Any]],
        cohesion: float,
        hazard_risk: float,
    ) -> None:
        """Record events for replay and analysis.
        
        Args:
            hazard_events: Events from hazard systems
            beacon_events: Events from beacon systems
            cohesion: Current cohesion value
            hazard_risk: Current hazard risk level
        """
        # Record tick event every second
        if self.current_tick % 60 == 0:
            active_agents = [agent for agent in self.agents if agent.alive]
            
            tick_event = {
                't': self.current_tick,
                'evt': 'tick',
                'level': self.config.level,
                'seed': self.config.seed,
                'C': cohesion,
                'pop': len(active_agents),
                'arrivals': self.arrivals,
                'losses': self.losses,
                'protected_deaths': self.protected_deaths,
                'beacons_active': len([b for b in self.environment.beacons if b.active]),
                'haz_risk_local': hazard_risk,
                'reward': self._calculate_collective_reward(active_agents, hazard_risk),
            }
            self.events.append(tick_event)
        
        # Add system events
        for event in hazard_events + beacon_events:
            event.update({
                't': self.current_tick,
                'level': self.config.level,
                'seed': self.config.seed,
            })
            self.events.append(event)
    
    def _calculate_collective_reward(self, agents: List[Agent], hazard_risk: float) -> float:
        """Calculate collective reward for the entire flock.
        
        Args:
            agents: List of active agents
            hazard_risk: Current hazard risk level
            
        Returns:
            Collective reward value
        """
        if not agents:
            return 0.0
        
        # Base cohesion reward
        cohesion = compute_flock_cohesion(agents)
        cohesion_reward = cohesion * 0.1
        
        # Progress reward
        avg_x = np.mean([agent.position[0] for agent in agents])
        progress_reward = (avg_x / self.environment.width) * 0.05
        
        # Energy efficiency
        avg_energy = np.mean([agent.energy for agent in agents])
        energy_reward = (avg_energy / 100.0) * 0.02
        
        # Risk penalty
        risk_penalty = -hazard_risk * 0.03
        
        return cohesion_reward + progress_reward + energy_reward + risk_penalty
    
    def run(self, progress_callback: Optional[Callable[[SimulationState], None]] = None) -> SimulationResult:
        """Run the complete simulation.
        
        Args:
            progress_callback: Optional callback for progress updates
            
        Returns:
            Final simulation result
        """
        self.start_time = time.time()
        target_frame_time = 1.0 / self.config.fps_target
        
        self.logger.info("Starting simulation run")
        
        # Main simulation loop
        while self.current_tick < self.config.n_ticks:
            # Execute simulation step
            state = self.step()
            
            # Check for early termination
            if not state.active_agents:
                self.logger.info("All agents lost or arrived, terminating early")
                break
            
            # Progress callback
            if progress_callback:
                progress_callback(state)
            
            # Progress logging
            if self.current_tick % 1800 == 0 and self.current_tick > 0:
                self._log_progress(state)
            
            # FPS limiting
            if not self.config.headless:
                frame_time = self.frame_times[-1] if self.frame_times else 0.0
                if frame_time < target_frame_time:
                    time.sleep(target_frame_time - frame_time)
        
        # Generate final results
        return self._generate_final_result()
    
    def _log_progress(self, state: SimulationState) -> None:
        """Log simulation progress.
        
        Args:
            state: Current simulation state
        """
        progress = (self.current_tick / self.config.n_ticks) * 100
        current_fps = 1.0 / np.mean(self.frame_times[-60:]) if len(self.frame_times) >= 60 else 0.0
        
        self.logger.info(
            "Simulation progress",
            extra={
                "tick": self.current_tick,
                "progress": f"{progress:.1f}%",
                "active_agents": len(state.active_agents),
                "cohesion": state.metrics['cohesion'],
                "arrivals": self.arrivals,
                "losses": self.losses,
                "protected_deaths": self.protected_deaths,
                "current_fps": current_fps,
            }
        )
    
    def _generate_final_result(self) -> SimulationResult:
        """Generate the final simulation result.
        
        Returns:
            Complete simulation result
        """
        # Calculate metrics
        wall_time = time.time() - self.start_time
        avg_fps = len(self.frame_times) / sum(self.frame_times) if self.frame_times else 0.0
        cohesion_avg = float(np.mean(self.cohesion_history)) if self.cohesion_history else 0.0
        
        # Create simulation result for star rating
        beacons_used = len([b for b in self.environment.beacons if not b.active])
        days_used = self.current_tick / (30 * 60 * 24)  # Convert ticks to days
        
        result = SimulationResult(
            met_all_targets=True,  # Will be validated by star rating
            days_used=days_used,
            arrivals=self.arrivals,
            cohesion_avg=cohesion_avg,
            beacons_used=beacons_used,
            losses=self.losses,
            protected_deaths=self.protected_deaths,
        )
        
        # Performance check
        if avg_fps < self.config.fps_target:
            self.logger.warning(
                f"Performance below target: {avg_fps:.1f} FPS < {self.config.fps_target} FPS",
                extra={"target_fps": self.config.fps_target, "actual_fps": avg_fps}
            )
        
        self.logger.info(
            "Simulation completed",
            extra={
                "final_tick": self.current_tick,
                "wall_time": wall_time,
                "avg_fps": avg_fps,
                "arrivals": self.arrivals,
                "losses": self.losses,
                "protected_deaths": self.protected_deaths,
                "cohesion_avg": cohesion_avg,
            }
        )
        
        return result
    
    def save_events(self, file_path: str) -> None:
        """Save recorded events to a JSONL file.
        
        Args:
            file_path: Path to save events to
        """
        if not self.config.record_events:
            self.logger.warning("Events not recorded, cannot save")
            return
        
        output_path = Path(file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for event in self.events:
                f.write(json.dumps(event) + '\\n')
            
            # Write final metadata
            metadata = {
                'evt': 'simulation_end',
                't': self.current_tick,
                'level': self.config.level,
                'seed': self.config.seed,
                'final_arrivals': self.arrivals,
                'final_losses': self.losses,
                'final_protected_deaths': self.protected_deaths,
            }
            f.write(json.dumps(metadata) + '\\n')
        
        self.logger.info(f"Events saved to {output_path}")


def create_simulation(
    level: str,
    n_agents: int,
    n_ticks: int,
    seed: int,
    **kwargs
) -> SimulationEngine:
    """Create a simulation engine with the specified parameters.
    
    Args:
        level: Level identifier
        n_agents: Number of agents
        n_ticks: Number of ticks to run
        seed: Random seed
        **kwargs: Additional configuration options
        
    Returns:
        Configured simulation engine
    """
    config = SimulationConfig(
        level=level,
        n_agents=n_agents,
        n_ticks=n_ticks,
        seed=seed,
        **kwargs
    )
    
    return SimulationEngine(config)