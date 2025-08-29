import { Game, Types } from 'phaser';
import { WebSocketClient } from './WebSocketClient';
import { GameScene } from './GameScene';
import { UIScene } from './UIScene';
import { MenuScene } from './MenuScene';

class MurmurationGame {
  private game: Game;
  private wsClient: WebSocketClient;
  private menuScene: MenuScene;
  private gameScene: GameScene;
  private uiScene: UIScene;
  private levelStartRequested = false;

  constructor() {
    // Initialize WebSocket client
    this.wsClient = new WebSocketClient();
    
    // Initialize Phaser scenes
    this.menuScene = new MenuScene();
    this.gameScene = new GameScene();
    this.uiScene = new UIScene();
    
    // Set WebSocketClient in GameScene
    this.gameScene.setWebSocketClient(this.wsClient);

    // Calculate optimal dimensions for current screen
    this.calculateGameDimensions(); // Call but don't store result

    const gameConfig: Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width: 1280,
      height: 720,
      parent: 'game-container',
      backgroundColor: '#87CEEB',
      scale: {
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH,
        width: 1280,
        height: 720
      },
      physics: {
        default: 'arcade',
        arcade: {
          debug: false
        }
      },
      scene: [this.menuScene, this.gameScene, this.uiScene]
    };

    this.game = new Game(gameConfig);
    
    // Set up resize handling for responsive design
    this.setupResizeHandling();
    
