import { Scene } from 'phaser';
import { audioManager } from './AudioManager';

interface Agent {
  id: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  energy: number;
  stress: number;
  alive: boolean;
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
  private hazardSprites: Map<string, Phaser.GameObjects.Graphics> = new Map();
  private destinationSprite: Phaser.GameObjects.Graphics | null = null;
  
  // UI elements
  private infoText!: Phaser.GameObjects.Text;
  private connectionText!: Phaser.GameObjects.Text;
  private lastConnectionStatus: boolean = false;
  private beaconPanel!: Phaser.GameObjects.Container;
  private selectedBeaconType: string | null = null;
  private beaconButtons: Map<string, Phaser.GameObjects.Container> = new Map();
  
  // Audio
  private soundtrack!: Phaser.Sound.BaseSound;
  private musicEnabled = true;
  
  // Camera controls
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private cameraSpeed = 300;
  private zoomSpeed = 0.1;
  
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
    
    // Only load assets we know exist and work
    try {
      this.load.image('sky_bg', 'assets/sprites/environment/sky_gradient.png');
      this.load.image('clouds', 'assets/sprites/environment/clouds.png');
    } catch (error) {
      console.warn('Environment assets not loaded:', error);
    }
    
    // Skip complex asset loading for now - use procedural graphics
  }

  create() {
    console.log('GameScene created');
    
    // Set world bounds
    this.cameras.main.setBounds(0, 0, this.worldWidth, this.worldHeight);
    
    // Create enhanced background with layers
    this.createBackground();
    
    // Create enhanced UI elements
    this.createInfoPanel();
    
    this.connectionText = this.add.text(15, 55, 'Status: Disconnected', {
      fontSize: '14px',
      color: '#ff0000',
      backgroundColor: 'rgba(0,0,0,0.7)',
      padding: { x: 10, y: 5 },
      borderRadius: 5
    }).setScrollFactor(0).setDepth(100);

    // Update connection status now that text element exists
    this.setConnectionStatus(this.lastConnectionStatus);
    
    // Create controls info
    this.add.text(10, this.cameras.main.height - 120, 
      'Controls:\n' +
      'Arrow Keys: Move camera\n' +
      'Mouse Wheel: Zoom\n' +
      'Click: Place Food beacon\n' +
      'Right Click: Place Shelter beacon\n' +
      'Space: Pause/Resume',
      {
        fontSize: '12px',
        color: '#000000',
        backgroundColor: '#ffffff',
        padding: { x: 8, y: 8 }
      }
    ).setScrollFactor(0).setDepth(100);
    
    // Initialize soundtrack
    this.initializeSoundtrack();
    
    // Create beacon selection panel
    this.createBeaconPanel();
    
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
        camera.setZoom(Math.max(0.3, camera.zoom - this.zoomSpeed));
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
    // Camera movement
    const camera = this.cameras.main;
    const speed = this.cameraSpeed * (1 / camera.zoom);
    
    if (this.cursors.left?.isDown || this.cursors.A?.isDown) {
      camera.scrollX -= speed * 0.016;
    }
    if (this.cursors.right?.isDown || this.cursors.D?.isDown) {
      camera.scrollX += speed * 0.016;
    }
    if (this.cursors.up?.isDown || this.cursors.W?.isDown) {
      camera.scrollY -= speed * 0.016;
    }
    if (this.cursors.down?.isDown || this.cursors.S?.isDown) {
      camera.scrollY += speed * 0.016;
    }
  }

  public updateGameState(newState: GameState) {
    this.gameState = newState;
    this.updateVisuals();
    this.updateUI();
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
    this.updateHazards();
    this.updateDestination();
  }

  private updateAgents() {
    if (!this.gameState?.agents) return;
    
    // Remove agents that no longer exist
    for (const [agentId, sprite] of this.agentSprites.entries()) {
      if (!this.gameState.agents.find(a => a.id.toString() === agentId)) {
        sprite.destroy();
        this.agentSprites.delete(agentId);
      }
    }
    
    // Update or create agent sprites
    for (const agent of this.gameState.agents) {
      const agentId = agent.id.toString();
      let sprite = this.agentSprites.get(agentId);
      
      if (!sprite) {
        // Create luminous bird glyph sprite
        sprite = this.createLuminousBirdSprite(agent.x, agent.y);
        this.agentSprites.set(agentId, sprite);
      }
      
      // Update position
      sprite.setPosition(agent.x, agent.y);
      
      // Update color based on energy and alive status with smooth transitions
      let targetColor;
      if (!agent.alive) {
        targetColor = 0x666666; // Gray for dead
      } else if (agent.energy < 30) {
        targetColor = 0xff4444; // Red for low energy
      } else if (agent.energy < 60) {
        targetColor = 0xffaa44; // Orange for medium energy
      } else {
        targetColor = 0x44ff44; // Green for high energy
      }
      
      // Update bird sprite color with luminous effect
      this.updateBirdSpriteColor(sprite, targetColor);
      
      // Scale based on energy with animation
      const targetScale = agent.alive ? Math.max(0.6, agent.energy / 100 * 1.2) : 0.3;
      
      // Add subtle stress shaking for high stress birds
      if (agent.alive && agent.stress > 70) {
        sprite.x += Math.random() * 2 - 1;
        sprite.y += Math.random() * 2 - 1;
      }
      
      // Smooth scale transitions
      if (Math.abs(sprite.scaleX - targetScale) > 0.1) {
        this.tweens.add({
          targets: sprite,
          scaleX: targetScale,
          scaleY: targetScale,
          duration: 300,
          ease: 'Power2'
        });
      } else {
        sprite.setScale(targetScale);
      }
    }
  }

  private updateBeacons() {
    if (!this.gameState?.beacons) return;
    
    // Remove only SERVER beacons that no longer exist (keep client beacons)
    for (const [beaconId, container] of this.beaconSprites.entries()) {
      // Don't remove client-created beacons
      if (beaconId.startsWith('client_')) {
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
        
        // Create beacon container
        container = this.add.container(x, y);
        
        // Beacon colors and textures
        let color = 0xffffff;
        let textureKey = 'beacon_food';
        switch (beacon.type.toLowerCase()) {
          case 'food': 
            color = 0x00ff00; 
            textureKey = 'beacon_food';
            break;
          case 'shelter': 
            color = 0x0000ff; 
            textureKey = 'beacon_shelter';
            break;
          case 'thermal': 
            color = 0xff0000; 
            textureKey = 'beacon_thermal';
            break;
        }
        
        // Main beacon sprite - simple approach
        let beaconSprite;
        const iconKey = beacon.type === 'food' ? 'icon_food' : 
                       beacon.type === 'shelter' ? 'icon_shelter' : 'icon_thermal';
        
        if (this.textures.exists(iconKey)) {
          beaconSprite = this.add.image(0, 0, iconKey).setScale(0.5);
        } else {
          beaconSprite = this.add.circle(0, 0, 10, color);
        }
        container.add(beaconSprite);
        
        // Simple pulsing animation
        this.tweens.add({
          targets: beaconSprite,
          alpha: 0.6,
          duration: 1500,
          yoyo: true,
          repeat: -1,
          ease: 'Sine.easeInOut'
        });
        
        // Influence radius (semi-transparent)
        const radius = this.add.circle(0, 0, beacon.range || 30, color, 0.1);
        radius.setStrokeStyle(2, color, 0.5);
        container.add(radius);
        
        // Add gentle radius pulsing
        this.tweens.add({
          targets: radius,
          alpha: 0.05,
          duration: 3000,
          yoyo: true,
          repeat: -1,
          ease: 'Sine.easeInOut'
        });
        
        this.beaconSprites.set(beaconId, container);
      }
      
      // Update position
      const x = beacon.x ?? beacon.position?.[0] ?? 0;
      const y = beacon.y ?? beacon.position?.[1] ?? 0;
      container.setPosition(x, y);
    }
  }

  private updateHazards() {
    if (!this.gameState?.hazards) return;
    
    // Remove hazards that no longer exist
    for (const [hazardId, graphics] of this.hazardSprites.entries()) {
      if (!this.gameState.hazards.find(h => h.id === hazardId)) {
        graphics.destroy();
        this.hazardSprites.delete(hazardId);
      }
    }
    
    // Update or create hazard sprites
    for (const hazard of this.gameState.hazards) {
      const hazardId = `${hazard.type}_${hazard.x || hazard.position?.[0] || 0}_${hazard.y || hazard.position?.[1] || 0}`;
      let graphics = this.hazardSprites.get(hazardId);
      
      if (!graphics) {
        graphics = this.add.graphics();
        this.hazardSprites.set(hazardId, graphics);
      }
      
      graphics.clear();
      
      // Get position from either x,y or position array
      const x = hazard.x ?? hazard.position?.[0] ?? 0;
      const y = hazard.y ?? hazard.position?.[1] ?? 0;
      const radius = hazard.radius ?? 50;
      
      // Different visual styles for different hazards
      if (hazard.type.toLowerCase().includes('tornado')) {
        // Red spiral for tornado
        graphics.lineStyle(3, 0xff0000, 0.8);
        graphics.strokeCircle(x, y, radius);
        graphics.lineStyle(2, 0xffaa00, 0.6);
        graphics.strokeCircle(x, y, radius * 0.7);
      } else if (hazard.type.toLowerCase().includes('predator')) {
        // Dark red circle for predator
        graphics.fillStyle(0x990000, 0.5);
        graphics.fillCircle(x, y, radius);
        graphics.lineStyle(2, 0xff0000, 0.8);
        graphics.strokeCircle(x, y, radius);
      } else {
        // Generic hazard
        graphics.fillStyle(0xff4444, 0.3);
        graphics.fillCircle(x, y, radius);
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
    if (!this.gameState || !this.infoText) return;
    
    const aliveCount = this.gameState.agents.filter(a => a.alive).length;
    const totalEnergy = this.gameState.agents.reduce((sum, a) => sum + a.energy, 0);
    
    this.infoText.setText(
      `Level: ${this.gameState.level} | ` +
      `Tick: ${this.gameState.tick} | ` +
      `Time Left: ${this.gameState.time_remaining.toFixed(1)}s | ` +
      `Alive: ${aliveCount}/${this.gameState.population} | ` +
      `Energy: ${totalEnergy.toFixed(0)} | ` +
      `Beacons: ${this.gameState.beacons.length}/${this.gameState.beacon_budget + this.gameState.beacons.length}`
    );
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
      case 'food': color = 0x00ff00; break;
      case 'shelter': color = 0x0000ff; break;
      case 'thermal': color = 0xff0000; break;
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
    // Use camera dimensions instead of hardcoded values
    const cameraHeight = this.cameras.main.height;
    this.beaconPanel = this.add.container(10, cameraHeight - 120);
    this.beaconPanel.setScrollFactor(0).setDepth(100);
    
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
    
    // Beacon types with working texture support
    const beaconTypes = [
      { type: 'food', name: 'Food', color: 0x00ff00, texture: 'icon_food' },
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
      const color = buttonType === 'food' ? 0x00ff00 : buttonType === 'shelter' ? 0x0000ff : 0xff0000;
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
      const color = type === 'food' ? 0x00ff00 : type === 'shelter' ? 0x0000ff : 0xff0000;
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
      const color = buttonType === 'food' ? 0x00ff00 : buttonType === 'shelter' ? 0x0000ff : 0xff0000;
      this.tweens.killTweensOf(bg);
      bg.setFillStyle(color, 0.3);
      bg.setAlpha(1.0);
    });
  }
  
  private createBackground() {
    // Sky gradient background
    if (this.textures.exists('sky_bg')) {
      const sky = this.add.image(this.worldWidth / 2, this.worldHeight / 2, 'sky_bg');
      sky.setDisplaySize(this.worldWidth, this.worldHeight);
      sky.setDepth(-10);
    } else {
      // Fallback to solid color
      const bg = this.add.rectangle(this.worldWidth/2, this.worldHeight/2, this.worldWidth, this.worldHeight, 0x87CEEB);
      bg.setDepth(-10);
    }
    
    // Add animated cloud layers
    if (this.textures.exists('clouds')) {
      for (let i = 0; i < 3; i++) {
        const cloud = this.add.image(Math.random() * this.worldWidth, Math.random() * this.worldHeight * 0.6, 'clouds');
        cloud.setScale(0.5 + Math.random() * 0.5);
        cloud.setAlpha(0.3 + Math.random() * 0.4);
        cloud.setDepth(-5 + i);
        
        // Animate clouds slowly across the sky
        this.tweens.add({
          targets: cloud,
          x: cloud.x + this.worldWidth + 200,
          duration: 60000 + Math.random() * 30000,
          repeat: -1,
          yoyo: false
        });
      }
    }
  }
  
  private createInfoPanel() {
    // Create info panel background
    const infoPanelBg = this.textures.exists('ui_panel')
      ? this.add.image(150, 35, 'ui_panel').setScale(0.6).setOrigin(0.5)
      : this.add.rectangle(150, 35, 280, 50, 0x000000, 0.7);
    
    infoPanelBg.setScrollFactor(0).setDepth(99);
    
    // Info text with enhanced styling
    this.infoText = this.add.text(15, 15, 'Connecting to server...', {
      fontSize: '15px',
      color: '#ffffff',
      fontWeight: 'bold',
      backgroundColor: 'rgba(0,0,0,0.7)',
      padding: { x: 12, y: 8 },
      borderRadius: 8
    }).setScrollFactor(0).setDepth(100);
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
    
    // Create bird shape (luminous glyph)
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
    
    // Add subtle pulsing animation
    this.tweens.add({
      targets: glow,
      alpha: 0.2,
      duration: 1000 + Math.random() * 500,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut'
    });
    
    birdContainer.add([glow, bird]);
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
}