export interface AssetConfig {
  key: string;
  url: string;
  type: 'image' | 'audio' | 'json' | 'atlas';
  frameConfig?: {
    frameWidth: number;
    frameHeight: number;
  };
}

export interface SpriteConfig {
  key: string;
  frame?: string | number;
  x?: number;
  y?: number;
  scale?: number;
  rotation?: number;
  alpha?: number;
  tint?: number;
}

export interface AudioConfig {
  key: string;
  volume?: number;
  loop?: boolean;
  delay?: number;
}

export type AssetKeys = {
  // Sprites
  BIRD: 'bird';
  BEACON_FOOD: 'beacon_food';
  BEACON_SHELTER: 'beacon_shelter';
  BEACON_THERMAL: 'beacon_thermal';
  TORNADO: 'tornado';
  PREDATOR: 'predator';
  BACKGROUND: 'background';
  
  // UI
  BUTTON: 'button';
  PANEL: 'panel';
  HUD_BACKGROUND: 'hud_background';
  
  // Audio
  AMBIENT: 'ambient';
  BEACON_PLACE: 'beacon_place';
  HAZARD_WARNING: 'hazard_warning';
  LEVEL_COMPLETE: 'level_complete';
};