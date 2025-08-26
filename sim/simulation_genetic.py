"""Genetic evolution simulation with breeding pairs and inheritance.

This module implements individual genetic evolution through breeding,
where survivors pair up to produce offspring with inherited traits.
"""

import time
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import json
from pathlib import Path

from .core.agent import Agent, create_agent
from .core.types import AgentID
from .utils.logging import get_logger

logger = get_logger("genetic_simulation")


class Gender(Enum):
    """Bird gender for breeding."""
    MALE = "male"
    FEMALE = "female"


@dataclass
class Genetics:
    """Individual bird genetics."""
    # Core traits (0-1 scale)
    hazard_awareness: float = 0.5
    energy_efficiency: float = 0.5
    flock_cohesion: float = 0.5
    beacon_sensitivity: float = 0.5
    stress_resilience: float = 0.5
    
    # Physical traits (affect appearance)
    size_factor: float = 1.0  # 0.8-1.2
    speed_factor: float = 1.0  # 0.9-1.1
    
    # Hidden traits (affect survival)
    fertility: float = 1.0  # Chance to successfully breed
    longevity: float = 1.0  # Resistance to exhaustion
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'hazard_awareness': self.hazard_awareness,
            'energy_efficiency': self.energy_efficiency,
            'flock_cohesion': self.flock_cohesion,
            'beacon_sensitivity': self.beacon_sensitivity,
            'stress_resilience': self.stress_resilience,
            'size_factor': self.size_factor,
            'speed_factor': self.speed_factor,
            'fertility': self.fertility,
            'longevity': self.longevity
        }
    
    @classmethod
    def random(cls, rng: np.random.Generator):
        """Generate random genetics for Gen 0."""
        return cls(
            hazard_awareness=rng.uniform(0.3, 0.7),
            energy_efficiency=rng.uniform(0.4, 0.6),
            flock_cohesion=rng.uniform(0.4, 0.6),
            beacon_sensitivity=rng.uniform(0.4, 0.6),
            stress_resilience=rng.uniform(0.3, 0.7),
            size_factor=rng.uniform(0.9, 1.1),
            speed_factor=rng.uniform(0.95, 1.05),
            fertility=rng.uniform(0.8, 1.0),
            longevity=rng.uniform(0.8, 1.0)
        )
    
    @classmethod
    def mutate(cls, base: 'Genetics', rng: np.random.Generator, mutation_rate: float = 0.1) -> 'Genetics':
        """Create a mutated version of genetics for population filling."""
        mutated = cls()
        
        # Copy base genetics with mutations
        for trait in ['hazard_awareness', 'energy_efficiency', 'flock_cohesion', 
                     'beacon_sensitivity', 'stress_resilience', 'fertility', 'longevity']:
            base_value = getattr(base, trait)
            if rng.random() < mutation_rate:
                # Apply mutation
                mutation = rng.normal(0, 0.1)
                new_value = np.clip(base_value + mutation, 0, 1)
            else:
                # Keep base value
                new_value = base_value
            setattr(mutated, trait, new_value)
        
        # Physical traits
        mutated.size_factor = np.clip(base.size_factor + rng.normal(0, 0.05), 0.8, 1.2)
        mutated.speed_factor = np.clip(base.speed_factor + rng.normal(0, 0.05), 0.8, 1.2)
        mutated.color_hue = (base.color_hue + rng.uniform(-0.1, 0.1)) % 1.0
        
        return mutated
    
    @classmethod
    def breed(cls, parent1: 'Genetics', parent2: 'Genetics', rng: np.random.Generator) -> 'Genetics':
        """Create offspring genetics from two parents with more interesting inheritance."""
        child = cls()
        
        # Define trait relationships (some traits are linked)
        trait_groups = {
            'survival': ['hazard_awareness', 'stress_resilience'],
            'efficiency': ['energy_efficiency', 'longevity'],
            'social': ['flock_cohesion', 'beacon_sensitivity'],
            'breeding': ['fertility']
        }
        
        # Inherit trait groups together sometimes
        for group_name, traits in trait_groups.items():
            # 40% chance to inherit the whole group from one parent
            if rng.random() < 0.4:
                parent = parent1 if rng.random() < 0.5 else parent2
                for trait in traits:
                    value = getattr(parent, trait)
                    # Small mutation
                    mutation = rng.normal(0, 0.03)
                    value = np.clip(value + mutation, 0, 1)
                    setattr(child, trait, value)
            else:
                # Inherit traits individually
                for trait in traits:
                    # Dominant/recessive model
                    p1_value = getattr(parent1, trait)
                    p2_value = getattr(parent2, trait)
                    
                    # Higher values are "dominant"
                    if abs(p1_value - p2_value) > 0.3:
                        # Large difference - dominant trait wins more often
                        dominant = max(p1_value, p2_value)
                        recessive = min(p1_value, p2_value)
                        value = dominant if rng.random() < 0.75 else recessive
                    else:
                        # Similar values - blend them
                        value = p1_value * rng.uniform(0.3, 0.7) + p2_value * (1 - rng.uniform(0.3, 0.7))
                    
                    # Mutation with variable rate based on generation stress
                    mutation_rate = 0.05
                    if rng.random() < 0.1:  # 10% chance of larger mutation
                        mutation_rate = 0.15
                    
                    mutation = rng.normal(0, mutation_rate)
                    value = np.clip(value + mutation, 0, 1)
                    
                    setattr(child, trait, value)
        
        # Physical traits with correlated inheritance
        # Size and speed are inversely correlated
        if rng.random() < 0.6:  # 60% chance of correlation
            parent = parent1 if rng.random() < 0.5 else parent2
            child.size_factor = getattr(parent, 'size_factor') + rng.normal(0, 0.03)
            # Larger birds are slower
            child.speed_factor = 2.0 - child.size_factor + rng.normal(0, 0.02)
        else:
            # Independent inheritance
            child.size_factor = (parent1.size_factor + parent2.size_factor) / 2 + rng.normal(0, 0.03)
            child.speed_factor = (parent1.speed_factor + parent2.speed_factor) / 2 + rng.normal(0, 0.03)
        
        child.size_factor = np.clip(child.size_factor, 0.7, 1.3)
        child.speed_factor = np.clip(child.speed_factor, 0.8, 1.2)
        
        # Rare chance of "super mutation" for interesting evolution jumps
        if rng.random() < 0.02:  # 2% chance
            super_trait = rng.choice(['hazard_awareness', 'energy_efficiency', 'stress_resilience'])
            setattr(child, super_trait, min(1.0, getattr(child, super_trait) + 0.2))
            logger.info(f"Super mutation! {super_trait} boosted in offspring")
        
        return child


