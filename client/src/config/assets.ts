import type { AssetConfig, AssetKeys } from '@/types';

export const ASSET_KEYS: AssetKeys = {
  // Sprites
  BIRD: 'bird',
  BEACON_FOOD: 'beacon_food',
  BEACON_SHELTER: 'beacon_shelter',
  BEACON_THERMAL: 'beacon_thermal',
  TORNADO: 'tornado',
  PREDATOR: 'predator',
  BACKGROUND: 'background',
  
  // UI
  BUTTON: 'button',
  PANEL: 'panel',
  HUD_BACKGROUND: 'hud_background',
  
  // Audio
  AMBIENT: 'ambient',
  BEACON_PLACE: 'beacon_place',
  HAZARD_WARNING: 'hazard_warning',
  LEVEL_COMPLETE: 'level_complete',
};

export const ASSET_MANIFEST: AssetConfig[] = [
  // Images - using placeholder paths until actual assets are created
  {
    key: ASSET_KEYS.BIRD,
    url: 'assets/sprites/bird.png',
    type: 'image',
  },
  {
    key: ASSET_KEYS.BEACON_FOOD,
    url: 'assets/sprites/beacon_food.png',
    type: 'image',
  },
  {
    key: ASSET_KEYS.BEACON_SHELTER,
    url: 'assets/sprites/beacon_shelter.png',
    type: 'image',
  },
  {
    key: ASSET_KEYS.BEACON_THERMAL,
    url: 'assets/sprites/beacon_thermal.png',
    type: 'image',
  },
  {
    key: ASSET_KEYS.TORNADO,
    url: 'assets/sprites/tornado.png',
    type: 'image',
  },
  {
    key: ASSET_KEYS.PREDATOR,
    url: 'assets/sprites/predator.png',
    type: 'image',
  },
  {
    key: ASSET_KEYS.BACKGROUND,
    url: 'assets/sprites/background.png',
    type: 'image',
  },
  
  // UI
  {
    key: ASSET_KEYS.BUTTON,
    url: 'assets/sprites/ui/button.png',
    type: 'image',
  },
  {
    key: ASSET_KEYS.PANEL,
    url: 'assets/sprites/ui/panel.png',
    type: 'image',
  },
  {
    key: ASSET_KEYS.HUD_BACKGROUND,
    url: 'assets/sprites/ui/hud_background.png',
    type: 'image',
  },
  
  // Audio
  {
    key: ASSET_KEYS.AMBIENT,
    url: 'assets/sounds/ambient.ogg',
    type: 'audio',
  },
  {
    key: ASSET_KEYS.BEACON_PLACE,
    url: 'assets/sounds/beacon_place.ogg',
    type: 'audio',
  },
  {
    key: ASSET_KEYS.HAZARD_WARNING,
    url: 'assets/sounds/hazard_warning.ogg',
    type: 'audio',
  },
  {
    key: ASSET_KEYS.LEVEL_COMPLETE,
    url: 'assets/sounds/level_complete.ogg',
    type: 'audio',
  },
];