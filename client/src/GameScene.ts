import { Scene } from 'phaser';
import { audioManager } from './AudioManager';
import { LAYER_DEPTHS } from './config/gameConfig';
import { BirdAnimationSystem } from './BirdAnimationSystem';
import { WebSocketClient } from './WebSocketClient';

// Object Pool class for efficient memory management
class ObjectPool<T extends Phaser.GameObjects.GameObject & { setVisible(visible: boolean): T; setActive(active: boolean): T }> {
  private available: T[] = [];
  private inUse: Set<T> = new Set();

  // Get an object from the pool or create a new one
  acquire(factory: () => T): T {
    let obj = this.available.pop();
    if (!obj) {
      obj = factory();
    }
    this.inUse.add(obj);
    obj.setActive(true).setVisible(true);
    return obj;
  }

  // Return an object to the pool
  release(obj: T): void {
    if (this.inUse.has(obj)) {
      this.inUse.delete(obj);
      this.available.push(obj);
      obj.setActive(false).setVisible(false);
      
      // Reset common properties
      if ('x' in obj && 'y' in obj) {
        (obj as any).x = 0;
        (obj as any).y = 0;
      }
      if ('alpha' in obj) {
        (obj as any).alpha = 1;
      }
      if ('scaleX' in obj && 'scaleY' in obj) {
        (obj as any).scaleX = 1;
        (obj as any).scaleY = 1;
      }
      if ('rotation' in obj) {
        (obj as any).rotation = 0;
      }
      
      // Special handling for Containers - reset all child positions/properties
      if (obj instanceof Phaser.GameObjects.Container) {
        obj.list.forEach(child => {
          if ('x' in child && 'y' in child) {
            (child as any).x = 0;
            (child as any).y = 0;
          }
          if ('alpha' in child) {
            (child as any).alpha = 1;
          }
        });
      }
    }
  }

  // Release all objects back to the pool
  releaseAll(): void {
    for (const obj of this.inUse) {
      this.available.push(obj);
      obj.setActive(false).setVisible(false);
    }
    this.inUse.clear();
  }

  // Clean up the pool
  destroy(): void {
    for (const obj of [...this.available, ...this.inUse]) {
      obj.destroy();
    }
    this.available = [];
    this.inUse.clear();
  }

  // Get pool statistics
  getStats(): { available: number; inUse: number; total: number } {
    return {
      available: this.available.length,
      inUse: this.inUse.size,
      total: this.available.length + this.inUse.size
    };
  }
}

interface Agent {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  energy: number;
  stress: number;
  alive: boolean;
  // NEW: Enhanced genetic traits for visualization
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

// Beacon interface removed - using path-based system

interface Hazard {
  id?: string;
  type: string;
  position?: [number, number];
  x?: number;
  y?: number;
  radius?: number;
  strength?: number;
  active?: boolean;
  dangerZones?: Array<{
    radius: number;
    intensity: number;
  }>;
}

interface GameState {
  tick: number;
  level: string;
  agents: Agent[];
  population: number;
  arrivals: number;
  losses: number;
  cohesion: number;
  // beacons: Beacon[]; // Beacon system removed
  hazards: Hazard[];
  food_sites?: Array<{x: number, y: number, radius: number}>;
  destination: [number, number, number] | null; // [x, y, radius]
  game_over: boolean;
  victory: boolean;
  time_remaining: number;
  season: {
    day: number;
    hour: number;
  };
  // beacon_budget: number; // Removed with beacon system
  breed?: any;
  survival_rate: number;
  close_calls: number;
  panic_events: number;
  // Additional properties from server
  migration_id?: number;
  current_leg?: number;
  total_legs?: number;
  level_name?: string;
  males?: number;
  females?: number;
  migration_complete?: boolean;
  population_stats?: any;
  leadership_leaders?: any[];
  stats?: any;
}

export class GameScene extends Scene {
  private gameState: GameState | null = null;
  private agentSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  // Path drawing system - replaces beacon-based guidance
  private isPlanningPhase: boolean = false;
  private drawnPath: Phaser.Math.Vector2[] = [];
  private pathGraphics: Phaser.GameObjects.Graphics | null = null;
  private pathPreview: Phaser.GameObjects.Graphics | null = null;
  private isDrawing: boolean = false;

  private foodSiteSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private hazardSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private hazardParticles: Map<string, Phaser.GameObjects.Particles.ParticleEmitter> = new Map();
  private destinationSprite: Phaser.GameObjects.Graphics | null = null;
  private birdAnimationSystem!: BirdAnimationSystem;
  
  // UI elements
  // private infoText!: Phaser.GameObjects.Text; // DISABLED: Now handled by UIScene
  private connectionText!: Phaser.GameObjects.Text;
  private lastConnectionStatus: boolean = false;
  // Beacon system completely removed - path drawing replaces beacons
  
  // Enhanced HUD properties (DISABLED: Now handled by UIScene)
  // private hudContainer!: Phaser.GameObjects.Container;
  // private levelText!: Phaser.GameObjects.Text;
  // private missionText!: Phaser.GameObjects.Text;
  // private timeText!: Phaser.GameObjects.Text;
  // private flockStatusText!: Phaser.GameObjects.Text;
  // private populationText!: Phaser.GameObjects.Text;
  // private energyText!: Phaser.GameObjects.Text;
  // private telemetryFields!: {
  //   cohesion: Phaser.GameObjects.Text;
  //   separation: Phaser.GameObjects.Text;
  //   alignment: Phaser.GameObjects.Text;
  //   avgSpeed: Phaser.GameObjects.Text;
  //   stress: Phaser.GameObjects.Text;
  //   beaconCount: Phaser.GameObjects.Text;
  // };
  // private healthBarBg!: Phaser.GameObjects.Graphics;
  // private healthBarFill!: Phaser.GameObjects.Graphics;
  // private healthBarText!: Phaser.GameObjects.Text;
  // private telemetryToggle!: Phaser.GameObjects.Text;
  // private telemetryVisible: boolean = true;
  
  // Evolution/Breed panel (DISABLED: Now handled by UIScene)
  // private evolutionFields: {
  //   breedName?: Phaser.GameObjects.Text;
  //   generation?: Phaser.GameObjects.Text;
  //   survivalRate?: Phaser.GameObjects.Text;
  //   hazardAwareness?: Phaser.GameObjects.Text;
  //   energyEfficiency?: Phaser.GameObjects.Text;
  //   beaconSensitivity?: Phaser.GameObjects.Text;
  // } = {};
  // private evolutionToggle!: Phaser.GameObjects.Text;
  // private evolutionVisible: boolean = true;
  
  // Audio
  private soundtrack!: Phaser.Sound.BaseSound;
  private musicEnabled = true;
  
  // Object Pooling System
  private agentPool: ObjectPool<Phaser.GameObjects.Container> = new ObjectPool();
  
  // NEW: Bird inspection system
  private birdInspectionPanel?: Phaser.GameObjects.Container;
  private inspectedBirdId?: number;
  private particlePool: ObjectPool<Phaser.GameObjects.Particles.ParticleEmitter> = new ObjectPool();
  private graphicsPool: ObjectPool<Phaser.GameObjects.Graphics> = new ObjectPool();
  private textPool: ObjectPool<Phaser.GameObjects.Text> = new ObjectPool();
  
  // Camera controls
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private cameraSpeed = 300;
  private zoomSpeed = 0.1;
  
  // Enhanced camera system
  private cameraMode: 'manual' | 'flock_follow' | 'frame_all' = 'flock_follow';
  private cameraModeOptions: readonly ['manual', 'flock_follow', 'frame_all'] = ['manual', 'flock_follow', 'frame_all'];
  private flockCentroid = { x: 0, y: 0 };
  private flockVelocity = { x: 0, y: 0 };
  private cameraTargetPos = { x: 0, y: 0 };
  private cameraFollowSmoothness = 0.05;
  
  // World bounds (matching Python simulation)
  private worldWidth = 2000;
  private worldHeight = 1200;
  
  // In class properties
  private wsClient: WebSocketClient | null = null; // Will be set from main.ts
  // private pathLocked: boolean = false; // Removed - not used yet
  
  constructor() {
    super({ key: 'GameScene' });
  }
  
