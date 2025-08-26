/**
 * GameCanvas component using PixiJS for high-performance rendering
 * Renders agents as luminous glyphs with motion trails at 60fps for 300+ agents
 */

import React, { useEffect, useRef, useCallback, useMemo } from 'react';
import * as PIXI from 'pixi.js';
import type { 
  GameState, 
  Agent, 
  Beacon, 
  Vector2D, 
  OverlayType,
  MapData,
  GameSettings 
} from '../types/game';
import { BEACON_TYPES, PERFORMANCE } from '../types/game';

interface GameCanvasProps {
  readonly gameState: GameState | null;
  readonly mapData: MapData | null;
  readonly settings: GameSettings;
  readonly onCanvasClick?: (position: Vector2D) => void;
  readonly onAgentClick?: (agent: Agent) => void;
  readonly onBeaconClick?: (beacon: Beacon) => void;
  readonly className?: string;
}

interface AgentSprite extends PIXI.Container {
  agentId: string;
  trail: PIXI.Graphics;
  glyph: PIXI.Graphics;
  trailPositions: Vector2D[];
}

interface BeaconSprite extends PIXI.Container {
  beaconId: string;
  beacon: Beacon;
  radiusCircle: PIXI.Graphics;
  icon: PIXI.Graphics;
  decayArc: PIXI.Graphics;
}

interface OverlaySprite extends PIXI.Container {
  overlayType: OverlayType;
  field: PIXI.Graphics;
}

const CANVAS_WIDTH = 1200;
const CANVAS_HEIGHT = 800;
const WORLD_WIDTH = 2000;
const WORLD_HEIGHT = 1200;
const TRAIL_LENGTH = 20;
const GLYPH_SIZE = 3;
const BEACON_ICON_SIZE = 8;

