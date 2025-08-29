"""Clean path-following simulation for Murmuration.

Birds ONLY follow the path drawn by the player.
No pre-defined trajectories, no evolved simulation complexity.
"""

import time
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .core.agent import Agent, create_agent
from .core.types import AgentID
from .utils.logging import get_logger

logger = get_logger("path_simulation")


@dataclass
class PathSimConfig:
    """Simple configuration for path-based simulation."""
    n_agents: int = 100
    seed: int = 42
    
    # Start and destination zones - birds always start from middle-left
    start_zone: Tuple[float, float, float] = (150, 600, 80)  # x, y, radius - middle left
    destination_zone: Tuple[float, float, float] = (1850, 600, 100)  # x, y, radius - middle right
    
    # Current leg info
    current_leg: int = 1
    total_legs: int = 4
    leg_name: str = "Migration Leg 1"


class PathSimulation:
    """Clean simulation where birds ONLY follow the drawn path."""
    
    def __init__(self, config: PathSimConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        
        # Birds
        self.agents: List[Agent] = []
        self.next_id = 0
        
        # Path from player
        self.migration_path: List[List[float]] = []
        self.path_progress: Dict[AgentID, int] = {}  # Which waypoint each bird is targeting
        
        # Gender assignment (50/50 split)
        self.genders: Dict[AgentID, str] = {}  # 'male' or 'female'
        
        # Leadership (first 5 birds are leaders)
        self.leader_count = 5
        self.is_leader: Dict[AgentID, bool] = {}
        
        # Hazards (randomly placed)
        self.hazards: List[Dict[str, Any]] = []
        self._spawn_hazards()
        
        # Game state
        self.tick = 0
        self.start_time = time.time()
        self.arrivals = 0
        self.losses = 0
        self.game_over = False
        self.victory = False
        self.paused = False
        
        # Create initial population
        self._spawn_birds()
        
        logger.info(f"Path simulation initialized: {config.n_agents} birds, Leg {config.current_leg}/{config.total_legs}")
    
    def _spawn_hazards(self):
        """Spawn random hazards in the middle area."""
        # Spawn 2-4 hazards randomly in the middle zone
        num_hazards = self.rng.integers(2, 5)
        
        for i in range(num_hazards):
            hazard_type = self.rng.choice(['storm', 'predator'])
            
            # Place hazards in middle 60% of map, away from start/end
            x = self.rng.uniform(400, 1600)
            y = self.rng.uniform(200, 1000)
            
            hazard = {
                'type': hazard_type,
                'x': float(x),
                'y': float(y),
                'radius': 150.0 if hazard_type == 'storm' else 100.0,
                'id': f"hazard_{i}"
            }
            
            # Predators can move
            if hazard_type == 'predator':
                hazard['vx'] = self.rng.uniform(-20, 20)
                hazard['vy'] = self.rng.uniform(-20, 20)
            
            self.hazards.append(hazard)
        
        logger.info(f"Spawned {len(self.hazards)} hazards")
    
    def _spawn_birds(self):
        """Spawn birds in the start zone."""
        start_x, start_y, start_radius = self.config.start_zone
        
        for i in range(self.config.n_agents):
            bird_id = AgentID(self.next_id)
            self.next_id += 1
            
            agent = create_agent(bird_id, rng=self.rng)
            
            # Assign gender (50/50 split)
            self.genders[bird_id] = 'male' if i < self.config.n_agents // 2 else 'female'
            
            # Designate leaders (first few birds)
            self.is_leader[bird_id] = i < self.leader_count
            
            # Spawn birds in a tighter cluster for better initial cohesion
            # Leaders spawn closer to center, followers around them
            if self.is_leader[bird_id]:
                # Leaders spawn in inner 30% of start zone
                angle = self.rng.uniform(0, 2 * np.pi)
                radius = self.rng.uniform(0, start_radius * 0.3)
            else:
                # Followers spawn in 20-60% of start zone (around leaders)
                angle = self.rng.uniform(0, 2 * np.pi)
                radius = self.rng.uniform(start_radius * 0.2, start_radius * 0.6)
            
            agent.position = np.array([
                start_x + radius * np.cos(angle),
                start_y + radius * np.sin(angle)
            ], dtype=np.float32)
            
            # Initial velocity toward destination for cohesion
            # Start with velocity pointing toward destination
            dest_x, dest_y, _ = self.config.destination_zone
            to_dest = np.array([dest_x - start_x, dest_y - start_y])
            to_dest_norm = to_dest / (np.linalg.norm(to_dest) + 0.01)
            
            # All birds start with similar direction toward destination
            base_velocity = to_dest_norm * 80.0  # Good initial speed
            # Add small random variation
            agent.velocity = base_velocity + np.array([
                self.rng.uniform(-15, 15),
                self.rng.uniform(-15, 15)
            ], dtype=np.float32)
            
            # Full energy
            agent.energy = 100.0
            agent.stress = 0.0
            agent.alive = True
            
            self.agents.append(agent)
            self.path_progress[bird_id] = 0  # Start at first waypoint
    
    def set_path(self, path: List[Dict[str, float]]):
        """Set the migration path from the player."""
        self.migration_path = [[p['x'], p['y']] for p in path]
        # Reset all birds to target first waypoint
        for agent in self.agents:
            self.path_progress[agent.id] = 0
        logger.info(f"Path set with {len(self.migration_path)} waypoints")
    
    def step(self) -> Dict[str, Any]:
        """Execute one simulation step."""
        if self.paused or self.game_over:
            return self.get_state()
        
        self.tick += 1
        dt = 1.0 / 30.0  # 30 FPS
        
        # Update predator positions
        for hazard in self.hazards:
            if hazard['type'] == 'predator':
                hazard['x'] += hazard.get('vx', 0) * dt
                hazard['y'] += hazard.get('vy', 0) * dt
                
                # Bounce off boundaries
                if hazard['x'] < 100 or hazard['x'] > 1900:
                    hazard['vx'] = -hazard.get('vx', 0)
                if hazard['y'] < 100 or hazard['y'] > 1100:
                    hazard['vy'] = -hazard.get('vy', 0)
        
        alive_birds = []
        
        for agent in self.agents:
            if not agent.alive:
                continue
            
            # Calculate stress from various sources
            self._update_stress(agent, dt)
            
            # All birds follow the path (leaders strongly, followers weakly)
            self._follow_path(agent, dt)
            
            # All birds use flocking (leaders and followers)
            self._apply_flocking(agent, dt)
            
            # Update position
            agent.position += agent.velocity * dt
            
            # Speed adjustment based on stress (stress makes birds fly faster)
            speed = np.linalg.norm(agent.velocity)
            stress_speed_multiplier = 1.0 + (agent.stress / 100.0)  # 10% faster per 10% stress
            max_speed = 150.0 * stress_speed_multiplier  # Base max speed adjusted by stress
            
            # Enforce minimum speed for all birds to prevent stopping
            min_speed = 50.0 if self.is_leader.get(agent.id, False) else 30.0
            if speed < min_speed:
                # If too slow, add forward momentum
                if speed > 0.1:
                    agent.velocity = (agent.velocity / speed) * min_speed
                else:
                    # If completely stopped, push toward destination
                    dest_x, dest_y, _ = self.config.destination_zone
                    to_dest = np.array([dest_x - agent.position[0], dest_y - agent.position[1]])
                    agent.velocity = (to_dest / (np.linalg.norm(to_dest) + 0.01)) * min_speed
            
            # Cap maximum speed to prevent 10x flyaway
            MAX_SPEED = 100.0  # Hard cap to prevent crazy speeds
            if speed > MAX_SPEED:
                agent.velocity = (agent.velocity / (speed + 0.001)) * MAX_SPEED
            
            # World boundaries
            agent.position[0] = np.clip(agent.position[0], 0, 2000)
            agent.position[1] = np.clip(agent.position[1], 0, 1200)
            
            # Energy consumption based on distance and time
            # Distance-based: proportional to speed (5x faster than before)
            distance_energy_loss = (speed / 100.0) * 0.5 * dt  # 0.5% per 100 units/s
            
            # Time-based: 1% every 4 seconds (0.25% per second)
            time_energy_loss = 0.25 * dt
            
            # Stress multiplier: stress increases energy consumption
            # At 20% stress, energy depletes 20% faster
            stress_multiplier = 1.0 + (agent.stress / 100.0)
            
            # Total energy loss with stress factor
            total_energy_loss = (distance_energy_loss + time_energy_loss) * stress_multiplier
            agent.energy = max(0, agent.energy - total_energy_loss)
            
            if agent.energy <= 0:
                agent.alive = False
                self.losses += 1
                logger.info(f"Bird {agent.id} exhausted after {self.tick} ticks")
                continue
            
            # Check arrival
            dest_x, dest_y, dest_r = self.config.destination_zone
            dist_to_dest = np.linalg.norm(agent.position - np.array([dest_x, dest_y]))
            
            if dist_to_dest < dest_r:
                self.arrivals += 1
                agent.alive = False  # Remove from simulation
                logger.info(f"Bird {agent.id} arrived! Total: {self.arrivals}")
                continue
            
            alive_birds.append(agent)
        
        # Check victory conditions - let level end naturally
        if len(alive_birds) == 0:
            if self.arrivals > 0:
                self.victory = True
                self.game_over = True
                logger.info(f"VICTORY! {self.arrivals} birds completed the leg")
            else:
                self.game_over = True
                logger.info("FAILURE! All birds lost")
        # Removed 50% early win - let all birds complete their journey
        
        return self.get_state()
    
    def _update_stress(self, agent: Agent, dt: float):
        """Update bird stress based on hazards and distance from flock."""
        stress_increase = 0.0
        in_hazard = False
        
        # Check hazards (storms and predators)
        for hazard in self.hazards:
            hazard_pos = np.array([hazard['x'], hazard['y']])
            dist_to_hazard = np.linalg.norm(agent.position - hazard_pos)
            
            if dist_to_hazard < hazard['radius']:
                # Inside hazard zone - stress increases 1% per second
                stress_increase = 1.0 * dt * 30.0  # 1% per second (30 ticks/sec)
                in_hazard = True
                break
        
        # Check distance from nearest leader (for non-leaders)
        if not self.is_leader.get(agent.id, False):
            min_leader_dist = float('inf')
            for other in self.agents:
                if other.alive and self.is_leader.get(other.id, False):
                    dist = np.linalg.norm(agent.position - other.position)
                    min_leader_dist = min(min_leader_dist, dist)
            
            # Stress from being too far from leaders
            if min_leader_dist > 200:  # More than 200 units from nearest leader
                distance_stress = ((min_leader_dist - 200) / 100) * 0.5 * dt * 30.0  # 0.5% per 100 units
                stress_increase = max(stress_increase, distance_stress)
        
        # Check if in safe zone (close to many birds)
        nearby_count = 0
        for other in self.agents:
            if other.id != agent.id and other.alive:
                dist = np.linalg.norm(agent.position - other.position)
                if dist < 50:  # Within 50 units
                    nearby_count += 1
        
        # If close to many birds and not in hazard, reduce stress
        if nearby_count >= 3 and not in_hazard:
            # Safe zone - stress decreases 1% per second
            agent.stress = max(0, agent.stress - 1.0 * dt * 30.0)
        else:
            # Apply stress increase
            agent.stress = min(100, agent.stress + stress_increase)
    
    def _follow_path(self, agent: Agent, dt: float):
        """Make the bird follow the drawn path."""
        if not self.migration_path:
            # No path set yet - don't apply any path forces
            # Birds will just use flocking behavior
            return
        
        # Get current waypoint index for this bird
        waypoint_idx = self.path_progress.get(agent.id, 0)
        
        # Find next waypoint to target (with lookahead)
        while waypoint_idx < len(self.migration_path):
            waypoint = np.array(self.migration_path[waypoint_idx])
            dist_to_waypoint = np.linalg.norm(agent.position - waypoint)
            
            # If close enough to waypoint, target next one
            if dist_to_waypoint < 40:  # Reduced radius for tighter following
                waypoint_idx += 1
                self.path_progress[agent.id] = waypoint_idx
            else:
                break
        
        # Look ahead for smoother path following
        if waypoint_idx < len(self.migration_path):
            lookahead_idx = min(waypoint_idx + 2, len(self.migration_path) - 1)
            # Blend current waypoint with lookahead for smoother curves
            current_waypoint = np.array(self.migration_path[waypoint_idx])
            lookahead_waypoint = np.array(self.migration_path[lookahead_idx])
            # 70% current, 30% lookahead
            blended_target = current_waypoint * 0.7 + lookahead_waypoint * 0.3
        else:
            blended_target = None
        
        # Determine target based on progress
        if waypoint_idx >= len(self.migration_path):
            # Finished path - continue on same trajectory to find destination
            if len(self.migration_path) >= 2:
                # Calculate trajectory from last two waypoints
                last_point = np.array(self.migration_path[-1])
                second_last = np.array(self.migration_path[-2])
                trajectory = last_point - second_last
                
                # Normalize and extend trajectory
                if np.linalg.norm(trajectory) > 0:
                    trajectory = trajectory / np.linalg.norm(trajectory)
                    # Project forward on same trajectory
                    extended_target = last_point + trajectory * 200.0
                    
                    # But also blend with destination for eventual arrival
                    dest_x, dest_y, _ = self.config.destination_zone
                    destination = np.array([dest_x, dest_y])
                    
                    # Blend: 70% trajectory continuation, 30% destination pull
                    target = extended_target * 0.7 + destination * 0.3
                else:
                    # Fallback to destination
                    dest_x, dest_y, _ = self.config.destination_zone
                    target = np.array([dest_x, dest_y])
            else:
                # No path or too short - head to destination
                dest_x, dest_y, _ = self.config.destination_zone
                target = np.array([dest_x, dest_y])
            
            path_strength = 3.0  # Strong force to continue trajectory
        elif blended_target is not None:
            # Use blended target for smoother following
            target = blended_target
            path_strength = 4.0  # Very strong force on path
        else:
            # Still following path (normal)
            target = np.array(self.migration_path[waypoint_idx])
            path_strength = 4.0  # Very strong force on path
        
        # Steer toward target
        to_target = target - agent.position
        dist = np.linalg.norm(to_target)
        
        if dist > 0:
            # Path following weight: leaders=1.0, followers=0.4
            path_weight = 1.0 if self.is_leader.get(agent.id, False) else 0.4
            
            # Strong attraction to path
            desired_velocity = (to_target / dist) * 150.0  # High desired speed
            steering = desired_velocity - agent.velocity
            # Apply steering force more smoothly
            max_force = 300.0 if self.is_leader.get(agent.id, False) else 200.0
            if np.linalg.norm(steering) > max_force:
                steering = (steering / np.linalg.norm(steering)) * max_force
            agent.velocity += steering * dt * path_strength * path_weight  # Apply weight
            
            # Prevent complete stops - maintain momentum
            speed = np.linalg.norm(agent.velocity)
            if speed < 20.0:  # If too slow
                # Boost in direction of target
                boost_dir = to_target / (dist + 0.01)
                agent.velocity += boost_dir * 50.0 * dt
    
    def _apply_flocking(self, agent: Agent, dt: float):
        """Apply basic flocking for cohesion."""
        neighbor_radius = 120.0  # Increased for better awareness
        separation_radius = 30.0
        
        cohesion_force = np.zeros(2)
        separation_force = np.zeros(2)
        alignment_force = np.zeros(2)
        neighbor_count = 0
        
        # Check if this bird is a leader
        is_leader = self.is_leader.get(agent.id, False)
        
        # Stronger flocking when no path is set (initial phase)
        no_path_multiplier = 2.0 if not self.migration_path else 1.0
        
        for other in self.agents:
            if other.id == agent.id or not other.alive:
                continue
            
            diff = other.position - agent.position
            dist = np.linalg.norm(diff)
            
            if dist < neighbor_radius and dist > 0:
                # Cohesion - move toward neighbors
                cohesion_force += diff
                
                # Alignment - match neighbor velocity
                alignment_force += other.velocity
                
                neighbor_count += 1
                
                # Separation - avoid getting too close
                if dist < separation_radius:
                    separation_force -= diff / (dist * dist)
        
        if neighbor_count > 0:
            # Average forces
            cohesion_force = cohesion_force / neighbor_count - agent.position
            alignment_force = alignment_force / neighbor_count - agent.velocity
            
            # Non-leaders follow the flock more strongly
            if is_leader:
                # Leaders: moderate flocking to maintain group but follow path
                agent.velocity += cohesion_force * 0.5 * dt * no_path_multiplier
                agent.velocity += alignment_force * 0.4 * dt * no_path_multiplier
            else:
                # Followers: very strong flocking (they follow the leaders)
                agent.velocity += cohesion_force * 2.0 * dt * no_path_multiplier
                agent.velocity += alignment_force * 1.5 * dt * no_path_multiplier
            
            # Separation is critical to avoid collisions
            agent.velocity += separation_force * 15.0 * dt
    
    def get_state(self) -> Dict[str, Any]:
        """Get current simulation state."""
        alive_agents = [a for a in self.agents if a.alive]
        
        # Debug log
        if self.tick % 30 == 0:  # Log once per second
            logger.info(f"State update: {len(alive_agents)} birds alive at tick {self.tick}")
        
        return {
            'tick': self.tick,
            'agents': [self._agent_to_dict(a) for a in alive_agents],  # Changed from 'birds' to 'agents'
            'birds': [self._agent_to_dict(a) for a in alive_agents],  # Keep for backward compatibility
            'population': len(alive_agents),
            'arrivals': self.arrivals,
            'losses': self.losses,
            'destination': self.config.destination_zone,
            'hazards': self.hazards,  # Add hazards for client rendering
            'game_over': self.game_over,
            'victory': self.victory,
            'current_leg': self.config.current_leg,
            'total_legs': self.config.total_legs,
            'leg_name': self.config.leg_name,
            'migration_path': self.migration_path
        }
    
    def _agent_to_dict(self, agent: Agent) -> Dict[str, Any]:
        """Convert agent to dictionary for client."""
        return {
            'id': int(agent.id),
            'x': float(agent.position[0]),
            'y': float(agent.position[1]),
            'vx': float(agent.velocity[0]),
            'vy': float(agent.velocity[1]),
            'energy': float(agent.energy),
            'stress': float(agent.stress),
            'alive': agent.alive,
            'gender': self.genders.get(agent.id, 'male'),  # Add gender
            'is_leader': self.is_leader.get(agent.id, False)  # Add leader status
        }
    
    def continue_to_next_leg(self) -> bool:
        """Continue to the next leg of migration."""
        if self.config.current_leg >= self.config.total_legs:
            return False  # Migration complete
        
        self.config.current_leg += 1
        self.config.leg_name = f"Migration Leg {self.config.current_leg}"
        
        # Reset state
        self.tick = 0
        self.start_time = time.time()
        self.arrivals = 0
        self.game_over = False
        self.victory = False
        self.migration_path = []  # Clear path for new leg
        
        # Only carry over actual survivors (alive or arrived)
        survived_ids = set()
        for agent in self.agents:
            # Only carry over birds that actually survived (arrived or still alive)
            if agent.alive and agent.energy > 0:
                survived_ids.add(agent.id)
        
        # Add arrived birds to survivors
        if self.arrivals > 0:
            # Find birds that made it to destination
            for agent in self.agents:
                dest_x, dest_y, dest_radius = self.config.destination_zone
                dist_to_dest = np.linalg.norm(agent.position - np.array([dest_x, dest_y]))
                if dist_to_dest < dest_radius:
                    survived_ids.add(agent.id)
        
        # Reset only survivors for next leg
        for agent in self.agents:
            if agent.id in survived_ids:
                # Reset position to start zone
                start_x, start_y, start_radius = self.config.start_zone
                angle = self.rng.uniform(0, 2 * np.pi)
                radius = self.rng.uniform(0, start_radius)
                agent.position = np.array([
                    start_x + radius * np.cos(angle),
                    start_y + radius * np.sin(angle)
                ], dtype=np.float32)
                
                # Reset state for survivors
                agent.alive = True
                agent.energy = 100.0
                agent.stress = 0.0
                agent.velocity = np.array([
                    self.rng.uniform(-5, 5),
                    self.rng.uniform(-5, 5)
                ], dtype=np.float32)
                
                self.path_progress[agent.id] = 0
                # Gender and leader status are preserved
            else:
                # Dead birds stay dead
                agent.alive = False
        
        logger.info(f"Advanced to leg {self.config.current_leg}/{self.config.total_legs}")
        return True