  preload() {
    console.log('Loading game assets...');
    
    // Load soundtrack with multiple formats for browser compatibility
    this.load.audio('soundtrack', [
      'murmuration.mp3'
    ]);
    
    // Load YOUR actual sprite assets from client/assets/sprites/
    try {
      // Bird sprites
      this.load.image('bird_female', 'assets/sprites/bird-female.png');
      this.load.image('bird_exhausted', 'assets/sprites/bird-exhausted.png');
      this.load.image('bird_leader_crown', 'assets/sprites/bird-leader-crown.png');
      
      // Hazard sprites  
      this.load.image('tornado_sprite', 'assets/sprites/tornado.png');
      this.load.image('predator_sprite', 'assets/sprites/predator.png');
      
      // Beacon sprites removed - using path-based system instead
      
      // Environment and UI sprites
      this.load.image('food_site', 'assets/sprites/food-site.png');
      this.load.image('checkpoint', 'assets/sprites/checkpoint.png');
      this.load.image('genetics_panel_bg', 'assets/sprites/genetics-panel-bg.png');
      this.load.image('trait_bar_bg', 'assets/sprites/trait-bar-bg.png');
      this.load.image('trait_bar_fill', 'assets/sprites/trait-bar-fill.png');
      
      // Status indicators
      this.load.image('stress_indicator', 'assets/sprites/stress-indicator.png');
      this.load.image('generation_icon', 'assets/sprites/generation-icon.png');
      this.load.image('breeding_heart', 'assets/sprites/breeding-heart.png');
      this.load.image('migration_path', 'assets/sprites/migration-path.png');
      
      console.log('🎨 Your custom sprites loaded successfully');
    } catch (error) {
      console.warn('Some sprites not loaded:', error);
    }
    
    // Create procedural particle textures
    this.createParticleTextures();
  }

  private createParticleTextures() {
    // Create debris particle texture (small brown squares for tornado debris)
    const debrisGraphics = this.add.graphics();
    debrisGraphics.fillStyle(0x996633, 1);
    debrisGraphics.fillRect(0, 0, 4, 4);
    debrisGraphics.generateTexture('debris', 4, 4);
    debrisGraphics.destroy();
    
    // Create shadow particle texture (soft dark circles for predator shadows)
    const shadowGraphics = this.add.graphics();
    shadowGraphics.fillStyle(0x000000, 0.6);
    shadowGraphics.fillCircle(4, 4, 3);
    shadowGraphics.generateTexture('shadow', 8, 8);
    shadowGraphics.destroy();
    
    // Create spark particle texture (bright small circles for warning effects)
    const sparkGraphics = this.add.graphics();
    sparkGraphics.fillStyle(0xffffff, 1);
    sparkGraphics.fillCircle(2, 2, 1.5);
    sparkGraphics.generateTexture('spark', 4, 4);
    sparkGraphics.destroy();
  }

  create() {
    console.log('GameScene created');
    
    // Set world bounds
    this.cameras.main.setBounds(0, 0, this.worldWidth, this.worldHeight);
    
    // Set initial zoom to show entire map
    const zoomX = this.scale.width / this.worldWidth;
    const zoomY = this.scale.height / this.worldHeight;
    const optimalZoom = Math.min(zoomX, zoomY) * 0.9; // 90% to add padding
    this.cameras.main.setZoom(optimalZoom);
    this.cameras.main.centerOn(this.worldWidth / 2, this.worldHeight / 2); // Center on middle of world
    
    // Create enhanced background with layers
    this.createBackground();
    
    // Initialize bird animation system
    this.birdAnimationSystem = new BirdAnimationSystem(this);
    
    // Debug bird removed - no longer needed
    
    // Create enhanced UI elements - DISABLED: Now handled by UIScene
    // this.createInfoPanel();
    
    // Connection text - DISABLED: Now handled by UIScene
    // this.connectionText = this.createCrispText(15, 55, 'Status: Disconnected', {
    //   fontSize: '14px',
    //   color: '#ff0000',
    //   backgroundColor: 'rgba(0,0,0,0.7)',
    //   padding: { x: 10, y: 5 },
    //   borderRadius: 5
    // }).setScrollFactor(0).setDepth(100);

    // Update connection status now that text element exists
    this.setConnectionStatus(this.lastConnectionStatus);
    
    // Create controls info - DISABLED: Now handled by UIScene
    // this.add.text(10, this.cameras.main.height - 120, 
    //   'Controls:\n' +
    //   'Arrow Keys: Move camera\n' +
    //   'Mouse Wheel: Zoom\n' +
    //   'Click: Place Food beacon\n' +
    //   'Right Click: Place Shelter beacon\n' +
    //   'Space: Pause/Resume',
    //   {
    //     fontSize: '12px',
    //     color: '#000000',
    //     backgroundColor: '#ffffff',
    //     padding: { x: 8, y: 8 }
    //   }
    // ).setScrollFactor(0).setDepth(100);
    
    // Initialize soundtrack
    this.initializeSoundtrack();
    
    // Create beacon selection panel - DISABLED: Now handled by UIScene
    // this.createBeaconPanel();
    
    // Create music toggle
    this.createMusicToggle();

    // Setup keyboard controls
    this.cursors = this.input.keyboard!.createCursorKeys();
    
    // Add WASD controls
    const wasd = this.input.keyboard!.addKeys('W,S,A,D,SPACE') as any;
    this.cursors = { ...this.cursors, ...wasd };
    
    // Mouse controls for camera
    this.input.on('wheel', (_pointer: any, _gameObjects: any, _deltaX: number, deltaY: number) => {
      const camera = this.cameras.main;
      if (deltaY > 0) {
        camera.setZoom(Math.max(0.1, camera.zoom - this.zoomSpeed));
      } else {
        camera.setZoom(Math.min(2.0, camera.zoom + this.zoomSpeed));
      }
    });
    
    // Path drawing and bird inspection
    this.input.on('pointerdown', (pointer: Phaser.Input.Pointer, gameObjects: any) => {
      // Check if click was on UI element first
      const clickedOnUI = gameObjects.some((obj: any) => obj.depth >= 100);
      if (clickedOnUI) {
        console.log('Clicked on UI, ignoring');
        return;
      }

      if (this.isPlanningPhase && pointer.leftButtonDown()) {
        // Path drawing mode
        this.startPathDrawing(pointer.worldX, pointer.worldY);
      } else if (pointer.leftButtonDown()) {
        // Normal gameplay - check for bird inspection
        this.checkBirdInspection(pointer.worldX, pointer.worldY);
        console.log('Checking for bird inspection at:', pointer.worldX, pointer.worldY);
      }
    });

    // Path drawing continuation
    this.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
      if (this.isPlanningPhase && this.isDrawing && pointer.leftButtonDown()) {
        this.continuePathDrawing(pointer.worldX, pointer.worldY);
      }
    });

    // Path drawing completion
    this.input.on('pointerup', () => {
      if (this.isPlanningPhase && this.isDrawing) {
        this.finishPathDrawing();
      }
    });

    // Right-click to clear path during planning
    this.input.on('pointerdown', (pointer: Phaser.Input.Pointer) => {
      if (this.isPlanningPhase && pointer.rightButtonDown()) {
        this.clearDrawnPath();
      }
    });
    
    // Space for pause/resume
    this.input.keyboard!.on('keydown-SPACE', () => {
      this.togglePause();
    });