@dataclass
class BirdEntity:
    """Extended bird with genetics and family."""
    agent: Agent
    gender: Gender
    genetics: Genetics
    generation: int = 0
    
    # Family tracking
    parent1_id: Optional[AgentID] = None
    parent2_id: Optional[AgentID] = None
    offspring_ids: List[AgentID] = field(default_factory=list)
    partner_id: Optional[AgentID] = None  # Current breeding partner
    
    # Lifetime stats
    survived_levels: int = 0
    close_calls: int = 0
    total_distance: float = 0.0
    
    @property
    def fitness_score(self) -> float:
        """Calculate overall fitness for breeding selection."""
        # Higher fitness = better genes + survival experience
        base_fitness = (
            self.genetics.hazard_awareness * 0.3 +
            self.genetics.energy_efficiency * 0.2 +
            self.genetics.flock_cohesion * 0.2 +
            self.genetics.stress_resilience * 0.2 +
            self.genetics.longevity * 0.1
        )
        
        # Bonus for survival experience
        experience_bonus = min(0.3, self.survived_levels * 0.1)
        
        return base_fitness + experience_bonus


@dataclass
class PopulationStats:
    """Population-level statistics."""
    total_population: int = 0
    males: int = 0
    females: int = 0
    
    # Genetic diversity
    avg_hazard_awareness: float = 0.0
    avg_energy_efficiency: float = 0.0
    avg_flock_cohesion: float = 0.0
    avg_beacon_sensitivity: float = 0.0
    avg_stress_resilience: float = 0.0
    
    genetic_diversity: float = 0.0  # 0 = clones, 1 = max diversity
    inbreeding_coefficient: float = 0.0
    
    # Dynasties
    top_bloodlines: List[Dict] = field(default_factory=list)
    hall_of_fame: List[Dict] = field(default_factory=list)


