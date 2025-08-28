export interface GameConfig {
  width: number;
  height: number;
  worldWidth: number;
  worldHeight: number;
  debug: boolean;
}

export interface Agent {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  energy: number;
  stress: number;
  alive: boolean;
  // NEW: Genetic traits for enhanced UI
  gender?: 'male' | 'female';
  generation?: number;
  genetics?: {
    hazard_awareness: number;
    energy_efficiency: number;
    flock_cohesion: number;
    beacon_sensitivity: number;
    stress_resilience: number;
    leadership: number;
    speed_factor: number;
  };
  fitness?: number;
  survived_levels?: number;
  close_calls?: number;
  leadership_time?: number;
}

export interface Beacon {
  id: string;
  type: 'food' | 'shelter' | 'thermal' | 'light' | 'wind_up' | 'wind_down';
  x: number;
  y: number;
  active: boolean;
  strength: number;
  environmental?: boolean; // NEW: Environmental food vs player beacons
  radius?: number;
  decay?: number;
}

export interface Hazard {
  id: string;
  type: 'tornado' | 'predator' | 'light_pollution';
  x: number;
  y: number;
  active: boolean;
  dangerZones: Array<{
    radius: number;
    intensity: number;
  }>;
}

export interface GameState {
  agents: Agent[];
  beacons: Beacon[];
  hazards: Hazard[];
  level: number;
  generation: number;
  running: boolean;
  completed: boolean;
  // NEW: Enhanced stats for genetic gameplay
  migration_id?: number;
  current_leg?: number;
  total_legs?: number;
  level_name?: string;
  population?: number;
  males?: number;
  females?: number;
  arrivals?: number;
  losses?: number;
  food_sites?: Array<{x: number, y: number, radius: number}>;
  migration_complete?: boolean;
  population_stats?: {
    total_population: number;
    males: number;
    females: number;
    avg_hazard_awareness: number;
    avg_energy_efficiency: number;
    avg_flock_cohesion: number;
    avg_beacon_sensitivity: number;
    avg_stress_resilience: number;
    avg_leadership: number;
    genetic_diversity: number;
  };
  leadership_leaders?: Array<{
    id: number;
    gender: string;
    generation: number;
    lead_time: number;
    lead_percentage: number;
    leadership_trait: number;
  }>;
  close_calls?: number;
  panic_events?: number;
  stats: {
    survived: number;
    total: number;
    energy: number;
    stress: number;
  };
}

// NEW: Breeding result interface for UI
export interface BreedingResult {
  pairs_formed: number;
  offspring_created: number;
  survivors: number;
  new_generation: number;
  population_size: number;
  experience_bonuses: {
    leadership: number;
    storm_survival: number;
    predator_escape: number;
  };
}

export interface WebSocketMessage {
  type: 'game_state' | 'level_complete' | 'agent_update' | 'error' | 'migration_breeding_complete' | 'state_update';
  data: GameState | string | Record<string, unknown> | BreedingResult;
  timestamp: number;
}