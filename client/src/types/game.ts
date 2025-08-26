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
}

export interface Beacon {
  id: string;
  type: 'food' | 'shelter' | 'thermal';
  x: number;
  y: number;
  active: boolean;
  strength: number;
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
  stats: {
    survived: number;
    total: number;
    energy: number;
    stress: number;
  };
}

export interface WebSocketMessage {
  type: 'game_state' | 'level_complete' | 'agent_update' | 'error';
  data: GameState | string | Record<string, unknown>;
  timestamp: number;
}