"""Unified simulation combining genetic evolution with advanced game mechanics.

This module merges the best features from both genetic and evolved simulations:
- Individual bird genetics with breeding (from genetic simulation)  
- Advanced hazard behaviors and BeaconManager (from evolved simulation)
- Multi-level persistence for migration campaigns
- Distance-based energy consumption for new gameplay
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

# Import genetic components
from .simulation_genetic import Genetics, BirdEntity, Gender, PopulationStats

logger = get_logger("unified_simulation")


@dataclass
class MigrationConfig:
    """Configuration for a complete migration (A->B->C->Z)."""
    migration_id: int = 1
    current_leg: int = 1
    total_legs: int = 3
    
    # Current level configuration
    level_name: str = "Migration1-Leg1"
    seed: int = 42
    
    # Level geometry
    start_zone: Tuple[float, float, float] = (200, 600, 100) 
    destination_zone: Tuple[float, float, float] = (1800, 600, 150)
    
    # Food sites (environmental, not player-placed)
    food_sites: List[Dict[str, Any]] = field(default_factory=list)
    
    # Hazards for this leg
    hazards: List[Dict[str, Any]] = field(default_factory=list)
    
    # Gameplay parameters
    beacon_budget: int = 3
    pulse_cooldown: float = 5.0
    
    @classmethod
    def generate_migration(cls, migration_id: int, rng: np.random.Generator) -> 'MigrationConfig':
        """Generate a complete migration with procedural levels."""
        # Migration difficulty scales with ID
        total_legs = min(2 + migration_id, 6)  # 3 to 6 legs max
        base_distance = 40 + migration_id * 20  # 60 to 140 distance
        
        config = cls(
            migration_id=migration_id,
            total_legs=total_legs,
            current_leg=1
        )
        
        # Generate first leg
        config.generate_leg(1, rng)
        
        return config
    
    def generate_leg(self, leg_number: int, rng: np.random.Generator):
        """Generate a specific leg of the migration."""
        self.current_leg = leg_number
        self.level_name = f"Migration{self.migration_id}-Leg{leg_number}"
        
        # Distance for this leg (40-80 units requiring food stops)
        leg_distance = rng.uniform(800, 1200)  # Requires ~2 food stops
        
        # Start position (for leg 1, fixed; for others, previous destination) 
        if leg_number == 1:
            start_x = 200
        else:
            start_x = 200 + (leg_number - 1) * 400  # Space out legs
            
        # Destination position
        dest_x = start_x + leg_distance
        dest_y = rng.uniform(400, 800)  # Some vertical variation
        
        self.start_zone = (start_x, 600, 100)
        self.destination_zone = (dest_x, dest_y, 150)
        
        # Place food sites (2-3 per leg, spaced for strategic routing)
        self.food_sites = []
        food_count = 2 if leg_distance < 1000 else 3
        
        for i in range(food_count):
            # Space food sites along the route with some offset
            food_x = start_x + (i + 1) * (leg_distance / (food_count + 1))
            food_y = rng.uniform(400, 800)  # Random Y position
            
            self.food_sites.append({
                'x': food_x,
                'y': food_y, 
                'radius': 80,
                'energy_restore_rate': 8.0  # Energy per second (increased for better survival)
            })
        
        # Place hazards based on migration difficulty
        self.hazards = []
        hazard_count = self.migration_id  # 1 hazard per migration level
        
        for i in range(hazard_count):
            if rng.random() < 0.6:  # 60% chance of storm
                hazard = self.generate_storm(rng, start_x, dest_x)
            else:  # 40% chance of predator
                hazard = self.generate_predator(rng, start_x, dest_x)
                
            self.hazards.append(hazard)
    
    def generate_storm(self, rng: np.random.Generator, start_x: float, dest_x: float) -> Dict:
        """Generate a storm hazard with tornado behavior."""
        # Place storm roughly in middle section of route
        storm_x = rng.uniform(start_x + 200, dest_x - 200)
        storm_y = rng.uniform(300, 900)
        
        # Storm strength scales with migration difficulty
        base_strength = 15 + self.migration_id * 3
        
        return {
            'type': 'tornado',
            'x': storm_x,
            'y': storm_y,
            'radius': rng.uniform(120, 180),
            'strength': base_strength,
            'confusion_strength': base_strength * 2,
            'kill_chance': 0.05 + self.migration_id * 0.015,  # 5% to 14% - More forgiving
            'energy_drain': 0.2 + self.migration_id * 0.1,  # Drastically reduced
            'spin_rate': rng.uniform(0.5, 2.0),
            'direction': rng.uniform(-1, 1, 2).tolist(),  # Random drift direction
            'danger_zones': [
                {'radius': 180 * 1.5, 'intensity': 0.2},  # Warning zone
                {'radius': 180, 'intensity': 0.6},        # Danger zone  
                {'radius': 180 * 0.5, 'intensity': 1.0}   # Death zone
            ]
        }
    
    def generate_predator(self, rng: np.random.Generator, start_x: float, dest_x: float) -> Dict:
        """Generate a predator hazard with chase behavior."""
        # Place predator closer to destination (ambush point)
        predator_x = rng.uniform(dest_x - 400, dest_x - 100)
        predator_y = rng.uniform(300, 900)
        
        # Predator danger scales with migration difficulty
        base_danger = 0.08 + self.migration_id * 0.02  # 8% to 18% kill chance - More balanced
        
        return {
            'type': 'predator', 
            'x': predator_x,
            'y': predator_y,
            'radius': 100,
            'kill_chance': base_danger,
            'pursuit_speed': 8 + self.migration_id,
            'detection_range': 150,
            'attack_range': 40,
            'chase_duration': 5.0,  # 5 seconds of active hunting
            'trigger_panic': True,
            'alpha': self.migration_id > 3,  # Alpha predators in late migrations
            'last_kill_time': 0,
            'chase_timer': 0,
            'danger_zones': [
                {'radius': 150, 'intensity': 0.3},   # Detection zone
                {'radius': 100, 'intensity': 0.7},   # Chase zone
                {'radius': 40, 'intensity': 1.0}     # Kill zone
            ]
        }
    
    def advance_to_next_leg(self, rng: np.random.Generator) -> bool:
        """Advance to next leg of migration. Returns True if migration continues."""
        if self.current_leg >= self.total_legs:
            return False  # Migration complete
            
        self.generate_leg(self.current_leg + 1, rng)
        return True


class UnifiedSimulation:
    """Unified simulation combining genetic evolution with advanced mechanics."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rng = np.random.default_rng(config.get('seed', 42))
        
        # Migration system
        self.migration_config = MigrationConfig.generate_migration(
            migration_id=config.get('migration_id', 1),
            rng=self.rng
        )
        
        # Population management (from GeneticSimulation)
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
        self.migration_complete = False
        self.waiting_for_continue = False  # NEW: Manual progression control
        
        # Advanced beacon system (from EvolvedSimulation)
        self.beacon_manager = BeaconManager(budget_limit=self.migration_config.beacon_budget)
        
        # Environmental food sites (new for overhaul)
        self.food_beacons: List[Dict] = []
        self.spawn_environmental_food()
        
        # Enhanced hazard system (from EvolvedSimulation)
        self.hazards: List[Dict] = []
        self.spawn_hazards()
        
        # Tracking for evolution and breeding
        self.hazards_encountered = {'tornado': 0, 'predator': 0}
        self.leadership_tracking: Dict[AgentID, float] = {}  # Track leadership time
        self.close_calls = 0
        self.panic_events = 0
        
        # Population statistics
        self.population_stats = PopulationStats()
        self.family_trees: Dict[AgentID, Dict] = {}
        
        # Path following system
        self.migration_path = []  # List of [x, y] waypoints for birds to follow
        
        # Create initial population with gender balance
        n_agents = config.get('n_agents', 100)
        for i in range(n_agents):
            gender = Gender.MALE if i < n_agents // 2 else Gender.FEMALE
            bird = self.create_bird(gender=gender, generation=0)
            self.birds[bird.agent.id] = bird
        
        logger.info(f"Unified simulation initialized: Migration {self.migration_config.migration_id}, "
                   f"Leg {self.migration_config.current_leg}/{self.migration_config.total_legs}, "
                   f"{len(self.birds)} birds (Gen {self.generation})")
    
    def create_bird(self, gender: Gender = None, generation: int = 0, 
                   genetics: Genetics = None, parents: Tuple[AgentID, AgentID] = None) -> BirdEntity:
        """Create a new bird entity with enhanced traits."""
        bird_id = AgentID(self.next_id)
        self.next_id += 1
        
        agent = create_agent(bird_id, rng=self.rng)
        
        if gender is None:
            gender = Gender.MALE if self.rng.random() < 0.5 else Gender.FEMALE
        
        if genetics is None:
            genetics = Genetics.random(self.rng)
            # Add leadership trait if not present (for overhaul)
            if not hasattr(genetics, 'leadership'):
                genetics.leadership = self.rng.uniform(0.3, 0.7)
        
        # Apply genetics to agent behavior
        agent.hazard_detection = genetics.hazard_awareness
        agent.beacon_response = genetics.beacon_sensitivity
        agent.energy = 100.0  # Start with full energy each level
        agent.stress = max(0, 0.2 * (1 - genetics.stress_resilience))
        
        # Position in start zone
        start_x, start_y, start_radius = self.migration_config.start_zone
        angle = self.rng.uniform(0, 2 * np.pi)
        radius = self.rng.uniform(0, start_radius)
        agent.position = np.array([
            start_x + radius * np.cos(angle),
            start_y + radius * np.sin(angle)
        ], dtype=np.float32)
        
        # Initial velocity with genetic speed variation (slowed down for strategic observation)
        agent.velocity = np.array([
            self.rng.uniform(1, 3) * genetics.speed_factor,
            self.rng.uniform(-1, 1) * genetics.speed_factor
        ], dtype=np.float32)
        
        # Create bird entity
        bird = BirdEntity(
            agent=agent,
            gender=gender, 
            genetics=genetics,
            generation=generation,
            parent1_id=parents[0] if parents else None,
            parent2_id=parents[1] if parents else None
        )
        
        # Initialize leadership tracking
        self.leadership_tracking[bird_id] = 0.0
        
        return bird
    
    def spawn_environmental_food(self):
        """Spawn environmental food sites as permanent beacons."""
        self.food_beacons = []
        
        for i, food_site in enumerate(self.migration_config.food_sites):
            # Create food beacon using BeaconManager
            food_beacon_id = f"food_site_{i}"
            position = create_vector2d(food_site['x'], food_site['y'])
            
            # Add to beacon manager as permanent food source
            # Using WIND_UP as a placeholder for food beacons
            beacon = self.beacon_manager.place_beacon(
                BeaconType.WIND_UP,  # Using wind_up as food beacon placeholder
                position, 
                Tick(0)  # Place at start
            )
            
            if beacon:
                # Mark as environmental (not player-placed)
                beacon.environmental = True
                beacon.energy_restore_rate = food_site.get('energy_restore_rate', 2.0)
                logger.info(f"Environmental food site placed at ({food_site['x']:.0f}, {food_site['y']:.0f})")
    
    def spawn_hazards(self):
        """Spawn hazards for current migration leg."""
        self.hazards = self.migration_config.hazards.copy()
        
        # Initialize hazard state
        for hazard in self.hazards:
            if 'direction' in hazard:
                hazard['direction'] = np.array(hazard['direction'])
            if hazard['type'] == 'predator':
                hazard['chase_timer'] = 0  # Not actively hunting yet
                
        logger.info(f"Spawned {len(self.hazards)} hazards for {self.migration_config.level_name}")
    
    def step(self) -> Dict[str, Any]:
        """Execute one simulation step with distance-based energy consumption."""
        self.tick += 1
        dt = 1.0 / 30.0
        
        # Track living birds and update leadership
        alive_birds = []
        flock_positions = []
        
        for bird_id, bird in list(self.birds.items()):
            if not bird.agent.alive:
                continue
                
            agent = bird.agent
            genetics = bird.genetics
            
            # Store position for leadership tracking
            flock_positions.append((bird_id, agent.position[0]))  # X coordinate for eastward migration
            
            # 1. Apply all movement forces
            self.apply_path_following_force(agent, genetics, dt)
            self.apply_flocking_forces(bird, dt) 
            self.apply_beacon_influence(agent, genetics, dt)
            self.apply_hazard_effects(bird, dt)
            
            # 2. **NEW: Distance-based energy consumption**
            velocity_magnitude = np.linalg.norm(agent.velocity)
            distance_this_step = velocity_magnitude * dt
            
            # Energy drain scales with distance traveled (not time) - Ultra forgiving for testing
            base_energy_rate = 0.005  # Energy per distance unit (heavily reduced for testing)
            energy_drain = distance_this_step * base_energy_rate / genetics.energy_efficiency
            
            # Additional drain from stress (reduced)
            stress_drain = agent.stress * 0.005 * dt
            
            agent.energy = max(0, agent.energy - energy_drain - stress_drain)
            
            # 3. **NEW: Exhaustion death mechanics**
            if agent.energy <= 0:
                agent.alive = False
                self.losses += 1
                logger.info(f"Bird {bird_id} died from exhaustion ({bird.gender.value}, Gen {bird.generation})")
                continue
            elif agent.energy < 10:  # Critical exhaustion zone
                # Increased energy drain when exhausted (point of no return)
                agent.energy = max(0, agent.energy - 0.5 * dt)
                # Visual indication needed: this bird is flashing red
                
            # 4. Speed limits affected by genetics and energy (reduced for strategic observation)
            speed = np.linalg.norm(agent.velocity)
            max_speed = 40 * genetics.speed_factor
            
            if agent.energy < 30:
                max_speed *= 0.7  # Slower when tired
            elif agent.energy > 80:
                max_speed *= 1.1  # Faster when energetic
                
            if speed > max_speed:
                agent.velocity = (agent.velocity / speed) * max_speed
            
            # 5. Update position
            agent.position += agent.velocity * dt
            bird.total_distance += speed * dt
            
            # 6. World boundaries
            agent.position[0] = np.clip(agent.position[0], 0, 2000)
            agent.position[1] = np.clip(agent.position[1], 0, 1200)
            
            # 7. Check arrival at destination
            dest_x, dest_y, dest_r = self.migration_config.destination_zone
            dist_to_dest = np.linalg.norm(agent.position - np.array([dest_x, dest_y]))
            
            if dist_to_dest < dest_r:
                self.arrivals += 1
                bird.survived_levels += 1
                agent.alive = False  # Remove from simulation (they've reached safety)
                logger.info(f"Bird arrived at checkpoint! {bird.gender.value} Gen {bird.generation} "
                           f"({self.arrivals} total arrivals)")
                continue
            
            alive_birds.append(bird)
        
        # Track leadership (birds at front of migration)
        if flock_positions:
            # Sort by X position (eastward is positive)
            flock_positions.sort(key=lambda x: x[1], reverse=True)
            leaders_count = max(1, len(flock_positions) // 10)  # Top 10% are "leaders"
            
            for i in range(leaders_count):
                bird_id = flock_positions[i][0]
                self.leadership_tracking[bird_id] += dt
        
        # Update hazard behaviors (moving storms, predator chase timers)
        self.update_hazards(dt)
        
        # Check level completion conditions
        total_accounted = len(alive_birds) + self.arrivals
        
        if len(alive_birds) == 0 and self.arrivals == 0:
            # Total extinction - no arrivals and no living birds
            self.game_over = True
            logger.info("MIGRATION FAILED - All birds lost")
        elif len(alive_birds) == 0 and self.arrivals > 0:
            # All remaining birds have arrived - complete success!
            self.victory = True
            logger.info(f"Level complete! All {self.arrivals} birds reached destination")
        elif self.arrivals > 0 and len(alive_birds) < 5:
            # Minimal survivors reached destination - partial success
            self.victory = True
            logger.info(f"Level complete! {self.arrivals} arrivals, {len(alive_birds)} still traveling")
        
        # Check if migration leg is complete
        if self.victory and not self.migration_complete and not self.waiting_for_continue:
            if self.migration_config.current_leg >= self.migration_config.total_legs:
                # Full migration complete - trigger breeding
                self.migration_complete = True
                self.game_over = True
                logger.info(f"MIGRATION COMPLETE! Ready for breeding phase.")
            else:
                # More legs to go - wait for manual continuation
                self.waiting_for_continue = True
                logger.info(f"Leg {self.migration_config.current_leg} complete! Waiting for player to continue to next leg.")
        
        # Update population statistics
        if self.tick % 30 == 0:
            self.population_stats = self.calculate_population_stats()
        
        # Cleanup expired beacons (but keep environmental food)
        self.beacon_manager.cleanup_expired_beacons(Tick(self.tick))
        
        return {
            'tick': self.tick,
            'generation': self.generation,
            'migration_id': self.migration_config.migration_id,
            'current_leg': self.migration_config.current_leg,
            'total_legs': self.migration_config.total_legs,
            'level_name': self.migration_config.level_name,
            'birds': [self.bird_to_dict(b) for b in alive_birds],
            'population': len(alive_birds),
            'males': sum(1 for b in alive_birds if b.gender == Gender.MALE),
            'females': sum(1 for b in alive_birds if b.gender == Gender.FEMALE),
            'arrivals': self.arrivals,
            'losses': self.losses,
            'destination': self.migration_config.destination_zone,
            'hazards': self.hazards,
            'beacons': self.get_beacon_data(),
            'food_sites': self.migration_config.food_sites,
            'game_over': self.game_over,
            'victory': self.victory,
            'migration_complete': self.migration_complete,
            'waiting_for_continue': self.waiting_for_continue,
            'population_stats': self.population_stats.__dict__ if self.population_stats else {},
            'leadership_leaders': self.get_current_leaders(),
            'close_calls': self.close_calls,
            'panic_events': self.panic_events
        }
    
    def update_hazards(self, dt: float):
        """Update hazard behaviors like moving storms and predator timers."""
        for hazard in self.hazards:
            if hazard['type'] == 'tornado':
                # Moving storms
                if 'direction' in hazard:
                    move_speed = hazard.get('move_speed', 10)  # Units per second
                    hazard['x'] += hazard['direction'][0] * move_speed * dt
                    hazard['y'] += hazard['direction'][1] * move_speed * dt
                    
                    # Keep storms in bounds
                    hazard['x'] = np.clip(hazard['x'], 0, 2000)
                    hazard['y'] = np.clip(hazard['y'], 0, 1200)
            
            elif hazard['type'] == 'predator':
                # Predator chase timer management
                if hazard['chase_timer'] > 0:
                    hazard['chase_timer'] -= dt
                    if hazard['chase_timer'] <= 0:
                        logger.info("Predator tired of chasing, becomes less dangerous")
                        # Reduce danger after chase period
                        hazard['kill_chance'] *= 0.3  # Much less dangerous when tired
    
    def get_beacon_data(self) -> List[Dict]:
        """Get beacon data for client rendering."""
        beacon_data = []
        
        for beacon in self.beacon_manager.beacons:
            beacon_data.append({
                'id': beacon.beacon_id,
                'type': beacon.beacon_type.value,
                'x': float(beacon.position[0]),
                'y': float(beacon.position[1]), 
                'radius': beacon.spec.radius,
                'strength': beacon.get_field_strength(beacon.position, Tick(self.tick)),
                'environmental': getattr(beacon, 'environmental', False),
                'decay': beacon.get_temporal_decay(Tick(self.tick))
            })
        
        return beacon_data
    
    def get_current_leaders(self) -> List[Dict]:
        """Get current flock leaders for UI display."""
        if not self.leadership_tracking:
            return []
            
        # Get top 3 leaders by time spent leading
        leaders = sorted(self.leadership_tracking.items(), key=lambda x: x[1], reverse=True)[:3]
        
        result = []
        for bird_id, lead_time in leaders:
            if bird_id in self.birds and lead_time > 0:
                bird = self.birds[bird_id]
                total_time = self.tick / 30.0  # Convert ticks to seconds
                lead_percentage = (lead_time / total_time) * 100 if total_time > 0 else 0
                
                result.append({
                    'id': int(bird_id),
                    'gender': bird.gender.value,
                    'generation': bird.generation, 
                    'lead_time': lead_time,
                    'lead_percentage': lead_percentage,
                    'leadership_trait': bird.genetics.leadership if hasattr(bird.genetics, 'leadership') else 0.5
                })
        
        return result
    
    def apply_path_following_force(self, agent: Agent, genetics: Genetics, dt: float):
        """Apply path following force to steer birds toward the next waypoint."""
        # First, find the next waypoint the bird should head to
        current_pos = agent.position
        next_idx = 0
        
        # Skip waypoints we've already passed (within 50 units)
        for i, wp in enumerate(self.migration_path):
            wp_pos = np.array(wp)
            if np.linalg.norm(current_pos - wp_pos) < 50:
                next_idx = i + 1
            else:
                break
        
        # Check if we have a valid path and next waypoint
        if not self.migration_path or next_idx >= len(self.migration_path):
            # No path or reached end of path - apply wandering and destination attraction
            wander_force = self.rng.normal(0, 5.0, 2)  # Small random force
            agent.velocity += wander_force * dt
            
            # Check for destination detection
            dest_x, dest_y, dest_r = self.migration_config.destination_zone
            to_dest = np.array([dest_x - agent.position[0], dest_y - agent.position[1]])
            dist_to_dest = np.linalg.norm(to_dest)
            detection_range = 200.0
            if dist_to_dest < detection_range:
                pull_strength = 20.0 * (1 - dist_to_dest / detection_range)  # Progressive: stronger when closer
                if dist_to_dest > 0:
                    dest_force = (to_dest / dist_to_dest) * pull_strength
                    agent.velocity += dest_force * dt
            return
        
        next_wp = np.array(self.migration_path[next_idx])
        to_wp = next_wp - current_pos
        dist = np.linalg.norm(to_wp)
        
        if dist > 1: # Avoid div0
            base_strength = 30.0 * (0.8 + genetics.leadership * 0.4)
            steering_force = (to_wp / dist) * base_strength
            agent.velocity += steering_force * dt
            logger.debug(f"Applying path force to bird {agent.id}: strength {base_strength}, dist {dist}")
            
            # Add some deviation based on cohesion (lower cohesion = more wander)
            deviation = self.rng.normal(0, (1 - genetics.flock_cohesion) * 2, 2)
            agent.velocity += deviation * dt
    
    def apply_flocking_forces(self, bird: BirdEntity, dt: float):
        """Apply advanced flocking with leadership mechanics."""
        agent = bird.agent
        genetics = bird.genetics
        
        # Find neighbors within genetics-influenced radius
        neighbors = []
        for other_id, other in self.birds.items():
            if other_id != agent.id and other.agent.alive:
                dist = np.linalg.norm(agent.position - other.agent.position)
                if dist < 120 * (1 + genetics.flock_cohesion * 0.5):
                    neighbors.append(other)
        
        if not neighbors:
            return
        
        # **NEW: Leadership-weighted flocking**
        # Birds with high leadership influence neighbors more strongly
        positions = []
        velocities = []
        weights = []
        
        for neighbor in neighbors:
            positions.append(neighbor.agent.position)
            velocities.append(neighbor.agent.velocity)
            
            # Weight by neighbor's leadership trait
            neighbor_leadership = getattr(neighbor.genetics, 'leadership', 0.5)
            weight = 1.0 + neighbor_leadership * 2.0  # Leaders have 1.0-3.0x influence
            weights.append(weight)
        
        weights = np.array(weights)
        positions = np.array(positions)
        velocities = np.array(velocities)
        
        # Weighted cohesion (drawn to leaders more strongly)
        center = np.average(positions, weights=weights, axis=0)
        cohesion = (center - agent.position) * genetics.flock_cohesion * 0.6
        agent.velocity += cohesion * dt
        
        # Weighted alignment
        avg_vel = np.average(velocities, weights=weights, axis=0)
        alignment = (avg_vel - agent.velocity) * 0.4
        agent.velocity += alignment * dt
        
        # Separation (unweighted - avoid all neighbors equally)
        for neighbor in neighbors[:6]:  # Limit for performance
            diff = agent.position - neighbor.agent.position
            dist = np.linalg.norm(diff)
            if dist < 35 and dist > 0:
                separation = (diff / dist) * 60 / dist
                agent.velocity += separation * dt
    
    def apply_beacon_influence(self, agent: Agent, genetics: Genetics, dt: float):
        """Apply beacon effects using BeaconManager."""
        # Get beacon field contributions
        contributions = self.beacon_manager.get_combined_field_contribution(
            agent.position,
            Tick(self.tick),
            is_night=(self.tick % 1800) > 900
        )
        
        beacon_response = genetics.beacon_sensitivity
        
        # Apply beacon effects
        if contributions["light_attraction"] > 0:
            # Find strongest light beacon for directional pull
            max_strength = 0
            light_direction = np.array([0.0, 0.0])
            
            for beacon in self.beacon_manager.beacons:
                if beacon.beacon_type == BeaconType.LIGHT:
                    strength = beacon.get_field_strength(agent.position, Tick(self.tick))
                    if strength > max_strength:
                        max_strength = strength
                        to_beacon = beacon.position - agent.position
                        dist = np.linalg.norm(to_beacon)
                        if dist > 0:
                            light_direction = to_beacon / dist
            
            if max_strength > 0:
                light_force = light_direction * contributions["light_attraction"] * beacon_response * 30 * dt
                agent.velocity += light_force
        
        # Food scent attraction and energy restoration
        if contributions["foraging_bias"] > 0:
            for beacon in self.beacon_manager.beacons:
                if hasattr(beacon, 'environmental') and beacon.environmental:
                    strength = beacon.get_field_strength(agent.position, Tick(self.tick))
                    
                    if strength > 0.1:
                        # **NEW: Enhanced energy restoration for environmental food**
                        if hasattr(beacon, 'environmental') and beacon.environmental:
                            restore_rate = getattr(beacon, 'energy_restore_rate', 2.0)
                            energy_gain = strength * restore_rate * dt
                            old_energy = agent.energy
                            agent.energy = min(100, agent.energy + energy_gain)
                            
                            # Log significant energy restoration
                            if energy_gain > 0.5:
                                logger.debug(f"Bird {agent.id} feeding: {old_energy:.1f}→{agent.energy:.1f}")
                        else:
                            # Player beacon - smaller restoration
                            energy_gain = strength * beacon_response * 1.0 * dt
                            agent.energy = min(100, agent.energy + energy_gain)
                        
                        # Attraction toward food source
                        to_beacon = beacon.position - agent.position
                        dist = np.linalg.norm(to_beacon)
                        if dist > 0:
                            food_force = (to_beacon / dist) * strength * beacon_response * 25 * dt
                            agent.velocity += food_force
        
        # Shelter/cohesion effects
        if contributions["cohesion_boost"] > 0:
            cohesion_strength = contributions["cohesion_boost"] * beacon_response
            
            # Stress reduction
            agent.stress = max(0, agent.stress - cohesion_strength * 0.8 * dt)
            
            # Slowing effect (for rest behavior)
            slowing_factor = 1.0 - (cohesion_strength * 0.4)
            agent.velocity *= slowing_factor
        
        # Wind/thermal boost
        if contributions["wind_boost"] > 0:
            wind_boost = contributions["wind_boost"] * beacon_response * 20 * dt
            agent.velocity[0] += wind_boost  # Eastward boost
            
            # Small energy bonus
            energy_gain = contributions["wind_boost"] * beacon_response * 0.5 * dt
            agent.energy = min(100, agent.energy + energy_gain)
    
    def apply_hazard_effects(self, bird: BirdEntity, dt: float):
        """Apply enhanced hazard effects with trait interactions."""
        agent = bird.agent
        genetics = bird.genetics
        
        for hazard in self.hazards:
            to_hazard = np.array([hazard['x'] - agent.position[0], hazard['y'] - agent.position[1]])
            dist = np.linalg.norm(to_hazard)
            
            # **NEW: Trait-based hazard detection**
            detection_multiplier = 1 + genetics.hazard_awareness
            effective_radius = hazard.get('radius', 100) * detection_multiplier
            
            # Check danger zones
            danger_level = 0
            if 'danger_zones' in hazard:
                for zone in hazard['danger_zones']:
                    if dist < zone['radius'] * detection_multiplier:
                        danger_level = zone['intensity']
                        break
            else:
                # Fallback danger calculation
                danger_level = max(0, 1 - dist / effective_radius)
            
            if danger_level > 0:
                if hazard['type'] == 'tornado':
                    # Enhanced tornado with genetics interactions
                    if danger_level > 0.3:
                        self.hazards_encountered['tornado'] += dt / 30.0
                        
                        # Spin and confusion effects
                        if dist > 0:
                            tangent = np.array([-to_hazard[1], to_hazard[0]]) / dist
                            spin_force = tangent * hazard['confusion_strength'] * danger_level
                            agent.velocity += spin_force * dt
                        
                        # Random confusion (reduced by awareness)
                        confusion_strength = hazard['confusion_strength'] * (1 - genetics.hazard_awareness * 0.5)
                        confusion = self.rng.normal(0, confusion_strength * danger_level, 2)
                        agent.velocity += confusion * dt
                        
                        # Energy drain (reduced by efficiency)
                        energy_loss = hazard['energy_drain'] * danger_level / genetics.energy_efficiency
                        agent.energy = max(0, agent.energy - energy_loss * dt)
                        
                        # Kill chance (only in death zone)
                        if danger_level >= 1.0:
                            if self.rng.random() < hazard['kill_chance'] * dt:
                                agent.alive = False
                                self.losses += 1
                                logger.info(f"🌪️ Bird lost in tornado! ({bird.gender.value}, Gen {bird.generation})")
                        
                        # Stress (reduced by resilience)
                        stress_increase = 0.08 * danger_level * (1 - genetics.stress_resilience)
                        agent.stress = min(1.0, agent.stress + stress_increase * dt)
                
                elif hazard['type'] == 'predator':
                    # Enhanced predator with chase mechanics
                    if danger_level > 0.5:
                        self.hazards_encountered['predator'] += dt / 30.0
                        
                        # Start predator chase if not already chasing
                        if hazard['chase_timer'] <= 0:
                            hazard['chase_timer'] = hazard.get('chase_duration', 5.0)
                            logger.info(f"🦅 Predator begins hunt! Chase timer: {hazard['chase_timer']:.1f}s")
                            
                            # Trigger flock panic
                            if hazard.get('trigger_panic', False):
                                self.trigger_flock_panic(agent.position, radius=200)
                        
                        # Escape response (stronger with awareness and speed)
                        if dist > 0:
                            escape_strength = 180 * danger_level * genetics.hazard_awareness
                            escape_direction = -to_hazard / dist
                            agent.velocity += escape_direction * escape_strength * dt
                        
                        # High stress during chase
                        stress_increase = 0.15 * danger_level * (1 - genetics.stress_resilience)
                        agent.stress = min(1.0, agent.stress + stress_increase * dt)
                        
                        # Kill chance (only if predator is actively hunting)
                        if hazard['chase_timer'] > 0 and dist < hazard.get('attack_range', 40):
                            kill_chance = hazard['kill_chance']
                            if hazard.get('alpha', False):
                                kill_chance *= 1.5  # Alpha predators more dangerous
                            
                            # Speed factor affects escape chance
                            escape_factor = genetics.speed_factor
                            effective_kill_chance = kill_chance * (2 - escape_factor) * dt
                            
                            if self.rng.random() < effective_kill_chance:
                                agent.alive = False
                                self.losses += 1 
                                logger.info(f"🦅 Predator strike! ({bird.gender.value}, Gen {bird.generation})")
                            else:
                                bird.close_calls += 1  # Track near-death for trait bonuses
    
    def trigger_flock_panic(self, origin: np.ndarray, radius: float = 200):
        """Trigger panic response in nearby birds."""
        self.panic_events += 1
        
        for bird in self.birds.values():
            if not bird.agent.alive:
                continue
                
            dist = np.linalg.norm(bird.agent.position - origin)
            if dist < radius:
                panic_factor = (1 - dist / radius)
                
                # Scatter response (reduced by stress resilience)
                scatter_strength = 120 * panic_factor * (1 - bird.genetics.stress_resilience * 0.5)
                if dist > 0:
                    scatter_direction = (bird.agent.position - origin) / dist
                    bird.agent.velocity += scatter_direction * scatter_strength
                
                # Stress increase
                stress_increase = 0.4 * panic_factor * (1 - bird.genetics.stress_resilience)
                bird.agent.stress = min(1.0, bird.agent.stress + stress_increase)
    
    def continue_to_next_leg(self):
        """Manually continue to next leg of migration (for manual progression)."""
        if not self.waiting_for_continue:
            logger.warning("Not waiting for continue - ignoring continue request")
            return False
            
        self.waiting_for_continue = False
        return self.advance_to_next_leg()
    
    def advance_to_next_leg(self):
        """Advance to next leg of migration."""
        if self.migration_config.advance_to_next_leg(self.rng):
            # Reset level state but keep birds
            self.tick = 0
            self.start_time = time.time()
            self.arrivals = 0
            # Don't reset losses - they carry across legs
            self.game_over = False
            self.victory = False
            
            # Clear the path for the new leg
            self.migration_path = []
            
            # Respawn hazards and food for new leg
            self.spawn_environmental_food()
            self.spawn_hazards()
            
            # Reset bird positions and energy for next leg
            for bird in self.birds.values():
                if bird.agent.alive or bird.survived_levels > 0:  # Include recent arrivals
                    # Reset position to new start zone
                    start_x, start_y, start_radius = self.migration_config.start_zone
                    angle = self.rng.uniform(0, 2 * np.pi)
                    radius = self.rng.uniform(0, start_radius * 0.8)
                    bird.agent.position = np.array([
                        start_x + radius * np.cos(angle),
                        start_y + radius * np.sin(angle)
                    ], dtype=np.float32)
                    
                    # Reset velocity (slowed down for strategic observation)
                    bird.agent.velocity = np.array([
                        self.rng.uniform(1, 3) * bird.genetics.speed_factor,
                        self.rng.uniform(-1, 1) * bird.genetics.speed_factor
                    ], dtype=np.float32)
                    
                    # **NEW: Full energy restoration at checkpoints**
                    bird.agent.alive = True  # Reactivate birds that reached previous checkpoint
                    bird.agent.energy = 100.0  # Full energy recharge
                    bird.agent.stress = max(0, 0.2 * (1 - bird.genetics.stress_resilience))
            
            logger.info(f"Advanced to {self.migration_config.level_name} "
                       f"({self.migration_config.current_leg}/{self.migration_config.total_legs})")
        else:
            # Migration complete - trigger breeding
            self.migration_complete = True
            self.game_over = True
    
    def breed_population(self) -> Dict[str, Any]:
        """Perform breeding after migration completion with experience bonuses."""
        self.generation += 1
        
        # Collect all survivors (birds that completed the migration)
        survivors = []
        for bird in self.birds.values():
            if bird.survived_levels > 0 or bird.agent.alive:  # Include recent arrivals
                survivors.append(bird)
        
        logger.info(f"Starting breeding phase: {len(survivors)} survivors from Generation {self.generation-1}")
        
        # **NEW: Apply experience-based trait bonuses**
        leadership_bonuses = 0
        storm_bonuses = 0
        predator_bonuses = 0
        
        total_migration_time = self.tick / 30.0  # Total seconds
        
        for bird in survivors:
            # Leadership bonus for birds who led the flock
            lead_time = self.leadership_tracking.get(bird.agent.id, 0)
            if lead_time > total_migration_time * 0.1:  # Led for 10%+ of time
                if not hasattr(bird.genetics, 'leadership'):
                    bird.genetics.leadership = 0.5  # Add if missing
                old_leadership = bird.genetics.leadership
                bird.genetics.leadership = min(1.0, bird.genetics.leadership + 0.05)
                leadership_bonuses += 1
                logger.info(f"Bird {bird.agent.id} gained leadership: {old_leadership:.2f}→{bird.genetics.leadership:.2f}")
            
            # Storm survival bonus
            if bird.agent.id in self.hazards_encountered.get('tornado_survivors', []):
                old_awareness = bird.genetics.hazard_awareness
                bird.genetics.hazard_awareness = min(1.0, bird.genetics.hazard_awareness + 0.08)
                storm_bonuses += 1
                logger.info(f"Bird {bird.agent.id} gained storm awareness: {old_awareness:.2f}→{bird.genetics.hazard_awareness:.2f}")
            
            # Predator escape bonus  
            if bird.close_calls > 0:
                old_speed = bird.genetics.speed_factor
                bird.genetics.speed_factor = min(1.2, bird.genetics.speed_factor * 1.05)
                predator_bonuses += 1
                logger.info(f"Bird {bird.agent.id} gained speed from escapes: {old_speed:.2f}→{bird.genetics.speed_factor:.2f}")
        
        # Perform breeding using genetic simulation logic
        from .simulation_genetic import GeneticSimulation
        
        # Temporarily use existing breeding logic
        old_birds = self.birds
        self.birds = {b.agent.id: b for b in survivors}
        
        # Sort by fitness for selective breeding
        survivors.sort(key=lambda b: b.fitness_score, reverse=True)
        
        # Apply selection pressure
        breeding_cutoff = 0.8 if len(survivors) > 30 else 1.0
        breeding_pool = survivors[:int(len(survivors) * breeding_cutoff)]
        
        males = [b for b in breeding_pool if b.gender == Gender.MALE]
        females = [b for b in breeding_pool if b.gender == Gender.FEMALE]
        
        logger.info(f"Breeding pool: {len(males)} males, {len(females)} females")
        
        # Create offspring
        offspring = []
        breeding_pairs = []
        
        for i in range(min(len(males), len(females))):
            male = males[i]
            female = females[i]
            
            # Offspring count based on population health
            offspring_count = 2 if len(survivors) < 40 else 1
            
            for _ in range(offspring_count):
                if self.rng.random() <= male.genetics.fertility * female.genetics.fertility:
                    # Breed offspring
                    child_genetics = Genetics.breed(male.genetics, female.genetics, self.rng)
                    child_gender = Gender.MALE if self.rng.random() < 0.5 else Gender.FEMALE
                    
                    child = self.create_bird(
                        gender=child_gender,
                        generation=self.generation,
                        genetics=child_genetics,
                        parents=(male.agent.id, female.agent.id)
                    )
                    
                    offspring.append(child)
                    breeding_pairs.append((male.agent.id, female.agent.id))
        
        # Rebuild population with survivors + offspring (cap at 100 birds for performance)
        max_population = 100
        total_candidates = len(survivors) + len(offspring)
        
        self.birds.clear()
        
        # Population control: Balance survivors vs offspring to stay under cap
        if total_candidates > max_population:
            # Prioritize top survivors, fill remainder with offspring
            survivor_slots = min(len(survivors), max_population * 2 // 3)  # Reserve 2/3 for survivors
            offspring_slots = max_population - survivor_slots
            survivors = survivors[:survivor_slots]
            offspring = offspring[:offspring_slots]
        
        # Add survivors back (reset for next migration)
        survivors_to_keep = len(survivors)
        for survivor in survivors:
            survivor.agent.alive = True
            survivor.agent.energy = 100.0
            survivor.agent.stress = max(0, 0.2 * (1 - survivor.genetics.stress_resilience))
            self.birds[survivor.agent.id] = survivor
        
        # Add offspring
        offspring_to_keep = min(len(offspring), 100 - len(self.birds))
        for child in offspring[:offspring_to_keep]:
            self.birds[child.agent.id] = child
        
        # Fill to minimum if needed (ensure at least 100 birds)
        while len(self.birds) < 100:
            gender = Gender.MALE if len([b for b in self.birds.values() if b.gender == Gender.MALE]) < len(self.birds) // 2 else Gender.FEMALE
            new_bird = self.create_bird(gender=gender, generation=self.generation)
            self.birds[new_bird.agent.id] = new_bird
        
        final_population = len(self.birds)
        logger.info(f"Breeding complete: {len(offspring)} offspring, {survivors_to_keep} survivors, "
                   f"{final_population} total population, Generation {self.generation}")
        
        return {
            'pairs_formed': len(breeding_pairs),
            'offspring_created': len(offspring),
            'survivors': survivors_to_keep,
            'new_generation': self.generation,
            'population_size': final_population,
            'experience_bonuses': {
                'leadership': leadership_bonuses,
                'storm_survival': storm_bonuses,
                'predator_escape': predator_bonuses
            }
        }
    
    def calculate_population_stats(self) -> PopulationStats:
        """Calculate population statistics."""
        from .simulation_genetic import PopulationStats
        
        stats = PopulationStats()
        alive_birds = [b for b in self.birds.values() if b.agent.alive]
        
        if not alive_birds:
            return stats
        
        stats.total_population = len(alive_birds)
        stats.males = sum(1 for b in alive_birds if b.gender == Gender.MALE)
        stats.females = stats.total_population - stats.males
        
        # Calculate average genetics
        if alive_birds:
            stats.avg_hazard_awareness = np.mean([b.genetics.hazard_awareness for b in alive_birds])
            stats.avg_energy_efficiency = np.mean([b.genetics.energy_efficiency for b in alive_birds])
            stats.avg_flock_cohesion = np.mean([b.genetics.flock_cohesion for b in alive_birds])
            stats.avg_beacon_sensitivity = np.mean([b.genetics.beacon_sensitivity for b in alive_birds])
            stats.avg_stress_resilience = np.mean([b.genetics.stress_resilience for b in alive_birds])
            
            # Genetic diversity
            trait_variances = [
                np.var([b.genetics.hazard_awareness for b in alive_birds]),
                np.var([b.genetics.energy_efficiency for b in alive_birds]),
                np.var([b.genetics.flock_cohesion for b in alive_birds]),
                np.var([b.genetics.beacon_sensitivity for b in alive_birds]),
                np.var([b.genetics.stress_resilience for b in alive_birds])
            ]
            stats.genetic_diversity = np.mean(trait_variances)
        
        return stats
    
    def bird_to_dict(self, bird: BirdEntity) -> Dict:
        """Convert bird to dictionary for client."""
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
            'genetics': {
                'hazard_awareness': bird.genetics.hazard_awareness,
                'energy_efficiency': bird.genetics.energy_efficiency,
                'flock_cohesion': bird.genetics.flock_cohesion,
                'beacon_sensitivity': bird.genetics.beacon_sensitivity,
                'stress_resilience': bird.genetics.stress_resilience,
                'speed_factor': bird.genetics.speed_factor,
                'leadership': getattr(bird.genetics, 'leadership', 0.5)
            },
            'fitness': bird.fitness_score,
            'survived_levels': bird.survived_levels,
            'close_calls': bird.close_calls,
            'leadership_time': self.leadership_tracking.get(bird.agent.id, 0)
        }
    
    def place_beacon(self, beacon_type: str, x: float, y: float) -> bool:
        """Place beacon using BeaconManager (no food beacons for players)."""
        # **NEW: Remove food beacon from player options**
        if beacon_type == 'food':
            logger.warning("Food beacons not available to players - use environmental food sites")
            return False
        
        # Map client beacon types to BeaconType
        type_mapping = {
            'light': BeaconType.LIGHT,
            'shelter': BeaconType.SOUND,  # Sound provides cohesion/shelter  
            'thermal': BeaconType.WIND_LURE  # Wind provides forward boost
        }
        
        if beacon_type not in type_mapping:
            logger.warning(f"Unknown beacon type: {beacon_type}")
            return False
        
        mapped_type = type_mapping[beacon_type]
        position = create_vector2d(x, y)
        
        beacon = self.beacon_manager.place_beacon(mapped_type, position, Tick(self.tick))
        
        if beacon:
            logger.info(f"Beacon placed: {beacon_type} at ({x:.0f}, {y:.0f})")
            return True
        else:
            logger.warning("Beacon placement failed: budget exceeded")
            return False
    
    def reset(self):
        """Reset for new migration attempt."""
        # Reset migration to start
        self.migration_config = MigrationConfig.generate_migration(
            migration_id=self.migration_config.migration_id,
            rng=self.rng
        )
        
        # Reset all state
        self.tick = 0
        self.start_time = time.time()
        self.arrivals = 0
        self.losses = 0
        self.game_over = False
        self.victory = False
        self.migration_complete = False
        self.waiting_for_continue = False
        
        # Clear tracking
        self.hazards_encountered = {'tornado': 0, 'predator': 0}
        self.leadership_tracking.clear()
        self.close_calls = 0
        self.panic_events = 0
        
        # Reset beacon system  
        self.beacon_manager = BeaconManager(budget_limit=self.migration_config.beacon_budget)
        
        # Respawn environmental elements
        self.spawn_environmental_food()
        self.spawn_hazards()
        
        # Reset bird positions and state
        for bird in self.birds.values():
            start_x, start_y, start_radius = self.migration_config.start_zone
            angle = self.rng.uniform(0, 2 * np.pi)
            radius = self.rng.uniform(0, start_radius)
            bird.agent.position = np.array([
                start_x + radius * np.cos(angle),
                start_y + radius * np.sin(angle)
            ], dtype=np.float32)
            
            bird.agent.velocity = np.array([
                self.rng.uniform(1, 3) * bird.genetics.speed_factor,
                self.rng.uniform(-1, 1) * bird.genetics.speed_factor
            ], dtype=np.float32)
            
            bird.agent.alive = True
            bird.agent.energy = 100.0
            bird.agent.stress = max(0, 0.2 * (1 - bird.genetics.stress_resilience))
            
            # Reset leadership tracking
            self.leadership_tracking[bird.agent.id] = 0.0
        
        logger.info(f"Migration reset: {self.migration_config.level_name}, {len(self.birds)} birds")