export function GameCanvas({
  gameState,
  mapData,
  settings,
  onCanvasClick,
  onAgentClick,
  onBeaconClick,
  className = ''
}: GameCanvasProps): JSX.Element {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pixiAppRef = useRef<PIXI.Application | null>(null);
  const agentSpritesRef = useRef<Map<string, AgentSprite>>(new Map());
  const beaconSpritesRef = useRef<Map<string, BeaconSprite>>(new Map());
  const overlaySpritesRef = useRef<Map<OverlayType, OverlaySprite>>(new Map());
  const lastUpdateTimeRef = useRef<number>(0);

  // Color schemes for accessibility
  const colorScheme = useMemo(() => {
    const base = {
      agent: settings.highContrast ? 0xFFFFFF : 0x87CEEB,
      agentTrail: settings.highContrast ? 0xCCCCCC : 0x4169E1,
      background: settings.highContrast ? 0x000000 : 0x0F0F23,
      wind: settings.highContrast ? 0xFFFF00 : 0xE6E6FA,
      risk: settings.highContrast ? 0xFF0000 : 0xFF6B6B,
      food: settings.highContrast ? 0x00FF00 : 0x90EE90,
      light: settings.highContrast ? 0xFFFFFF : 0xFFD700
    };
    return base;
  }, [settings.highContrast]);

  // Initialize PixiJS application
  const initializePixi = useCallback(async () => {
    if (!canvasRef.current || pixiAppRef.current) return;

    try {
      const app = new PIXI.Application({
        view: canvasRef.current,
        width: CANVAS_WIDTH,
        height: CANVAS_HEIGHT,
        backgroundColor: colorScheme.background,
        antialias: !settings.reducedMotion, // Disable antialiasing for reduced motion
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      });

      await app.init();
      pixiAppRef.current = app;

      // Set up interaction
      app.stage.eventMode = 'static';
      app.stage.hitArea = new PIXI.Rectangle(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);
      
      app.stage.on('pointerdown', (event) => {
        if (!onCanvasClick) return;
        
        const worldPos = screenToWorld({ 
          x: event.global.x, 
          y: event.global.y 
        });
        onCanvasClick(worldPos);
      });

    } catch (error) {
      console.error('Failed to initialize PixiJS:', error);
    }
  }, [colorScheme.background, settings.reducedMotion, onCanvasClick]);

  // World to screen coordinate conversion
  const worldToScreen = useCallback((worldPos: Vector2D): Vector2D => ({
    x: (worldPos.x / WORLD_WIDTH) * CANVAS_WIDTH,
    y: (worldPos.y / WORLD_HEIGHT) * CANVAS_HEIGHT
  }), []);

  const screenToWorld = useCallback((screenPos: Vector2D): Vector2D => ({
    x: (screenPos.x / CANVAS_WIDTH) * WORLD_WIDTH,
    y: (screenPos.y / CANVAS_HEIGHT) * WORLD_HEIGHT
  }), []);

  // Create agent sprite
  const createAgentSprite = useCallback((agent: Agent): AgentSprite => {
    const container = new PIXI.Container() as AgentSprite;
    container.agentId = agent.id;
    container.trailPositions = [];

    // Create trail
    const trail = new PIXI.Graphics();
    container.trail = trail;
    container.addChild(trail);

    // Create glyph
    const glyph = new PIXI.Graphics();
    container.glyph = glyph;
    container.addChild(glyph);

    // Make interactive
    container.eventMode = 'static';
    container.cursor = 'pointer';
    container.on('pointerdown', (event) => {
      event.stopPropagation();
      onAgentClick?.(agent);
    });

    return container;
  }, [onAgentClick]);

  // Update agent sprite
  const updateAgentSprite = useCallback((sprite: AgentSprite, agent: Agent) => {
    const screenPos = worldToScreen(agent.position);
    sprite.position.set(screenPos.x, screenPos.y);

    // Update trail positions
    sprite.trailPositions.push(agent.position);
    if (sprite.trailPositions.length > TRAIL_LENGTH) {
      sprite.trailPositions.shift();
    }

    // Draw trail
    if (!settings.reducedMotion && sprite.trailPositions.length > 1) {
      sprite.trail.clear();
      sprite.trail.moveTo(0, 0);
      
      for (let i = 1; i < sprite.trailPositions.length; i++) {
        const trailPos = worldToScreen(sprite.trailPositions[i]!);
        const alpha = i / sprite.trailPositions.length;
        const relativePos = {
          x: trailPos.x - screenPos.x,
          y: trailPos.y - screenPos.y
        };
        
        sprite.trail.lineStyle({
          width: 1,
          color: colorScheme.agentTrail,
          alpha: alpha * 0.6
        });
        sprite.trail.lineTo(relativePos.x, relativePos.y);
      }
    }

    // Draw glyph based on agent state
    sprite.glyph.clear();
    
    const glyphColor = agent.energy < 30 ? 0xFF6B6B : 
                      agent.stress > 70 ? 0xFFA500 : 
                      colorScheme.agent;
    
    const glyphSize = GLYPH_SIZE * (1 + agent.energy / 200);
    
    sprite.glyph.beginFill(glyphColor, 0.9);
    sprite.glyph.drawCircle(0, 0, glyphSize);
    sprite.glyph.endFill();

    // Add velocity indicator
    if (agent.velocity.x !== 0 || agent.velocity.y !== 0) {
      const velocityMagnitude = Math.sqrt(agent.velocity.x ** 2 + agent.velocity.y ** 2);
      const normalizedVel = {
        x: agent.velocity.x / velocityMagnitude,
        y: agent.velocity.y / velocityMagnitude
      };
      
      sprite.glyph.lineStyle(1, glyphColor, 0.7);
      sprite.glyph.moveTo(0, 0);
      sprite.glyph.lineTo(
        normalizedVel.x * glyphSize * 2,
        normalizedVel.y * glyphSize * 2
      );
    }
  }, [worldToScreen, settings.reducedMotion, colorScheme]);

  // Create beacon sprite
  const createBeaconSprite = useCallback((beacon: Beacon): BeaconSprite => {
    const container = new PIXI.Container() as BeaconSprite;
    container.beaconId = beacon.id;
    container.beacon = beacon;

    // Create radius circle
    const radiusCircle = new PIXI.Graphics();
    container.radiusCircle = radiusCircle;
    container.addChild(radiusCircle);

    // Create icon
    const icon = new PIXI.Graphics();
    container.icon = icon;
    container.addChild(icon);

    // Create decay arc
    const decayArc = new PIXI.Graphics();
    container.decayArc = decayArc;
    container.addChild(decayArc);

    // Make interactive
    container.eventMode = 'static';
    container.cursor = 'pointer';
    container.on('pointerdown', (event) => {
      event.stopPropagation();
      onBeaconClick?.(beacon);
    });

    return container;
  }, [onBeaconClick]);

  // Update beacon sprite
  const updateBeaconSprite = useCallback((sprite: BeaconSprite, beacon: Beacon) => {
    const screenPos = worldToScreen(beacon.position);
    sprite.position.set(screenPos.x, screenPos.y);

    const beaconType = BEACON_TYPES.find(type => type.id === beacon.type.id);
    if (!beaconType) return;

    // Draw radius circle
    const radiusInScreen = (beaconType.radius / WORLD_WIDTH) * CANVAS_WIDTH;
    sprite.radiusCircle.clear();
    sprite.radiusCircle.lineStyle({
      width: 1,
      color: parseInt(beaconType.color.replace('#', ''), 16),
      alpha: 0.3
    });
    sprite.radiusCircle.drawCircle(0, 0, radiusInScreen);

    // Draw icon
    sprite.icon.clear();
    const iconColor = parseInt(beaconType.color.replace('#', ''), 16);
    
    sprite.icon.beginFill(iconColor, beacon.strength);
    sprite.icon.drawCircle(0, 0, BEACON_ICON_SIZE);
    sprite.icon.endFill();

    // Draw decay arc
    sprite.decayArc.clear();
    if (beacon.strength < 1) {
      const angle = beacon.strength * Math.PI * 2;
      sprite.decayArc.lineStyle(2, iconColor, 0.8);
      sprite.decayArc.arc(0, 0, BEACON_ICON_SIZE + 2, -Math.PI / 2, -Math.PI / 2 + angle);
    }
  }, [worldToScreen]);

  // Create overlay sprite
  const createOverlaySprite = useCallback((overlayType: OverlayType): OverlaySprite => {
    const container = new PIXI.Container() as OverlaySprite;
    container.overlayType = overlayType;

    const field = new PIXI.Graphics();
    container.field = field;
    container.addChild(field);

    return container;
  }, []);

  // Update overlay sprite
  const updateOverlaySprite = useCallback((sprite: OverlaySprite, overlayType: OverlayType) => {
    if (!mapData) return;

    sprite.field.clear();

    switch (overlayType) {
      case 'wind':
        // Draw wind field as arrows
        sprite.field.lineStyle(1, colorScheme.wind, 0.6);
        for (let x = 0; x < mapData.windField.length; x += 4) {
          for (let y = 0; y < mapData.windField[0]!.length; y += 4) {
            const windX = mapData.windField[x]?.[y] ?? 0;
            const windY = mapData.windField[x]?.[y + 1] ?? 0;
            
            if (windX === 0 && windY === 0) continue;
            
            const worldX = (x / mapData.windField.length) * WORLD_WIDTH;
            const worldY = (y / mapData.windField[0]!.length) * WORLD_HEIGHT;
            const screenPos = worldToScreen({ x: worldX, y: worldY });
            
            const arrowLength = 8;
            sprite.field.moveTo(screenPos.x, screenPos.y);
            sprite.field.lineTo(
              screenPos.x + windX * arrowLength,
              screenPos.y + windY * arrowLength
            );
          }
        }
        break;

      case 'risk':
        // Draw risk field as heatmap
        sprite.field.beginFill(colorScheme.risk, 0.3);
        for (let x = 0; x < mapData.riskField.length; x++) {
          for (let y = 0; y < mapData.riskField[0]!.length; y++) {
            const risk = mapData.riskField[x]?.[y] ?? 0;
            if (risk > 0.1) {
              const worldX = (x / mapData.riskField.length) * WORLD_WIDTH;
              const worldY = (y / mapData.riskField[0]!.length) * WORLD_HEIGHT;
              const screenPos = worldToScreen({ x: worldX, y: worldY });
              const size = 4;
              sprite.field.drawRect(screenPos.x - size/2, screenPos.y - size/2, size, size);
            }
          }
        }
        sprite.field.endFill();
        break;

      case 'light':
        // Show beacon light influence
        if (gameState?.beacons) {
          sprite.field.lineStyle(1, colorScheme.light, 0.4);
          gameState.beacons.forEach(beacon => {
            const beaconType = BEACON_TYPES.find(type => type.id === beacon.type.id);
            if (beaconType?.id === 'light') {
              const screenPos = worldToScreen(beacon.position);
              const radiusInScreen = (beaconType.radius / WORLD_WIDTH) * CANVAS_WIDTH;
              sprite.field.drawCircle(screenPos.x, screenPos.y, radiusInScreen * beacon.strength);
            }
          });
        }
        break;
    }
  }, [mapData, gameState, worldToScreen, colorScheme]);

  // Render loop
  const render = useCallback(() => {
    if (!pixiAppRef.current || !gameState) return;

    const now = performance.now();
    const deltaTime = now - lastUpdateTimeRef.current;
    lastUpdateTimeRef.current = now;

    // Update agents
    const currentAgentIds = new Set(gameState.agents.map(agent => agent.id));
    
    // Remove old agent sprites
    agentSpritesRef.current.forEach((sprite, agentId) => {
      if (!currentAgentIds.has(agentId)) {
        pixiAppRef.current!.stage.removeChild(sprite);
        agentSpritesRef.current.delete(agentId);
      }
    });

    // Update existing and create new agent sprites
    gameState.agents.forEach(agent => {
      let sprite = agentSpritesRef.current.get(agent.id);
      if (!sprite) {
        sprite = createAgentSprite(agent);
        agentSpritesRef.current.set(agent.id, sprite);
        pixiAppRef.current!.stage.addChild(sprite);
      }
      updateAgentSprite(sprite, agent);
    });

    // Update beacons
    const currentBeaconIds = new Set(gameState.beacons.map(beacon => beacon.id));
    
    // Remove old beacon sprites
    beaconSpritesRef.current.forEach((sprite, beaconId) => {
      if (!currentBeaconIds.has(beaconId)) {
        pixiAppRef.current!.stage.removeChild(sprite);
        beaconSpritesRef.current.delete(beaconId);
      }
    });

    // Update existing and create new beacon sprites
    gameState.beacons.forEach(beacon => {
      let sprite = beaconSpritesRef.current.get(beacon.id);
      if (!sprite) {
        sprite = createBeaconSprite(beacon);
        beaconSpritesRef.current.set(beacon.id, sprite);
        pixiAppRef.current!.stage.addChild(sprite);
      }
      updateBeaconSprite(sprite, beacon);
    });

    // Update overlays
    settings.overlays.forEach(overlayType => {
      let sprite = overlaySpritesRef.current.get(overlayType);
      if (!sprite) {
        sprite = createOverlaySprite(overlayType);
        overlaySpritesRef.current.set(overlayType, sprite);
        pixiAppRef.current!.stage.addChildAt(sprite, 0); // Add behind other sprites
      }
      updateOverlaySprite(sprite, overlayType);
    });

    // Remove disabled overlays
    overlaySpritesRef.current.forEach((sprite, overlayType) => {
      if (!settings.overlays.includes(overlayType)) {
        pixiAppRef.current!.stage.removeChild(sprite);
        overlaySpritesRef.current.delete(overlayType);
      }
    });
  }, [
    gameState,
    settings.overlays,
    createAgentSprite,
    updateAgentSprite,
    createBeaconSprite,
    updateBeaconSprite,
    createOverlaySprite,
    updateOverlaySprite
  ]);

  // Initialize PixiJS
  useEffect(() => {
    initializePixi();

    return () => {
      if (pixiAppRef.current) {
        pixiAppRef.current.destroy();
        pixiAppRef.current = null;
      }
    };
  }, [initializePixi]);

  // Render on game state updates
  useEffect(() => {
    render();
  }, [render]);

  // Handle settings changes
  useEffect(() => {
    if (pixiAppRef.current) {
      pixiAppRef.current.renderer.background.color = colorScheme.background;
    }
  }, [colorScheme.background]);

  return (
    <canvas
      ref={canvasRef}
      className={`game-canvas ${className}`}
      style={{
        display: 'block',
        width: '100%',
        height: '100%',
        maxWidth: `${CANVAS_WIDTH}px`,
        maxHeight: `${CANVAS_HEIGHT}px`,
        cursor: 'crosshair'
      }}
      role="img"
      aria-label="Murmuration simulation visualization showing bird agents, beacons, and environmental overlays"
      tabIndex={0}
    />
  );
}