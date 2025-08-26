"""Game-focused simulation with actual objectives and gameplay.

This module implements the actual game mechanics, not just physics simulation.
"""

import time
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from .core.agent import Agent, create_agent
from .core.types import AgentID
from .utils.logging import get_logger

logger = get_logger("game_simulation")


@dataclass
class GameConfig:
    """Configuration for a playable game session."""
    level: str = "W1-1"
    seed: int = 42
    
    # Level-specific data (loaded from JSON)
    n_agents: int = 100
    start_zone: Tuple[float, float, float] = (200, 600, 100)  # x, y, radius
    destination_zone: Tuple[float, float, float] = (1800, 600, 150)  # x, y, radius
    migration_direction: Tuple[float, float] = (1.0, 0.0)  # General east direction
    
    # Win conditions
    target_arrivals: int = 80  # Need 80% to arrive
    max_losses: int = 20
    time_limit_seconds: int = 120  # 2 minutes per level
    
    # Gameplay
    beacon_budget: int = 4
    pulse_cooldown: float = 5.0
    
    # Hazards
    level_hazards: List[Dict] = None
    
    @classmethod
    def from_level(cls, level_name: str, seed: int = 42):
        """Load config from level JSON."""
        import json
        from pathlib import Path
        
        levels_file = Path(__file__).parent.parent / "levels" / "levels.json"
        if levels_file.exists():
            with open(levels_file) as f:
                levels = json.load(f)
                
            if level_name in levels:
                level_data = levels[level_name]
                return cls(
                    level=level_name,
                    seed=seed,
                    n_agents=level_data.get('n_agents', 100),
                    start_zone=tuple(level_data.get('start_zone', [200, 600, 100])),
                    destination_zone=tuple(level_data.get('destination_zone', [1800, 600, 150])),
                    target_arrivals=level_data.get('target_arrivals', 80),
                    max_losses=level_data.get('max_losses', 20),
                    time_limit_seconds=level_data.get('time_limit', 120),
                    beacon_budget=level_data.get('beacon_budget', 4),
                    level_hazards=level_data.get('hazards', [])
                )
        
        # Default config if level not found
        return cls(level=level_name, seed=seed)


