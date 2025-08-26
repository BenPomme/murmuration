import { Game, Types } from 'phaser';
import { WebSocketClient } from './WebSocketClient';
import { GameScene } from './GameScene';

class MurmurationGame {
  private game: Game;
  private wsClient: WebSocketClient;
  private gameScene: GameScene;

  constructor() {
    // Initialize WebSocket client
    this.wsClient = new WebSocketClient();
    
    // Initialize Phaser game
    this.gameScene = new GameScene();
    
    // Calculate optimal dimensions for current screen
    const dimensions = this.calculateGameDimensions();
    
    const gameConfig: Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width: dimensions.width,
      height: dimensions.height,
      parent: 'game-container',
      backgroundColor: '#87CEEB',
      resolution: window.devicePixelRatio || 1, // High-DPI support
      scale: {
        mode: Phaser.Scale.RESIZE, // Dynamic resize instead of fixed
        autoCenter: Phaser.Scale.CENTER_BOTH,
        width: dimensions.width,
        height: dimensions.height,
        min: {
          width: 800,
          height: 450
        },
        max: {
          width: dimensions.maxWidth,
          height: dimensions.maxHeight
        }
      },
      physics: {
        default: 'arcade',
        arcade: {
          debug: false
        }
      },
      scene: this.gameScene
    };

    this.game = new Game(gameConfig);
    
    // Set up resize handling for responsive design
    this.setupResizeHandling();
    
    // Wait for game to be ready before setting up scene event handlers
    this.game.events.once('ready', () => {
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
      resizeTimeout = setTimeout(handleResize, 150);
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
        this.gameScene.updateGameState(data.data);
      } else if (data.type === 'level_loaded') {
        console.log('Level loaded:', data.level);
      } else if (data.type === 'error') {
        console.error('Server error:', data.message);
      }
    });

    // Handle connection status
    console.log('🔌 Setting up connection change handler');
    this.wsClient.onConnectionChange((connected) => {
      console.log(`🔌 Connection status changed: ${connected}`);
      this.gameScene.setConnectionStatus(connected);
      if (connected) {
        // Auto-load first level when connected
        console.log('🚀 Connected! Auto-loading level 0 in 1 second...');
        setTimeout(() => {
          this.wsClient.loadLevel(0);
        }, 1000);
      }
    });

    // Handle game events from scene
    this.gameScene.events.on('placeBeacon', (data: { type: string, x: number, y: number }) => {
      console.log('🎮 Main received placeBeacon event:', data);
      this.wsClient.placeBeacon(data.type, data.x, data.y);
    });

    this.gameScene.events.on('togglePause', () => {
      // Simple pause/resume toggle
      this.wsClient.send({ type: 'pause' });
    });

    this.gameScene.events.on('loadLevel', (levelIndex: number) => {
      this.wsClient.loadLevel(levelIndex);
    });

    // Add keyboard shortcuts
    document.addEventListener('keydown', (event) => {
      switch (event.key) {
        case '1':
          this.wsClient.loadLevel(0);
          break;
        case '2':
          this.wsClient.loadLevel(1);
          break;
        case '3':
          this.wsClient.loadLevel(2);
          break;
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
      }
    });
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

  // Add UI controls
  const controlsDiv = document.createElement('div');
  controlsDiv.innerHTML = `
    <div style="position: fixed; top: 10px; right: 10px; z-index: 1000; background: rgba(0,0,0,0.8); color: white; padding: 15px; border-radius: 8px; font-family: Arial, sans-serif;">
      <h3 style="margin: 0 0 10px 0; color: #4CAF50;">Murmuration Controls</h3>
      <div style="font-size: 12px; line-height: 1.4;">
        <div><strong>Game:</strong></div>
        <div>1/2/3: Load Level 1/2/3</div>
        <div>P: Pause, R: Resume</div>
        <div>-: Slow (0.5x), =: Fast (2x)</div>
        <div>E: Emergency Pulse</div>
        <div>F: Toggle Fullscreen</div>
        <br>
        <div><strong>Camera:</strong></div>
        <div>Arrow Keys / WASD: Move</div>
        <div>Mouse Wheel: Zoom</div>
        <div>Space: Pause/Resume</div>
        <br>
        <div><strong>Beacons:</strong></div>
        <div>1. Select beacon type from panel</div>
        <div>2. Click in game world to place</div>
        <div>3. Use 'Clear Selection' to deselect</div>
      </div>
    </div>
  `;
  document.body.appendChild(controlsDiv);

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