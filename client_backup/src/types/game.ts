/**
 * TypeScript types for Murmuration client
 * Following strict typing requirements from CLAUDE.md
 */

export interface Vector2D {
  readonly x: number;
  readonly y: number;
}

export interface Agent {
  readonly id: string;
  readonly position: Vector2D;
  readonly velocity: Vector2D;
  readonly energy: number; // 0-100
  readonly stress: number; // 0-100
  readonly genomeId: string;
}

export interface BeaconType {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly cost: number;
  readonly radius: number;
  readonly halfLifeDays: number;
  readonly color: string;
}

export interface Beacon {
  readonly id: string;
  readonly type: BeaconType;
  readonly position: Vector2D;
  readonly placedAt: number; // game tick
  readonly strength: number; // 0-1, decays over time
}

export interface PulseType {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly cooldownHours: number;
  readonly radius: number;
  readonly durationHours: number;
  readonly maxUses?: number;
}

export interface ActivePulse {
  readonly type: PulseType;
  readonly position: Vector2D;
  readonly activatedAt: number;
  readonly expiresAt: number;
}

export interface WeatherForecast {
  readonly hour: number; // hours from now
  readonly windDirection: number; // radians
  readonly windStrength: number; // 0-1
  readonly hazardType?: 'storm' | 'predator' | 'light_pollution';
  readonly hazardIntensity?: number; // 0-1
}

export interface GameState {
  readonly tick: number;
  readonly gameDay: number;
  readonly gameHour: number; // 0-23
  readonly season: number;
  readonly agents: readonly Agent[];
  readonly beacons: readonly Beacon[];
  readonly activePulses: readonly ActivePulse[];
  readonly wind: Vector2D;
  readonly forecast: readonly WeatherForecast[];
  readonly strikes: number;
  readonly population: number;
  readonly arrivals: number;
  readonly deaths: number;
  readonly cohesion: number; // 0-1
  readonly diversity: number; // 0-1
  readonly beaconBudgetRemaining: number;
}

export interface ContractTargets {
  readonly timeLimit: number; // days
  readonly arrivalsMin: number;
  readonly cohesionAvgMin: number;
  readonly lossesMax: number;
  readonly diversityMin?: number;
  readonly beaconBudgetMax: number;
  readonly seasonsAllowed: number;
}

export interface ContractResults {
  readonly metAllTargets: boolean;
  readonly daysUsed: number;
  readonly arrivals: number;
  readonly cohesionAvg: number;
  readonly losses: number;
  readonly diversity?: number;
  readonly beaconsUsed: number;
  readonly stars: number; // 0-3
}

export interface Level {
  readonly id: string;
  readonly name: string;
  readonly world: string;
  readonly mapData: MapData;
  readonly targets: ContractTargets;
  readonly hazards: readonly string[];
  readonly description: string;
}

export interface MapData {
  readonly width: number;
  readonly height: number;
  readonly startPosition: Vector2D;
  readonly targetPosition: Vector2D;
  readonly obstacles: readonly Vector2D[];
  readonly protectedZones?: readonly Vector2D[];
  readonly windField: readonly (readonly number[])[];
  readonly riskField: readonly (readonly number[])[];
  readonly foodField: readonly (readonly number[])[];
}

export type OverlayType = 'wind' | 'risk' | 'light' | 'paths' | 'heatmap';

export type GameSpeed = 0 | 1 | 2 | 4; // 0 = paused

export interface GameSettings {
  readonly overlays: readonly OverlayType[];
  readonly speed: GameSpeed;
  readonly showMinimap: boolean;
  readonly accessibilityMode: boolean;
  readonly reducedMotion: boolean;
  readonly highContrast: boolean;
}

export interface WebSocketMessage {
  readonly type: string;
  readonly payload: unknown;
}

export interface GameStateMessage extends WebSocketMessage {
  readonly type: 'game_state';
  readonly payload: GameState;
}

export interface LevelMessage extends WebSocketMessage {
  readonly type: 'level';
  readonly payload: Level;
}

export interface ErrorMessage extends WebSocketMessage {
  readonly type: 'error';
  readonly payload: {
    readonly message: string;
    readonly code?: string;
  };
}

export type IncomingMessage = GameStateMessage | LevelMessage | ErrorMessage;

export interface PlaceBeaconCommand {
  readonly type: 'place_beacon';
  readonly beaconTypeId: string;
  readonly position: Vector2D;
}

export interface RemoveBeaconCommand {
  readonly type: 'remove_beacon';
  readonly beaconId: string;
}

export interface ActivatePulseCommand {
  readonly type: 'activate_pulse';
  readonly pulseTypeId: string;
  readonly position: Vector2D;
}

export interface SetSpeedCommand {
  readonly type: 'set_speed';
  readonly speed: GameSpeed;
}

export type OutgoingMessage = PlaceBeaconCommand | RemoveBeaconCommand | ActivatePulseCommand | SetSpeedCommand;

// Predefined beacon and pulse types based on design doc
export const BEACON_TYPES: readonly BeaconType[] = [
  {
    id: 'light',
    name: 'Light Beacon',
    description: 'Draws birds at night',
    cost: 1,
    radius: 150,
    halfLifeDays: 1.5,
    color: '#FFD700'
  },
  {
    id: 'sound',
    name: 'Sound Beacon',
    description: 'Increases cohesion locally',
    cost: 1,
    radius: 180,
    halfLifeDays: 1.0,
    color: '#87CEEB'
  },
  {
    id: 'food',
    name: 'Food Scent',
    description: 'Biases foraging path',
    cost: 2,
    radius: 120,
    halfLifeDays: 0.8,
    color: '#32CD32'
  },
  {
    id: 'wind',
    name: 'Wind Lure',
    description: 'Boosts effective tailwind',
    cost: 2,
    radius: 200,
    halfLifeDays: 1.0,
    color: '#E6E6FA'
  }
] as const;

export const PULSE_TYPES: readonly PulseType[] = [
  {
    id: 'festival',
    name: 'Festival Pulse',
    description: 'Reward multiplier boost',
    cooldownHours: 24,
    radius: 220,
    durationHours: 12,
    maxUses: undefined
  },
  {
    id: 'scout',
    name: 'Scouting Ping',
    description: 'Reveals fog of war',
    cooldownHours: 0,
    radius: 200,
    durationHours: 24,
    maxUses: undefined
  }
] as const;

// Accessibility constants
export const ACCESSIBILITY = {
  MIN_CONTRAST_RATIO: 4.5,
  MIN_TOUCH_TARGET: 44, // pixels
  KEYBOARD_NAVIGATION: true,
  SCREEN_READER_SUPPORT: true
} as const;

// Performance constants
export const PERFORMANCE = {
  TARGET_FPS: 60,
  MAX_AGENTS: 300,
  RENDER_DISTANCE: 2000
} as const;