"""Evolved game simulation with learning, distinct hazards, and breed evolution.

This module implements advanced game mechanics including:
- Distinct hazard behaviors (tornadoes vs predators)
- Learning and evolution between levels
- Breed creation and training
- Flock reaction behaviors
"""

import time
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import json
from pathlib import Path

from .core.agent import Agent, create_agent
from .core.types import AgentID, Tick, create_vector2d
from .utils.logging import get_logger
from .beacons.beacon import BeaconManager, BeaconType, BEACON_SPECS

logger = get_logger("evolved_simulation")


@dataclass
class Breed:
    """Represents an evolved breed of birds with learned behaviors."""
    name: str = "Default"
    generation: int = 0
    
    # Learned parameters (evolve over time)
    hazard_awareness: float = 0.5  # How well they detect danger
    energy_efficiency: float = 1.0  # Energy consumption rate
    flock_cohesion: float = 0.7  # How tightly they stick together
    beacon_sensitivity: float = 1.0  # How well they respond to beacons
    stress_resilience: float = 0.5  # How well they handle stress
    
    # Experience counters
    storms_survived: int = 0
    predators_escaped: int = 0
    successful_migrations: int = 0
    total_distance: float = 0.0
    
    def evolve(self, survival_rate: float, hazards_encountered: Dict[str, int]):
        """Evolve breed based on survival experience."""
        # Increase generation
        self.generation += 1
        
        # Improve based on survival rate
        if survival_rate > 0.8:
            self.energy_efficiency *= 0.98  # Use less energy
            self.stress_resilience = min(1.0, self.stress_resilience + 0.05)
        elif survival_rate < 0.5:
            self.hazard_awareness = min(1.0, self.hazard_awareness + 0.1)
            self.flock_cohesion = min(1.0, self.flock_cohesion + 0.05)
        
        # Adapt to specific hazards
        if hazards_encountered.get('tornado', 0) > 0:
            self.energy_efficiency *= 0.99  # Better energy management in storms
        if hazards_encountered.get('predator', 0) > 0:
            self.hazard_awareness = min(1.0, self.hazard_awareness + 0.05)
            self.flock_cohesion = min(1.0, self.flock_cohesion + 0.03)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for saving."""
        return {
            'name': self.name,
            'generation': self.generation,
            'hazard_awareness': self.hazard_awareness,
            'energy_efficiency': self.energy_efficiency,
            'flock_cohesion': self.flock_cohesion,
            'beacon_sensitivity': self.beacon_sensitivity,
            'stress_resilience': self.stress_resilience,
            'storms_survived': self.storms_survived,
            'predators_escaped': self.predators_escaped,
            'successful_migrations': self.successful_migrations,
            'total_distance': self.total_distance
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Create from dictionary."""
        breed = cls(name=data.get('name', 'Loaded'))
        for key, value in data.items():
            if hasattr(breed, key):
                setattr(breed, key, value)
        return breed


@dataclass 
class GameConfig:
    """Configuration for evolved game session."""
    level: str = "W1-1"
    seed: int = 42
    breed: Optional[Breed] = None
    
    # Level data
    n_agents: int = 100
    start_zone: Tuple[float, float, float] = (200, 600, 100)
    destination_zone: Tuple[float, float, float] = (1800, 600, 150)
    
    # Win conditions
    target_arrivals: int = 80
    max_losses: int = 20
    time_limit_seconds: int = 120
    
    # Gameplay
    beacon_budget: int = 4
    pulse_cooldown: float = 5.0
    
    # Hazards
    level_hazards: List[Dict] = None
    
    @classmethod
    def from_level(cls, level_name: str, seed: int = 42, breed: Optional[Breed] = None):
        """Load config from level JSON."""
        levels_file = Path(__file__).parent.parent / "levels" / "levels.json"
        if levels_file.exists():
            with open(levels_file) as f:
                levels = json.load(f)
                
            if level_name in levels:
                level_data = levels[level_name]
                return cls(
                    level=level_name,
                    seed=seed,
                    breed=breed or Breed(),
                    n_agents=level_data.get('n_agents', 100),
                    start_zone=tuple(level_data.get('start_zone', [200, 600, 100])),
                    destination_zone=tuple(level_data.get('destination_zone', [1800, 600, 150])),
                    target_arrivals=level_data.get('target_arrivals', 80),
                    max_losses=level_data.get('max_losses', 20),
                    time_limit_seconds=level_data.get('time_limit', 120),
                    beacon_budget=level_data.get('beacon_budget', 4),
                    level_hazards=level_data.get('hazards', [])
                )
        
        return cls(level=level_name, seed=seed, breed=breed or Breed())


