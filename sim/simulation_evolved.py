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
    migration_number: int = 1  # New: tracks migration progression for scaling
    
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
    def from_level(cls, level_name: str, seed: int = 42, breed: Optional[Breed] = None, migration_number: int = 1, n_agents: Optional[int] = None):
        """Load config from level JSON with migration-based scaling."""
        levels_file = Path(__file__).parent.parent / "levels" / "levels.json"
        if levels_file.exists():
            with open(levels_file) as f:
                levels = json.load(f)
                
            if level_name in levels:
                level_data = levels[level_name]
                
                # Apply migration-based scaling
                scaled_data = cls._apply_difficulty_scaling(level_data, migration_number)
                
                return cls(
                    level=level_name,
                    seed=seed,
                    breed=breed or Breed(),
                    migration_number=migration_number,
                    n_agents=n_agents if n_agents is not None else scaled_data.get('n_agents', 100),
                    start_zone=tuple(scaled_data.get('start_zone', [200, 600, 100])),
                    destination_zone=tuple(scaled_data.get('destination_zone', [1800, 600, 150])),
                    target_arrivals=scaled_data.get('target_arrivals', 80),
                    max_losses=scaled_data.get('max_losses', 20),
                    time_limit_seconds=scaled_data.get('time_limit', 120),
                    beacon_budget=scaled_data.get('beacon_budget', 4),
                    level_hazards=scaled_data.get('hazards', [])
                )
        
        return cls(level=level_name, seed=seed, breed=breed or Breed(), migration_number=migration_number, n_agents=n_agents or 100)
    
    @staticmethod
    def _apply_difficulty_scaling(level_data: Dict, migration_number: int) -> Dict:
        """Apply progressive difficulty scaling based on migration number."""
        import copy
        scaled_data = copy.deepcopy(level_data)
        
        # Base difficulty multiplier (1.0 = normal, higher = more difficult)
        difficulty_mult = 1.0 + (migration_number - 1) * 0.15
        
        # Scale hazards - increase count, size, and intensity
        if 'hazards' in scaled_data:
            for hazard in scaled_data['hazards']:
                # Increase hazard radius by 5-10% per migration
                if 'radius' in hazard:
                    hazard['radius'] = int(hazard['radius'] * (1.0 + (migration_number - 1) * 0.08))
                
                # Increase hazard strength/danger
                if 'strength' in hazard:  # storms
                    hazard['strength'] = int(hazard['strength'] * difficulty_mult)
                if 'danger' in hazard:  # predators
                    hazard['danger'] = min(1.0, hazard['danger'] * (1.0 + (migration_number - 1) * 0.1))
                if 'speed' in hazard:  # predator speed
                    hazard['speed'] = int(hazard['speed'] * (1.0 + (migration_number - 1) * 0.05))
        
        # Reduce beacon budget for higher migrations (force more strategic play)
        if migration_number > 3:
            scaled_data['beacon_budget'] = max(2, scaled_data.get('beacon_budget', 4) - 1)
        
        # Increase population slightly to maintain challenge despite evolution
        if migration_number > 2:
            scaled_data['n_agents'] = int(scaled_data.get('n_agents', 100) * (1.0 + (migration_number - 2) * 0.1))
        
        # Tighter time limits for advanced migrations
        if migration_number > 4:
            scaled_data['time_limit'] = int(scaled_data.get('time_limit', 120) * 0.9)
        
        return scaled_data


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
            
            # Initial velocity with breed influence - REDUCED BY 20%
            agent.velocity = np.array([
                self.rng.uniform(4, 12) * (1 + self.breed.energy_efficiency * 0.1),  # Reduced from 5-15 to 4-12
                self.rng.uniform(-1.5, 1.5)  # Slightly reduced vertical speed
            ])
            
            # Apply breed traits - increased starting energy for better beacon timing
            # Adjust base energy based on migration difficulty
            base_energy = 100.0 * (1 + self.breed.energy_efficiency * 0.1)  # Start at 100%, not 300%
            if config.migration_number > 3:  # Later migrations get slightly less starting energy
                base_energy *= (0.95 - (config.migration_number - 3) * 0.02)
            agent.energy = base_energy
            agent.stress = max(0.3, 0.5 - self.breed.stress_resilience * 0.2)  # Higher base stress
            
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
        
        # Add food havens for energy restoration
        self.food_havens = [
            {'x': 600, 'y': 400, 'radius': 100},  # Early food haven
            {'x': 1000, 'y': 800, 'radius': 100},  # Mid journey haven
            {'x': 1400, 'y': 600, 'radius': 100}   # Late journey haven
        ]
        
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
    
    def get_current_state(self) -> Dict[str, Any]:
        """Get current state without stepping the simulation."""
        # Calculate alive agents
        alive_agents = [agent for agent in self.agents if agent.alive]
        
        # Calculate survival rate for evolution
        survival_rate = (self.config.n_agents - self.losses) / self.config.n_agents if self.config.n_agents > 0 else 0
        
        # Convert agents to dictionary format for client
        agents_data = [
            {
                'id': agent.id,
                'x': float(agent.position[0]),
                'y': float(agent.position[1]),
                'vx': float(agent.velocity[0]),
                'vy': float(agent.velocity[1]),
                'energy': float(agent.energy),
                'stress': float(agent.stress),
                'alive': agent.alive
            }
            for agent in alive_agents
        ]
        
        return {
            'tick': self.tick,
            'agents': agents_data,
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
            'food_havens': self.food_havens,
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
            
            # Wind up force - only strongly affects birds in direct contact
            if contributions["wind_up_force"] > 0:
                # Stronger effect for higher field strength (closer to beacon)
                contact_intensity = contributions["wind_up_force"]  # 0-1 based on distance
                
                # Only birds in strong contact (>0.7) get direct wind force
                if contact_intensity > 0.7:
                    wind_force = contact_intensity * beacon_response * 25  # Strong direct push
                    agent.velocity[1] -= wind_force  # Negative Y = upward
                    agent.velocity[1] = max(agent.velocity[1], -18)
                    agent.energy = max(0, agent.energy - 0.05)
                # Birds in moderate contact (0.3-0.7) get weaker effect based on cohesion
                elif contact_intensity > 0.3:
                    cohesion_factor = self.breed.flock_cohesion * agent.beacon_response
                    wind_force = contact_intensity * cohesion_factor * 8  # Weaker indirect effect
                    agent.velocity[1] -= wind_force
                    agent.velocity[1] = max(agent.velocity[1], -8)
            
            # Wind down force - only strongly affects birds in direct contact
            if contributions["wind_down_force"] > 0:
                contact_intensity = contributions["wind_down_force"]
                
                # Only birds in strong contact get direct wind force
                if contact_intensity > 0.7:
                    wind_force = contact_intensity * beacon_response * 25  # Strong direct push
                    agent.velocity[1] += wind_force  # Positive Y = downward
                    agent.velocity[1] = min(agent.velocity[1], 18)
                    agent.energy = max(0, agent.energy - 0.05)
                # Birds in moderate contact get weaker effect based on cohesion
                elif contact_intensity > 0.3:
                    cohesion_factor = self.breed.flock_cohesion * agent.beacon_response
                    wind_force = contact_intensity * cohesion_factor * 8  # Weaker indirect effect
                    agent.velocity[1] += wind_force
                    agent.velocity[1] = min(agent.velocity[1], 8)
                # Small energy cost for fighting wind
                agent.energy = max(0, agent.energy - 0.05)
            
            # Food havens provide energy restoration
            for haven in self.food_havens:
                haven_dist = np.linalg.norm(agent.position - np.array([haven['x'], haven['y']]))
                if haven_dist < haven['radius']:
                    # Restore energy when in food haven
                    energy_gain = 0.5 * (1 - haven_dist / haven['radius'])  # More energy closer to center
                    agent.energy = min(100, agent.energy + energy_gain)
                    # Reduce stress in safe haven
                    agent.stress = max(0, agent.stress - 0.01)
            
            # 4. PHASE 2: Enhanced trait-based hazard responses
            for hazard in self.hazards:
                to_hazard = np.array([hazard['x'] - agent.position[0], hazard['y'] - agent.position[1]])
                dist = np.linalg.norm(to_hazard)
                
                # ENHANCED: Scale hazard detection by bird awareness traits
                base_detection_range = hazard.get('radius', 100)
                effective_detection_range = base_detection_range * (0.5 + agent.hazard_detection)
                
                # Check if hazard affects this agent (trait-scaled detection)
                if dist > effective_detection_range:
                    continue
                
                # Calculate danger level with trait influence
                danger_level = 0
                for zone in hazard.get('danger_zones', [{'radius': base_detection_range, 'intensity': 1.0}]):
                    adjusted_radius = zone['radius'] * (1.0 + agent.hazard_detection * 0.2)  # Better birds detect earlier
                    if dist < adjusted_radius:
                        danger_level = zone['intensity']
                
                if danger_level > 0:
                    if hazard['type'] == 'tornado' or hazard['type'] == 'storm':
                        # ENHANCED: Storm effects with stress resistance
                        if danger_level > 0.3:
                            self.hazards_encountered['tornado'] += 1 / (self.config.n_agents * 30)
                            
                            # Spin effect reduced by awareness and resilience
                            confusion_resistance = (agent.hazard_detection + self.breed.stress_resilience) / 2
                            effective_confusion = hazard.get('confusion_strength', 50) * (1 - confusion_resistance * 0.5)
                            
                            if dist > 0.1:  # Avoid division by zero
                                tangent = np.array([-to_hazard[1], to_hazard[0]]) / dist
                                spin_force = tangent * effective_confusion * danger_level * hazard.get('spin_rate', 0.1)
                                agent.velocity += spin_force * dt
                                
                                # Random confusion (reduced by awareness)
                                confusion_strength = effective_confusion * (1 - agent.hazard_detection * 0.4)
                                confusion = self.rng.normal(0, confusion_strength * danger_level, 2)
                                agent.velocity += confusion * dt
                            
                            # Energy drain modified by breed efficiency and stress resistance
                            base_drain = hazard.get('energy_drain', 20)
                            stress_protection = self.breed.stress_resilience * 0.5
                            actual_drain = base_drain * danger_level * self.breed.energy_efficiency * (1 - stress_protection)
                            agent.energy = max(0, agent.energy - actual_drain * dt)
                            
                            # Kill chance reduced by stress resistance
                            if danger_level >= 1.0:
                                survival_bonus = self.breed.stress_resilience * 0.3  # Up to 30% better survival
                                kill_chance = hazard.get('kill_chance', 0.1) * (1 - survival_bonus)
                                if self.rng.random() < kill_chance * dt:
                                    agent.alive = False
                                    self.losses += 1
                                    logger.info(f"🌪️ Bird lost in storm! Losses: {self.losses}")
                        
                        # ENHANCED: Stress effects with resistance trait
                        base_stress = 0.08 * danger_level
                        stress_resistance = self.breed.stress_resilience * 0.7
                        actual_stress = base_stress * (1 - stress_resistance)
                        agent.stress = min(1.0, agent.stress + actual_stress)
                    
                    elif hazard['type'] == 'predator':
                        # ENHANCED: Predator detection and response scaled by traits
                        detection_multiplier = 1.0 + agent.hazard_detection
                        detection_dist = hazard.get('detection_range', 150) * detection_multiplier
                        
                        if dist < detection_dist:
                            self.hazards_encountered['predator'] += 1 / (self.config.n_agents * 30)
                            
                            # Escape response scales with hazard awareness
                            base_escape = 180
                            awareness_boost = agent.hazard_detection * 1.5  # Up to 150% boost
                            escape_strength = base_escape * (1 + awareness_boost) * danger_level
                            
                            if dist > 0.1:
                                escape = -to_hazard / dist * escape_strength
                                agent.velocity += escape * dt
                            
                            # ENHANCED: Leadership-based flock cohesion during panic
                            if hazard.get('trigger_panic', True) and danger_level > 0.7:
                                # Calculate leadership influence on nearby birds
                                leadership_effect = getattr(agent, 'leadership', self.breed.flock_cohesion)
                                panic_radius = 120 + leadership_effect * 50  # Leaders help more birds
                                panic_intensity = 1.5 * (1 - leadership_effect * 0.3)  # Leaders reduce panic
                                self.trigger_flock_panic(agent.position, radius=panic_radius, intensity=panic_intensity)
                            
                            # Stress modified by stress resistance - predators cause high stress
                            base_stress = 0.4 * danger_level  # Increased from 0.25 - predators are scary!
                            stress_mitigation = self.breed.stress_resilience * 0.5  # Less mitigation
                            actual_stress = base_stress * (1 - stress_mitigation)
                            agent.stress = min(1.0, agent.stress + actual_stress)
                            
                            # Log stress increase for debugging
                            if actual_stress > 0.1:
                                logger.debug(f"🦅 Predator increased bird {agent.id} stress by {actual_stress:.2f} -> {agent.stress:.2f}")
                            
                            # Attack zone with trait-based survival chances
                            attack_range = hazard.get('attack_range', 50)
                            if dist < attack_range:
                                # Survival chances improved by awareness and stress resistance
                                base_kill_chance = hazard.get('kill_chance', 0.2)
                                awareness_survival = agent.hazard_detection * 0.4  # Up to 40% better
                                stress_survival = self.breed.stress_resilience * 0.2  # Up to 20% better
                                survival_bonus = min(0.8, awareness_survival + stress_survival)  # Max 80% reduction
                                
                                actual_kill_chance = base_kill_chance * (1 - survival_bonus)
                                
                                if self.rng.random() < actual_kill_chance * dt:
                                    agent.alive = False
                                    self.losses += 1
                                    hazard['last_kill_time'] = self.tick
                                    logger.info(f"🦅 Predator strike! Losses: {self.losses}")
                                    
                                    # Major panic with leadership mitigation
                                    leadership_factor = getattr(agent, 'leadership', self.breed.flock_cohesion)
                                    panic_intensity = 2.5 * (1 - leadership_factor * 0.4)
                                    self.trigger_flock_panic(agent.position, radius=250, intensity=panic_intensity)
                                else:
                                    self.close_calls += 1
            
            # 5. Energy management (breed efficiency)
            base_consumption = 0.03 * self.breed.energy_efficiency  # Reduced to 0.03 for balanced gameplay
            stress_consumption = 0.02 * agent.stress  # Stress adds minor impact
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
                logger.info(f"✅ SAFE ARRIVAL! Bird {agent.id} reached destination. Total: {self.arrivals}/{self.config.n_agents}")
            
            # Add to alive agents list if still alive (moved outside the arrival check)
            if agent.alive:
                alive_agents.append(agent)
        
        # Update active effects
        self.active_pulses = [p for p in self.active_pulses if p['remaining'] > 0]
        for pulse in self.active_pulses:
            pulse['remaining'] -= dt
        
        # Check win/loss - Victory when migration is complete (no more living birds can reach destination)
        if self.arrivals > 0 and not self.victory:
            # Check if all remaining birds are too exhausted to continue or if reasonable time has passed
            exhausted_birds = sum(1 for agent in alive_agents if agent.energy < 20)
            remaining_healthy = len(alive_agents) - exhausted_birds
            
            # Victory conditions:
            # 1. Any arrivals AND no healthy birds left to continue
            # 2. Any arrivals AND reasonable time elapsed (60+ seconds)
            time_elapsed = time.time() - self.start_time
            
            if remaining_healthy == 0 or time_elapsed > 60:
                self.victory = True
                self.game_over = True
                self.breed.successful_migrations += 1
                logger.info(f"VICTORY! {self.arrivals} birds completed migration!")
        elif not self.victory and len(alive_agents) == 0 and self.arrivals == 0:
            # Complete failure - all birds dead with no arrivals
            self.game_over = True
            logger.info(f"COMPLETE FAILURE! All {self.losses} birds lost before reaching destination")
        elif not self.victory and self.losses > self.config.max_losses:
            # Only trigger defeat if victory hasn't been achieved and we haven't checked complete failure
            self.game_over = True
            logger.info(f"DEFEAT! Too many losses: {self.losses}")
        elif not self.victory and time.time() - self.start_time > self.config.time_limit_seconds:
            # Time up - check if any birds made it
            if self.arrivals > 0:
                self.victory = True
                self.game_over = True
                logger.info(f"TIME UP! But {self.arrivals} birds made it - SUCCESS!")
            else:
                self.game_over = True
                logger.info(f"TIME UP! No birds reached destination - FAILURE!")
        
        # PHASE 2: Update hazard positions (moving storms and predator chases)
        self._update_hazard_positions(dt)
        
        # Cleanup expired beacons
        self.beacon_manager.cleanup_expired_beacons(Tick(self.tick))
        
        # Calculate survival rate for evolution
        survival_rate = (self.config.n_agents - self.losses) / self.config.n_agents
        
        # Convert agents to dictionary format for client
        agents_data = [
            {
                'id': agent.id,
                'x': float(agent.position[0]),
                'y': float(agent.position[1]),
                'vx': float(agent.velocity[0]),
                'vy': float(agent.velocity[1]),
                'energy': float(agent.energy),
                'stress': float(agent.stress),
                'alive': agent.alive
            }
            for agent in alive_agents
        ]
        
        return {
            'tick': self.tick,
            'agents': agents_data,
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
            'food_havens': self.food_havens,  # Send food havens to client
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
        # Map client beacon types to BeaconType enum - using wind beacons now
        type_mapping = {
            'wind_up': BeaconType.WIND_UP,
            'wind_down': BeaconType.WIND_DOWN
        }
        
        if beacon_type not in type_mapping:
            logger.warning(f"Unknown beacon type: {beacon_type}")
            return False
        
        mapped_type = type_mapping[beacon_type]
        position = create_vector2d(x, y)
        
        # Check budget before attempting placement
        if not self.beacon_manager.can_place_beacon(mapped_type):
            logger.warning(f"Beacon placement failed: budget exceeded ({self.beacon_manager.budget_used}/{self.beacon_manager.budget_limit})")
            return False
        
        # Try to place the beacon
        beacon = self.beacon_manager.place_beacon(mapped_type, position, Tick(self.tick))
        
        if beacon:
            logger.info(f"Beacon placed: {beacon_type} -> {mapped_type.value} at ({x:.0f}, {y:.0f}) [Budget: {self.beacon_manager.budget_used}/{self.beacon_manager.budget_limit}]")
            return True
        else:
            logger.warning(f"Beacon placement failed: invalid position or system error")
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
            # Avoid division by zero
            if self.config.n_agents == 0:
                survival_rate = 0
            else:
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
    
    def breed_survivors(self, survivors: List[Agent], target_population: int = 100) -> List[Dict]:
        """Breed survivors to create next migration's population.
        
        Args:
            survivors: List of surviving agents
            target_population: Target population for next migration
            
        Returns:
            List of breeding results with genetic information
        """
        if len(survivors) < 2:
            logger.warning("Insufficient survivors for breeding - need at least 2")
            return []
        
        # Separate males and females (assume 50/50 split based on ID)
        males = [a for a in survivors if int(a.id) % 2 == 0]
        females = [a for a in survivors if int(a.id) % 2 == 1]
        
        if not males or not females:
            # Create missing gender if needed
            if not males and females:
                males = females[:len(females)//2]  # Convert some females to males
                females = females[len(females)//2:]
            elif not females and males:
                females = males[:len(males)//2]  # Convert some males to females
                males = males[len(males)//2:]
        
        breeding_pairs = []
        offspring_data = []
        
        # Create breeding pairs - prioritize high-fitness individuals
        survivors_by_fitness = sorted(survivors, 
                                    key=lambda a: a.energy + (100 if a.alive else 0) - a.stress * 50, 
                                    reverse=True)
        
        males_sorted = [a for a in survivors_by_fitness if int(a.id) % 2 == 0]
        females_sorted = [a for a in survivors_by_fitness if int(a.id) % 2 == 1]
        
        # Form pairs
        max_pairs = min(len(males_sorted), len(females_sorted))
        for i in range(max_pairs):
            breeding_pairs.append((males_sorted[i], females_sorted[i]))
        
        # Generate offspring
        offspring_per_pair = max(1, target_population // max_pairs) if max_pairs > 0 else 0
        current_id = 0
        
        for male, female in breeding_pairs:
            for _ in range(offspring_per_pair):
                if len(offspring_data) >= target_population:
                    break
                    
                # Inherit traits from parents (simple genetic mixing)
                offspring = {
                    'id': current_id,
                    'parent_male_id': int(male.id),
                    'parent_female_id': int(female.id),
                    'gender': 'male' if current_id % 2 == 0 else 'female',
                    'inherited_energy': (male.energy + female.energy) / 2,
                    'inherited_stress_resistance': min(1.0, (
                        (1.0 - male.stress) + (1.0 - female.stress)) / 2),
                    'generation': self.breed.generation + 1
                }
                offspring_data.append(offspring)
                current_id += 1
                
            if len(offspring_data) >= target_population:
                break
        
        # Fill remaining population if needed
        while len(offspring_data) < target_population and breeding_pairs:
            # Use best pairs to fill gaps
            best_male, best_female = breeding_pairs[0]
            offspring = {
                'id': current_id,
                'parent_male_id': int(best_male.id),
                'parent_female_id': int(best_female.id),
                'gender': 'male' if current_id % 2 == 0 else 'female',
                'inherited_energy': (best_male.energy + best_female.energy) / 2,
                'inherited_stress_resistance': min(1.0, (
                    (1.0 - best_male.stress) + (1.0 - best_female.stress)) / 2),
                'generation': self.breed.generation + 1
            }
            offspring_data.append(offspring)
            current_id += 1
        
        logger.info(f"Breeding complete: {len(survivors)} survivors -> {len(offspring_data)} offspring")
        return offspring_data
    
    def prepare_next_migration(self, offspring_data: List[Dict], new_config: 'GameConfig') -> None:
        """Prepare simulation for next migration with new population.
        
        Args:
            offspring_data: Breeding results from breed_survivors
            new_config: Configuration for next migration leg
        """
        # Update config and breed
        self.config = new_config
        self.breed.generation += 1
        
        # Clear current state
        self.agents.clear()
        self.beacon_manager = BeaconManager(budget_limit=self.config.beacon_budget)
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
        self.start_time = time.time()
        
        # Create new population from offspring
        for offspring in offspring_data:
            agent = create_agent(AgentID(offspring['id']), rng=self.rng)
            
            # Place in start zone
            angle = self.rng.uniform(0, 2 * np.pi)
            radius = self.rng.uniform(0, self.config.start_zone[2])
            agent.position = np.array([
                self.config.start_zone[0] + radius * np.cos(angle),
                self.config.start_zone[1] + radius * np.sin(angle)
            ])
            
            # Apply inherited traits
            base_energy = offspring.get('inherited_energy', 300.0)
            agent.energy = base_energy * (1 + self.breed.energy_efficiency * 0.1)
            agent.stress = max(0, 0.3 - offspring.get('inherited_stress_resistance', 0.5))
            
            # Initial velocity with some variation
            agent.velocity = np.array([
                self.rng.uniform(8, 18) * (1 + self.breed.energy_efficiency * 0.1),
                self.rng.uniform(-3, 3)
            ])
            
            # Apply breed-specific attributes  
            agent.hazard_detection = self.breed.hazard_awareness
            agent.beacon_response = self.breed.beacon_sensitivity
            
            # Store genetic info for tracking
            agent.parent_male_id = offspring.get('parent_male_id', -1)
            agent.parent_female_id = offspring.get('parent_female_id', -1)
            agent.gender = offspring.get('gender', 'unknown')
            
            self.agents.append(agent)
        
        # Initialize hazards and other game elements
        self._initialize_level_hazards()
        
        logger.info(f"Next migration prepared: Gen {self.breed.generation}, Population {len(self.agents)}")
    
    def _initialize_level_hazards(self):
        """Initialize hazards from config with enhanced movement mechanics."""
        if not self.config.level_hazards:
            return
            
        for hazard_data in self.config.level_hazards:
            hazard = hazard_data.copy()
            hazard['id'] = len(self.hazards)
            
            # PHASE 2: Enhanced movement mechanics for storms
            if hazard.get('type') == 'storm':
                # Add movement vector if not specified
                if 'movement_vector' not in hazard:
                    direction = hazard.get('direction', [0, 0])
                    if direction == [0, 0] and hazard.get('rotating', False):
                        # Stationary rotating storm
                        hazard['movement_vector'] = [0, 0]
                    else:
                        # Moving storm - calculate movement from direction
                        speed = hazard.get('movement_speed', 10.0)  # Default 10 units/tick
                        hazard['movement_vector'] = [direction[0] * speed, direction[1] * speed]
                
                # Add predictive path data for strategic planning
                hazard['predicted_path'] = self._calculate_storm_path(
                    start_pos=[hazard.get('x', 0), hazard.get('y', 0)],
                    movement_vector=hazard.get('movement_vector', [0, 0]),
                    duration_ticks=300  # 5 seconds at 60fps
                )
                
                # Enhanced storm properties for Phase 2
                if not hazard.get('initialized_phase2', False):
                    hazard['last_position'] = [hazard.get('x', 0), hazard.get('y', 0)]
                    hazard['spawn_tick'] = self.tick
                    hazard['initialized_phase2'] = True
                    
            # PHASE 2: Enhanced predator mechanics preparation  
            elif hazard.get('type') == 'predator':
                if not hazard.get('initialized_phase2', False):
                    hazard['target_agent_id'] = None
                    hazard['chase_duration'] = 0
                    hazard['exhaustion_level'] = 0.0
                    hazard['last_position'] = [hazard.get('x', 0), hazard.get('y', 0)]
                    hazard['initialized_phase2'] = True
                    
            self.hazards.append(hazard)
            
        logger.info(f"Initialized {len(self.hazards)} hazards with Phase 2 enhancements")
    
    def _calculate_storm_path(self, start_pos: List[float], movement_vector: List[float], duration_ticks: int) -> List[List[float]]:
        """Calculate predicted path for moving storm.
        
        Args:
            start_pos: Starting position [x, y]
            movement_vector: Movement per tick [dx, dy]
            duration_ticks: How many ticks to predict
            
        Returns:
            List of predicted positions [[x, y], ...]
        """
        path = []
        current_pos = start_pos.copy()
        
        for tick in range(0, duration_ticks, 10):  # Sample every 10 ticks
            path.append(current_pos.copy())
            current_pos[0] += movement_vector[0] * 10  # 10 ticks forward
            current_pos[1] += movement_vector[1] * 10
            
            # Keep within world bounds for visualization
            current_pos[0] = max(0, min(2000, current_pos[0]))
            current_pos[1] = max(0, min(1200, current_pos[1]))
            
        return path
    
    def _update_hazard_positions(self, dt: float) -> None:
        """Update positions of moving hazards (storms and predators).
        
        Args:
            dt: Time delta in seconds
        """
        for hazard in self.hazards:
            hazard_type = hazard.get('type', 'unknown')
            
            # MOVING STORMS: Update position based on movement vector
            if hazard_type == 'storm' and hazard.get('movement_vector', [0, 0]) != [0, 0]:
                # Store previous position
                hazard['last_position'] = [hazard.get('x', 0), hazard.get('y', 0)]
                
                # Move storm according to movement vector
                movement = hazard['movement_vector']
                hazard['x'] += movement[0] * dt * 30  # Scale by frame rate (30 FPS)
                hazard['y'] += movement[1] * dt * 30
                
                # Keep storm within world bounds or allow it to move off-screen
                hazard['x'] = max(-200, min(2200, hazard['x']))  # Allow slight off-screen
                hazard['y'] = max(-200, min(1400, hazard['y']))
                
                # Update predicted path if needed (every 30 ticks = 1 second)
                if self.tick % 30 == 0:
                    hazard['predicted_path'] = self._calculate_storm_path(
                        start_pos=[hazard['x'], hazard['y']],
                        movement_vector=hazard['movement_vector'],
                        duration_ticks=300
                    )
                
                # Log storm movement occasionally
                if self.tick % 180 == 0:  # Every 3 seconds
                    logger.debug(f"Storm {hazard['id']} moved to ({hazard['x']:.1f}, {hazard['y']:.1f})")
            
            # PREDATOR CHASES: Enhanced movement logic (basic implementation for Phase 2)
            elif hazard_type == 'predator':
                if not hazard.get('target_agent_id'):
                    # Find nearest target if no current target
                    alive_agents = [a for a in self.agents if a.alive]
                    if alive_agents:
                        hazard_pos = np.array([hazard.get('x', 0), hazard.get('y', 0)])
                        distances = [(np.linalg.norm(a.position - hazard_pos), a.id) for a in alive_agents]
                        distances.sort()
                        
                        # Target closest agent within detection range
                        detection_range = hazard.get('radius', 100) * 1.5
                        if distances and distances[0][0] <= detection_range:
                            hazard['target_agent_id'] = distances[0][1]
                            hazard['chase_duration'] = 0
                            predator_id = hazard.get('id', f"predator_{hazard.get('x', 0)}_{hazard.get('y', 0)}")
                            logger.debug(f"Predator {predator_id} targeting agent {distances[0][1]}")
                
                # Chase current target if exists
                if hazard.get('target_agent_id'):
                    target_agent = next((a for a in self.agents if a.alive and a.id == hazard['target_agent_id']), None)
                    if target_agent:
                        # Move toward target
                        hazard_pos = np.array([hazard.get('x', 0), hazard.get('y', 0)])
                        to_target = target_agent.position - hazard_pos
                        distance = np.linalg.norm(to_target)
                        
                        if distance > 5:  # Don't get too close
                            chase_speed = hazard.get('speed', 6) * 0.8 * (1.0 - hazard.get('exhaustion_level', 0) * 0.5)  # Reduced by 20%
                            move_vector = (to_target / distance) * chase_speed * dt * 30
                            
                            hazard['x'] += move_vector[0]
                            hazard['y'] += move_vector[1]
                            
                            # Keep within bounds
                            hazard['x'] = max(0, min(2000, hazard['x']))
                            hazard['y'] = max(0, min(1200, hazard['y']))
                        
                        # Increase chase duration and exhaustion
                        hazard['chase_duration'] += dt
                        if hazard['chase_duration'] > 10:  # 10 seconds max chase
                            hazard['exhaustion_level'] = min(1.0, hazard.get('exhaustion_level', 0) + 0.1)
                            if hazard['exhaustion_level'] >= 0.8:  # Give up when exhausted
                                hazard['target_agent_id'] = None
                                hazard['chase_duration'] = 0
                                logger.debug(f"Predator {hazard.get('id', 'unknown')} gave up chase due to exhaustion")
                    else:
                        # Target no longer exists
                        hazard['target_agent_id'] = None
                        hazard['chase_duration'] = 0

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