    // Wait for game to be ready before setting up scene event handlers
    this.game.events.once('ready', () => {
      // Start with MenuScene first
      this.game.scene.start('MenuScene');
      
      this.setupEventHandlers();
      this.connectToServer();
    });
  }

  private calculateGameDimensions() {
    // Get available screen space (accounting for browser UI)
    const availableWidth = window.innerWidth;
    const availableHeight = window.innerHeight;
    
    // Target aspect ratio (16:9 to match common displays and game world 2000x1200 ≈ 1.67:1)
    const targetAspect = 16 / 9;
    
    // Calculate dimensions that fit within available space while maintaining aspect ratio
    let width = availableWidth;
    let height = availableWidth / targetAspect;
    
    // If height exceeds available space, constrain by height instead
    if (height > availableHeight) {
      height = availableHeight;
      width = availableHeight * targetAspect;
    }
    
    // Ensure minimum viable size
    const minWidth = 800;
    const minHeight = 450;
    
    width = Math.max(width, minWidth);
    height = Math.max(height, minHeight);
    
    // Set reasonable maximums to prevent performance issues
    const maxWidth = Math.min(availableWidth, 2560); // 2K max width
    const maxHeight = Math.min(availableHeight, 1440); // 2K max height
    
    return {
      width: Math.round(width),
      height: Math.round(height),
      maxWidth: Math.round(maxWidth),
      maxHeight: Math.round(maxHeight)
    };
  }

  private setupResizeHandling() {
    // Handle window resize events
    const handleResize = () => {
      const dimensions = this.calculateGameDimensions();
      
      if (this.game && this.game.scale) {
        // Update game scale with new dimensions
        this.game.scale.resize(dimensions.width, dimensions.height);
      }
    };

    // Debounce resize events to prevent excessive updates
    let resizeTimeout: number | null = null;
    window.addEventListener('resize', () => {
      if (resizeTimeout) {
        clearTimeout(resizeTimeout);
      }
      resizeTimeout = window.setTimeout(handleResize, 150);
    });
  }

  private toggleFullscreen() {
    if (this.game && this.game.scale) {
      if (this.game.scale.isFullscreen) {
        this.game.scale.stopFullscreen();
      } else {
        this.game.scale.startFullscreen();
      }
    }
  }

  private setupEventHandlers() {
    // Handle WebSocket messages
    this.wsClient.onMessage((data) => {
      if (data.type === 'state_update') {
        // Update both scenes with game state
        this.gameScene.updateGameState(data.data);
        this.uiScene.updateGameData(data.data);
      } else if (data.type === 'level_loaded') {
        console.log('📋 Level loaded event received:', data);
        // Only show level panel if this is the initial connection, not after user clicked "START LEVEL"
        // We can detect this by checking if the game is already paused or if this is a fresh connection
        if (!this.levelStartRequested) {
          const levelNumber = this.extractLevelNumber(data.level || 'Level 1');
          const males = data.males || 50;
          const females = data.females || 50;
          const legName = data.leg_name || 'Migration Leg A-B';
          console.log('📋 Showing level panel:', { levelNumber, males, females, legName });
          this.uiScene.showLevelPanel(levelNumber, males, females, legName);
          this.gameScene.hideBirdInspection();
          // Pause the game initially
          this.wsClient.pauseGame();
        } else {
          console.log('📋 Level loaded after START button clicked - not showing panel again');
          this.levelStartRequested = false; // Reset flag
        }
      } else if (data.type === 'level_completed') {
        console.log('✅ Migration leg completed:', data.data);
        this.uiScene.showMigrationResultsPanel(data.data);
      } else if (data.type === 'level_failed') {
        console.log('💀 Level failed:', data.data);
        // Show failure panel with option to retry
        this.uiScene.showFailurePanel(data.data);
        this.gameScene.hideBirdInspection();
      } else if (data.type === 'error') {
        console.error('Server error:', data.message);
      } else if (data.type === 'migration_continued') {
        console.log('🔄 Migration continued to next leg:', data.data);
        const survivors = data.data.survivors;
        const males = Math.floor(survivors / 2);
        const females = survivors - males;
        // Show level panel for new leg
        this.uiScene.showLevelPanel(data.data.current_leg, males, females, data.data.level_name);  // Adjust population based on survivors later
        // Start planning phase for new leg
        this.gameScene.startPlanningPhase();
      }
    });

    // Handle connection status
    console.log('🔌 Setting up connection change handler');
    this.wsClient.onConnectionChange((connected) => {
      console.log(`🔌 Connection status changed: ${connected}`);
      this.gameScene.setConnectionStatus(connected);
      
      if (connected) {
        // When connected, show the level panel immediately
        // The server might auto-load a level, but we'll pause it and wait for user input
        setTimeout(() => {
          console.log('📋 Showing level panel on connection');
          this.uiScene.showLevelPanel(1, 50, 50, 'Breeding Grounds to Coastal Wetlands');
        }, 1000); // Give server time to auto-load if it does
      }
    });

    // Handle beacon placement - now coordinated through UIScene
    this.uiScene.events.on('beaconSelected', (_data: { type: string }) => {
      // Update GameScene's selected beacon type
      // Beacon selection removed - using path-based system
    });

    this.uiScene.events.on('beaconCleared', () => {
      // Clear GameScene's beacon selection
      // Beacon clearing removed - using path-based system
    });

    // Handle level panel events
    this.uiScene.events.on('startLevel', () => {
      console.log('🎮 Level start requested');
      // Set flag to prevent level panel from showing again
      this.levelStartRequested = true;
      
      // Remove this line to keep paused until end of planning
      // this.wsClient.resumeGame();
      
      // NEW: Start planning phase for path drawing
      this.gameScene.startPlanningPhase();
    });

    // Handle continue to next leg events  
    this.uiScene.events.on('continueToNextLeg', () => {
      console.log('🎮 Continue to next migration leg requested');
      // Don't set the flag here - we want to see the level panel for the next leg
      // this.levelStartRequested = true;  // REMOVED - we want to see level panel
      // Continue to next migration leg
      this.wsClient.continueMigration();
    });

    // Handle game events from GameScene
    this.gameScene.events.on('placeBeacon', (data: { type: string, x: number, y: number }) => {
      console.log('🎮 Main received placeBeacon event:', data);
      this.wsClient.placeBeacon(data.type, data.x, data.y);
    });

    // Handle path submission from GameScene
    this.gameScene.events.on('pathSubmitted', (data: { path: Array<{x: number, y: number}> }) => {
      console.log('🛤️ Main received pathSubmitted event:', data);
      this.wsClient.sendPath(data.path);
    });

    this.gameScene.events.on('togglePause', () => {
      // Simple pause/resume toggle
      this.wsClient.send({ type: 'pause' });
    });

    this.gameScene.events.on('loadLevel', (levelIndex: number) => {
      this.wsClient.loadLevel(levelIndex);
    });
    
    // Handle loadFirstLevel event from MenuScene
    this.gameScene.events.on('loadFirstLevel', () => {
      console.log('🎮 Loading first level after Start Game clicked...');
      // Give scenes a moment to fully initialize
      setTimeout(() => {
        this.wsClient.loadLevel(0);
      }, 500);
    });

    // Add keyboard shortcuts
    document.addEventListener('keydown', (event) => {
      switch (event.key) {
        // Removed manual level switching - levels progress automatically
        case 'p':
          this.wsClient.pauseGame();
          break;
        case 'r':
          this.wsClient.resumeGame();
          break;
        case '-':
          this.wsClient.setSpeed(0.5);
          break;
        case '=':
          this.wsClient.setSpeed(2.0);
          break;
        case 'e':
          this.wsClient.activatePulse();
          break;
        case 'f':
        case 'F':
          this.toggleFullscreen();
          break;
        case 'c':
        case 'C':
          this.gameScene.cycleCameraMode();
          break;
        case 'v':
        case 'V':
          this.gameScene.frameAllBirds();
          break;
      }
    });

    this.uiScene.events.on('continueMigration', () => {
      console.log('🔄 Continuing to next migration leg');
      this.wsClient.send({ type: 'continue_migration' });
      // Start planning for next leg
      this.gameScene.startPlanningPhase();
    });
  }

  private extractLevelNumber(levelString: string): number {
    const match = levelString.match(/\d+/);
    return match ? parseInt(match[0]) : 1;
  }

  private async connectToServer() {
    try {
      await this.wsClient.connect();
      console.log('Connected to Murmuration server');
    } catch (error) {
      console.error('Failed to connect to server:', error);
    }
  }
}

// Initialize the game
function initializeGame(): void {
  console.log('Initializing Murmuration game...');
  
  // Create game container
  let gameContainer = document.getElementById('game-container');
  if (!gameContainer) {
    gameContainer = document.createElement('div');
    gameContainer.id = 'game-container';
    gameContainer.style.width = '100vw';
    gameContainer.style.height = '100vh';
    gameContainer.style.display = 'flex';
    gameContainer.style.justifyContent = 'center';
    gameContainer.style.alignItems = 'center';
    gameContainer.style.background = '#1a1a2e';
    gameContainer.style.overflow = 'hidden'; // Prevent scrollbars
    gameContainer.style.position = 'relative';
    document.body.appendChild(gameContainer);
  }

  // Clean UI - controls are now integrated into the game interface

  // Start the game
  new MurmurationGame();
}

// Start the game when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeGame);
} else {
  initializeGame();
}

export {};