class EvolvedSimulation:
    """Advanced game simulation with learning and evolution."""
    
    def __init__(self, config: GameConfig):
        self.config = config
        self.breed = config.breed or Breed()
        self.rng = np.random.default_rng(config.seed)
        
        # Initialize evolved agents
        self.agents: List[Agent] = []
        for i in range(config.n_agents):
            agent = create_agent(AgentID(i), rng=self.rng)
            
            # Place in start zone
            angle = self.rng.uniform(0, 2 * np.pi)
            radius = self.rng.uniform(0, config.start_zone[2])
            agent.position = np.array([
                config.start_zone[0] + radius * np.cos(angle),
                config.start_zone[1] + radius * np.sin(angle)
            ])
            
            # Initial velocity with breed influence
            agent.velocity = np.array([
                self.rng.uniform(5, 15) * (1 + self.breed.energy_efficiency * 0.1),
                self.rng.uniform(-2, 2)
            ])
            
            # Apply breed traits - increased starting energy for better beacon timing
            agent.energy = 300.0 * (1 + self.breed.energy_efficiency * 0.1)
            agent.stress = max(0, 0.2 - self.breed.stress_resilience * 0.2)
            
            # Add breed-specific attributes
            agent.hazard_detection = self.breed.hazard_awareness
            agent.beacon_response = self.breed.beacon_sensitivity
            
            self.agents.append(agent)
        
        # Game state
        self.tick = 0
        self.start_time = time.time()
        self.arrivals = 0
        self.losses = 0
        self.game_over = False
        self.victory = False
        
        # Tracking for evolution
        self.hazards_encountered = {'tornado': 0, 'predator': 0, 'storm': 0}
        self.close_calls = 0  # Near-death experiences
        self.panic_events = 0  # Times flock panicked
        
        # Beacons and effects
        self.beacon_manager = BeaconManager(budget_limit=self.config.beacon_budget)
        self.active_pulses: List[Dict[str, Any]] = []
        self.last_pulse_time = 0
        
        # Advanced hazards with distinct behaviors
        self.hazards: List[Dict[str, Any]] = []
        self.spawn_evolved_hazards()
        
        logger.info(f"Evolved game initialized: Breed '{self.breed.name}' Gen {self.breed.generation}")
    
    def spawn_evolved_hazards(self):
        """Spawn hazards with distinct, characterized behaviors."""
        if self.config.level_hazards:
            for hazard_data in self.config.level_hazards:
                hazard = hazard_data.copy()
                
                # Enhanced hazard types with unique behaviors
                if hazard['type'] == 'storm':
                    # Storms are now tornadoes with confusion effect
                    hazard['type'] = 'tornado'
                    hazard['confusion_strength'] = hazard.get('strength', 20) * 2
                    hazard['kill_chance'] = 0.1  # 10% chance in center
                    hazard['energy_drain'] = 1.5  # Moderate energy drain
                    hazard['spin_rate'] = self.rng.uniform(0.5, 2.0)  # Rotation speed
                    
                elif hazard['type'] == 'predator':
                    # Predators trigger flock reactions
                    hazard['kill_chance'] = 0.2  # 20% chance when caught
                    hazard['pursuit_speed'] = hazard.get('speed', 8)
                    hazard['detection_range'] = hazard.get('radius', 100) * 1.5
                    hazard['attack_range'] = 30
                    hazard['trigger_panic'] = True
                    hazard['last_kill_time'] = 0
                    
                # Add visual gradient zones
                hazard['danger_zones'] = [
                    {'radius': hazard['radius'] * 1.5, 'intensity': 0.2},  # Outer warning
                    {'radius': hazard['radius'], 'intensity': 0.6},  # Danger zone
                    {'radius': hazard['radius'] * 0.5, 'intensity': 1.0}  # Death zone
                ]
                
                if 'direction' in hazard:
                    hazard['direction'] = np.array(hazard['direction'])
                    
                self.hazards.append(hazard)
            
            logger.info(f"Spawned {len(self.hazards)} evolved hazards")
    
    def step(self) -> Dict[str, Any]:
        """Execute one simulation step with advanced behaviors."""
        self.tick += 1
        dt = 1.0 / 30.0
        
        # Track alive agents
        alive_agents = []
        flock_center = np.mean([a.position for a in self.agents if a.alive], axis=0) if any(a.alive for a in self.agents) else np.array([1000, 600])
        
        for agent in self.agents:
            if not agent.alive:
                continue
            
            # 1. Migration instinct (stronger with experience)
            dest_x, dest_y, dest_r = self.config.destination_zone
            to_dest = np.array([dest_x - agent.position[0], dest_y - agent.position[1]])
            dist_to_dest = np.linalg.norm(to_dest)
            
            if dist_to_dest > dest_r:
                migration_strength = 15.0 * (1 + self.breed.successful_migrations * 0.01)
                migration_force = (to_dest / dist_to_dest) * migration_strength
                agent.velocity += migration_force * dt
            
            # 2. Advanced flocking with breed cohesion
            neighbors = self.get_neighbors(agent, radius=100 * (1 + self.breed.flock_cohesion))
            if neighbors:
                # Cohesion (stronger with breed trait)
                center = np.mean([n.position for n in neighbors], axis=0)
                cohesion = (center - agent.position) * (0.5 * self.breed.flock_cohesion)
                agent.velocity += cohesion * dt
                
                # Alignment
                avg_vel = np.mean([n.velocity for n in neighbors], axis=0)
                alignment = (avg_vel - agent.velocity) * 0.3
                agent.velocity += alignment * dt
                
                # Separation (critical for survival)
                for neighbor in neighbors:
                    diff = agent.position - neighbor.position
                    dist = np.linalg.norm(diff)
                    if dist < 30 and dist > 0:
                        separation = (diff / dist) * 50 / dist
                        agent.velocity += separation * dt
            
            # 3. Sophisticated beacon influence using BeaconManager
            contributions = self.beacon_manager.get_combined_field_contribution(
                agent.position, 
                Tick(self.tick),
                is_night=(self.tick % 1800) > 900  # Day/night cycle: night from tick 900-1800
            )
            
            # DEBUG: Log beacon contributions for first agent occasionally
            if agent.id == 0 and self.tick % 120 == 0 and len(self.beacon_manager.beacons) > 0:
                logger.info(f"🌟 BEACON: Agent {agent.id} - Contributions: {contributions}, Active beacons: {len(self.beacon_manager.beacons)}")
            
            # Apply beacon effects with agent sensitivity
            beacon_response = agent.beacon_response
            
            # Light beacon attraction (mainly at night)
            if contributions["light_attraction"] > 0:
                # Find strongest light beacon for directional attraction
                max_light_strength = 0
                light_direction = np.array([0.0, 0.0])
                
                for beacon in self.beacon_manager.beacons:
                    if beacon.beacon_type == BeaconType.LIGHT:
                        strength = beacon.get_field_strength(agent.position, Tick(self.tick))
                        if strength > max_light_strength:
                            max_light_strength = strength
                            to_beacon = beacon.position - agent.position
                            dist = np.linalg.norm(to_beacon)
                            if dist > 0:
                                light_direction = to_beacon / dist
                
                if max_light_strength > 0:
                    light_force = light_direction * contributions["light_attraction"] * beacon_response * 25 * dt
                    agent.velocity += light_force
            
            # Sound beacon cohesion enhancement and shelter effects
            if contributions["cohesion_boost"] > 0:
                # Enhanced flocking behavior near sound beacons
                cohesion_strength = contributions["cohesion_boost"] * beacon_response
                
                # SHELTER EFFECT 1: Stress reduction
                stress_reduction = cohesion_strength * 0.5 * dt
                agent.stress = max(0, agent.stress - stress_reduction)
                
                # SHELTER EFFECT 2: Velocity slowing (for rest/shelter behavior)
                slowing_factor = 1.0 - (cohesion_strength * 0.3)  # Up to 30% slower
                agent.velocity *= slowing_factor
                
                # Apply stronger cohesion forces (already calculated above in step 1)
                for other in alive_agents:
                    if other.id != agent.id:
                        diff = other.position - agent.position
                        dist = np.linalg.norm(diff)
                        if 50 < dist < 100:  # Cohesion range
                            cohesion = (diff / dist) * 30 * (1 + cohesion_strength) / dist
                            agent.velocity += cohesion * dt
            
            # Food scent foraging bias
            if contributions["foraging_bias"] > 0:
                # Find closest food beacon for energy restoration
                for beacon in self.beacon_manager.beacons:
                    if beacon.beacon_type == BeaconType.FOOD_SCENT:
                        strength = beacon.get_field_strength(agent.position, Tick(self.tick))
                        
                        if strength > 0.1:  # Within effective range
                            # Energy restoration - increased multiplier from 0.8 to 20 for meaningful restoration
                            energy_gain = strength * beacon_response * 20 * dt
                            old_energy = agent.energy
                            agent.energy = min(300, agent.energy + energy_gain)
                            
                            # DEBUG: Log energy restoration occasionally
                            if agent.id == 0 and self.tick % 120 == 0:
                                logger.info(f"🍯 ENERGY RESTORE: Agent {agent.id} - gain={energy_gain:.3f}, {old_energy:.1f}→{agent.energy:.1f}")
                            
                            # Attraction toward food source
                            to_beacon = beacon.position - agent.position
                            dist = np.linalg.norm(to_beacon)
                            if dist > 0:
                                food_force = (to_beacon / dist) * strength * beacon_response * 20 * dt
                                agent.velocity += food_force
            
            # Wind lure tailwind boost  
            if contributions["wind_boost"] > 0:
                # Forward velocity boost (assuming eastward migration)
                wind_boost = contributions["wind_boost"] * beacon_response * 15 * dt
                agent.velocity[0] += wind_boost  # Boost in X direction
                
                # Small energy bonus from favorable winds
                energy_gain = contributions["wind_boost"] * beacon_response * 0.4 * dt
                agent.energy = min(300, agent.energy + energy_gain)
            
            # 4. Advanced hazard responses
            for hazard in self.hazards:
                to_hazard = np.array([hazard['x'] - agent.position[0], hazard['y'] - agent.position[1]])
                dist = np.linalg.norm(to_hazard)
                
                # Check danger zones
                danger_level = 0
                for zone in hazard['danger_zones']:
                    if dist < zone['radius']:
                        danger_level = zone['intensity']
                
                if danger_level > 0:
                    if hazard['type'] == 'tornado':
                        # Tornado: Confusion and spin effect
                        if danger_level > 0.5:
                            self.hazards_encountered['tornado'] += 1 / (self.config.n_agents * 30)  # Normalize
                            
                            # Spin effect (stronger at center)
                            tangent = np.array([-to_hazard[1], to_hazard[0]]) / dist
                            spin_force = tangent * hazard['confusion_strength'] * danger_level * hazard['spin_rate']
                            agent.velocity += spin_force * dt
                            
                            # Random confusion
                            confusion = self.rng.normal(0, hazard['confusion_strength'] * danger_level, 2)
                            agent.velocity += confusion * dt
                            
                            # Energy drain
                            agent.energy = max(0, agent.energy - hazard['energy_drain'] * danger_level * self.breed.energy_efficiency)
                            
                            # Kill chance (only in death zone)
                            if danger_level >= 1.0 and self.rng.random() < hazard['kill_chance'] * dt:
                                agent.alive = False
                                self.losses += 1
                                logger.info(f"🌪️ Bird lost in tornado! Losses: {self.losses}")
                        
                        # Stress from proximity
                        agent.stress = min(1.0, agent.stress + 0.05 * danger_level * (1 - self.breed.stress_resilience))
                    
                    elif hazard['type'] == 'predator':
                        # Predator: Direct pursuit and flock panic
                        detection_dist = hazard['detection_range'] * agent.hazard_detection
                        
                        if dist < detection_dist:
                            self.hazards_encountered['predator'] += 1 / (self.config.n_agents * 30)
                            
                            # Escape response (stronger with awareness)
                            escape_strength = 200 * danger_level * agent.hazard_detection
                            escape = -to_hazard / dist * escape_strength
                            agent.velocity += escape * dt
                            
                            # Trigger panic in nearby birds
                            if hazard.get('trigger_panic') and danger_level > 0.8:
                                self.trigger_flock_panic(agent.position, radius=150)
                            
                            # High stress
                            agent.stress = min(1.0, agent.stress + 0.2 * danger_level * (1 - self.breed.stress_resilience))
                            
                            # Attack zone
                            if dist < hazard['attack_range']:
                                if self.rng.random() < hazard['kill_chance'] * dt:
                                    agent.alive = False
                                    self.losses += 1
                                    hazard['last_kill_time'] = self.tick
                                    logger.info(f"🦅 Predator strike! Losses: {self.losses}")
                                    # Trigger major panic after kill
                                    self.trigger_flock_panic(agent.position, radius=200, intensity=2.0)
                                else:
                                    self.close_calls += 1
            
            # 5. Energy management (breed efficiency) - reduced consumption for beacon timing
            base_consumption = 0.01 * self.breed.energy_efficiency
            stress_consumption = 0.02 * agent.stress
            agent.energy = max(0, agent.energy - (base_consumption + stress_consumption))
            
            if agent.energy <= 0:
                agent.alive = False
                self.losses += 1
                logger.info(f"Exhaustion. Losses: {self.losses}")
            
            # 6. Speed limits (adjusted by breed)
            speed = np.linalg.norm(agent.velocity)
            max_speed = (80 if agent.energy > 50 else 60) * (1 + self.breed.energy_efficiency * 0.1)
            if speed > max_speed:
                agent.velocity = (agent.velocity / speed) * max_speed
            
            # 7. Update position
            agent.position += agent.velocity * dt
            
            # 8. Boundaries
            agent.position[0] = np.clip(agent.position[0], 0, 2000)
            agent.position[1] = np.clip(agent.position[1], 0, 1200)
            
            # 9. Check arrival (birds reaching destination are marked as not alive but this is ARRIVAL, not death)
            if dist_to_dest < dest_r:
                self.arrivals += 1
                agent.alive = False  # Remove from simulation - they've reached safety!
                logger.info(f"✅ SAFE ARRIVAL! Bird {agent.id} reached destination. Total: {self.arrivals}/{self.config.target_arrivals}")
                
            if agent.alive:
                alive_agents.append(agent)
        
        # Update active effects
        self.active_pulses = [p for p in self.active_pulses if p['remaining'] > 0]
        for pulse in self.active_pulses:
            pulse['remaining'] -= dt
        
        # Check win/loss
        if self.arrivals >= self.config.target_arrivals:
            self.victory = True
            self.game_over = True
            self.breed.successful_migrations += 1
            logger.info(f"VICTORY! Breed '{self.breed.name}' succeeds!")
        elif self.losses > self.config.max_losses:
            self.game_over = True
            logger.info(f"DEFEAT! Breed needs more training")
        elif time.time() - self.start_time > self.config.time_limit_seconds:
            self.game_over = True
            logger.info(f"TIME UP! Partial success: {self.arrivals} arrivals")
        
        # Cleanup expired beacons
        self.beacon_manager.cleanup_expired_beacons(Tick(self.tick))
        
        # Calculate survival rate for evolution
        survival_rate = (self.config.n_agents - self.losses) / self.config.n_agents
        
        return {
            'tick': self.tick,
            'agents': alive_agents,
            'population': len(alive_agents),
            'arrivals': self.arrivals,
            'losses': self.losses,
            'beacons': [
                {
                    'id': beacon.beacon_id,
                    'type': beacon.beacon_type.value,
                    'x': float(beacon.position[0]),
                    'y': float(beacon.position[1]),
                    'radius': beacon.spec.radius,
                    'strength': beacon.get_field_strength(beacon.position, Tick(self.tick)),
                    'cost': beacon.spec.cost,
                    'decay': beacon.get_temporal_decay(Tick(self.tick))
                }
                for beacon in self.beacon_manager.beacons
            ],
            'hazards': self.hazards,
            'destination': self.config.destination_zone,
            'game_over': self.game_over,
            'victory': self.victory,
            'time_remaining': max(0, self.config.time_limit_seconds - (time.time() - self.start_time)),
            'cohesion': self.calculate_cohesion(alive_agents),
            'breed': self.breed.to_dict(),
            'survival_rate': survival_rate,
            'close_calls': self.close_calls,
            'panic_events': self.panic_events
        }
    
    def trigger_flock_panic(self, origin: np.ndarray, radius: float = 150, intensity: float = 1.0):
        """Trigger panic response in nearby birds."""
        self.panic_events += 1
        for agent in self.agents:
            if not agent.alive:
                continue
            
            dist = np.linalg.norm(agent.position - origin)
            if dist < radius:
                # Scatter response
                panic_factor = (1 - dist / radius) * intensity
                scatter = (agent.position - origin) / (dist + 1) * 100 * panic_factor
                agent.velocity += scatter
                agent.stress = min(1.0, agent.stress + 0.3 * panic_factor)
    
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
        
        distances = []
        for agent in agents[:20]:  # Sample
            neighbors = self.get_neighbors(agent, radius=200)
            if neighbors:
                min_dist = min(np.linalg.norm(agent.position - n.position) for n in neighbors)
                distances.append(min_dist)
        
        if not distances:
            return 0.0
        
        avg_dist = np.mean(distances)
        return max(0, min(1, 1 - avg_dist / 200))
    
    def place_beacon(self, beacon_type: str, x: float, y: float) -> bool:
        """Place a beacon using the sophisticated BeaconManager system."""
        # Map client beacon types to BeaconType enum
        type_mapping = {
            'food': BeaconType.FOOD_SCENT,
            'shelter': BeaconType.SOUND,  # Sound beacons provide cohesion/shelter effect
            'thermal': BeaconType.WIND_LURE  # Wind lures provide forward boost like thermals
        }
        
        if beacon_type not in type_mapping:
            logger.warning(f"Unknown beacon type: {beacon_type}")
            return False
        
        mapped_type = type_mapping[beacon_type]
        position = create_vector2d(x, y)
        
        # Try to place the beacon
        beacon = self.beacon_manager.place_beacon(mapped_type, position, Tick(self.tick))
        
        if beacon:
            logger.info(f"Beacon placed: {beacon_type} -> {mapped_type.value} at ({x:.0f}, {y:.0f})")
            return True
        else:
            logger.warning(f"Beacon placement failed: budget exceeded or invalid position")
            return False
    
    def activate_pulse(self, pulse_type: str) -> bool:
        """Activate a pulse effect."""
        current_time = time.time()
        if current_time - self.last_pulse_time < self.config.pulse_cooldown:
            return False
        
        self.active_pulses.append({
            'type': pulse_type,
            'remaining': 2.0
        })
        self.last_pulse_time = current_time
        logger.info(f"Pulse activated: {pulse_type}")
        return True
    
    def evolve_breed(self):
        """Evolve the breed based on this level's performance."""
        if self.game_over:
            survival_rate = (self.config.n_agents - self.losses) / self.config.n_agents
            self.breed.evolve(survival_rate, self.hazards_encountered)
            
            # Update experience
            self.breed.total_distance += sum(np.linalg.norm(a.velocity) for a in self.agents) * self.tick / 30
            
            logger.info(f"Breed evolved to Gen {self.breed.generation}, Survival rate: {survival_rate:.1%}")
    
    def save_breed(self, filepath: str):
        """Save breed to file."""
        with open(filepath, 'w') as f:
            json.dump(self.breed.to_dict(), f, indent=2)
        logger.info(f"Breed saved: {filepath}")
    
    def reset(self):
        """Complete reset for new attempt."""
        # Clear all game state
        self.agents.clear()
        self.beacon_manager = BeaconManager(budget_limit=self.config.beacon_budget)  # Reset beacon manager
        self.active_pulses.clear()
        self.hazards.clear()
        
        # Reset counters
        self.tick = 0
        self.arrivals = 0
        self.losses = 0
        self.game_over = False
        self.victory = False
        self.close_calls = 0
        self.panic_events = 0
        self.hazards_encountered = {'tornado': 0, 'predator': 0, 'storm': 0}
        
        # Reinitialize
        self.__init__(self.config)
        logger.info("Simulation fully reset")