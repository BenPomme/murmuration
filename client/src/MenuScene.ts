import Phaser from 'phaser';

export class MenuScene extends Phaser.Scene {
  private keyArt!: Phaser.GameObjects.Image;
  private startButton!: Phaser.GameObjects.Container;
  private backgroundMusic?: Phaser.Sound.BaseSound;
  
  // Color palette extracted from key art
  private readonly colors = {
    sunset: 0xFFB366,      // Golden sunset
    purple: 0x9B7EC7,      // Soft purple
    pink: 0xE6A8D0,        // Sunset pink  
    blue: 0x7BB3E6,        // Sky blue
    dark: 0x2D1B3D,        // Dark purple
    white: 0xFFFFFF        // Pure white
  };

  constructor() {
    super({ key: 'MenuScene' });
  }

  preload() {
    console.log('MenuScene: Loading assets...');
    
    // Load key art
    this.load.image('keyart', 'assets/Murmurationhomescreen.png');
    
    // Load UI button assets (using the Blue theme to match colors)
    this.load.image('button_normal', 'assets/sprites/ui/Blue/ButtonsBig [Normal]/Button1.png');
    this.load.image('button_hover', 'assets/sprites/ui/Blue/ButtonsBig [Hover]/Button-1.png');
    
    // Audio loading disabled to prevent crashes
    console.log('Audio loading disabled for stability');
  }

  create() {
    console.log('MenuScene: Creating menu...');
    
    const { width, height } = this.scale.gameSize;
    
    // Create gradient background as fallback
    this.createGradientBackground(width, height);
    
    // Add key art as background
    this.keyArt = this.add.image(width / 2, height / 2, 'keyart');
    this.keyArt.setDisplaySize(width, height);
    
    // Add subtle overlay to ensure text readability
    const overlay = this.add.graphics();
    overlay.fillStyle(this.colors.dark, 0.1);
    overlay.fillRect(0, 0, width, height);
    
    // Create animated floating particles
    this.createFloatingParticles();
    
    // Create title and subtitle (they're already in the key art, but we can add interactive elements)
    this.createUI(width, height);
    
    // Music disabled for stability
    console.log('Music disabled for stability');
    
    // Handle window resize
    this.scale.on('resize', this.handleResize, this);
    
    // Add entrance animation
    this.createEntranceAnimation();
  }

  private createGradientBackground(width: number, height: number) {
    // Create simple gradient background matching key art colors
    const bg = this.add.graphics();
    
    // Simple vertical gradient
    bg.fillGradientStyle(this.colors.purple, this.colors.purple, this.colors.sunset, this.colors.sunset, 1);
    bg.fillRect(0, 0, width, height);
  }

  private createFloatingParticles() {
    // Create subtle floating particles to mimic the murmuration in the key art
    try {
      const particles = this.add.particles(0, 0, 'keyart', {
        x: { min: 0, max: this.scale.gameSize.width },
        y: { min: 0, max: this.scale.gameSize.height },
        scale: { start: 0.001, end: 0.003 },
        alpha: { start: 0.3, end: 0 },
        lifespan: 8000,
        frequency: 200,
        tint: this.colors.white,
        blendMode: 'ADD'
      });
      
      particles.setDepth(-1);
    } catch (error) {
      console.warn('Could not create particles:', error);
    }
  }

