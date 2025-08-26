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
    
    const gameConfig: Types.Core.GameConfig = {
      type: Phaser.AUTO,
      width: 1280,
      height: 720,
      parent: 'game-container',
      backgroundColor: '#87CEEB',
      scale: {
        mode: Phaser.Scale.SHOW_ALL,
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
      scene: this.gameScene
    };

    this.game = new Game(gameConfig);
    
    // Wait for game to be ready before setting up scene event handlers
    this.game.events.once('ready', () => {
      this.setupEventHandlers();
      this.connectToServer();
    });
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
    gameContainer.style.width = '100%';
    gameContainer.style.height = '100vh';
    gameContainer.style.display = 'flex';
    gameContainer.style.justifyContent = 'center';
    gameContainer.style.alignItems = 'center';
    gameContainer.style.background = '#1a1a2e';
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