    // Event listeners for planning phase coordination
    this.events.on('startPlanningPhase', this.startPlanningPhase, this);
    this.events.on('endPlanningPhase', this.endPlanningPhase, this);
  }

  override update() {
    // Enhanced camera system
    this.updateCameraSystem();
  }

  private updateCameraSystem() {
    // Calculate flock metrics if we have agents
    if (this.gameState?.agents && this.gameState.agents.length > 0) {
      this.calculateFlockMetrics();
    }
    
    // Handle camera modes
    switch (this.cameraMode) {
      case 'manual':
        this.handleManualCamera();
        break;
      case 'flock_follow':
        this.handleFlockFollowCamera();
        break;
      case 'frame_all':
        this.handleFrameAllCamera();
        break;
    }
  }

  private calculateFlockMetrics() {
    if (!this.gameState?.agents) return;
    
    const aliveAgents = this.gameState.agents.filter(a => a.alive);
    if (aliveAgents.length === 0) return;
    
    // Calculate centroid (center of mass)
    let totalX = 0, totalY = 0, totalVx = 0, totalVy = 0;
    
    for (const agent of aliveAgents) {
      totalX += agent.x;
      totalY += agent.y;
      totalVx += agent.vx || 0;
      totalVy += agent.vy || 0;
    }
    
    this.flockCentroid.x = totalX / aliveAgents.length;
    this.flockCentroid.y = totalY / aliveAgents.length;
    this.flockVelocity.x = totalVx / aliveAgents.length;
    this.flockVelocity.y = totalVy / aliveAgents.length;
  }

  private handleManualCamera() {
    // Traditional manual camera controls
    const camera = this.cameras.main;
    const speed = this.cameraSpeed * (1 / camera.zoom);
    
    if (this.cursors.left?.isDown) {
      camera.scrollX -= speed * 0.016;
    }
    if (this.cursors.right?.isDown) {
      camera.scrollX += speed * 0.016;
    }
    if (this.cursors.up?.isDown) {
      camera.scrollY -= speed * 0.016;
    }
    if (this.cursors.down?.isDown) {
      camera.scrollY += speed * 0.016;
    }
  }

  private handleFlockFollowCamera() {
    // Predictive smooth following of flock centroid
    const camera = this.cameras.main;
    
    // Predict where the flock will be (looking ahead based on velocity)
    const predictionTime = 2.0; // seconds
    this.cameraTargetPos.x = this.flockCentroid.x + (this.flockVelocity.x * predictionTime);
    this.cameraTargetPos.y = this.flockCentroid.y + (this.flockVelocity.y * predictionTime);
    
    // Smoothly interpolate camera position
    const targetScrollX = this.cameraTargetPos.x - camera.width / 2 / camera.zoom;
    const targetScrollY = this.cameraTargetPos.y - camera.height / 2 / camera.zoom;
    
    camera.scrollX += (targetScrollX - camera.scrollX) * this.cameraFollowSmoothness;
    camera.scrollY += (targetScrollY - camera.scrollY) * this.cameraFollowSmoothness;
    
    // Keep camera within world bounds
    camera.scrollX = Phaser.Math.Clamp(camera.scrollX, 0, this.worldWidth - camera.width / camera.zoom);
    camera.scrollY = Phaser.Math.Clamp(camera.scrollY, 0, this.worldHeight - camera.height / camera.zoom);
  }

  private handleFrameAllCamera() {
    // Automatically zoom and position to fit all alive birds
    if (!this.gameState?.agents) return;
    
    const camera = this.cameras.main;
    const aliveAgents = this.gameState.agents.filter(a => a.alive && typeof a.x === 'number' && typeof a.y === 'number');
    if (aliveAgents.length === 0) return;
    
    // Find bounding box of all alive agents
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    
    for (const agent of aliveAgents) {
      if (isFinite(agent.x) && isFinite(agent.y)) {
        minX = Math.min(minX, agent.x);
        maxX = Math.max(maxX, agent.x);
        minY = Math.min(minY, agent.y);
        maxY = Math.max(maxY, agent.y);
      }
    }
    
    // Validate bounding box
    if (!isFinite(minX) || !isFinite(maxX) || !isFinite(minY) || !isFinite(maxY)) {
      console.warn('Invalid bird positions for camera framing');
      return;
    }
    
    // Add padding around the flock
    const padding = 100;
    minX -= padding;
    maxX += padding;
    minY -= padding;
    maxY += padding;
    
    // Calculate required zoom and position
    const flockWidth = maxX - minX;
    const flockHeight = maxY - minY;
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    
    // Ensure minimum dimensions to avoid extreme zoom
    const minFlockWidth = 200;
    const minFlockHeight = 200;
    const effectiveWidth = Math.max(flockWidth, minFlockWidth);
    const effectiveHeight = Math.max(flockHeight, minFlockHeight);
    
    // Calculate zoom to fit all birds (with some margin)
    const zoomX = camera.width / effectiveWidth;
    const zoomY = camera.height / effectiveHeight;
    const targetZoom = Math.min(Math.max(zoomX, zoomY, 0.1), 2.0); // Cap min and max zoom
    
    // Smoothly adjust zoom and position
    camera.zoom += (targetZoom - camera.zoom) * 0.02;
    
    const targetScrollX = centerX - camera.width / 2 / camera.zoom;
    const targetScrollY = centerY - camera.height / 2 / camera.zoom;
    
    // Clamp to world bounds
    const maxScrollX = Math.max(0, this.worldWidth - camera.width / camera.zoom);
    const maxScrollY = Math.max(0, this.worldHeight - camera.height / camera.zoom);
    
    camera.scrollX += (Phaser.Math.Clamp(targetScrollX, 0, maxScrollX) - camera.scrollX) * 0.05;
    camera.scrollY += (Phaser.Math.Clamp(targetScrollY, 0, maxScrollY) - camera.scrollY) * 0.05;
  }

  public cycleCameraMode() {
    // Cycle through camera modes
    const currentIndex = this.cameraModeOptions.indexOf(this.cameraMode);
    if (currentIndex !== -1) {
      const nextIndex = (currentIndex + 1) % this.cameraModeOptions.length;
      this.cameraMode = this.cameraModeOptions[nextIndex] as 'manual' | 'flock_follow' | 'frame_all';
    } else {
      // Fallback to first mode if current mode not found
      this.cameraMode = this.cameraModeOptions[0];
    }
    
    // Show camera mode indicator
    const modeNames = {
      manual: 'Manual Camera',
      flock_follow: 'Follow Flock',
      frame_all: 'Frame All Birds'
    };
    
    // Create temporary indicator text
    if (this.connectionText) {
      const indicator = this.add.text(this.connectionText.x, this.connectionText.y + 25, 
        `Camera: ${modeNames[this.cameraMode]}`, {
        fontSize: '12px',
        color: '#00ff88',
        backgroundColor: 'rgba(0,0,0,0.7)',
        padding: { x: 8, y: 4 }
      }).setScrollFactor(0).setDepth(100);
      
      // Fade out after 2 seconds
      this.tweens.add({
        targets: indicator,
        alpha: 0,
        duration: 2000,
        onComplete: () => indicator.destroy()
      });
    }
    
    console.log(`🎮 Camera mode changed to: ${modeNames[this.cameraMode]}`);
  }

  public frameAllBirds() {
    // Temporarily switch to frame_all mode for one-time framing
    if (this.gameState?.agents && this.gameState.agents.length > 0) {
      this.handleFrameAllCamera();
      
      // Show frame indicator
      if (this.connectionText) {
        const indicator = this.add.text(this.connectionText.x, this.connectionText.y + 25, 
          'Framing All Birds', {
          fontSize: '12px',
          color: '#ffaa00',
          backgroundColor: 'rgba(0,0,0,0.7)',
          padding: { x: 8, y: 4 }
        }).setScrollFactor(0).setDepth(100);
        
        this.tweens.add({
          targets: indicator,
          alpha: 0,
          duration: 1500,
          onComplete: () => indicator.destroy()
        });
      }
    }
  }

  public updateGameState(newState: GameState) {
    console.log('🎮 GameScene received state update:', {
      agents: newState.agents?.length || 0,
      aliveAgents: newState.agents?.filter(a => a.alive).length || 0,
      firstAgent: newState.agents?.[0] ? {x: newState.agents[0].x, y: newState.agents[0].y} : null,
      hazards: newState.hazards?.length || 0,
      food_sites: newState.food_sites?.length || 0
    });
    this.gameState = newState;
    this.updateVisuals();
    this.updateUI();
    this.updatePoolStats();
  }

  private updatePoolStats(): void {
    // Disable expensive pool stats logging for performance
    // Only log occasionally for debugging
    if (this.game?.loop.frame % 300 === 0) { // Every 5 seconds at 60fps
      const agentStats = this.agentPool.getStats();
      console.log(`Pool Stats - Agents: ${agentStats.inUse}/${agentStats.total}`);
    }
  }

  public destroy(): void {
    // Clean up object pools before destroying scene
    this.agentPool.destroy();
    this.particlePool.destroy();
    this.graphicsPool.destroy();
    this.textPool.destroy();

    // Clean up food site sprites
    for (const container of this.foodSiteSprites.values()) {
      container.destroy();
    }
    this.foodSiteSprites.clear();

    // Scene cleanup is handled automatically by Phaser
  }

  // Helper function for crisp text rendering (DISABLED: Not currently used)
  // private createCrispText(x: number, y: number, text: string, style: Phaser.Types.GameObjects.Text.TextStyle): Phaser.GameObjects.Text {
  //   const resolution = window.devicePixelRatio || 1;
  //   const crispStyle = {
  //     ...style,
  //     resolution: resolution,
  //     padding: { x: 2, y: 2 } // Add padding to prevent clipping
  //   };
  //   return this.add.text(x, y, text, crispStyle);
  // }

  public setConnectionStatus(connected: boolean) {
    console.log(`🎮 GameScene.setConnectionStatus called with: ${connected}`);
    this.lastConnectionStatus = connected;
    
    if (this.connectionText) {
      this.connectionText.setText(`Status: ${connected ? 'Connected' : 'Disconnected'}`);
      this.connectionText.setColor(connected ? '#00ff00' : '#ff0000');
      console.log(`🎮 Updated connection text to: ${connected ? 'Connected' : 'Disconnected'}`);
    } else {
      console.log('⚠️ connectionText is null/undefined, storing status for later update');
    }
  }

  private updateVisuals() {
    if (!this.gameState) return;

    this.updateAgents();
    // Beacons removed - using path-based system
    this.updateFoodSites();
    this.updateHazards();
    this.updateDestination();
    // NEW: Update bird inspection panel if active
    this.updateBirdInspection();
  }

  private updateAgents() {
    if (!this.gameState?.agents) return;
    
    // Safety check - ensure animation system is initialized
    if (!this.birdAnimationSystem) return;
    
    // Remove birds that no longer exist
    const currentAgentIds = new Set(this.gameState.agents.map(a => a.id.toString()));
    for (const agentId of this.agentSprites.keys()) {
      if (!currentAgentIds.has(agentId)) {
        this.birdAnimationSystem.removeBird(agentId);
        this.agentSprites.delete(agentId);
      }
    }
    
    // Update birds using the animation system
    for (const agent of this.gameState.agents) {
      const agentId = agent.id.toString();
      
      // Update bird with animation system
      this.birdAnimationSystem.updateBird({
        id: agentId,
        x: agent.x,
        y: agent.y,
        vx: agent.vx,
        vy: agent.vy,
        energy: agent.energy,
        stress: agent.stress,
        alive: agent.alive,
        gender: agent.gender
      });
      
      // Mark as tracked - just use a flag since BirdAnimationSystem manages the actual sprites
      this.agentSprites.set(agentId, true as any);
    }
    
    // Update cohesion effects
    if (this.gameState.cohesion !== undefined) {
      this.birdAnimationSystem.updateCohesionEffects(this.gameState.cohesion);
    }
    
    // Interpolate positions for smooth movement
    this.birdAnimationSystem.interpolatePositions(this.game.loop.delta);
  }

  // Beacon system completely removed - replaced with path-based guidance

  private updateFoodSites() {
    if (!this.gameState?.food_sites) return;

    // Remove food site sprites that no longer exist
    const currentFoodSiteIds = new Set(
      this.gameState.food_sites.map((_site, index) => `food_site_${index}`)
    );
    for (const [siteId, container] of this.foodSiteSprites.entries()) {
      if (!currentFoodSiteIds.has(siteId)) {
        container.destroy();
        this.foodSiteSprites.delete(siteId);
      }
    }

    // Update or create food site sprites
    for (let i = 0; i < this.gameState.food_sites.length; i++) {
      const foodSite = this.gameState.food_sites[i];
      const siteId = `food_site_${i}`;
      let container = this.foodSiteSprites.get(siteId);

      if (!container) {
        // Create new food site visual
        const siteX = foodSite && typeof foodSite.x === 'number' ? foodSite.x : 0;
        const siteY = foodSite && typeof foodSite.y === 'number' ? foodSite.y : 0;
        container = this.createFoodSiteVisual(foodSite, siteX, siteY);
        this.foodSiteSprites.set(siteId, container);
        console.log(`🟢 Created food site visual at (${siteX}, ${siteY})`);
      } else {
        // Update existing food site position (in case it moves)
        const siteX = foodSite && typeof foodSite.x === 'number' ? foodSite.x : 0;
        const siteY = foodSite && typeof foodSite.y === 'number' ? foodSite.y : 0;
        container.setPosition(siteX, siteY);
      }
    }
  }

  private createFoodSiteVisual(foodSite: any, x: number, y: number): Phaser.GameObjects.Container {
    const container = this.add.container(x, y);
    container.setDepth(LAYER_DEPTHS.BEACONS); // Same depth as beacons for visibility

    // Create the main food site circle (bright green to stand out)
    const mainCircle = this.add.circle(0, 0, 12, 0x00ff00, 0.8);
    container.add(mainCircle);

    // Create inner food icon (darker green circle with white cross)
    const innerCircle = this.add.circle(0, 0, 8, 0x006600, 1.0);
    container.add(innerCircle);

    // Add food cross symbol
    const crossGraphics = this.add.graphics();
    crossGraphics.lineStyle(2, 0xffffff, 1.0);
    crossGraphics.lineBetween(-4, 0, 4, 0); // horizontal line
    crossGraphics.lineBetween(0, -4, 0, 4); // vertical line
    container.add(crossGraphics);

    // Create influence radius ring to show feeding area
    const radius = foodSite.radius || 80;
    const radiusRing = this.add.circle(0, 0, radius, 0x00ff00, 0.06);
    radiusRing.setStrokeStyle(2, 0x00ff00, 0.3);
    container.add(radiusRing);

    // Add gentle pulsing animation to make it obvious
    this.tweens.add({
      targets: mainCircle,
      scaleX: 1.2,
      scaleY: 1.2,
      alpha: 0.9,
      duration: 2000,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut'
    });

    // Add subtle pulsing to the radius ring
    this.tweens.add({
      targets: radiusRing,
      alpha: 0.12,
      scaleX: 1.05,
      scaleY: 1.05,
      duration: 3000,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut'
    });

    return container;
  }



  private updateHazards() {
    if (!this.gameState?.hazards) return;
    
    // Remove hazards that no longer exist
    for (const [hazardId, container] of this.hazardSprites.entries()) {
      if (!this.gameState.hazards.find(h => h.id === hazardId)) {
        // Clean up particle emitter
        const particles = this.hazardParticles.get(hazardId);
        if (particles) {
          particles.destroy();
          this.hazardParticles.delete(hazardId);
        }
        container.destroy();
        this.hazardSprites.delete(hazardId);
      }
    }
    
    // Update or create hazard sprites with particle effects
    for (const hazard of this.gameState.hazards) {
      const hazardId = `${hazard.type}_${hazard.x || hazard.position?.[0] || 0}_${hazard.y || hazard.position?.[1] || 0}`;
      let container = this.hazardSprites.get(hazardId);
      
      // Get position from either x,y or position array
      const x = hazard.x ?? hazard.position?.[0] ?? 0;
      const y = hazard.y ?? hazard.position?.[1] ?? 0;
      const radius = hazard.radius ?? 50;
      
      if (!container) {
        // Create new hazard with particle effects
        container = this.createHazardWithParticles(hazard.type, x, y, radius);
        this.hazardSprites.set(hazardId, container);
      } else {
        // Update existing hazard position
        container.setPosition(x, y);
        
        // Update particle emitter position
        const particles = this.hazardParticles.get(hazardId);
        if (particles) {
          particles.setPosition(x, y);
        }
      }
    }
  }

  private updateDestination() {
    if (!this.gameState?.destination) {
      if (this.destinationSprite) {
        this.destinationSprite.destroy();
        this.destinationSprite = null;
      }
      return;
    }

    if (!this.destinationSprite) {
      this.destinationSprite = this.add.graphics();
    }

    const [x, y] = this.gameState.destination;
    const radius = 50; // Default radius since destination tuple might not have radius

    this.destinationSprite.clear();

    // Green destination circle with pulsing effect
    this.destinationSprite.lineStyle(4, 0x00ff00, 0.8);
    this.destinationSprite.strokeCircle(x, y, radius);
    this.destinationSprite.lineStyle(2, 0x44ff44, 0.4);
    this.destinationSprite.strokeCircle(x, y, radius + 20);
    
    // Add goal text
    this.destinationSprite.fillStyle(0x00ff00);
    // Note: Graphics doesn't support text, we'd need a separate text object for this
  }

  private updateUI() {
    // UI updates are now handled by UIScene
    // This method is kept for potential future use but currently disabled
    if (!this.gameState) return;

    const agents = this.gameState.agents || [];
    const aliveAgents = agents.filter(a => a.alive);
    const aliveCount = aliveAgents.length;

    // Update telemetry less frequently for performance (every 10 frames)
    if ((this.game?.loop.frame || 0) % 10 === 0) {
      this.updateTelemetryData(aliveAgents);
    }

    // Update health bar less frequently (every 5 frames)
    if ((this.game?.loop.frame || 0) % 5 === 0) {
      this.updateHealthBar(aliveAgents);
      this.updateStatusColors(aliveCount, this.gameState.population || 1);
    }
  }
  

  
  private updateTelemetryData(aliveAgents: any[]) {
    // Telemetry updates disabled - now handled by UIScene
    if (aliveAgents.length === 0) {
      return;
    }

    // Calculate flock metrics for potential future use
    const avgSpeed = aliveAgents.reduce((sum, a) => sum + Math.sqrt(a.vx * a.vx + a.vy * a.vy), 0) / aliveAgents.length;
    const avgStress = aliveAgents.reduce((sum, a) => sum + (a.stress || 0), 0) / aliveAgents.length;

    // Calculate cohesion (inverse of average distance to centroid)
    const centroidX = aliveAgents.reduce((sum, a) => sum + a.x, 0) / aliveAgents.length;
    const centroidY = aliveAgents.reduce((sum, a) => sum + a.y, 0) / aliveAgents.length;
    const avgDistanceToCenter = aliveAgents.reduce((sum, a) => {
      return sum + Math.sqrt((a.x - centroidX) ** 2 + (a.y - centroidY) ** 2);
    }, 0) / aliveAgents.length;
    const cohesion = Math.max(0, 100 - avgDistanceToCenter / 2); // Normalize to 0-100

    // Telemetry fields are now handled by UIScene
    console.log(`Flock metrics - Cohesion: ${cohesion.toFixed(1)}%, Avg Speed: ${avgSpeed.toFixed(1)}, Stress: ${avgStress.toFixed(1)}`);
  }
  
  private updateHealthBar(aliveAgents: any[]) {
    // Health bar updates disabled - now handled by UIScene
    if (!this.gameState) return;

    const totalPopulation = this.gameState.population || 1;
    const aliveCount = aliveAgents.length;
    const healthPercentage = aliveCount / totalPopulation;

    // Health bar visuals are now handled by UIScene
    console.log(`Flock health: ${(healthPercentage * 100).toFixed(0)}% (${aliveCount}/${totalPopulation})`);
  }
  

  
  private updateStatusColors(aliveCount: number, totalPopulation: number) {
    // Status color updates disabled - now handled by UIScene
    const healthPercentage = aliveCount / totalPopulation;
    const status = healthPercentage > 0.7 ? 'Good' : healthPercentage > 0.4 ? 'Fair' : 'Critical';
    console.log(`Flock status: ${status} (${aliveCount}/${totalPopulation})`);
  }

  // Path drawing system implementation

  private togglePause() {
    this.events.emit('togglePause');
  }

  // Path Drawing Methods
  private startPathDrawing(worldX: number, worldY: number) {
    console.log('🎯 Starting path drawing at:', worldX, worldY);

    // Clear any existing path
    this.clearDrawnPath();

    // Initialize path drawing
    this.isDrawing = true;
    this.drawnPath = [new Phaser.Math.Vector2(worldX, worldY)];
    
    // Hide planning panel when drawing starts
    const uiScene = this.scene.get('UIScene') as any;
    if (uiScene && uiScene.hidePlanningPanel) {
      uiScene.hidePlanningPanel();
    }

    // Create path graphics if not exists
    if (!this.pathGraphics) {
      this.pathGraphics = this.add.graphics();
      this.pathGraphics.setDepth(LAYER_DEPTHS.UI);
    }
    if (!this.pathPreview) {
      this.pathPreview = this.add.graphics();
      this.pathPreview.setDepth(LAYER_DEPTHS.UI + 1);
    }

    // Draw initial point
    this.updatePathVisualization();
  }

  private continuePathDrawing(worldX: number, worldY: number) {
    if (!this.isDrawing || this.drawnPath.length === 0) return;

    const newPoint = new Phaser.Math.Vector2(worldX, worldY);
    const lastPoint = this.drawnPath[this.drawnPath.length - 1];

    // Only add point if it's far enough from the last point (prevents too many points)
    if (lastPoint && lastPoint.distance(newPoint) > 10) {
      this.drawnPath.push(newPoint);
      this.updatePathVisualization();
    }

    // Update preview line to destination
    this.updatePathPreview(worldX, worldY);
  }

  private finishPathDrawing() {
    console.log('✅ Finished path drawing, points:', this.drawnPath.length);
    this.isDrawing = false;

    // Clear preview
    if (this.pathPreview) {
      this.pathPreview.clear();
    }

    // Validate and finalize path
    if (this.drawnPath.length >= 2) {
      this.validatePath();
    }
  }

  private clearDrawnPath() {
    console.log('🗑️ Clearing drawn path');
    this.drawnPath = [];
    this.isDrawing = false;

    if (this.pathGraphics) {
      this.pathGraphics.clear();
    }
    if (this.pathPreview) {
      this.pathPreview.clear();
    }
  }

  private updatePathVisualization() {
    if (!this.pathGraphics || this.drawnPath.length < 2) return;

    this.pathGraphics.clear();

    // Draw the path as a series of connected lines
    this.pathGraphics.lineStyle(3, 0x00ff00, 0.8); // Green path
    this.pathGraphics.beginPath();

    for (let i = 0; i < this.drawnPath.length; i++) {
      const point = this.drawnPath[i];
      if (point) {
        if (i === 0) {
          this.pathGraphics.moveTo(point.x, point.y);
        } else {
          this.pathGraphics.lineTo(point.x, point.y);
        }
      }
    }

    this.pathGraphics.strokePath();

    // Draw waypoints as small circles
    this.pathGraphics.fillStyle(0x00ff00, 1.0);
    for (const point of this.drawnPath) {
      if (point) {
        this.pathGraphics.fillCircle(point.x, point.y, 4);
      }
    }
  }

  private updatePathPreview(worldX: number, worldY: number) {
    if (!this.pathPreview || this.drawnPath.length === 0) return;

    const lastPoint = this.drawnPath[this.drawnPath.length - 1];
    if (!lastPoint) return;

    this.pathPreview.clear();

    // Draw preview line from last path point to current mouse position
    this.pathPreview.lineStyle(2, 0x00ff00, 0.4); // Semi-transparent preview
    this.pathPreview.beginPath();
    this.pathPreview.moveTo(lastPoint.x, lastPoint.y);
    this.pathPreview.lineTo(worldX, worldY);
    this.pathPreview.strokePath();
  }

  private validatePath() {
    if (!this.gameState?.agents || !this.gameState?.destination || this.drawnPath.length < 2) return false;

    const startPos = this.getFlockCenter();
    const destination = this.gameState.destination;

    const pathStart = this.drawnPath[0];
    const pathEnd = this.drawnPath[this.drawnPath.length - 1];

    if (!pathStart || !pathEnd) return false;

    // Check if path starts near flock
    const startDistance = Phaser.Math.Distance.Between(
      startPos.x, startPos.y, pathStart.x, pathStart.y
    );

    // Check if path ends near destination
    const endDistance = Phaser.Math.Distance.Between(
      destination[0], destination[1], pathEnd.x, pathEnd.y
    );

    const startValid = startDistance < 100; // Within 100 units of flock
    const endValid = endDistance < 50; // Within 50 units of destination

    if (!startValid || !endValid) {
      console.log('❌ Path validation failed:', { startValid, endValid, startDistance, endDistance });
      // Show validation feedback (could add UI notification here)
      return false;
    }

    console.log('✅ Path validation passed');
    return true;
  }

  private getFlockCenter(): Phaser.Math.Vector2 {
    if (!this.gameState?.agents) {
      return new Phaser.Math.Vector2(0, 0);
    }

    let totalX = 0;
    let totalY = 0;
    let count = 0;

    for (const agent of this.gameState.agents) {
      totalX += agent.x;
      totalY += agent.y;
      count++;
    }

    return new Phaser.Math.Vector2(totalX / count, totalY / count);
  }

  // Public methods for path drawing phase management
  public startPlanningPhase() {
    console.log('📝 Starting path planning phase');
    this.isPlanningPhase = true;
    this.clearDrawnPath();

    // Pause the game during planning
    this.events.emit('togglePause');

    // Update cursor for drawing
    this.input.setDefaultCursor('crosshair');

    // Notify UIScene to show planning panel
    this.scene.get('UIScene')?.events.emit('showPlanningPhase');

    // In startPlanningPhase
    this.wsClient?.pauseGame();
  }

  public endPlanningPhase() {
    console.log('🚀 Ending planning phase, starting migration');
    this.isPlanningPhase = false;

    // Resume the game
    this.events.emit('togglePause');

    // Reset cursor
    this.input.setDefaultCursor('default');

    // Send the path to the server
    if (this.drawnPath.length > 0) {
      this.sendPathToServer();
    }

    // Notify UIScene to hide planning panel
    this.scene.get('UIScene')?.events.emit('hidePlanningPhase');

    // In endPlanningPhase
    this.wsClient?.resumeGame();
    // this.pathLocked = true; // Will be used when we implement path locking
  }

  private sendPathToServer() {
    const pathData = this.drawnPath.map(point => ({ x: point.x, y: point.y }));
    console.log('📤 Sending path to server:', pathData);

    // Emit event for the server to receive the path
    this.events.emit('pathSubmitted', { path: pathData });
  }

  public getDrawnPath(): Phaser.Math.Vector2[] {
    return [...this.drawnPath];
  }

  public loadLevel(levelIndex: number) {
    this.events.emit('loadLevel', levelIndex);
  }
  
  // DISABLED: Beacon panel now handled by UIScene
  // private createBeaconPanel(): void {
  //   // Position beacon panel in bottom-left area for better visibility
  //   const cameraHeight = this.cameras.main.height;
  //   this.beaconPanel = this.add.container(10, cameraHeight - 140);
  //   this.beaconPanel.setScrollFactor(0).setDepth(LAYER_DEPTHS.UI + 10); // Above HUD
  //
  //   // Much smaller, simpler panel background
  //   const panelBg = this.add.rectangle(0, 0, 90, 90, 0x000000, 0.8);
  //   panelBg.setStrokeStyle(1, 0x4CAF50);
  //   this.beaconPanel.add(panelBg);
  //
  //   // Smaller panel title
  //   const title = this.add.text(-35, -35, 'Beacons', {
  //     fontSize: '10px',
  //     color: '#4CAF50',
  //     fontStyle: 'bold'
  //   });
  //   this.beaconPanel.add(title);
  //
  //   // Beacon types with working texture support - FOOD REMOVED: Food is now environmental
  //   const beaconTypes = [
  //     { type: 'shelter', name: 'Shelter', color: 0x0000ff, texture: 'icon_shelter' },
  //     { type: 'thermal', name: 'Thermal', color: 0xff0000, texture: 'icon_thermal' }
  //   ];
  //
  //   beaconTypes.forEach((beacon, index) => {
  //     const y = -15 + (index * 18); // Much smaller spacing
  //     const button = this.createBeaconButton(beacon.type, beacon.name, beacon.color, beacon.texture, 0, y);
  //     this.beaconPanel.add(button);
  //     this.beaconButtons.set(beacon.type, button);
  //   });
  //
  //   // Clear selection button
  //   const clearButton = this.createClearButton(0, 30); // Much closer position
  //   this.beaconPanel.add(clearButton);
  // }
  
  // DISABLED: Beacon UI now handled by UIScene
  // private createBeaconButton(type: string, name: string, color: number, _textureKey: string, x: number, y: number): Phaser.GameObjects.Container {
  //   const button = this.add.container(x, y);
  //
  //   // Much smaller button background
  //   const bg = this.add.rectangle(0, 0, 70, 15, color, 0.3);
  //   bg.setStrokeStyle(1, color, 0.8);
  //   button.add(bg);
  //
  //   // Smaller text
  //   const nameText = this.add.text(0, 0, name, {
  //     fontSize: '8px',
  //     color: '#ffffff',
  //     fontStyle: 'bold'
  //   }).setOrigin(0.5);
  //   button.add(nameText);
  //
  //   // Make interactive with simple color changes
  //   bg.setInteractive({ useHandCursor: true });
  //   bg.on('pointerover', () => {
  //     bg.setFillStyle(color, 0.5);
  //   });
  //   bg.on('pointerout', () => {
  //     if (this.selectedBeaconType !== type) {
  //       bg.setFillStyle(color, 0.3);
  //     }
  //   });
  //   bg.on('pointerdown', () => {
  //     audioManager.playButtonClick();
  //     this.selectBeaconType(type);
  //   });
  //
  //   return button;
  // }
  //
  // private createClearButton(x: number, y: number): Phaser.GameObjects.Container {
  //   const button = this.add.container(x, y);
  //
  //   const bg = this.add.rectangle(0, 0, 60, 12, 0x666666, 0.8);
  //   bg.setStrokeStyle(1, 0xcccccc);
  //   const text = this.add.text(0, 0, 'Clear', { fontSize: '7px', color: '#ffffff' }).setOrigin(0.5);
  //
  //   button.add([bg, text]);
  //
  //   bg.setInteractive({ useHandCursor: true });
  //   bg.on('pointerover', () => bg.setFillStyle(0x888888, 0.9));
  //   bg.on('pointerout', () => bg.setFillStyle(0x666666, 0.8));
  //   bg.on('pointerdown', () => this.clearBeaconSelection());
  //
  //   return button;
  // }
  
  // Beacon selection system completely removed - replaced with path drawing
  
  private createBackground() {
    // Create day-night gradient overlay
    const dayNightOverlay = this.add.graphics();
    dayNightOverlay.fillStyle(0x000033, 0);
    dayNightOverlay.fillRect(0, 0, this.worldWidth, this.worldHeight);
    dayNightOverlay.setDepth(-11);
    
    // Draw visible start zone (middle-left)
    const startZoneGraphics = this.add.graphics();
    startZoneGraphics.lineStyle(3, 0x00ff00, 0.8);
    startZoneGraphics.fillStyle(0x00ff00, 0.1);
    startZoneGraphics.fillCircle(150, 600, 80); // Match server coordinates
    startZoneGraphics.strokeCircle(150, 600, 80);
    startZoneGraphics.setDepth(-5);
    
    // Add "START" label
    this.add.text(150, 600, 'START', {
      fontSize: '16px',
      color: '#00ff00',
      fontStyle: 'bold'
    }).setOrigin(0.5).setDepth(-5);
    
    // Draw destination zone (middle-right)
    const destZoneGraphics = this.add.graphics();
    destZoneGraphics.lineStyle(3, 0xff0000, 0.8);
    destZoneGraphics.fillStyle(0xff0000, 0.1);
    destZoneGraphics.fillCircle(1850, 600, 100); // Match server coordinates
    destZoneGraphics.strokeCircle(1850, 600, 100);
    destZoneGraphics.setDepth(-5);
    
    // Add "DESTINATION" label
    this.add.text(1850, 600, 'DEST', {
      fontSize: '16px',
      color: '#ff0000',
      fontStyle: 'bold'
    }).setOrigin(0.5).setDepth(-5);
    
    // Animate day-night cycle
    this.tweens.add({
      targets: dayNightOverlay,
      alpha: { from: 0, to: 0.3 },
      duration: 120000, // 2 minutes for full cycle
      yoyo: true,
      repeat: -1,
      onUpdate: (tween) => {
        const progress = tween.progress;
        // Shift color from day (blue) to dusk (orange) to night (dark blue)
        if (progress < 0.5) {
          dayNightOverlay.clear();
          dayNightOverlay.fillStyle(0xff6600, progress * 0.2); // Sunset orange
        } else {
          dayNightOverlay.clear();
          dayNightOverlay.fillStyle(0x000033, (progress - 0.5) * 0.6); // Night blue
        }
        dayNightOverlay.fillRect(0, 0, this.worldWidth, this.worldHeight);
      }
    });
    
    // Sky gradient background
    if (this.textures.exists('sky_bg')) {
      const sky = this.add.image(this.worldWidth / 2, this.worldHeight / 2, 'sky_bg');
      sky.setDisplaySize(this.worldWidth, this.worldHeight);
      sky.setDepth(-10);
    } else {
      // Procedural sky with gradient
      const skyGradient = this.add.graphics();
      skyGradient.fillStyle(0x87CEEB); // Sky blue
      skyGradient.fillRect(0, 0, this.worldWidth, this.worldHeight);
      skyGradient.setDepth(-10);
    }
    
    // Animated clouds with parallax
    for (let layer = 0; layer < 3; layer++) {
      for (let i = 0; i < 5; i++) {
        const cloudGraphics = this.add.graphics();
        const cloudX = Math.random() * this.worldWidth;
        const cloudY = 100 + Math.random() * 300;
        const cloudScale = 0.5 + layer * 0.3;
        
        // Draw procedural cloud
        cloudGraphics.fillStyle(0xffffff, 0.3 + layer * 0.1);
        for (let j = 0; j < 5; j++) {
          const cx = cloudX + (Math.random() - 0.5) * 100;
          const cy = cloudY + (Math.random() - 0.5) * 30;
          const radius = 20 + Math.random() * 30;
          cloudGraphics.fillCircle(cx, cy, radius * cloudScale);
        }
        
        cloudGraphics.setDepth(-8 + layer);
        
        // Animate with different speeds for parallax
        this.tweens.add({
          targets: cloudGraphics,
          x: this.worldWidth + 200,
          duration: (60000 + Math.random() * 30000) / (layer + 1),
          repeat: -1,
          onRepeat: () => {
            cloudGraphics.x = -200;
          }
        });
      }
    }
    
    // Add animated grass/vegetation
    const grassContainer = this.add.container(0, 0);
    grassContainer.setDepth(-3);
    
    for (let i = 0; i < 50; i++) {
      const grassX = Math.random() * this.worldWidth;
      const grassY = this.worldHeight - 50 - Math.random() * 150;
      
      const grass = this.add.graphics();
      grass.lineStyle(2, 0x228B22, 0.6);
      
      // Draw grass blades
      for (let j = 0; j < 5; j++) {
        const bladeX = grassX + (Math.random() - 0.5) * 20;
        grass.moveTo(bladeX, grassY);
        grass.lineTo(bladeX + Math.random() * 5 - 2.5, grassY - 10 - Math.random() * 20);
      }
      grass.strokePath();
      
      // Animate swaying
      this.tweens.add({
        targets: grass,
        x: { from: -3, to: 3 },
        duration: 2000 + Math.random() * 1000,
        yoyo: true,
        repeat: -1,
        ease: 'Sine.easeInOut',
        delay: Math.random() * 2000
      });
      
      grassContainer.add(grass);
    }
    
    // Add animated river/water
    const riverGraphics = this.add.graphics();
    riverGraphics.setDepth(-4);
    
    // Draw river path
    const riverPath = new Phaser.Curves.Path(100, 800);
    // Create a simpler curved path using multiple line segments
    riverPath.lineTo(400, 850);
    riverPath.lineTo(800, 750);
    riverPath.lineTo(1200, 900);
    riverPath.lineTo(1600, 850);
    riverPath.lineTo(1900, 950);
    
    // Animated water shader effect
    let waveOffset = 0;
    this.time.addEvent({
      delay: 50,
      callback: () => {
        waveOffset += 0.1;
        riverGraphics.clear();
        
        // Draw river with animated waves
        riverGraphics.lineStyle(30, 0x4682B4, 0.6);
        const points = riverPath.getPoints(100);
        
        for (let i = 0; i < points.length - 1; i++) {
          const currentPoint = points[i];
          const nextPoint = points[i + 1];
          if (currentPoint && nextPoint) {
            const wave = Math.sin(waveOffset + i * 0.1) * 5;
            riverGraphics.beginPath();
            riverGraphics.moveTo(currentPoint.x, currentPoint.y + wave);
            riverGraphics.lineTo(nextPoint.x, nextPoint.y + wave);
            riverGraphics.strokePath();
          }
        }
        
        // Add sparkles on water
        riverGraphics.fillStyle(0xffffff, 0.8);
        for (let i = 0; i < 10; i++) {
          const sparkleIndex = Math.floor(Math.random() * points.length);
          const sparkle = points[sparkleIndex];
          if (sparkle) {
            const sparkleSize = Math.sin(waveOffset * 2 + i) * 2 + 2;
            if (sparkleSize > 2) {
              riverGraphics.fillCircle(
                sparkle.x + Math.random() * 20 - 10,
                sparkle.y + Math.random() * 10 - 5,
                sparkleSize
              );
            }
          }
        }
      },
      loop: true
    });
  }
  

  

  

  

  

  

  
  private initializeSoundtrack() {
    try {
      // Check if audio system is available
      if (!this.sound) {
        console.warn('Audio system not available');
        return;
      }
      
      if (this.cache.audio.exists('soundtrack')) {
        this.soundtrack = this.sound.add('soundtrack', {
          volume: 0.2, // Lower volume
          loop: true
        });
        
        // Add error handler
        this.soundtrack.on('error', (error: any) => {
          console.warn('Soundtrack playback error:', error);
        });
        
        // Start playing after a short delay
        this.time.delayedCall(2000, () => {
          if (this.musicEnabled && this.soundtrack) {
            // Phaser audio doesn't return promises
            try {
              this.soundtrack.play();
              console.log('Soundtrack started');
            } catch (error) {
              console.warn('Could not start soundtrack:', error);
            }
          }
        });
      } else {
        console.warn('Soundtrack asset not loaded');
      }
    } catch (error) {
      console.warn('Failed to initialize soundtrack:', error);
    }
  }
  
  private createMusicToggle() {
    const musicButton = this.add.text(this.cameras.main.width - 80, 10, '🎵 ON', {
      fontSize: '12px',
      color: '#ffffff',
      backgroundColor: 'rgba(0,0,0,0.7)',
      padding: { x: 8, y: 4 }
    }).setScrollFactor(0).setDepth(100);
    
    musicButton.setInteractive({ useHandCursor: true });
    musicButton.on('pointerdown', () => {
      this.toggleMusic();
    });
  }
  
  private toggleMusic() {
    this.musicEnabled = !this.musicEnabled;
    
    if (this.soundtrack) {
      if (this.musicEnabled) {
        // Try to start or resume music
        try {
          if (!this.soundtrack.isPlaying) {
            this.soundtrack.play();
          } else {
            this.soundtrack.resume();
          }
        } catch (error) {
          console.warn('Could not start music:', error);
        }
        audioManager.playButtonClick();
      } else {
        this.soundtrack.pause();
        audioManager.playButtonClick();
      }
    } else {
      // Try to initialize if not already done
      this.initializeSoundtrack();
      audioManager.playButtonClick();
    }
  }



  private createHazardWithParticles(type: string, x: number, y: number, radius: number): Phaser.GameObjects.Container {
    const container = this.add.container(x, y);
    
    // Create base graphics for hazard
    const graphics = this.add.graphics();
    
    if (type.toLowerCase().includes('tornado')) {
      // Use storm sprite if available
      if (this.textures.exists('tornado_sprite')) {
        // Use actual storm sprite - sized EXACTLY to match the hazard circle
        const stormSprite = this.add.image(0, 0, 'tornado_sprite');
        
        // Get the actual sprite dimensions
        const spriteWidth = stormSprite.width;
        const spriteHeight = stormSprite.height;
        const spriteDiameter = Math.max(spriteWidth, spriteHeight);
        
        // Scale sprite so its visual diameter exactly matches the hazard radius circle
        const targetDiameter = radius * 2; // Convert radius to diameter
        const scale = targetDiameter / spriteDiameter;
        
        stormSprite.setScale(scale);
        stormSprite.setAlpha(0.7);
        stormSprite.setBlendMode(Phaser.BlendModes.MULTIPLY);
        
        // Add animated rotation for storm effect
        this.tweens.add({
          targets: stormSprite,
          rotation: Math.PI * 2,
          duration: 4000,
          repeat: -1,
          ease: 'Linear'
        });
        
        container.add([stormSprite]);
      } else {
        // Fallback: Enhanced tornado graphics with spiraling lines
        graphics.lineStyle(4, 0xff0000, 0.9);
        graphics.strokeCircle(0, 0, radius);
        graphics.lineStyle(3, 0xffaa00, 0.7);
        graphics.strokeCircle(0, 0, radius * 0.7);
        graphics.lineStyle(2, 0xff6600, 0.5);
        graphics.strokeCircle(0, 0, radius * 0.4);
        
        // Add spiral lines for tornado effect
        const spiralPoints = [];
        for (let i = 0; i < 16; i++) {
          const angle = (i / 16) * Math.PI * 2;
          const spiralRadius = radius * 0.3 + (radius * 0.4) * (i / 16);
          const x = Math.cos(angle + this.time.now * 0.002) * spiralRadius;
          const y = Math.sin(angle + this.time.now * 0.002) * spiralRadius;
          spiralPoints.push(x, y);
        }
        graphics.lineStyle(2, 0xffffff, 0.3);
        graphics.strokePoints(spiralPoints, false, true);
        
        container.add([graphics]);
      }
      
    } else if (type.toLowerCase().includes('predator')) {
      // Use predator sprite if available
      if (this.textures.exists('predator_sprite')) {
        // Use actual predator sprite
        const predatorSprite = this.add.image(0, 0, 'predator_sprite');
        
        // Scale predator to be slightly larger than birds but not huge
        const predatorSize = 16; // Twice bird size for visibility
        const spriteWidth = predatorSprite.width;
        const spriteHeight = predatorSprite.height;
        const spriteDiameter = Math.max(spriteWidth, spriteHeight);
        const scale = (predatorSize * 2) / spriteDiameter;
        
        predatorSprite.setScale(scale);
        predatorSprite.setTint(0xff4444); // Red tint to indicate danger
        predatorSprite.setAlpha(0.9);
        
        // Add subtle hover animation for circling motion
        this.tweens.add({
          targets: predatorSprite,
          y: predatorSprite.y - 10,
          duration: 2000,
          yoyo: true,
          repeat: -1,
          ease: 'Sine.easeInOut'
        });
        
        container.add([predatorSprite]);
      } else {
        // Fallback: Enhanced predator graphics with motion trails
        const predatorSize = 8; // Same size as birds
        graphics.fillStyle(0x990000, 0.8);
        graphics.fillCircle(0, 0, predatorSize);
        graphics.lineStyle(2, 0xff0000, 1.0);
        graphics.strokeCircle(0, 0, predatorSize);
        
        // Add predator eyes and teeth (scaled to bird size)
        graphics.fillStyle(0xff0000, 1.0);
        graphics.fillCircle(-predatorSize * 0.3, -predatorSize * 0.2, 2);
        graphics.fillCircle(predatorSize * 0.3, -predatorSize * 0.2, 2);
        
        // Add angular lines for teeth/claws (scaled to bird size)
        graphics.lineStyle(1, 0xffffff, 0.8);
        for (let i = 0; i < 6; i++) {
          const angle = (i / 6) * Math.PI * 2;
          const x1 = Math.cos(angle) * predatorSize * 0.7;
          const y1 = Math.sin(angle) * predatorSize * 0.7;
          const x2 = Math.cos(angle) * predatorSize * 0.9;
          const y2 = Math.sin(angle) * predatorSize * 0.9;
          graphics.lineBetween(x1, y1, x2, y2);
        }
        
        container.add([graphics]);
      }
      
    } else {
      // Enhanced generic hazard with warning pattern (PERFORMANCE: Removed particles)
      graphics.fillStyle(0xff4444, 0.4);
      graphics.fillCircle(0, 0, radius);
      graphics.lineStyle(2, 0xff0000, 0.7);
      graphics.strokeCircle(0, 0, radius);
      
      // Add warning triangle
      graphics.lineStyle(3, 0xffffff, 0.9);
      graphics.beginPath();
      graphics.moveTo(0, -radius * 0.4);
      graphics.lineTo(-radius * 0.3, radius * 0.2);
      graphics.lineTo(radius * 0.3, radius * 0.2);
      graphics.closePath();
      graphics.strokePath();
      
      // Add exclamation mark
      graphics.lineStyle(2, 0xffffff, 1.0);
      graphics.lineBetween(0, -radius * 0.2, 0, radius * 0.05);
      graphics.fillStyle(0xffffff, 1.0);
      graphics.fillCircle(0, radius * 0.15, 2);
      
      container.add([graphics]);
    }
    
    container.setDepth(LAYER_DEPTHS.HAZARDS);
    return container;
  }

  // Beacon selection methods removed - using path drawing system instead

  // NEW: Bird inspection methods
  private checkBirdInspection(worldX: number, worldY: number) {
    if (!this.gameState?.agents) return;
    
    const clickRadius = 25; // Pixels - how close click must be to bird
    let closestBird: Agent | null = null;
    let closestDistance = Infinity;
    
    // Find closest bird to click
    for (const agent of this.gameState.agents) {
      if (!agent.alive) continue;
      
      const distance = Math.sqrt(
        Math.pow(agent.x - worldX, 2) + 
        Math.pow(agent.y - worldY, 2)
      );
      
      if (distance < clickRadius && distance < closestDistance) {
        closestDistance = distance;
        closestBird = agent;
      }
    }
    
    if (closestBird) {
      this.showBirdInspection(closestBird);
      console.log('Bird inspection triggered for bird:', closestBird.id);
    } else {
      // Hide inspection panel if clicked elsewhere
      this.hideBirdInspection();
    }
  }
  
  private showBirdInspection(agent: Agent) {
    // Remove existing panel
    if (this.birdInspectionPanel) {
      this.birdInspectionPanel.destroy();
    }
    
    this.inspectedBirdId = agent.id;
    
    // Create inspection panel
    const panelWidth = 280;
    const panelHeight = 320;
    
    const panel = this.add.container(100, 100);
    panel.setDepth(LAYER_DEPTHS.UI + 10); // Above other UI
    
    // Background
    const bg = this.add.graphics();
    bg.fillStyle(0x0a0a0a, 0.95);
    bg.lineStyle(3, agent.gender === 'male' ? 0x4488ff : 0xff4488, 0.9);
    bg.fillRoundedRect(0, 0, panelWidth, panelHeight, 10);
    bg.strokeRoundedRect(0, 0, panelWidth, panelHeight, 10);
    panel.add(bg);
    
    // Header with bird info
    const genderSymbol = agent.gender === 'male' ? '♂' : '♀';
    const genderColor = agent.gender === 'male' ? '#4488ff' : '#ff4488';
    
    const headerText = this.add.text(panelWidth / 2, 20, `${genderSymbol} Bird ${agent.id}`, {
      fontSize: '16px',
      color: genderColor,
      fontStyle: 'bold'
    });
    headerText.setOrigin(0.5);
    panel.add(headerText);
    
    // Generation info
    const genText = this.add.text(panelWidth / 2, 40, 
      `Generation ${agent.generation || 0}`, {
      fontSize: '12px',
      color: '#ffdd44'
    });
    genText.setOrigin(0.5);
    panel.add(genText);
    
    // Status info
    let yPos = 70;
    
    // Energy and stress
    const energyText = this.add.text(15, yPos, `Energy: ${Math.round(agent.energy)}/100`, {
      fontSize: '11px',
      color: agent.energy > 60 ? '#44ff44' : agent.energy > 30 ? '#ffaa44' : '#ff4444'
    });
    panel.add(energyText);
    
    const stressText = this.add.text(150, yPos, `Stress: ${Math.round(agent.stress)}/100`, {
      fontSize: '11px',
      color: agent.stress > 70 ? '#ff4444' : agent.stress > 40 ? '#ffaa44' : '#44ff44'
    });
    panel.add(stressText);
    yPos += 25;
    
    // Stats
    if (agent.fitness !== undefined) {
      const fitnessText = this.add.text(15, yPos, `Fitness: ${agent.fitness.toFixed(2)}`, {
        fontSize: '11px',
        color: '#88ff88'
      });
      panel.add(fitnessText);
    }
    
    if (agent.survived_levels !== undefined) {
      const survivalText = this.add.text(150, yPos, `Survived: ${agent.survived_levels} levels`, {
        fontSize: '11px',
        color: '#88ff88'
      });
      panel.add(survivalText);
    }
    yPos += 25;
    
    // Close calls and leadership time
    if (agent.close_calls !== undefined) {
      const closeCallText = this.add.text(15, yPos, `Close calls: ${agent.close_calls}`, {
        fontSize: '11px',
        color: '#ffaa44'
      });
      panel.add(closeCallText);
    }
    
    if (agent.leadership_time !== undefined) {
      const leadTime = agent.leadership_time.toFixed(1);
      const leadText = this.add.text(150, yPos, `Led: ${leadTime}s`, {
        fontSize: '11px',
        color: '#ffdd44'
      });
      panel.add(leadText);
    }
    yPos += 35;
    
    // Genetics section
    if (agent.genetics) {
      const geneticsHeader = this.add.text(15, yPos, 'Genetic Traits:', {
        fontSize: '12px',
        color: '#aa44ff',
        fontStyle: 'bold'
      });
      panel.add(geneticsHeader);
      yPos += 20;
      
      const traits = [
        { key: 'hazard_awareness', name: 'Hazard Awareness', color: '#ff4444' },
        { key: 'energy_efficiency', name: 'Energy Efficiency', color: '#44ff44' },
        { key: 'flock_cohesion', name: 'Flock Cohesion', color: '#4444ff' },
        // Beacon sensitivity removed - using path-based system instead
        { key: 'stress_resilience', name: 'Stress Resilience', color: '#aa44ff' },
        { key: 'leadership', name: 'Leadership', color: '#ffdd44' }
      ];
      
      for (const trait of traits) {
        const genetics = agent.genetics as any; // Type assertion to allow indexing
        if (genetics[trait.key] !== undefined) {
          const value = genetics[trait.key];
          const percentage = Math.round(value * 100);
          
          // Trait name
          const traitText = this.add.text(15, yPos, trait.name, {
            fontSize: '10px',
            color: '#cccccc'
          });
          panel.add(traitText);
          
          // Trait bar background
          const barBg = this.add.graphics();
          barBg.fillStyle(0x333333, 0.5);
          barBg.fillRect(140, yPos - 4, 100, 10);
          panel.add(barBg);
          
          // Trait bar
          const traitBar = this.add.graphics();
          traitBar.fillStyle(parseInt(trait.color.replace('#', '0x')), 0.8);
          traitBar.fillRect(140, yPos - 4, Math.max(2, 100 * value), 10);
          panel.add(traitBar);
          
          // Percentage text
          const percentText = this.add.text(250, yPos, `${percentage}%`, {
            fontSize: '9px',
            color: '#ffffff'
          });
          percentText.setOrigin(1, 0);
          panel.add(percentText);
          
          yPos += 18;
        }
      }
    }
    
    // Close button
    const closeBtn = this.add.text(panelWidth - 15, 15, '×', {
      fontSize: '20px',
      color: '#ff4444'
    });
    closeBtn.setOrigin(0.5);
    closeBtn.setInteractive({ cursor: 'pointer' });
    closeBtn.on('pointerdown', () => this.hideBirdInspection());
    panel.add(closeBtn);
    
    // Position panel near bird but keep on screen
    const birdSprite = this.agentSprites.get(agent.id.toString());
    if (birdSprite) {
      let panelX = birdSprite.x + 30;
      let panelY = birdSprite.y - panelHeight / 2;
      
      // Keep panel on screen
      const camera = this.cameras.main;
      panelX = Math.max(10, Math.min(panelX, camera.width - panelWidth - 10));
      panelY = Math.max(10, Math.min(panelY, camera.height - panelHeight - 10));
      
      panel.setPosition(panelX, panelY);
    }
    
    this.birdInspectionPanel = panel;
    
    // Auto-hide after 10 seconds
    this.time.delayedCall(10000, () => {
      this.hideBirdInspection();
    });
  }
  
  public hideBirdInspection() {
    if (this.birdInspectionPanel) {
      this.birdInspectionPanel.destroy();
      this.birdInspectionPanel = null as any;
      this.inspectedBirdId = null as any;
    }
  }
  
  // Update the inspection panel if it's showing
  private updateBirdInspection() {
    if (!this.birdInspectionPanel || this.inspectedBirdId === undefined) return;
    
    // Find the inspected bird in current game state
    const inspectedBird = this.gameState?.agents.find(a => a.id === this.inspectedBirdId);
    
    if (!inspectedBird || !inspectedBird.alive) {
      // Bird is gone, hide panel
      this.hideBirdInspection();
      return;
    }
    
    // Refresh the panel with updated data
    this.showBirdInspection(inspectedBird);
  }

  public setWebSocketClient(client: WebSocketClient) {
    this.wsClient = client;
  }
}