class GeneticSimulation:
    """Simulation with genetic breeding mechanics."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rng = np.random.default_rng(config.get('seed', 42))
        
        # Initialize population
        self.birds: Dict[AgentID, BirdEntity] = {}
        self.next_id = 0
        self.generation = 0
        
        # Game state
        self.tick = 0
        self.start_time = time.time()
        self.arrivals = 0
        self.losses = 0
        self.game_over = False
        self.victory = False
        
        # Breeding state
        self.breeding_pairs: List[Tuple[AgentID, AgentID]] = []
        self.offspring_queue: List[BirdEntity] = []
        
        # Statistics
        self.population_stats = self.calculate_population_stats()
        self.family_trees: Dict[AgentID, Dict] = {}  # Genealogy tracking
        
        # Level config
        self.level_name = config.get('level', 'W1-1')
        
        # Initialize level attributes before loading config
        self.start_zone = (200, 600, 100)
        self.destination_zone = (1800, 600, 150)
        self.target_arrivals = 80
        self.max_losses = 20
        self.time_limit = 120
        self.level_hazards = []
        
        # Load actual level config (will override defaults)
        self.load_level_config()
        
        # Hazards and beacons
        self.hazards: List[Dict] = []
        self.beacons: List[Dict] = []
        self.spawn_hazards()
        
        # Create initial population AFTER level config is loaded
        for i in range(config.get('n_agents', 100)):
            gender = Gender.MALE if i < 50 else Gender.FEMALE
            bird = self.create_bird(gender=gender, generation=0)
            self.birds[bird.agent.id] = bird
        
        logger.info(f"Genetic simulation initialized: {len(self.birds)} birds (Gen {self.generation})")
    
    def create_bird(self, gender: Gender = None, generation: int = 0, 
                   genetics: Genetics = None, parents: Tuple[AgentID, AgentID] = None) -> BirdEntity:
        """Create a new bird entity."""
        # Assign ID and create agent
        bird_id = AgentID(self.next_id)
        self.next_id += 1
        
        agent = create_agent(bird_id, rng=self.rng)
        
        # Random gender if not specified
        if gender is None:
            gender = Gender.MALE if self.rng.random() < 0.5 else Gender.FEMALE
        
        # Random genetics if not specified (Gen 0)
        if genetics is None:
            genetics = Genetics.random(self.rng)
        
        # Apply genetics to agent
        agent.hazard_detection = genetics.hazard_awareness
        agent.beacon_response = genetics.beacon_sensitivity
        agent.energy = 100.0 * genetics.longevity
        agent.stress = max(0, 0.2 * (1 - genetics.stress_resilience))
        
        # Position in start zone
        angle = self.rng.uniform(0, 2 * np.pi)
        radius = self.rng.uniform(0, self.start_zone[2])
        agent.position = np.array([
            self.start_zone[0] + radius * np.cos(angle),
            self.start_zone[1] + radius * np.sin(angle)
        ])
        
        # Initial velocity (generally eastward with some variation)
        base_speed = 5 * genetics.speed_factor  # Reduced from 10
        agent.velocity = np.array([
            self.rng.uniform(3, 7) * genetics.speed_factor,  # Mostly forward
            self.rng.uniform(-2, 2) * genetics.speed_factor   # Some up/down variation
        ])
        
        # Create bird entity
        bird = BirdEntity(
            agent=agent,
            gender=gender,
            genetics=genetics,
            generation=generation,
            parent1_id=parents[0] if parents else None,
            parent2_id=parents[1] if parents else None
        )
        
        # Track in family tree
        if parents:
            for parent_id in parents:
                if parent_id in self.birds:
                    self.birds[parent_id].offspring_ids.append(bird_id)
        
        return bird
    
    def load_level_config(self):
        """Load level configuration."""
        levels_file = Path(__file__).parent.parent / "levels" / "levels.json"
        if levels_file.exists():
            with open(levels_file) as f:
                levels = json.load(f)
                if self.level_name in levels:
                    level_data = levels[self.level_name]
                    self.start_zone = tuple(level_data.get('start_zone', [200, 600, 100]))
                    self.destination_zone = tuple(level_data.get('destination_zone', [1800, 600, 150]))
                    self.target_arrivals = level_data.get('target_arrivals', 80)
                    self.max_losses = level_data.get('max_losses', 20)
                    self.time_limit = level_data.get('time_limit', 120)
                    self.level_hazards = level_data.get('hazards', [])
                    return
    
    def reset_level(self, level_name: str):
        """Reset to a new level while keeping the existing birds."""
        self.level_name = level_name
        self.tick = 0
        self.start_time = time.time()
        self.arrivals = 0
        self.losses = 0
        self.game_over = False
        self.victory = False
        
        # Load new level configuration
        self.load_level_config()
        
        # Clear and respawn hazards for new level
        self.hazards = []
        self.spawn_hazards()
        
        # Clear beacons
        self.beacons = []
        
        # Reset bird positions and states
        for bird in self.birds.values():
            # Reset position to start zone
            angle = self.rng.uniform(0, 2 * np.pi)
            distance = self.rng.uniform(0, self.start_zone[2] * 0.8)
            x = self.start_zone[0] + distance * np.cos(angle)
            y = self.start_zone[1] + distance * np.sin(angle)
            bird.agent.position = np.array([x, y], dtype=np.float32)
            
            # Reset velocity
            angle = self.rng.uniform(-np.pi/4, np.pi/4)
            speed = self.rng.uniform(2, 4)
            bird.agent.velocity = np.array([speed * np.cos(angle), speed * np.sin(angle)], dtype=np.float32)
            
            # Reset state
            bird.agent.alive = True
            bird.agent.energy = 100.0 * bird.genetics.longevity
            bird.agent.stress = max(0, 0.2 * (1 - bird.genetics.stress_resilience))
            
        logger.info(f"Level {level_name} reset with {len(self.birds)} birds from Generation {self.generation}")
        
        # Defaults
        self.start_zone = (200, 600, 100)
        self.destination_zone = (1800, 600, 150)
        self.target_arrivals = 80
        self.max_losses = 20
        self.time_limit = 120
        self.level_hazards = []
    
    def spawn_hazards(self):
        """Spawn level hazards."""
        for hazard_data in self.level_hazards:
            hazard = hazard_data.copy()
            if 'direction' in hazard:
                hazard['direction'] = np.array(hazard['direction'])
            self.hazards.append(hazard)
    
    def step(self) -> Dict[str, Any]:
        """Execute one simulation step."""
        self.tick += 1
        dt = 1.0 / 30.0
        
        # Update each living bird
        alive_birds = []
        for bird_id, bird in list(self.birds.items()):
            if not bird.agent.alive:
                continue
            
            agent = bird.agent
            genetics = bird.genetics
            
            # Calculate forces
            self.apply_migration_force(agent, genetics, dt)
            self.apply_flocking_forces(bird, dt)
            self.apply_beacon_influence(agent, genetics, dt)
            self.apply_hazard_effects(bird, dt)
            
            # Energy management (affected by genetics)
            energy_loss = 0.01 / genetics.energy_efficiency  # Reduced base consumption
            energy_loss *= (1 + agent.stress * 0.2)  # Less stress impact
            agent.energy = max(0, agent.energy - energy_loss)
            
            # Death from exhaustion
            if agent.energy <= 0:
                agent.alive = False
                self.losses += 1
                logger.info(f"Bird {bird_id} died (Gen {bird.generation}, {bird.gender.value})")
                continue
            
            # Speed limits (affected by genetics)
            speed = np.linalg.norm(agent.velocity)
            max_speed = 80 * genetics.speed_factor
            if agent.energy < 30:
                max_speed *= 0.7
            if speed > max_speed:
                agent.velocity = (agent.velocity / speed) * max_speed
            
            # Update position
            agent.position += agent.velocity * dt
            bird.total_distance += speed * dt
            
            # Boundaries
            agent.position[0] = np.clip(agent.position[0], 0, 2000)
            agent.position[1] = np.clip(agent.position[1], 0, 1200)
            
            # Check arrival
            dest_x, dest_y, dest_r = self.destination_zone
            dist_to_dest = np.linalg.norm(agent.position - np.array([dest_x, dest_y]))
            if dist_to_dest < dest_r:
                self.arrivals += 1
                bird.survived_levels += 1
                agent.alive = False  # Remove from active simulation but track as survivor
                logger.info(f"Bird arrived! {bird.gender.value} Gen {bird.generation}")
                continue
            
            alive_birds.append(bird)
        
        # Check win/loss conditions
        if self.arrivals >= self.target_arrivals:
            self.victory = True
            self.game_over = True
            logger.info(f"VICTORY! Generation {self.generation}")
        elif time.time() - self.start_time > self.time_limit:
            # Time's up - no longer checking losses as a failure condition
            self.game_over = True
            logger.info(f"TIME UP! {self.arrivals} birds made it (needed {self.target_arrivals})")
        
        # Update population stats
        if self.tick % 30 == 0:  # Update stats once per second
            self.population_stats = self.calculate_population_stats()
        
        return {
            'tick': self.tick,
            'generation': self.generation,
            'birds': [self.bird_to_dict(b) for b in alive_birds],
            'population': len(alive_birds),
            'males': sum(1 for b in alive_birds if b.gender == Gender.MALE),
            'females': sum(1 for b in alive_birds if b.gender == Gender.FEMALE),
            'arrivals': self.arrivals,
            'losses': self.losses,
            'destination': self.destination_zone,
            'hazards': self.hazards,
            'beacons': self.beacons,
            'game_over': self.game_over,
            'victory': self.victory,
            'time_remaining': max(0, self.time_limit - (time.time() - self.start_time)),
            'population_stats': self.population_stats.__dict__,
            'breeding_pairs': len(self.breeding_pairs)
        }
    
    def apply_migration_force(self, agent: Agent, genetics: Genetics, dt: float):
        """Apply migration force toward destination."""
        dest_x, dest_y, dest_r = self.destination_zone
        to_dest = np.array([dest_x - agent.position[0], dest_y - agent.position[1]])
        dist = np.linalg.norm(to_dest)
        
        if dist > dest_r:
            # Base migration instinct (balanced to make progress but hazards still matter)
            migration_strength = 8.0 * (0.5 + genetics.beacon_sensitivity * 0.5)  # Balanced between 3 and 15
            migration_force = (to_dest / dist) * migration_strength
            agent.velocity += migration_force * dt
    
    def apply_flocking_forces(self, bird: BirdEntity, dt: float):
        """Apply flocking behaviors."""
        agent = bird.agent
        genetics = bird.genetics
        
        # Find neighbors
        neighbors = []
        for other_id, other in self.birds.items():
            if other_id != agent.id and other.agent.alive:
                dist = np.linalg.norm(agent.position - other.agent.position)
                if dist < 100 * (1 + genetics.flock_cohesion):
                    neighbors.append(other)
        
        if not neighbors:
            return
        
        # Cohesion (stronger with genetics)
        positions = [n.agent.position for n in neighbors]
        center = np.mean(positions, axis=0)
        cohesion = (center - agent.position) * genetics.flock_cohesion * 0.5
        agent.velocity += cohesion * dt
        
        # Alignment
        velocities = [n.agent.velocity for n in neighbors]
        avg_vel = np.mean(velocities, axis=0)
        alignment = (avg_vel - agent.velocity) * 0.3
        agent.velocity += alignment * dt
        
        # Separation
        for neighbor in neighbors[:5]:  # Limit for performance
            diff = agent.position - neighbor.agent.position
            dist = np.linalg.norm(diff)
            if dist < 30 and dist > 0:
                separation = (diff / dist) * 50 / dist
                agent.velocity += separation * dt
        
        # Gender attraction (subtle, for visual interest)
        if bird.partner_id is None:  # Unpaired birds slightly attract opposite gender
            for neighbor in neighbors:
                if neighbor.gender != bird.gender:
                    dist = np.linalg.norm(agent.position - neighbor.agent.position)
                    if 30 < dist < 80:
                        attraction = (neighbor.agent.position - agent.position) / dist * 0.5
                        agent.velocity += attraction * dt
    
    def apply_beacon_influence(self, agent: Agent, genetics: Genetics, dt: float):
        """Apply beacon effects."""
        for beacon in self.beacons:
            to_beacon = np.array([beacon['x'] - agent.position[0], beacon['y'] - agent.position[1]])
            dist = np.linalg.norm(to_beacon)
            
            if dist < beacon['radius']:
                influence = (1.0 - (dist / beacon['radius'])**2) * genetics.beacon_sensitivity
                strength = beacon['strength'] * influence
                
                if beacon['type'] == 'food':
                    agent.energy = min(100, agent.energy + 0.5 * influence)
                    agent.velocity += (to_beacon / dist) * strength * dt
                elif beacon['type'] == 'shelter':
                    agent.stress = max(0, agent.stress - 0.02 * influence)
                    agent.velocity *= (1 - 0.05 * influence)
                elif beacon['type'] == 'thermal':
                    agent.velocity[0] += strength * influence * dt
                    agent.energy = min(100, agent.energy + 0.3 * influence)
    
    def apply_hazard_effects(self, bird: BirdEntity, dt: float):
        """Apply hazard damage and avoidance."""
        agent = bird.agent
        genetics = bird.genetics
        
        for hazard in self.hazards:
            to_hazard = np.array([hazard['x'] - agent.position[0], hazard['y'] - agent.position[1]])
            dist = np.linalg.norm(to_hazard)
            
            # Detection range affected by genetics
            detection_range = hazard.get('radius', 100) * (1 + genetics.hazard_awareness)
            
            if dist < detection_range:
                danger = max(0, 1 - dist / hazard.get('radius', 100))
                
                if hazard['type'] == 'storm' or hazard['type'] == 'tornado':
                    strength = hazard.get('strength', 20)
                    
                    # Wind push effect using storm direction
                    if 'direction' in hazard and danger > 0.2:
                        wind_dir = np.array(hazard['direction'], dtype=np.float32)
                        if np.linalg.norm(wind_dir) > 0:
                            wind_dir = wind_dir / np.linalg.norm(wind_dir)
                            wind_force = wind_dir * strength * danger * 3.0
                            agent.velocity += wind_force * dt
                    
                    # Rotating storms create vortex
                    if hazard.get('rotating', False) and danger > 0.3:
                        # Tangential velocity for rotation
                        tangent = np.array([-to_hazard[1], to_hazard[0]])
                        if dist > 0:
                            tangent = tangent / dist
                            vortex_strength = strength * danger * 2.0
                            agent.velocity += tangent * vortex_strength * dt
                    
                    # Confusion increases with storm strength
                    if danger > 0.3:
                        confusion = self.rng.normal(0, strength * danger * 0.5, 2)
                        agent.velocity += confusion * dt
                        
                    # Energy drain based on storm strength
                    agent.energy -= strength * danger * 0.05 * (2 - genetics.energy_efficiency)
                    agent.stress = min(1.0, agent.stress + danger * 0.1)
                    
                    # Lightning strikes for storms with lightning
                    if hazard.get('lightning', False) and danger > 0.7:
                        if self.rng.random() < 0.005 * danger:  # 0.5% chance at center
                            agent.alive = False
                            self.losses += 1
                            logger.info(f"Bird struck by lightning ({bird.gender.value})")
                    
                    # Storm kill chance based on strength
                    elif danger > 0.8:
                        kill_chance = 0.001 * (strength / 20)  # Scale with strength
                        if self.rng.random() < kill_chance:
                            agent.alive = False
                            self.losses += 1
                            logger.info(f"Bird killed by storm ({bird.gender.value})")
                
                elif hazard['type'] == 'predator':
                    # Escape response
                    if dist < detection_range * genetics.hazard_awareness:
                        escape_strength = 200 * danger * genetics.hazard_awareness
                        if dist > 0:
                            escape = -to_hazard / dist * escape_strength
                            agent.velocity += escape * dt
                        agent.stress = min(1.0, agent.stress + 0.1 * danger)
                        
                        # Alpha predators are more deadly
                        if hazard.get('alpha', False):
                            kill_chance = 0.05 * danger  # 5% at center
                        else:
                            kill_chance = 0.03 * danger  # 3% at center
                        
                        # Attack zone
                        if dist < 30 and self.rng.random() < kill_chance * (2 - genetics.stress_resilience):
                            agent.alive = False
                            self.losses += 1
                            logger.info(f"Bird caught by predator ({bird.gender.value})")
                        elif dist < 50:
                            bird.close_calls += 1
                
                elif hazard['type'] == 'fog':
                    # Fog reduces flocking ability and visibility
                    if danger > 0.3:
                        # Reduce perception range (will affect flocking)
                        agent.perception_range = max(20, 100 * (1 - danger * 0.7))
                        # Add disorientation
                        confusion = self.rng.normal(0, 15 * danger, 2)
                        agent.velocity += confusion * dt
                        agent.stress = min(1.0, agent.stress + 0.05 * danger)
                
                elif hazard['type'] == 'turbulence':
                    # Random violent pushes
                    if danger > 0.4 and self.rng.random() < 0.1:  # 10% chance per frame
                        push_dir = self.rng.normal(0, 1, 2)
                        push_dir = push_dir / (np.linalg.norm(push_dir) + 0.001)
                        push_strength = hazard.get('strength', 30) * danger * 5
                        agent.velocity += push_dir * push_strength * dt
                        agent.energy -= 2.0 * danger
                        agent.stress = min(1.0, agent.stress + 0.2)
                
                elif hazard['type'] == 'electric_field':
                    # Continuous damage and paralysis
                    if danger > 0.5:
                        # Slow down birds (paralysis effect)
                        agent.velocity *= (1 - 0.5 * danger * dt)
                        # Energy damage
                        damage = hazard.get('strength', 10) * danger * 0.1
                        agent.energy -= damage
                        agent.stress = min(1.0, agent.stress + 0.15 * danger)
                        # Chance of instant death
                        if danger > 0.9 and self.rng.random() < 0.01:
                            agent.alive = False
                            self.losses += 1
                            logger.info(f"Bird electrocuted ({bird.gender.value})")
    
    def breed_population(self):
        """Perform breeding after level completion."""
        # Increment generation first
        self.generation += 1
        
        # Get all survivors (including those that arrived)
        survivors = []
        for bird in self.birds.values():
            if bird.agent.alive or bird.survived_levels > 0:
                survivors.append(bird)
        
        # Remove birds that are too old (3+ generations)
        MAX_LIFESPAN = 3
        young_survivors = []
        retired_count = 0
        
        for bird in survivors:
            age_in_generations = self.generation - bird.generation
            if age_in_generations < MAX_LIFESPAN:
                young_survivors.append(bird)
            else:
                retired_count += 1
                logger.info(f"Retiring bird from Gen {bird.generation} (age: {age_in_generations} generations)")
        
        survivors = young_survivors
        
        # Sort by fitness for selective breeding
        survivors.sort(key=lambda b: b.fitness_score, reverse=True)
        
        # Apply adaptive selection pressure based on survivor count
        # With few survivors, let them all breed to preserve genetics
        if len(survivors) < 30:
            BREEDING_CUTOFF = 1.0  # All survivors can breed when population is low
        else:
            BREEDING_CUTOFF = 0.7  # Top 70% can breed when population is healthy
        
        breeding_pool = survivors[:int(len(survivors) * BREEDING_CUTOFF)]
        
        males = [b for b in breeding_pool if b.gender == Gender.MALE]
        females = [b for b in breeding_pool if b.gender == Gender.FEMALE]
        
        logger.info(f"Breeding: {len(males)} males, {len(females)} females from {len(breeding_pool)} selected (of {len(survivors)} survivors, {retired_count} retired)")
        
        # Sort by fitness for selective breeding (best with best)
        males.sort(key=lambda b: b.fitness_score, reverse=True)
        females.sort(key=lambda b: b.fitness_score, reverse=True)
        
        # Form breeding pairs
        self.breeding_pairs = []
        offspring = []
        
        # Top performers get to breed multiple times
        for i in range(min(len(males), len(females))):
            male = males[i]
            female = females[i]
            
            # With few survivors, increase offspring per pair to maintain population
            if len(survivors) < 20:
                offspring_count = 3  # More offspring when population is critically low
            elif len(survivors) < 40:
                offspring_count = 2  # Moderate offspring count
            else:
                # Normal breeding: Top 20% get 2 offspring, others get 1
                offspring_count = 2 if i < len(males) * 0.2 else 1
            
            for _ in range(offspring_count):
                # Check fertility
                if self.rng.random() > male.genetics.fertility * female.genetics.fertility:
                    continue  # Failed to breed
                
                # Create offspring with more mutation for diversity
                child_genetics = Genetics.breed(male.genetics, female.genetics, self.rng)
                
                # Add extra mutation chance for more interesting evolution
                if self.rng.random() < 0.2:  # 20% chance of extra mutation
                    trait = self.rng.choice(['hazard_awareness', 'energy_efficiency', 
                                            'flock_cohesion', 'beacon_sensitivity', 'stress_resilience'])
                    current = getattr(child_genetics, trait)
                    mutation = self.rng.normal(0, 0.1)
                    setattr(child_genetics, trait, np.clip(current + mutation, 0, 1))
                
                child_gender = Gender.MALE if self.rng.random() < 0.5 else Gender.FEMALE
                
                child = self.create_bird(
                    gender=child_gender,
                    generation=self.generation,
                    genetics=child_genetics,
                    parents=(male.agent.id, female.agent.id)
                )
                
                offspring.append(child)
                self.breeding_pairs.append((male.agent.id, female.agent.id))
            
            # Update family connections
            male.partner_id = female.agent.id
            female.partner_id = male.agent.id
        
        # Clear old population and rebuild
        self.birds.clear()
        
        # Population management - keep exactly 100 birds
        TARGET_POPULATION = 100
        
        # Calculate how many survivors and offspring to keep
        # Prioritize keeping a mix of both for genetic diversity
        survivors_to_keep = min(len(survivors), int(TARGET_POPULATION * 0.7))  # Max 70% survivors
        offspring_to_keep = min(len(offspring), TARGET_POPULATION - survivors_to_keep)
        
        # If we still have room, add more survivors
        if survivors_to_keep + offspring_to_keep < TARGET_POPULATION:
            survivors_to_keep = min(len(survivors), TARGET_POPULATION - offspring_to_keep)
        
        # Add survivors back (reset their state for next level)
        for i, survivor in enumerate(survivors[:survivors_to_keep]):
            survivor.agent.alive = True
            survivor.agent.energy = 100.0 * survivor.genetics.longevity
            survivor.agent.stress = max(0, 0.2 * (1 - survivor.genetics.stress_resilience))
            # Reset position to start zone
            angle = self.rng.uniform(0, 2 * np.pi)
            radius = self.rng.uniform(0, self.start_zone[2])
            survivor.agent.position = np.array([
                self.start_zone[0] + radius * np.cos(angle),
                self.start_zone[1] + radius * np.sin(angle)
            ])
            # Reset velocity (generally eastward)
            survivor.agent.velocity = np.array([
                self.rng.uniform(3, 7) * survivor.genetics.speed_factor,
                self.rng.uniform(-2, 2) * survivor.genetics.speed_factor
            ])
            survivor.survived_levels += 1
            self.birds[survivor.agent.id] = survivor
        
        # Add offspring (only up to our calculated limit)
        for child in offspring[:offspring_to_keep]:
            self.birds[child.agent.id] = child
        
        # Population should now be exactly TARGET_POPULATION or less
        MAX_POPULATION = 100  # Changed from 200
        MIN_POPULATION = 50
        
        # If over cap, keep only the youngest and fittest
        if len(self.birds) > MAX_POPULATION:
            all_birds = list(self.birds.values())
            # Sort by generation (newer first) then by fitness
            all_birds.sort(key=lambda b: (-b.generation, -b.fitness_score))
            self.birds = {b.agent.id: b for b in all_birds[:MAX_POPULATION]}
            logger.info(f"Population capped at {MAX_POPULATION} birds")
        
        # Fill remaining slots with new birds if under minimum
        # But base their genetics partially on survivors to maintain evolution progress
        while len(self.birds) < MIN_POPULATION:
            gender = Gender.MALE if len([b for b in self.birds.values() if b.gender == Gender.MALE]) < MIN_POPULATION // 2 else Gender.FEMALE
            
            # If we have survivors, create new birds with genetics influenced by them
            if survivors and self.rng.random() < 0.7:  # 70% chance to inherit from survivors
                # Pick a random survivor as genetic template
                template = self.rng.choice(survivors)
                new_genetics = Genetics.mutate(template.genetics, self.rng, mutation_rate=0.2)
                new_bird = self.create_bird(gender=gender, generation=self.generation, genetics=new_genetics)
            else:
                # Create completely random bird for genetic diversity
                new_bird = self.create_bird(gender=gender, generation=self.generation)
            
            self.birds[new_bird.agent.id] = new_bird
        
        logger.info(f"Breeding complete: {len(offspring)} offspring, {len(survivors)} survivors, total population: {len(self.birds)}, Generation {self.generation}")
        
        # Count actual males and females in breeding pool
        males_count = len(males)
        females_count = len(females)
        
        return {
            'pairs_formed': len(self.breeding_pairs),
            'offspring_created': len(offspring),
            'survivors': len(survivors),
            'males_breeding': males_count,
            'females_breeding': females_count,
            'new_generation': self.generation,
            'population_size': len(self.birds),
            'retired': retired_count
        }
    
    def calculate_population_stats(self) -> PopulationStats:
        """Calculate comprehensive population statistics."""
        stats = PopulationStats()
        
        alive_birds = [b for b in self.birds.values() if b.agent.alive]
        if not alive_birds:
            return stats
        
        stats.total_population = len(alive_birds)
        stats.males = sum(1 for b in alive_birds if b.gender == Gender.MALE)
        stats.females = stats.total_population - stats.males
        
        # Average genetics
        traits = {
            'hazard_awareness': [],
            'energy_efficiency': [],
            'flock_cohesion': [],
            'beacon_sensitivity': [],
            'stress_resilience': []
        }
        
        for bird in alive_birds:
            for trait, values in traits.items():
                values.append(getattr(bird.genetics, trait))
        
        stats.avg_hazard_awareness = np.mean(traits['hazard_awareness'])
        stats.avg_energy_efficiency = np.mean(traits['energy_efficiency'])
        stats.avg_flock_cohesion = np.mean(traits['flock_cohesion'])
        stats.avg_beacon_sensitivity = np.mean(traits['beacon_sensitivity'])
        stats.avg_stress_resilience = np.mean(traits['stress_resilience'])
        
        # Genetic diversity (standard deviation as proxy)
        diversity_scores = []
        for trait_values in traits.values():
            if len(trait_values) > 1:
                diversity_scores.append(np.std(trait_values))
        
        stats.genetic_diversity = np.mean(diversity_scores) if diversity_scores else 0
        
        # Find top bloodlines (birds with most successful offspring)
        bloodline_scores = {}
        for bird in self.birds.values():
            if bird.offspring_ids:
                score = sum(1 for oid in bird.offspring_ids 
                          if oid in self.birds and self.birds[oid].survived_levels > 0)
                bloodline_scores[bird.agent.id] = {
                    'id': int(bird.agent.id),
                    'gender': bird.gender.value,
                    'generation': bird.generation,
                    'offspring_count': len(bird.offspring_ids),
                    'successful_offspring': score
                }
        
        stats.top_bloodlines = sorted(
            bloodline_scores.values(), 
            key=lambda x: x['successful_offspring'], 
            reverse=True
        )[:5]
        
        return stats
    
    def bird_to_dict(self, bird: BirdEntity) -> Dict:
        """Convert bird to dictionary for serialization."""
        agent = bird.agent
        return {
            'id': int(agent.id),
            'x': float(agent.position[0]),
            'y': float(agent.position[1]),
            'vx': float(agent.velocity[0]),
            'vy': float(agent.velocity[1]),
            'energy': float(agent.energy),
            'stress': float(agent.stress),
            'alive': agent.alive,
            'gender': bird.gender.value,
            'generation': bird.generation,
            'genetics': bird.genetics.to_dict(),
            'parent1_id': int(bird.parent1_id) if bird.parent1_id else None,
            'parent2_id': int(bird.parent2_id) if bird.parent2_id else None,
            'partner_id': int(bird.partner_id) if bird.partner_id else None,
            'survived_levels': bird.survived_levels,
            'fitness': bird.fitness_score
        }
    
    def place_beacon(self, beacon_type: str, x: float, y: float) -> bool:
        """Place a beacon."""
        beacon = {
            'id': len(self.beacons),
            'type': beacon_type,
            'x': x,
            'y': y,
            'radius': 150,
            'strength': 30
        }
        self.beacons.append(beacon)
        return True
    
    def get_family_tree(self, bird_id: AgentID, depth: int = 3) -> Dict:
        """Get family tree for a bird."""
        if bird_id not in self.birds:
            return {}
        
        bird = self.birds[bird_id]
        tree = {
            'id': int(bird_id),
            'gender': bird.gender.value,
            'generation': bird.generation,
            'genetics': bird.genetics.to_dict(),
            'survived_levels': bird.survived_levels
        }
        
        if depth > 0:
            # Add parents
            if bird.parent1_id and bird.parent1_id in self.birds:
                tree['parent1'] = self.get_family_tree(bird.parent1_id, depth - 1)
            if bird.parent2_id and bird.parent2_id in self.birds:
                tree['parent2'] = self.get_family_tree(bird.parent2_id, depth - 1)
            
            # Add offspring
            if bird.offspring_ids and depth > 1:
                tree['offspring'] = []
                for oid in bird.offspring_ids[:5]:  # Limit to 5 for display
                    if oid in self.birds:
                        tree['offspring'].append(self.get_family_tree(oid, 1))
        
        return tree