  private createUI(width: number, height: number) {
    // Create elegant start button with key art colors
    this.startButton = this.add.container(width / 2, height * 0.75);
    
    // Button background with gradient
    const buttonBg = this.add.graphics();
    buttonBg.lineStyle(3, this.colors.white, 0.8);
    buttonBg.fillStyle(this.colors.sunset, 0.9);
    buttonBg.fillRoundedRect(-120, -30, 240, 60, 30);
    buttonBg.strokeRoundedRect(-120, -30, 240, 60, 30);
    
    // Button text
    const buttonText = this.add.text(0, 0, 'START GAME', {
      fontSize: '24px',
      fontFamily: 'Arial Black, sans-serif',
      color: '#FFFFFF',
      stroke: Phaser.Display.Color.ValueToColor(this.colors.dark).rgba,
      strokeThickness: 2
    }).setOrigin(0.5);
    
    this.startButton.add([buttonBg, buttonText]);
    this.startButton.setSize(240, 60);
    this.startButton.setInteractive({ cursor: 'pointer' });
    
    // Button hover effects
    this.startButton.on('pointerover', () => {
      this.tweens.add({
        targets: this.startButton,
        scaleX: 1.05,
        scaleY: 1.05,
        duration: 200,
        ease: 'Back.easeOut'
      });
      
      buttonBg.clear();
      buttonBg.lineStyle(4, this.colors.white, 1);
      buttonBg.fillStyle(this.colors.pink, 1);
      buttonBg.fillRoundedRect(-120, -30, 240, 60, 30);
      buttonBg.strokeRoundedRect(-120, -30, 240, 60, 30);
    });
    
    this.startButton.on('pointerout', () => {
      this.tweens.add({
        targets: this.startButton,
        scaleX: 1,
        scaleY: 1,
        duration: 200,
        ease: 'Back.easeOut'
      });
      
      buttonBg.clear();
      buttonBg.lineStyle(3, this.colors.white, 0.8);
      buttonBg.fillStyle(this.colors.sunset, 0.9);
      buttonBg.fillRoundedRect(-120, -30, 240, 60, 30);
      buttonBg.strokeRoundedRect(-120, -30, 240, 60, 30);
    });
    
    // Button click handler
    this.startButton.on('pointerdown', () => {
      this.startGame();
    });
    
    // Add subtle version text
    this.add.text(width - 20, height - 20, 'v1.0 - Evolution Build', {
      fontSize: '14px',
      fontFamily: 'Arial, sans-serif',
      color: Phaser.Display.Color.ValueToColor(this.colors.white).rgba,
      alpha: 0.7
    }).setOrigin(1, 1);
    
    // Add instructions
    this.add.text(width / 2, height * 0.85, 
      'Guide your flock through dangerous skies using beacons\nPress SPACE or click START to begin', {
      fontSize: '16px',
      fontFamily: 'Arial, sans-serif',
      color: Phaser.Display.Color.ValueToColor(this.colors.white).rgba,
      align: 'center',
      stroke: Phaser.Display.Color.ValueToColor(this.colors.dark).rgba,
      strokeThickness: 1
    }).setOrigin(0.5);
    
    // Keyboard shortcut
    this.input.keyboard?.addKey('SPACE').on('down', () => {
      this.startGame();
    });
  }

  private createEntranceAnimation() {
    // Fade in the key art
    this.keyArt.setAlpha(0);
    this.tweens.add({
      targets: this.keyArt,
      alpha: 1,
      duration: 2000,
      ease: 'Power2'
    });
    
    // Animate button entrance
    this.startButton.setScale(0);
    this.startButton.setAlpha(0);
    
    this.tweens.add({
      targets: this.startButton,
      scaleX: 1,
      scaleY: 1,
      alpha: 1,
      duration: 1000,
      delay: 1500,
      ease: 'Elastic.easeOut'
    });
    
    // Add gentle floating animation to button
    this.tweens.add({
      targets: this.startButton,
      y: this.startButton.y - 10,
      duration: 2000,
      yoyo: true,
      repeat: -1,
      ease: 'Sine.easeInOut'
    });
  }


  private startGame() {
    console.log('Starting game...');
    
    // Add click/press animation
    this.tweens.add({
      targets: this.startButton,
      scaleX: 0.95,
      scaleY: 0.95,
      duration: 100,
      yoyo: true,
      onComplete: () => {
        console.log('Button animation complete, starting scene transition...');
        
        // Skip music fade since audio is disabled
        // Transition to game immediately
        this.cameras.main.fade(1000, 0, 0, 0);
        this.cameras.main.once('camerafadeoutcomplete', () => {
          console.log('Camera fade complete, starting GameScene...');
          this.scene.start('GameScene');
          this.scene.start('UIScene');
          
          // Emit event to load level after scenes are started
          this.scene.get('GameScene').events.emit('loadFirstLevel');
          
          this.scene.stop();
        });
      }
    });
  }

  private handleResize = () => {
    const { width, height } = this.scale.gameSize;
    
    if (this.keyArt) {
      this.keyArt.setPosition(width / 2, height / 2);
      this.keyArt.setDisplaySize(width, height);
    }
    
    if (this.startButton) {
      this.startButton.setPosition(width / 2, height * 0.75);
    }
  };

  destroy() {
    if (this.backgroundMusic) {
      this.backgroundMusic.stop();
      this.backgroundMusic.destroy();
    }
    super.destroy();
  }
}