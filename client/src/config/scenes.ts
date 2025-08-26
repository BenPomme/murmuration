import type { Types } from 'phaser';

export const SCENE_CONFIG: Types.Core.GameConfig['scene'] = [
  {
    key: 'LoadingScene',
    // Will be imported dynamically to reduce initial bundle size
  },
  {
    key: 'MenuScene',
  },
  {
    key: 'GameScene',
  },
];

export const SCENE_TRANSITIONS = {
  FADE_DURATION: 300,
  SLIDE_DURATION: 500,
} as const;