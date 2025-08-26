export const GAME_CONFIG = {
  width: 1200,
  height: 800,
  worldWidth: 2000,
  worldHeight: 1200,
  debug: import.meta.env.DEV || false,
};

export const PHYSICS_CONFIG = {
  fps: 60,
  fixedTimeStep: true,
  timeScale: 1,
  maxSubSteps: 3,
  gravity: { x: 0, y: 0 },
} as const;

export const WEBSOCKET_CONFIG = {
  url: 'ws://localhost:8765',
  reconnectInterval: 3000,
  maxReconnectAttempts: 5,
  heartbeatInterval: 30000,
} as const;

export const CAMERA_CONFIG = {
  followSmoothness: 0.1,
  zoomSpeed: 0.02,
  minZoom: 0.5,
  maxZoom: 2.0,
  panSpeed: 10,
} as const;

export const SCENE_KEYS = {
  LOADING: 'LoadingScene',
  MENU: 'MenuScene',
  GAME: 'GameScene',
} as const;

export const LAYER_DEPTHS = {
  BACKGROUND: 0,
  HAZARDS: 10,
  AGENTS: 20,
  BEACONS: 30,
  UI: 40,
  DEBUG: 50,
} as const;