class GameSimulation:
    """Playable game simulation with objectives."""
    
    def __init__(self, config: GameConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        
        # Initialize agents in start zone
        self.agents: List[Agent] = []
        for i in range(config.n_agents):
            agent = create_agent(AgentID(i), rng=self.rng)
            # Place in start zone with some scatter
            angle = self.rng.uniform(0, 2 * np.pi)
            radius = self.rng.uniform(0, config.start_zone[2])
            agent.position = np.array([
                config.start_zone[0] + radius * np.cos(angle),
                config.start_zone[1] + radius * np.sin(angle)
            ])
            # Give initial migration velocity
            agent.velocity = np.array([
                self.rng.uniform(5, 15),  # Move east
                self.rng.uniform(-2, 2)   # Slight vertical variation
            ])
            agent.energy = 100.0
            self.agents.append(agent)
        
        # Game state
        self.tick = 0
        self.start_time = time.time()
        self.arrivals = 0
        self.losses = 0
        self.game_over = False
        self.victory = False
        
        # Beacons and effects
        self.beacons: List[Dict[str, Any]] = []
        self.active_pulses: List[Dict[str, Any]] = []
        self.last_pulse_time = 0
        
        # Hazards
        self.hazards: List[Dict[str, Any]] = []
        self.spawn_initial_hazards()
        
        logger.info(f"Game initialized: {config.n_agents} birds, destination at ({config.destination_zone[0]}, {config.destination_zone[1]})")
    
    def spawn_initial_hazards(self):
        """Spawn hazards from level configuration."""
        if self.config.level_hazards:
            for hazard_data in self.config.level_hazards:
                hazard = hazard_data.copy()
                # Convert direction to numpy array if present
                if 'direction' in hazard:
                    hazard['direction'] = np.array(hazard['direction'])
                self.hazards.append(hazard)
            logger.info(f"Spawned {len(self.hazards)} hazards from level {self.config.level}")
        else:
            # Default hazards if none specified
            self.hazards.append({
                'type': 'storm',
                'x': 1000,
                'y': 600,
                'radius': 150,
                'strength': 15,
                'direction': np.array([0, -1])
            })
            self.hazards.append({
                'type': 'predator',
                'x': 800,
                'y': 500,
                'radius': 100,
                'danger': 0.5,
                'speed': 5.0
            })
    
    def step(self) -> Dict[str, Any]:
        """Execute one game step with actual gameplay."""
        self.tick += 1
        dt = 1.0 / 30.0  # 30 FPS
        
        # Update each agent
        alive_agents = []
        for agent in self.agents:
            if not agent.alive:
                continue
                
            # Save old position for arrival checking
            old_x = agent.position[0]
            
            # 1. Migration force (towards destination)
            dest_x, dest_y, dest_r = self.config.destination_zone
            to_dest = np.array([dest_x - agent.position[0], dest_y - agent.position[1]])
            dist_to_dest = np.linalg.norm(to_dest)
            
            if dist_to_dest > dest_r:
                # Apply migration force
                migration_force = (to_dest / dist_to_dest) * 15.0  # Strong pull toward destination
                agent.velocity += migration_force * dt
            
            # 2. Flocking forces (cohesion with nearby birds)
            neighbors = self.get_neighbors(agent, radius=100)
            if neighbors:
                # Cohesion - move toward center of neighbors
                center = np.mean([n.position for n in neighbors], axis=0)
                cohesion = (center - agent.position) * 0.5
                agent.velocity += cohesion * dt
                
                # Alignment - match neighbor velocities
                avg_vel = np.mean([n.velocity for n in neighbors], axis=0)
                alignment = (avg_vel - agent.velocity) * 0.3
                agent.velocity += alignment * dt
                
                # Separation - avoid crowding
                for neighbor in neighbors:
                    diff = agent.position - neighbor.position
                    dist = np.linalg.norm(diff)
                    if dist < 30 and dist > 0:
                        separation = (diff / dist) * 50 / dist
                        agent.velocity += separation * dt
            
            # 3. Beacon influence
            for beacon in self.beacons:
                to_beacon = np.array([beacon['x'] - agent.position[0], beacon['y'] - agent.position[1]])
                dist = np.linalg.norm(to_beacon)
                
                if dist < beacon['radius']:
                    strength = beacon['strength'] * (1 - dist / beacon['radius'])
                    if beacon['type'] == 'food':
                        # Food beacons restore energy and attract
                        agent.energy = min(100, agent.energy + 0.5)
                        agent.velocity += (to_beacon / dist) * strength * dt
                    elif beacon['type'] == 'shelter':
                        # Shelter reduces stress and slows birds
                        agent.stress = max(0, agent.stress - 0.01)
                        agent.velocity *= 0.95
                    elif beacon['type'] == 'thermal':
                        # Thermal lifts boost upward and forward
                        agent.velocity[0] += strength * dt  # Forward boost
                        agent.energy = min(100, agent.energy + 0.2)
            
            # 4. Hazard avoidance
            for hazard in self.hazards:
                to_hazard = np.array([hazard['x'] - agent.position[0], hazard['y'] - agent.position[1]])
                dist = np.linalg.norm(to_hazard)
                
                if dist < hazard['radius']:
                    danger_factor = 1.0 - (dist / hazard['radius'])  # Closer = more dangerous
                    danger_factor = danger_factor ** 2  # Square for more dramatic effect near center
                    
                    if hazard['type'] == 'storm':
                        # Storm pushes birds around and drains energy HEAVILY
                        force_strength = hazard.get('strength', 20)
                        agent.velocity += hazard['direction'] * force_strength * danger_factor * dt * 2
                        agent.stress = min(1.0, agent.stress + 0.1 * danger_factor)
                        
                        # MASSIVE energy drain in storms
                        energy_loss = 3.0 * danger_factor  # Up to 3 energy per tick!
                        agent.energy = max(0, agent.energy - energy_loss)
                        
                        # Higher stress causes even more energy loss
                        if agent.stress > 0.5:
                            agent.energy = max(0, agent.energy - 1.0)
                        
                        # Lightning strike chance in severe storms
                        if hazard.get('lightning') and self.rng.random() < 0.005 * danger_factor:
                            agent.alive = False
                            self.losses += 1
                            logger.info(f"⚡ Bird struck by lightning! Losses: {self.losses}")
                            
                    elif hazard['type'] == 'predator':
                        # Predators are DEADLY
                        escape = -to_hazard / dist * 200 * danger_factor
                        agent.velocity += escape * dt
                        agent.stress = min(1.0, agent.stress + 0.15 * danger_factor)
                        
                        # Much higher chance of being caught
                        base_danger = hazard.get('danger', 0.5)
                        catch_chance = base_danger * 0.05 * danger_factor  # 5x more deadly
                        
                        if dist < 50:  # Larger kill zone
                            if self.rng.random() < catch_chance:
                                agent.alive = False
                                self.losses += 1
                                logger.info(f"🦅 Bird caught by predator! Losses: {self.losses}")
                        
                        # Predators drain energy from fear
                        agent.energy = max(0, agent.energy - 1.5 * danger_factor)
                        
                        # Alpha predators are instant death if too close
                        if hazard.get('alpha') and dist < 30:
                            if self.rng.random() < 0.1:  # 10% instant death chance
                                agent.alive = False
                                self.losses += 1
                                logger.info(f"💀 Alpha predator kill! Losses: {self.losses}")
            
            # 5. Apply pulses
            for pulse in self.active_pulses:
                if pulse['remaining'] > 0:
                    if pulse['type'] == 'gather':
                        # Pull toward flock center
                        if neighbors:
                            center = np.mean([n.position for n in neighbors], axis=0)
                            agent.velocity += (center - agent.position) * 2 * dt
                    elif pulse['type'] == 'scatter':
                        # Push away from neighbors
                        for neighbor in neighbors[:3]:  # Limit to closest 3
                            diff = agent.position - neighbor.position
                            agent.velocity += diff * dt
                    elif pulse['type'] == 'boost':
                        # Speed boost toward destination
                        agent.velocity[0] += 20 * dt
            
            # 6. Speed limits
            speed = np.linalg.norm(agent.velocity)
            max_speed = 80 if agent.energy > 50 else 60
            if speed > max_speed:
                agent.velocity = (agent.velocity / speed) * max_speed
            
            # 7. Update position
            agent.position += agent.velocity * dt
            
            # 8. Boundary constraints
            agent.position[0] = np.clip(agent.position[0], 0, 2000)
            agent.position[1] = np.clip(agent.position[1], 0, 1200)
            
            # 9. Energy decay
            agent.energy = max(0, agent.energy - 0.05)  # Base energy loss
            if agent.energy <= 0:
                agent.alive = False
                self.losses += 1
                logger.info(f"Bird died from exhaustion. Total losses: {self.losses}")
            
            # 10. Check arrival at destination
            if dist_to_dest < dest_r and old_x < dest_x:
                self.arrivals += 1
                agent.alive = False  # Remove from simulation
                logger.info(f"Bird arrived! Total: {self.arrivals}/{self.config.target_arrivals}")
            
            if agent.alive:
                alive_agents.append(agent)
        
        # Update pulse timers
        self.active_pulses = [p for p in self.active_pulses if p['remaining'] > 0]
        for pulse in self.active_pulses:
            pulse['remaining'] -= dt
        
        # Check win/loss conditions
        if self.arrivals >= self.config.target_arrivals:
            self.victory = True
            self.game_over = True
            logger.info(f"VICTORY! {self.arrivals} birds reached destination!")
        elif self.losses > self.config.max_losses:
            self.game_over = True
            logger.info(f"DEFEAT! Too many losses: {self.losses}")
        elif time.time() - self.start_time > self.config.time_limit_seconds:
            self.game_over = True
            logger.info(f"TIME UP! Only {self.arrivals} birds arrived")
        
        # Return game state
        return {
            'tick': self.tick,
            'agents': alive_agents,
            'population': len(alive_agents),
            'arrivals': self.arrivals,
            'losses': self.losses,
            'beacons': self.beacons,
            'hazards': self.hazards,
            'destination': self.config.destination_zone,
            'game_over': self.game_over,
            'victory': self.victory,
            'time_remaining': max(0, self.config.time_limit_seconds - (time.time() - self.start_time)),
            'cohesion': self.calculate_cohesion(alive_agents)
        }
    
    def get_neighbors(self, agent: Agent, radius: float) -> List[Agent]:
        """Get neighboring agents within radius."""
        neighbors = []
        for other in self.agents:
            if other.alive and other.id != agent.id:
                dist = np.linalg.norm(agent.position - other.position)
                if dist < radius:
                    neighbors.append(other)
        return neighbors
    
    def calculate_cohesion(self, agents: List[Agent]) -> float:
        """Calculate flock cohesion metric."""
        if len(agents) < 2:
            return 0.0
        
        # Average distance to nearest neighbors
        distances = []
        for agent in agents[:20]:  # Sample for performance
            neighbors = self.get_neighbors(agent, radius=200)
            if neighbors:
                min_dist = min(np.linalg.norm(agent.position - n.position) for n in neighbors)
                distances.append(min_dist)
        
        if not distances:
            return 0.0
        
        avg_dist = np.mean(distances)
        # Normalize: closer = higher cohesion
        return max(0, min(1, 1 - avg_dist / 200))
    
    def place_beacon(self, beacon_type: str, x: float, y: float) -> bool:
        """Place a beacon at position."""
        beacon = {
            'id': len(self.beacons),
            'type': beacon_type,
            'x': x,
            'y': y,
            'radius': 150,
            'strength': 30
        }
        self.beacons.append(beacon)
        logger.info(f"Beacon placed: {beacon_type} at ({x:.0f}, {y:.0f})")
        return True
    
    def remove_beacon(self, beacon_id: int) -> bool:
        """Remove a beacon."""
        self.beacons = [b for b in self.beacons if b['id'] != beacon_id]
        return True
    
    def activate_pulse(self, pulse_type: str) -> bool:
        """Activate a pulse effect."""
        current_time = time.time()
        if current_time - self.last_pulse_time < self.config.pulse_cooldown:
            return False
        
        self.active_pulses.append({
            'type': pulse_type,
            'remaining': 2.0  # 2 second duration
        })
        self.last_pulse_time = current_time
        logger.info(f"Pulse activated: {pulse_type}")
        return True