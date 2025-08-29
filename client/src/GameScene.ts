import { Scene } from 'phaser';
import { audioManager } from './AudioManager';
import { LAYER_DEPTHS } from './config/gameConfig';
import { BirdAnimationSystem } from './BirdAnimationSystem';

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

interface Beacon {
  id?: string;
  type: string;
  position?: [number, number];
  x?: number;
  y?: number;
  strength: number;
  range?: number;
}

interface Hazard {
  type: string;
  position?: [number, number];
  x?: number;
  y?: number;
  radius?: number;
  strength?: number;
}

interface GameState {
  tick: number;
  level: string;
  agents: Agent[];
  population: number;
  arrivals: number;
  losses: number;
  cohesion: number;
  beacons: Beacon[];
  hazards: Hazard[];
  destination: [number, number] | null;
  game_over: boolean;
  victory: boolean;
  time_remaining: number;
  season: {
    day: number;
    hour: number;
  };
  beacon_budget: number;
  breed: any;
  survival_rate: number;
  close_calls: number;
  panic_events: number;
}

export class GameScene extends Scene {
  private gameState: GameState | null = null;
  private agentSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private beaconSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private foodSiteSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private hazardSprites: Map<string, Phaser.GameObjects.Container> = new Map();
  private hazardParticles: Map<string, Phaser.GameObjects.Particles.ParticleEmitter> = new Map();
  private destinationSprite: Phaser.GameObjects.Graphics | null = null;
  private birdAnimationSystem!: BirdAnimationSystem;
  
  // UI elements
  private infoText!: Phaser.GameObjects.Text;
  private connectionText!: Phaser.GameObjects.Text;
  private lastConnectionStatus: boolean = false;
  private beaconPanel!: Phaser.GameObjects.Container;
  private selectedBeaconType: string | null = null;
  private beaconButtons: Map<string, Phaser.GameObjects.Container> = new Map();
  
  // Enhanced HUD properties
  private hudContainer!: Phaser.GameObjects.Container;
  private levelText!: Phaser.GameObjects.Text;
  private missionText!: Phaser.GameObjects.Text;
  private timeText!: Phaser.GameObjects.Text;
  private flockStatusText!: Phaser.GameObjects.Text;
  private populationText!: Phaser.GameObjects.Text;
  private energyText!: Phaser.GameObjects.Text;
  private telemetryFields!: {
    cohesion: Phaser.GameObjects.Text;
    separation: Phaser.GameObjects.Text;
    alignment: Phaser.GameObjects.Text;
    avgSpeed: Phaser.GameObjects.Text;
    stress: Phaser.GameObjects.Text;
    beaconCount: Phaser.GameObjects.Text;
  };
  private healthBarBg!: Phaser.GameObjects.Graphics;
  private healthBarFill!: Phaser.GameObjects.Graphics;
  private healthBarText!: Phaser.GameObjects.Text;
  private telemetryToggle!: Phaser.GameObjects.Text;
  private telemetryVisible: boolean = true;
  
  // Evolution/Breed panel
  private evolutionFields: {
    breedName?: Phaser.GameObjects.Text;
    generation?: Phaser.GameObjects.Text;
    survivalRate?: Phaser.GameObjects.Text;
    hazardAwareness?: Phaser.GameObjects.Text;
    energyEfficiency?: Phaser.GameObjects.Text;
    beaconSensitivity?: Phaser.GameObjects.Text;
  } = {};
  private evolutionToggle!: Phaser.GameObjects.Text;
  private evolutionVisible: boolean = true;
  
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
  private flockCentroid = { x: 0, y: 0 };
  private flockVelocity = { x: 0, y: 0 };
  private cameraTargetPos = { x: 0, y: 0 };
  private cameraFollowSmoothness = 0.05;
  
  // World bounds (matching Python simulation)
  private worldWidth = 2000;
  private worldHeight = 1200;
  
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
      
      // Beacon sprites
      this.load.image('beacon_food', 'assets/sprites/beacon-food.png');
      this.load.image('beacon_shelter', 'assets/sprites/beacon-shelter.png');
      this.load.image('beacon_thermal', 'assets/sprites/beacon-thermal.png');
      
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
    
    // Set initial zoom for better visibility
    this.cameras.main.setZoom(0.8);
    this.cameras.main.centerOn(1000, 600); // Center on middle of world
    
    // Create enhanced background with layers
    this.createBackground();
    
    // Initialize bird animation system
    this.birdAnimationSystem = new BirdAnimationSystem(this);
    
    // DEBUG: Add a test bird at center of view to check visibility
    const testBird = this.add.graphics();
    testBird.lineStyle(4, 0xFF0000, 1);
    testBird.fillStyle(0xFFFF00, 1);
    testBird.fillCircle(1000, 600, 20); // Center of camera view
    testBird.strokeCircle(1000, 600, 20);
    testBird.setDepth(100);
    console.log('🔴 DEBUG: Added yellow test bird at 1000, 600');
    
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
    this.input.on('wheel', (pointer: any, gameObjects: any, deltaX: number, deltaY: number) => {
      const camera = this.cameras.main;
      if (deltaY > 0) {
        camera.setZoom(Math.max(0.1, camera.zoom - this.zoomSpeed));
      } else {
        camera.setZoom(Math.min(2.0, camera.zoom + this.zoomSpeed));
      }
    });
    
    // Mouse click for beacon placement
    this.input.on('pointerdown', (pointer: Phaser.Input.Pointer, gameObjects: any) => {
      console.log('Click detected:', {
        worldX: pointer.worldX,
        worldY: pointer.worldY,
        selectedBeacon: this.selectedBeaconType,
        leftButton: pointer.leftButtonDown(),
        gameObjects: gameObjects.length
      });
      
      // Check if click was on UI element first
      const clickedOnUI = gameObjects.some((obj: any) => obj.depth >= 100);
      if (clickedOnUI) {
        console.log('Clicked on UI, ignoring');
        return; // Don't place beacon if clicking on UI
      }
      
      if (pointer.leftButtonDown() && this.selectedBeaconType) {
        console.log('Placing beacon:', this.selectedBeaconType, 'at', pointer.worldX, pointer.worldY);
        this.placeBeacon(this.selectedBeaconType, pointer.worldX, pointer.worldY);
        console.log('Beacon placement completed');
        // Keep beacon selected for multiple placements
      } else if (pointer.leftButtonDown()) {
        // NEW: Check for bird click (inspect bird if close enough)
        this.checkBirdInspection(pointer.worldX, pointer.worldY);
        console.log('Clicked without beacon selected - checking for bird inspection');
      } else {
        console.log('Not placing beacon - leftButton:', pointer.leftButtonDown(), 'selectedType:', this.selectedBeaconType);
      }
    });
    
    // Space for pause/resume
    this.input.keyboard!.on('keydown-SPACE', () => {
      this.togglePause();
    });
  }

  update() {
    // Enhanced camera system
    this.updateCameraSystem();
  }

  private updateCameraSystem() {
    const camera = this.cameras.main;
    
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
    const modes: Array<'manual' | 'flock_follow' | 'frame_all'> = ['manual', 'flock_follow', 'frame_all'];
    const currentIndex = modes.indexOf(this.cameraMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    this.cameraMode = modes[nextIndex];
    
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
      beacons: newState.beacons?.length || 0,
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
    
    super.destroy();
  }

  // Helper function for crisp text rendering
  private createCrispText(x: number, y: number, text: string, style: Phaser.Types.GameObjects.Text.TextStyle): Phaser.GameObjects.Text {
    const resolution = window.devicePixelRatio || 1;
    const crispStyle = {
      ...style,
      resolution: resolution,
      padding: { x: 2, y: 2 } // Add padding to prevent clipping
    };
    return this.add.text(x, y, text, crispStyle);
  }

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
    this.updateBeacons();
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
      
      // Mark as tracked
      this.agentSprites.set(agentId, true as any);
    }
    
    // Update cohesion effects
    if (this.gameState.cohesion !== undefined) {
      this.birdAnimationSystem.updateCohesionEffects(this.gameState.cohesion);
    }
    
    // Interpolate positions for smooth movement
    this.birdAnimationSystem.interpolatePositions(this.game.loop.delta);
  }

  private updateBeacons() {
    if (!this.gameState?.beacons) return;
    
    // Remove only SERVER beacons that no longer exist (keep client beacons)
    for (const [beaconId, container] of this.beaconSprites.entries()) {
      // Don't remove client-created beacons - ensure beaconId is string
      if (typeof beaconId === 'string' && beaconId.startsWith('client_')) {
        continue;
      }
      
      if (!this.gameState.beacons.find(b => b.id === beaconId)) {
        container.destroy();
        this.beaconSprites.delete(beaconId);
      }
    }
    
    // Update or create beacon sprites
    for (const beacon of this.gameState.beacons) {
      const beaconId = beacon.id || `${beacon.type}_${beacon.x || beacon.position?.[0] || 0}_${beacon.y || beacon.position?.[1] || 0}`;
      let container = this.beaconSprites.get(beaconId);
      
      if (!container) {
        // Get position from either x,y or position array
        const x = beacon.x ?? beacon.position?.[0] ?? 0;
        const y = beacon.y ?? beacon.position?.[1] ?? 0;
        
        // Create enhanced beacon with iconography and decay timer
        container = this.createEnhancedBeacon(beacon, x, y);
        this.beaconSprites.set(beaconId, container);
      } else {
        // Update existing beacon position and decay state
        const x = beacon.x ?? beacon.position?.[0] ?? 0;
        const y = beacon.y ?? beacon.position?.[1] ?? 0;
        container.setPosition(x, y);
        
        // Update decay timer if beacon has decay information
        this.updateBeaconDecay(container, beacon);
      }
    }
  }

  private createEnhancedBeacon(beacon: any, x: number, y: number): Phaser.GameObjects.Container {
    const container = this.add.container(x, y);
    container.setDepth(LAYER_DEPTHS.BEACONS);
    
    // Determine beacon color and iconography
    let color = 0xffffff;
    let iconKey = '';
    
    switch (beacon.type.toLowerCase()) {
      case 'shelter': 
        color = 0x0000ff; 
        iconKey = 'icon_shelter';
        break;
      case 'thermal': 
        color = 0xff0000; 
        iconKey = 'icon_thermal';
        break;
    }
    
    // Create the main beacon icon
    let beaconSprite;
    if (this.textures.exists(iconKey)) {
      beaconSprite = this.add.image(0, 0, iconKey).setScale(0.6);
    } else {
      // Fallback: create procedural icon based on type
      beaconSprite = this.add.graphics();
      beaconSprite.fillStyle(color);
      if (beacon.type === 'shelter') {
        // Shelter: house shape
        beaconSprite.fillTriangle(0, -8, -6, 2, 6, 2);
        beaconSprite.fillRect(-4, 2, 8, 6);
      } else if (beacon.type === 'thermal') {
        // Thermal: flame/triangle shape
        beaconSprite.fillTriangle(0, -8, -4, 4, 4, 4);
        beaconSprite.fillEllipse(0, 2, 6, 4);
      } else {
        // Default: circle for unknown types
        beaconSprite.fillCircle(0, 0, 8);
      }
    }
    container.add(beaconSprite);
    
    // Create influence radius ring
    const influenceRadius = beacon.range || 50;
    const radiusRing = this.add.circle(0, 0, influenceRadius, color, 0.08);
    radiusRing.setStrokeStyle(2, color, 0.4);
    container.add(radiusRing);
    
    // Add pulsing range indicator
    this.tweens.add({
      targets: radiusRing,
      alpha: 0.15,
      scaleX: 1.05,
      scaleY: 1.05,
      duration: 2000,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut'
    });
    
    // Create decay timer visualization (if beacon has lifetime)
    if (beacon.lifetime || beacon.decay_time) {
      const decayRing = this.add.graphics();
      decayRing.lineStyle(3, color, 0.8);
      // Draw full circle initially
      decayRing.strokeCircle(0, 0, 12);
      container.add(decayRing);
      
      // Store reference for decay updates
      container.setData('decayRing', decayRing);
      container.setData('originalLifetime', beacon.lifetime || beacon.decay_time);
    }
    
    // Add beacon glow/pulse animation
    this.tweens.add({
      targets: beaconSprite,
      alpha: 0.7,
      scaleX: 1.1,
      scaleY: 1.1,
      duration: 1500,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut'
    });
    
    return container;
  }

  private updateBeaconDecay(container: Phaser.GameObjects.Container, beacon: any): void {
    const decayRing = container.getData('decayRing') as Phaser.GameObjects.Graphics;
    const originalLifetime = container.getData('originalLifetime') as number;
    
    if (decayRing && originalLifetime && (beacon.remaining_time !== undefined || beacon.decay_remaining !== undefined)) {
      const remainingTime = beacon.remaining_time || beacon.decay_remaining || originalLifetime;
      const decayProgress = remainingTime / originalLifetime;
      
      // Clear and redraw decay ring based on remaining time
      decayRing.clear();
      
      if (decayProgress > 0) {
        const startAngle = -Math.PI / 2; // Start at top
        const endAngle = startAngle + (decayProgress * 2 * Math.PI);
        
        // Color changes as beacon decays (green -> yellow -> red)
        let decayColor = 0x00ff00; // Green
        if (decayProgress < 0.5) {
          decayColor = 0xffff00; // Yellow
        }
        if (decayProgress < 0.25) {
          decayColor = 0xff0000; // Red
        }
        
        decayRing.lineStyle(3, decayColor, 0.8);
        decayRing.beginPath();
        decayRing.arc(0, 0, 12, startAngle, endAngle);
        decayRing.strokePath();
        
        // Add urgency pulsing when decay is critical
        if (decayProgress < 0.3) {
          this.tweens.killTweensOf(decayRing);
          this.tweens.add({
            targets: decayRing,
            alpha: 0.4,
            duration: 200,
            yoyo: true,
            repeat: -1,
            ease: 'Power2'
          });
        }
      }
    }
  }

  private updateFoodSites() {
    if (!this.gameState?.food_sites) return;

    // Remove food site sprites that no longer exist
    const currentFoodSiteIds = new Set(
      this.gameState.food_sites.map((site, index) => `food_site_${index}`)
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
        container = this.createFoodSiteVisual(foodSite, foodSite.x, foodSite.y);
        this.foodSiteSprites.set(siteId, container);
        console.log(`🟢 Created food site visual at (${foodSite.x}, ${foodSite.y})`);
      } else {
        // Update existing food site position (in case it moves)
        container.setPosition(foodSite.x, foodSite.y);
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

  private updateBirdFeedingEffects(agent: any, sprite: Phaser.GameObjects.Container): void {
    if (!agent.alive || !this.gameState?.food_sites) return;

    // Check if bird is within any food site radius
    let isFeeding = false;
    for (const foodSite of this.gameState.food_sites) {
      const distance = Math.sqrt(
        Math.pow(agent.x - foodSite.x, 2) + Math.pow(agent.y - foodSite.y, 2)
      );
      
      const feedingRadius = (foodSite.radius || 80) * 0.8; // Slightly smaller than visual radius
      if (distance < feedingRadius) {
        isFeeding = true;
        
        // Create feeding particle effect if not already active
        if (!sprite.getData('feedingEffect')) {
          this.createFeedingParticleEffect(agent.x, agent.y);
          sprite.setData('feedingEffect', true);
          
          // Add temporary glow effect to the bird while feeding
          const glowEffect = this.add.circle(0, 0, 15, 0x00ff00, 0.3);
          sprite.add(glowEffect);
          sprite.setData('feedingGlow', glowEffect);
          
          // Pulse the glow
          this.tweens.add({
            targets: glowEffect,
            alpha: 0.6,
            scaleX: 1.3,
            scaleY: 1.3,
            duration: 800,
            yoyo: true,
            repeat: -1,
            ease: 'Sine.easeInOut'
          });
          
          console.log(`🟢 Bird ${agent.id} started feeding at (${agent.x.toFixed(0)}, ${agent.y.toFixed(0)})`);
        }
        break;
      }
    }

    // Remove feeding effects if no longer feeding
    if (!isFeeding && sprite.getData('feedingEffect')) {
      sprite.setData('feedingEffect', false);
      
      // Remove glow effect
      const glowEffect = sprite.getData('feedingGlow');
      if (glowEffect) {
        this.tweens.killTweensOf(glowEffect);
        glowEffect.destroy();
        sprite.setData('feedingGlow', null);
      }
      
      console.log(`🟢 Bird ${agent.id} stopped feeding`);
    }
  }

  private createFeedingParticleEffect(x: number, y: number): void {
    // Create small green particles rising upward to indicate feeding
    const particles = this.add.particles(x, y, 'spark', {
      speed: { min: 10, max: 30 },
      scale: { start: 0.3, end: 0 },
      lifespan: 1000,
      tint: [0x00ff00, 0x66ff66, 0xccffcc],
      frequency: 100,
      angle: { min: 260, max: 280 }, // Upward direction
      quantity: 2
    });
    
    particles.setDepth(LAYER_DEPTHS.BEACONS + 1); // Above food sites
    
    // Auto-destroy the particle effect after a short time
    this.time.delayedCall(1500, () => {
      particles.destroy();
    });
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

    const [x, y, radius] = this.gameState.destination;
    
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
    if (!this.gameState) return;
    
    const agents = this.gameState.agents || [];
    const aliveAgents = agents.filter(a => a.alive);
    const aliveCount = aliveAgents.length;
    const totalEnergy = agents.reduce((sum, a) => sum + a.energy, 0);
    const avgEnergy = agents.length > 0 ? totalEnergy / agents.length : 0;
    
    // Update main status elements
    this.levelText?.setText(`Level: ${this.gameState.level || 'N/A'} | Tick: ${this.gameState.tick || 0}`);
    this.missionText?.setText(`${this.getMissionDescription()}`);
    this.timeText?.setText(`Time: ${(this.gameState.time_remaining || 0).toFixed(1)}s | Beacons: ${(this.gameState?.beacons?.length || 0)}`);
    
    // Update flock status
    this.populationText?.setText(`Population: ${aliveCount}/${this.gameState.population || 0}`);
    this.energyText?.setText(`Energy: ${avgEnergy.toFixed(1)} avg`);
    
    // Update telemetry less frequently for performance (every 10 frames)
    if (this.telemetryVisible && this.telemetryFields && (this.game?.loop.frame || 0) % 10 === 0) {
      this.updateTelemetryData(aliveAgents);
    }
    
    // Update health bar less frequently (every 5 frames)
    if ((this.game?.loop.frame || 0) % 5 === 0) {
      this.updateHealthBar(aliveAgents);
      this.updateStatusColors(aliveCount, this.gameState.population || 1);
    }
    
    // Update basic info text as fallback
    if (this.infoText) {
      this.infoText.setText(
        `Level: ${this.gameState.level} | Tick: ${this.gameState.tick} | ` +
        `Time: ${(this.gameState.time_remaining || 0).toFixed(1)}s | ` +
        `Population: ${aliveCount}/${this.gameState.population} | ` +
        `Energy: ${avgEnergy.toFixed(0)} | Beacons: ${(this.gameState?.beacons?.length || 0)}`
      );
    }
  }
  
  private getMissionDescription(): string {
    if (!this.gameState) return 'Loading...';
    
    const level = this.gameState.level;
    if (level?.includes('W1')) return 'Training: Navigate safely to destination';
    if (level?.includes('W2')) return 'Challenge: Avoid hazards and conserve energy';
    if (level?.includes('W3')) return 'Expert: Master complex environments';
    return 'Guide the flock to safety';
  }
  
  private updateTelemetryData(aliveAgents: any[]) {
    if (aliveAgents.length === 0) {
      Object.values(this.telemetryFields).forEach(field => {
        field.setText(field.text.split(':')[0] + ': --');
      });
      return;
    }
    
    // Calculate flock metrics
    const avgSpeed = aliveAgents.reduce((sum, a) => sum + Math.sqrt(a.vx * a.vx + a.vy * a.vy), 0) / aliveAgents.length;
    const avgStress = aliveAgents.reduce((sum, a) => sum + (a.stress || 0), 0) / aliveAgents.length;
    
    // Calculate cohesion (inverse of average distance to centroid)
    const centroidX = aliveAgents.reduce((sum, a) => sum + a.x, 0) / aliveAgents.length;
    const centroidY = aliveAgents.reduce((sum, a) => sum + a.y, 0) / aliveAgents.length;
    const avgDistanceToCenter = aliveAgents.reduce((sum, a) => {
      return sum + Math.sqrt((a.x - centroidX) ** 2 + (a.y - centroidY) ** 2);
    }, 0) / aliveAgents.length;
    const cohesion = Math.max(0, 100 - avgDistanceToCenter / 2); // Normalize to 0-100
    
    // Update telemetry fields
    this.telemetryFields.cohesion?.setText(`Cohesion: ${cohesion.toFixed(1)}%`);
    this.telemetryFields.avgSpeed?.setText(`Avg Speed: ${avgSpeed.toFixed(1)}`);
    this.telemetryFields.stress?.setText(`Stress Level: ${avgStress.toFixed(1)}`);
    this.telemetryFields.beaconCount?.setText(`Beacons: ${(this.gameState?.beacons?.length || 0)}`);
    
    // Placeholder for separation and alignment (would need velocity data)
    this.telemetryFields.separation?.setText('Separation: Good');
    this.telemetryFields.alignment?.setText('Alignment: Stable');
    
    // Update evolution fields
    this.updateEvolutionData();
  }
  
  private updateHealthBar(aliveAgents: any[]) {
    if (!this.healthBarFill || !this.gameState) return;
    
    const totalPopulation = this.gameState.population || 1;
    const aliveCount = aliveAgents.length;
    const healthPercentage = aliveCount / totalPopulation;
    
    // Clear and redraw health bar
    this.healthBarFill.clear();
    
    // Color based on health percentage
    let healthColor = 0x00ff00; // Green
    if (healthPercentage < 0.7) healthColor = 0xffaa00; // Yellow
    if (healthPercentage < 0.4) healthColor = 0xff4400; // Orange
    if (healthPercentage < 0.2) healthColor = 0xff0000; // Red
    
    this.healthBarFill.fillStyle(healthColor, 0.8);
    this.healthBarFill.fillRoundedRect(20, 170, 280 * healthPercentage, 12, 6);
    
    // Update health bar text
    this.healthBarText?.setText(`Flock Health: ${(healthPercentage * 100).toFixed(0)}%`);
  }
  
  private updateEvolutionData() {
    if (!this.gameState || !this.gameState.breed || !this.evolutionFields) return;
    
    const breed = this.gameState.breed;
    
    // Update breed information
    this.evolutionFields.breedName?.setText(`Breed: ${breed.name || 'Unknown'}`);
    this.evolutionFields.generation?.setText(`Generation: ${breed.generation || 0}`);
    this.evolutionFields.survivalRate?.setText(`Survival: ${((this.gameState.survival_rate || 0) * 100).toFixed(1)}%`);
    
    // Update trait information (convert 0-1 values to percentages)
    this.evolutionFields.hazardAwareness?.setText(`Hazard Aware: ${((breed.hazard_awareness || 0) * 100).toFixed(0)}%`);
    this.evolutionFields.energyEfficiency?.setText(`Energy Eff: ${((breed.energy_efficiency || 1.0) * 100).toFixed(0)}%`);
    this.evolutionFields.beaconSensitivity?.setText(`Beacon Sens: ${((breed.beacon_sensitivity || 0) * 100).toFixed(0)}%`);
    
    // Update visual trait bars (if they exist)
    this.updateTraitBars(breed);
  }
  
  private updateTraitBars(breed: any) {
    // Update the visual trait bars with current breed values
    // This would animate the bars to show current trait levels
    // For now, we'll just ensure the text labels are updated
    // TODO: Implement visual bar fill animations based on trait values
  }
  
  private updateStatusColors(aliveCount: number, totalPopulation: number) {
    const healthPercentage = aliveCount / totalPopulation;
    
    // Update population text color based on health
    if (this.populationText) {
      if (healthPercentage > 0.7) {
        this.populationText.setColor('#00ff00');
      } else if (healthPercentage > 0.4) {
        this.populationText.setColor('#ffaa00');
      } else {
        this.populationText.setColor('#ff4400');
      }
    }
    
    // Update time text urgency
    if (this.timeText && this.gameState) {
      const timeLeft = this.gameState.time_remaining || 0;
      if (timeLeft < 20) {
        this.timeText.setColor('#ff0000');
        // Add pulsing animation for urgency
        if (timeLeft < 10) {
          this.tweens.killTweensOf(this.timeText);
          this.tweens.add({
            targets: this.timeText,
            alpha: 0.5,
            duration: 300,
            yoyo: true,
            repeat: -1
          });
        }
      } else {
        this.timeText.setColor('#ffaa00');
        this.tweens.killTweensOf(this.timeText);
        this.timeText.setAlpha(1);
      }
    }
  }

  private placeBeacon(type: string, x: number, y: number) {
    console.log('Placing beacon:', type, 'at', x, y);
    
    // Play beacon placement sound
    audioManager.playBeaconPlace();
    
    // Create a persistent visual beacon immediately for feedback
    this.createClientBeacon(type, x, y);
    
    // Emit event that will be handled by the main game
    console.log('🎯 Emitting placeBeacon event:', { type, x, y });
    this.events.emit('placeBeacon', { type, x, y });
  }
  
  private createClientBeacon(type: string, x: number, y: number) {
    // Create a persistent client beacon for immediate visual feedback
    const beaconId = `client_${type}_${x.toFixed(0)}_${y.toFixed(0)}_${Date.now()}`;
    const container = this.add.container(x, y);
    
    let color = 0xffffff;
    
    switch (type.toLowerCase()) {
      case 'shelter': color = 0x0000ff; break;
      case 'thermal': color = 0xff0000; break;
      default: color = 0xffffff; break; // Default white for unknown types
    }
    
    // Simple circle beacon (no complex assets)
    const beaconSprite = this.add.circle(0, 0, 8, color);
    container.add(beaconSprite);
    
    // Add influence radius
    const radius = this.add.circle(0, 0, 30, color, 0.1);
    radius.setStrokeStyle(2, color, 0.5);
    container.add(radius);
    
    // Add pulsing animation
    this.tweens.add({
      targets: beaconSprite,
      scaleX: 1.2,
      scaleY: 1.2,
      duration: 1500,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut'
    });
    
    // Store permanently - don't let server overwrite
    this.beaconSprites.set(beaconId, container);
    
    console.log('Beacon created at', x, y, 'with ID:', beaconId);
  }

  private togglePause() {
    this.events.emit('togglePause');
  }

  public loadLevel(levelIndex: number) {
    this.events.emit('loadLevel', levelIndex);
  }
  
  private createBeaconPanel() {
    // Position beacon panel in bottom-left area for better visibility
    const cameraHeight = this.cameras.main.height;
    this.beaconPanel = this.add.container(10, cameraHeight - 140);
    this.beaconPanel.setScrollFactor(0).setDepth(LAYER_DEPTHS.UI + 10); // Above HUD
    
    // Much smaller, simpler panel background
    const panelBg = this.add.rectangle(0, 0, 90, 90, 0x000000, 0.8);
    panelBg.setStrokeStyle(1, 0x4CAF50);
    this.beaconPanel.add(panelBg);
    
    // Smaller panel title
    const title = this.add.text(-35, -35, 'Beacons', {
      fontSize: '10px',
      color: '#4CAF50',
      fontWeight: 'bold'
    });
    this.beaconPanel.add(title);
    
    // Beacon types with working texture support - FOOD REMOVED: Food is now environmental
    const beaconTypes = [
      { type: 'shelter', name: 'Shelter', color: 0x0000ff, texture: 'icon_shelter' },
      { type: 'thermal', name: 'Thermal', color: 0xff0000, texture: 'icon_thermal' }
    ];
    
    beaconTypes.forEach((beacon, index) => {
      const y = -15 + (index * 18); // Much smaller spacing
      const button = this.createBeaconButton(beacon.type, beacon.name, beacon.color, beacon.texture, 0, y);
      this.beaconPanel.add(button);
      this.beaconButtons.set(beacon.type, button);
    });
    
    // Clear selection button
    const clearButton = this.createClearButton(0, 30); // Much closer position
    this.beaconPanel.add(clearButton);
  }
  
  private createBeaconButton(type: string, name: string, color: number, textureKey: string, x: number, y: number): Phaser.GameObjects.Container {
    const button = this.add.container(x, y);
    
    // Much smaller button background
    const bg = this.add.rectangle(0, 0, 70, 15, color, 0.3);
    bg.setStrokeStyle(1, color, 0.8);
    button.add(bg);
    
    // Smaller text
    const nameText = this.add.text(0, 0, name, { 
      fontSize: '8px', 
      color: '#ffffff',
      fontWeight: 'bold'
    }).setOrigin(0.5);
    button.add(nameText);
    
    // Make interactive with simple color changes
    bg.setInteractive({ useHandCursor: true });
    bg.on('pointerover', () => {
      bg.setFillStyle(color, 0.5);
    });
    bg.on('pointerout', () => {
      if (this.selectedBeaconType !== type) {
        bg.setFillStyle(color, 0.3);
      }
    });
    bg.on('pointerdown', () => {
      audioManager.playButtonClick();
      this.selectBeaconType(type);
    });
    
    return button;
  }
  
  private createClearButton(x: number, y: number): Phaser.GameObjects.Container {
    const button = this.add.container(x, y);
    
    const bg = this.add.rectangle(0, 0, 60, 12, 0x666666, 0.8);
    bg.setStrokeStyle(1, 0xcccccc);
    const text = this.add.text(0, 0, 'Clear', { fontSize: '7px', color: '#ffffff' }).setOrigin(0.5);
    
    button.add([bg, text]);
    
    bg.setInteractive({ useHandCursor: true });
    bg.on('pointerover', () => bg.setFillStyle(0x888888, 0.9));
    bg.on('pointerout', () => bg.setFillStyle(0x666666, 0.8));
    bg.on('pointerdown', () => this.clearBeaconSelection());
    
    return button;
  }
  
  private selectBeaconType(type: string) {
    console.log('Selecting beacon type:', type);
    
    // Clear previous selection
    this.beaconButtons.forEach((button, buttonType) => {
      const bg = button.list[0] as Phaser.GameObjects.Rectangle;
      const color = buttonType === 'shelter' ? 0x0000ff : 0xff0000;
      if (buttonType !== type) {
        this.tweens.killTweensOf(bg);
        bg.setFillStyle(color, 0.3);
        bg.setAlpha(1.0);
      }
    });
    
    // Highlight selected button
    const selectedButton = this.beaconButtons.get(type);
    if (selectedButton) {
      const bg = selectedButton.list[0] as Phaser.GameObjects.Rectangle;
      const color = type === 'shelter' ? 0x0000ff : 0xff0000;
      bg.setFillStyle(color, 0.8);
      
      // Add selection glow animation
      this.tweens.add({
        targets: bg,
        alpha: 0.6,
        duration: 800,
        yoyo: true,
        repeat: -1
      });
    }
    
    this.selectedBeaconType = type;
    console.log('Beacon type selected:', this.selectedBeaconType);
    
    // Update cursor to show selection
    this.input.setDefaultCursor('crosshair');
    console.log('Cursor changed to crosshair');
  }
  
  private clearBeaconSelection() {
    this.selectedBeaconType = null;
    this.input.setDefaultCursor('default');
    
    // Clear all button highlights and stop animations
    this.beaconButtons.forEach((button, buttonType) => {
      const bg = button.list[0] as Phaser.GameObjects.Rectangle;
      const color = buttonType === 'shelter' ? 0x0000ff : 0xff0000;
      this.tweens.killTweensOf(bg);
      bg.setFillStyle(color, 0.3);
      bg.setAlpha(1.0);
    });
  }
  
  private createBackground() {
    // Create day-night gradient overlay
    const dayNightOverlay = this.add.graphics();
    dayNightOverlay.fillStyle(0x000033, 0);
    dayNightOverlay.fillRect(0, 0, this.worldWidth, this.worldHeight);
    dayNightOverlay.setDepth(-11);
    
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
      const gradient = skyGradient.createLinearGradient(0, 0, 0, this.worldHeight);
      gradient.addColorStop(0, '#87CEEB'); // Sky blue at top
      gradient.addColorStop(0.7, '#98D8E8'); // Lighter blue
      gradient.addColorStop(1, '#F0E68C'); // Horizon color
      skyGradient.fillStyle(0x87CEEB);
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
    riverPath.cubicBezierTo(
      new Phaser.Math.Vector2(400, 850),
      new Phaser.Math.Vector2(800, 750),
      new Phaser.Math.Vector2(1200, 900),
      new Phaser.Math.Vector2(1600, 850),
      new Phaser.Math.Vector2(1900, 950)
    );
    
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
          const wave = Math.sin(waveOffset + i * 0.1) * 5;
          riverGraphics.beginPath();
          riverGraphics.moveTo(points[i].x, points[i].y + wave);
          riverGraphics.lineTo(points[i + 1].x, points[i + 1].y + wave);
          riverGraphics.strokePath();
        }
        
        // Add sparkles on water
        riverGraphics.fillStyle(0xffffff, 0.8);
        for (let i = 0; i < 10; i++) {
          const sparkleIndex = Math.floor(Math.random() * points.length);
          const sparkle = points[sparkleIndex];
          const sparkleSize = Math.sin(waveOffset * 2 + i) * 2 + 2;
          if (sparkleSize > 2) {
            riverGraphics.fillCircle(
              sparkle.x + Math.random() * 20 - 10,
              sparkle.y + Math.random() * 10 - 5,
              sparkleSize
            );
          }
        }
      },
      loop: true
    });
  }
  
  private createInfoPanel() {
    // Create enhanced HUD container
    this.hudContainer = this.add.container(0, 0);
    this.hudContainer.setScrollFactor(0).setDepth(LAYER_DEPTHS.UI);
    
    // Main status bar background
    const statusBarBg = this.add.graphics();
    statusBarBg.fillStyle(0x000000, 0.8);
    statusBarBg.lineStyle(2, 0x00ff44, 0.8);
    statusBarBg.fillRoundedRect(10, 10, 380, 70, 8);
    statusBarBg.strokeRoundedRect(10, 10, 380, 70, 8);
    this.hudContainer.add(statusBarBg);
    
    // Level and mission info with crisp text
    this.levelText = this.createCrispText(20, 20, 'Level: --', {
      fontSize: '16px',
      color: '#00ff44',
      fontWeight: 'bold'
    });
    this.hudContainer.add(this.levelText);
    
    this.missionText = this.createCrispText(20, 40, 'Mission: Loading...', {
      fontSize: '12px',
      color: '#ffffff'
    });
    this.hudContainer.add(this.missionText);
    
    // Time remaining with progress bar
    this.timeText = this.createCrispText(20, 58, 'Time: --', {
      fontSize: '12px',
      color: '#ffaa00'
    });
    this.hudContainer.add(this.timeText);
    
    // Flock status panel
    const flockPanelBg = this.add.graphics();
    flockPanelBg.fillStyle(0x001122, 0.9);
    flockPanelBg.lineStyle(2, 0x44aaff, 0.8);
    flockPanelBg.fillRoundedRect(200, 20, 180, 50, 6);
    flockPanelBg.strokeRoundedRect(200, 20, 180, 50, 6);
    this.hudContainer.add(flockPanelBg);
    
    this.flockStatusText = this.createCrispText(210, 28, 'Flock Status:', {
      fontSize: '12px',
      color: '#44aaff',
      fontWeight: 'bold'
    });
    this.hudContainer.add(this.flockStatusText);
    
    this.populationText = this.createCrispText(210, 42, 'Population: --/--', {
      fontSize: '11px',
      color: '#ffffff'
    });
    this.hudContainer.add(this.populationText);
    
    this.energyText = this.createCrispText(210, 56, 'Energy: --', {
      fontSize: '11px',
      color: '#ffdd00'
    });
    this.hudContainer.add(this.energyText);
    
    // Create telemetry panel (collapsible) - DISABLED: Now handled by UIScene
    // this.createTelemetryPanel();
    
    // Create evolution/breed panel - DISABLED: Now handled by UIScene
    // this.createEvolutionPanel();
    
    // Keep reference to basic info text for compatibility - DISABLED: Now handled by UIScene
    // this.infoText = this.createCrispText(15, 15, 'Connecting...', { 
    //   fontSize: '14px', 
    //   fontFamily: 'Arial, sans-serif',
    //   color: '#ffffff',
    //   backgroundColor: 'rgba(0,0,0,0.7)',
    //   padding: { x: 10, y: 5 }
    // }).setScrollFactor(0).setDepth(LAYER_DEPTHS.UI + 20);
  }
  
  private createTelemetryPanel() {
    // Telemetry panel background
    const telemetryBg = this.add.graphics();
    telemetryBg.fillStyle(0x220011, 0.85);
    telemetryBg.lineStyle(2, 0xff4488, 0.7);
    telemetryBg.fillRoundedRect(10, 90, 300, 120, 6);
    telemetryBg.strokeRoundedRect(10, 90, 300, 120, 6);
    this.hudContainer.add(telemetryBg);
    
    // Telemetry title
    const telemetryTitle = this.createCrispText(20, 100, '📊 Flock Telemetry', {
      fontSize: '14px',
      color: '#ff4488',
      fontWeight: 'bold'
    });
    this.hudContainer.add(telemetryTitle);
    
    // Create telemetry text fields with crisp text
    this.telemetryFields = {
      cohesion: this.createCrispText(20, 120, 'Cohesion: --', { fontSize: '11px', color: '#ffffff' }),
      separation: this.createCrispText(20, 135, 'Separation: --', { fontSize: '11px', color: '#ffffff' }),
      alignment: this.createCrispText(20, 150, 'Alignment: --', { fontSize: '11px', color: '#ffffff' }),
      avgSpeed: this.createCrispText(160, 120, 'Avg Speed: --', { fontSize: '11px', color: '#ffffff' }),
      stress: this.createCrispText(160, 135, 'Stress Level: --', { fontSize: '11px', color: '#ffffff' }),
      beaconCount: this.createCrispText(160, 150, 'Beacons: --', { fontSize: '11px', color: '#ffffff' })
    };
    
    Object.values(this.telemetryFields).forEach(field => {
      this.hudContainer.add(field);
    });
    
    // Visual health bar for flock
    this.createHealthBar();
    
    // Add toggle button for telemetry panel
    const toggleBtn = this.createCrispText(320, 100, '▼', {
      fontSize: '12px',
      color: '#ff4488',
      backgroundColor: 'rgba(0,0,0,0.5)',
      padding: { x: 6, y: 3 }
    });
    toggleBtn.setInteractive({ useHandCursor: true });
    toggleBtn.on('pointerdown', () => this.toggleTelemetryPanel());
    this.hudContainer.add(toggleBtn);
    this.telemetryToggle = toggleBtn;
    this.telemetryVisible = true;
  }
  
  private createEvolutionPanel() {
    // Evolution panel background - positioned BELOW telemetry panel to avoid overlap
    const evolutionBg = this.add.graphics();
    evolutionBg.fillStyle(0x001133, 0.85);
    evolutionBg.lineStyle(2, 0x44aaff, 0.7);
    evolutionBg.fillRoundedRect(10, 220, 300, 90, 6); // Moved below other panels
    evolutionBg.strokeRoundedRect(10, 220, 300, 90, 6);
    this.hudContainer.add(evolutionBg);
    
    // Evolution title
    const evolutionTitle = this.createCrispText(20, 230, '🧬 Breed Evolution', {
      fontSize: '14px',
      color: '#44aaff',
      fontWeight: 'bold'
    });
    this.hudContainer.add(evolutionTitle);
    
    // Create evolution text fields - repositioned to new panel location
    this.evolutionFields = {
      breedName: this.createCrispText(20, 250, 'Breed: --', { fontSize: '11px', color: '#ffffff' }),
      generation: this.createCrispText(20, 265, 'Generation: --', { fontSize: '11px', color: '#ffffff' }),
      survivalRate: this.createCrispText(20, 280, 'Survival Rate: --', { fontSize: '11px', color: '#ffffff' }),
      hazardAwareness: this.createCrispText(160, 250, 'Hazard Aware: --', { fontSize: '11px', color: '#ffffff' }),
      energyEfficiency: this.createCrispText(160, 265, 'Energy Eff: --', { fontSize: '11px', color: '#ffffff' }),
      beaconSensitivity: this.createCrispText(160, 280, 'Beacon Sens: --', { fontSize: '11px', color: '#ffffff' })
    };
    
    Object.values(this.evolutionFields).forEach(field => {
      if (field) this.hudContainer.add(field);
    });
    
    // Visual trait bars for breed traits
    this.createTraitBars();
    
    // Add toggle button for evolution panel
    const toggleBtn = this.createCrispText(320, 225, '▼', {
      fontSize: '12px',
      color: '#44aaff',
      backgroundColor: 'rgba(0,0,0,0.5)',
      padding: { x: 6, y: 3 }
    });
    toggleBtn.setInteractive({ useHandCursor: true });
    toggleBtn.on('pointerdown', () => this.toggleEvolutionPanel());
    this.hudContainer.add(toggleBtn);
    this.evolutionToggle = toggleBtn;
    this.evolutionVisible = true;
  }
  
  private createTraitBars() {
    // Add small visual bars for key traits at the bottom of evolution panel
    const traitY = 175;
    const barWidth = 40;
    const barHeight = 8;
    
    // Create trait bar backgrounds
    ['Hazard', 'Energy', 'Beacon'].forEach((trait, i) => {
      const x = 330 + i * 90;
      
      // Background bar
      const bg = this.add.graphics();
      bg.fillStyle(0x333333, 0.8);
      bg.fillRoundedRect(x, traitY, barWidth, barHeight, 2);
      this.hudContainer.add(bg);
      
      // Trait label
      const label = this.createCrispText(x, traitY + 12, trait, { 
        fontSize: '9px', 
        color: '#aaaaaa' 
      });
      this.hudContainer.add(label);
    });
  }
  
  private toggleEvolutionPanel() {
    this.evolutionVisible = !this.evolutionVisible;
    
    // Update toggle button
    this.evolutionToggle?.setText(this.evolutionVisible ? '▼' : '▶');
    
    // Show/hide evolution fields (implement animation similar to telemetry panel)
    Object.values(this.evolutionFields).forEach(field => {
      if (field) field.setVisible(this.evolutionVisible);
    });
  }
  
  private createHealthBar() {
    // Health bar background
    this.healthBarBg = this.add.graphics();
    this.healthBarBg.fillStyle(0x333333, 0.8);
    this.healthBarBg.fillRoundedRect(20, 170, 280, 12, 6);
    this.hudContainer.add(this.healthBarBg);
    
    // Health bar fill
    this.healthBarFill = this.add.graphics();
    this.hudContainer.add(this.healthBarFill);
    
    // Health bar text
    this.healthBarText = this.createCrispText(160, 175, 'Flock Health', {
      fontSize: '10px',
      color: '#ffffff'
    }).setOrigin(0.5, 0.5);
    this.hudContainer.add(this.healthBarText);
  }
  
  private toggleTelemetryPanel() {
    this.telemetryVisible = !this.telemetryVisible;
    
    // Toggle visibility of telemetry elements
    Object.values(this.telemetryFields).forEach(field => {
      field.setVisible(this.telemetryVisible);
    });
    
    this.healthBarBg?.setVisible(this.telemetryVisible);
    this.healthBarFill?.setVisible(this.telemetryVisible);
    this.healthBarText?.setVisible(this.telemetryVisible);
    
    // Update toggle button
    this.telemetryToggle?.setText(this.telemetryVisible ? '▼' : '▶');
    
    // Animate panel height
    const targetAlpha = this.telemetryVisible ? 0.85 : 0.3;
    this.tweens.add({
      targets: this.hudContainer.list.find(item => item.type === 'Graphics'),
      alpha: targetAlpha,
      duration: 200,
      ease: 'Power2'
    });
  }
  
  private initializeSoundtrack() {
    try {
      // Check if audio system is available
      if (!this.sound.context) {
        console.warn('Audio context not available');
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

  private createLuminousBirdSprite(x: number, y: number): Phaser.GameObjects.Container {
    // Create a container for the bird sprite with glow effect
    const birdContainer = this.add.container(x, y);
    
    // Create glow effect (larger, semi-transparent background)
    const glow = this.add.graphics();
    glow.fillStyle(0xffffff, 0.3);
    glow.fillCircle(0, 0, 8); // Glow radius
    glow.setBlendMode(Phaser.BlendModes.ADD); // Additive blending for glow
    
    // Create bird shape (procedural graphics - reverted as requested)
    const bird = this.add.graphics();
    bird.lineStyle(1, 0xffffff, 0.8);
    bird.fillStyle(0xffffff, 0.9);
    
    // Draw a simple bird glyph shape (triangle with wings)
    bird.beginPath();
    bird.moveTo(-3, 2);  // Left wing tip
    bird.lineTo(0, -4);  // Head/beak
    bird.lineTo(3, 2);   // Right wing tip  
    bird.lineTo(0, 1);   // Body center
    bird.closePath();
    bird.fillPath();
    bird.strokePath();
    
    // NEW: Gender indicator (small symbol above bird)
    const genderSymbol = this.add.text(0, -8, '', {
      fontSize: '8px',
      color: '#ffffff',
      align: 'center'
    });
    genderSymbol.setOrigin(0.5);
    genderSymbol.setAlpha(0.8);
    
    // NEW: Generation indicator (small text below bird) 
    const generationText = this.add.text(0, 6, '', {
      fontSize: '6px',
      color: '#ffffff',
      align: 'center'
    });
    generationText.setOrigin(0.5);
    generationText.setAlpha(0.7);
    
    // NEW: Leadership crown (only shown for high-leadership birds)
    const leadershipCrown = this.add.graphics();
    leadershipCrown.setVisible(false);
    
    // Add subtle pulsing animation
    this.tweens.add({
      targets: glow,
      alpha: 0.2,
      duration: 1000 + Math.random() * 500,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut'
    });
    
    // Add all components to container
    // Order: glow (0), bird (1), genderSymbol (2), generationText (3), leadershipCrown (4)
    birdContainer.add([glow, bird, genderSymbol, generationText, leadershipCrown]);
    
    birdContainer.setDepth(LAYER_DEPTHS.AGENTS);
    
    return birdContainer;
  }

  private updateBirdSpriteColor(container: Phaser.GameObjects.Container, color: number) {
    // Get the bird graphics (second child, first is glow)
    const bird = container.list[1] as Phaser.GameObjects.Graphics;
    const glow = container.list[0] as Phaser.GameObjects.Graphics;
    
    if (bird && glow) {
      // Clear and redraw bird with new color
      bird.clear();
      bird.lineStyle(1, color, 0.8);
      bird.fillStyle(color, 0.9);
      
      // Draw bird shape
      bird.beginPath();
      bird.moveTo(-3, 2);
      bird.lineTo(0, -4);
      bird.lineTo(3, 2);
      bird.lineTo(0, 1);
      bird.closePath();
      bird.fillPath();
      bird.strokePath();
      
      // Update glow color
      glow.clear();
      glow.fillStyle(color, 0.3);
      glow.fillCircle(0, 0, 8);
      glow.setBlendMode(Phaser.BlendModes.ADD);
    }
  }

  private updateBirdGeneticDisplay(container: Phaser.GameObjects.Container, agent: Agent) {
    // Get the genetic display components
    const genderSymbol = container.list[2] as Phaser.GameObjects.Text;
    const generationText = container.list[3] as Phaser.GameObjects.Text;
    const leadershipCrown = container.list[4] as Phaser.GameObjects.Graphics;
    
    if (genderSymbol && agent.gender) {
      // Display gender symbol with color coding
      const symbol = agent.gender === 'male' ? '♂' : '♀';
      const genderColor = agent.gender === 'male' ? '#4488ff' : '#ff4488';
      
      genderSymbol.setText(symbol);
      genderSymbol.setColor(genderColor);
    }
    
    if (generationText && agent.generation !== undefined) {
      // Display generation (G0, G1, G2, etc.)
      generationText.setText(`G${agent.generation}`);
      
      // Color code by generation (newer = brighter)
      const generationAlpha = 0.5 + (agent.generation * 0.1);
      generationText.setAlpha(Math.min(1.0, generationAlpha));
    }
    
    if (leadershipCrown && agent.genetics?.leadership) {
      // Show leadership crown for high-leadership birds
      const showCrown = agent.genetics.leadership > 0.7;
      leadershipCrown.setVisible(showCrown);
      
      if (showCrown) {
        leadershipCrown.clear();
        leadershipCrown.lineStyle(1, 0xffdd00, 0.9);
        leadershipCrown.fillStyle(0xffdd00, 0.8);
        
        // Draw simple crown shape above bird
        leadershipCrown.beginPath();
        leadershipCrown.moveTo(-4, -12);
        leadershipCrown.lineTo(-2, -16);
        leadershipCrown.lineTo(0, -14);
        leadershipCrown.lineTo(2, -16);
        leadershipCrown.lineTo(4, -12);
        leadershipCrown.lineTo(-4, -12);
        leadershipCrown.closePath();
        leadershipCrown.fillPath();
        leadershipCrown.strokePath();
      }
    }
  }

  private blendColors(color1: number, color2: number, factor: number): number {
    // Extract RGB components
    const r1 = (color1 >> 16) & 0xff;
    const g1 = (color1 >> 8) & 0xff;
    const b1 = color1 & 0xff;
    
    const r2 = (color2 >> 16) & 0xff;
    const g2 = (color2 >> 8) & 0xff;
    const b2 = color2 & 0xff;
    
    // Blend colors
    const r = Math.round(r1 * (1 - factor) + r2 * factor);
    const g = Math.round(g1 * (1 - factor) + g2 * factor);
    const b = Math.round(b1 * (1 - factor) + b2 * factor);
    
    // Combine back to single color
    return (r << 16) | (g << 8) | b;
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

  // Public method for UIScene coordination
  public setSelectedBeaconType(type: string | null) {
    this.selectedBeaconType = type;
    
    // Update cursor
    if (type) {
      this.input.setDefaultCursor('crosshair');
      console.log('GameScene beacon selection updated:', type);
    } else {
      this.input.setDefaultCursor('default');
      console.log('GameScene beacon selection cleared');
    }
  }

  public getSelectedBeaconType(): string | null {
    return this.selectedBeaconType;
  }

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
        { key: 'beacon_sensitivity', name: 'Beacon Sensitivity', color: '#ffaa44' },
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
      this.birdInspectionPanel = undefined;
      this.inspectedBirdId = undefined;
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
}