import Phaser from 'phaser';

interface BirdData {
  id: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  energy: number;
  stress: number;
  alive: boolean;
  gender?: string | undefined;
}

interface AnimatedBird {
  container: Phaser.GameObjects.Container;
  sprite: Phaser.GameObjects.Sprite | Phaser.GameObjects.Graphics; // Can be either sprite or graphics
  trail: Phaser.GameObjects.Particles.ParticleEmitter;
  lastX: number;
  lastY: number;
  targetX: number;
  targetY: number;
  interpolationFactor: number;
  wingFlapSpeed: number;
  glow: Phaser.GameObjects.Graphics;
  dustEmitter?: Phaser.GameObjects.Particles.ParticleEmitter;
}

export class BirdAnimationSystem {
  private scene: Phaser.Scene;
  private birds: Map<string, AnimatedBird> = new Map();
  private smoothing = 0.2; // Interpolation smoothing factor
  
  constructor(scene: Phaser.Scene) {
    this.scene = scene;
    
    // Create particle texture FIRST before bird animations
    this.createParticleTexture();
    
    // Create bird animation frames
    this.createBirdAnimations();
  }
  
  private createParticleTexture() {
    if (!this.scene.textures.exists('particle')) {
      const particleGraphics = this.scene.make.graphics({ x: 0, y: 0 }, false);
      particleGraphics.fillStyle(0xffffff, 1);
      particleGraphics.fillCircle(8, 8, 8); // Centered in 16x16 texture
      particleGraphics.generateTexture('particle', 16, 16);
      particleGraphics.destroy();
    }
  }
  
  private createBirdAnimations() {
    // Create procedural bird animation frames
    const frameCount = 3;
    const textures: string[] = [];
    
    for (let i = 0; i < frameCount; i++) {
      const textureName = `bird-frame-${i}`;
      
      // Check if texture already exists
      if (!this.scene.textures.exists(textureName)) {
        // Create dynamic texture for this frame - LARGER and more visible
        const graphics = this.scene.make.graphics({ x: 0, y: 0 }, false);
        
        // Draw bird with different wing positions - LARGER SIZE
        graphics.clear();
        graphics.lineStyle(2, 0x000000, 1); // Black outline for visibility
        graphics.fillStyle(0xffffff, 1); // White fill
        
        const wingAngle = (i / frameCount) * Math.PI * 0.5;
        const wingSpread = 12 + Math.sin(wingAngle) * 6; // Bigger wings
        
        // Body - much larger
        graphics.fillCircle(24, 24, 8); // 4x larger
        graphics.strokeCircle(24, 24, 8);
        
        // Wings - larger and more visible
        graphics.beginPath();
        graphics.moveTo(24 - wingSpread, 24 - Math.sin(wingAngle) * 6); // Left wing
        graphics.lineTo(24, 12); // Head
        graphics.lineTo(24 + wingSpread, 24 - Math.sin(wingAngle) * 6); // Right wing
        graphics.lineTo(24, 36); // Tail
        graphics.closePath();
        graphics.fillPath();
        graphics.strokePath();
        
        // Generate texture from graphics - larger texture
        graphics.generateTexture(textureName, 48, 48); // 3x larger texture
        graphics.destroy();
      }
      
      textures.push(textureName);
    }
    
    // Create wing-flap animation
    if (!this.scene.anims.exists('bird-flap')) {
      this.scene.anims.create({
        key: 'bird-flap',
        frames: textures.map((texture) => ({
          key: texture,
          frame: 0
        })),
        frameRate: 8,
        repeat: -1
      });
    }
  }
  
  public createBird(birdData: BirdData): AnimatedBird {
    // Create bird container
    const container = this.scene.add.container(birdData.x, birdData.y);
    container.setDepth(50); // Ensure birds are above background
    console.log(`🐦 Creating bird at position: ${birdData.x}, ${birdData.y}`);
    
    // Create glow effect
    const glow = this.scene.add.graphics();
    glow.fillStyle(0xffffff, 0.2);
    glow.fillCircle(0, 0, 12);
    glow.setBlendMode(Phaser.BlendModes.ADD);
    container.add(glow);
    
    // Create simple circle for bird instead of sprite for now
    const birdGraphics = this.scene.add.graphics();
    birdGraphics.lineStyle(2, 0x000000, 1);
    birdGraphics.fillStyle(0xFFFFFF, 1);
    birdGraphics.fillCircle(0, 0, 10);
    birdGraphics.strokeCircle(0, 0, 10);
    container.add(birdGraphics);
    
    // Store graphics as sprite for now
    const sprite = birdGraphics as any;
    
    // Create particle trail
    const trail = this.scene.add.particles(birdData.x, birdData.y, 'particle', {
      lifespan: { min: 200, max: 400 },
      speed: { min: 5, max: 10 },
      scale: { start: 0.3, end: 0 },
      alpha: { start: 0.5, end: 0 },
      blendMode: Phaser.BlendModes.ADD,
      frequency: 50,
      emitting: false
    });
    trail.setDepth(45); // Behind birds but above background
    
    // Create dust emitter for ground skimming
    const dustEmitter = this.scene.add.particles(birdData.x, birdData.y, 'particle', {
      lifespan: { min: 300, max: 500 },
      speed: { min: 10, max: 20 },
      scale: { start: 0.5, end: 0.1 },
      alpha: { start: 0.3, end: 0 },
      tint: 0x8B7355, // Brown dust color
      frequency: 100,
      emitting: false
    });
    dustEmitter.setDepth(44); // Behind birds and trails
    
    const bird: AnimatedBird = {
      container,
      sprite,
      trail,
      lastX: birdData.x,
      lastY: birdData.y,
      targetX: birdData.x,
      targetY: birdData.y,
      interpolationFactor: 0,
      wingFlapSpeed: 8 + Math.random() * 4, // Vary wing flap speeds
      glow,
      dustEmitter
    };
    
    // Vary animation start time for more natural look
    sprite.anims.setProgress(Math.random());
    
    this.birds.set(birdData.id, bird);
    return bird;
  }
  
  public updateBird(birdData: BirdData) {
    let bird = this.birds.get(birdData.id);
    
    if (!bird) {
      bird = this.createBird(birdData);
      console.log(`🐦 Created bird ${birdData.id} at ${birdData.x}, ${birdData.y}`);
    }
    
    // Store target position for interpolation
    bird.targetX = birdData.x;
    bird.targetY = birdData.y;
    
    // Calculate velocity for rotation
    const dx = birdData.vx;
    const dy = birdData.vy;
    const angle = Math.atan2(dy, dx) + Math.PI / 2;
    bird.sprite.setRotation(angle);
    
    // Update color based on energy
    let tint: number;
    if (!birdData.alive) {
      tint = 0x666666;
      bird.trail.stop();
      bird.dustEmitter?.stop();
    } else {
      // Energy-based color
      if (birdData.energy < 30) {
        tint = 0xff4444; // Red
      } else if (birdData.energy < 60) {
        tint = 0xffaa44; // Orange
      } else {
        tint = 0x44ff44; // Green
      }
      
      // Gender tinting
      if (birdData.gender === 'male') {
        tint = this.blendColors(tint, 0x4444ff, 0.2);
      } else if (birdData.gender === 'female') {
        tint = this.blendColors(tint, 0xff44ff, 0.2);
      }
      
      // Update trail emission based on speed
      const speed = Math.sqrt(dx * dx + dy * dy);
      if (speed > 5) {
        bird.trail.start();
        bird.trail.frequency = Math.max(20, 100 - speed * 2);
      } else {
        bird.trail.stop();
      }
      
      // Dust effect when close to ground
      if (birdData.y > 1000 && speed > 3) {
        bird.dustEmitter?.start();
      } else {
        bird.dustEmitter?.stop();
      }
    }
    
    // For graphics, we need to redraw with new color
    if (bird.sprite instanceof Phaser.GameObjects.Graphics) {
      const graphics = bird.sprite as Phaser.GameObjects.Graphics;
      graphics.clear();
      graphics.lineStyle(2, 0x000000, 1);
      graphics.fillStyle(tint, 1);
      graphics.fillCircle(0, 0, 10);
      graphics.strokeCircle(0, 0, 10);
    } else {
      bird.sprite.setTint(tint);
    }
    bird.glow.clear();
    bird.glow.fillStyle(tint, 0.2);
    bird.glow.fillCircle(0, 0, 12 + birdData.energy / 10);
    
    // Skip animation for now since we're using graphics
    // Adjust wing flap speed based on energy
    const targetFlapSpeed = birdData.alive ? 
      6 + (birdData.energy / 100) * 6 : 0;
    
    // Animation disabled for graphics
    // if (birdData.alive && Math.abs(bird.wingFlapSpeed - targetFlapSpeed) > 0.5) {
    //   bird.wingFlapSpeed = targetFlapSpeed;
    //   bird.sprite.anims.msPerFrame = 1000 / bird.wingFlapSpeed;
    // } else if (!birdData.alive) {
    //   bird.sprite.anims.stop();
    // }
    
    // Scale based on energy - adjusted for larger base size
    const targetScale = birdData.alive ? 
      0.5 + (birdData.energy / 100) * 0.5 : 0.3;
    bird.sprite.setScale(targetScale);
    
    // Stress shaking
    if (birdData.alive && birdData.stress > 70) {
      bird.container.x += (Math.random() - 0.5) * 2;
      bird.container.y += (Math.random() - 0.5) * 2;
    }
  }
  
  public interpolatePositions(_deltaTime: number) {
    for (const bird of this.birds.values()) {
      // Smooth interpolation using exponential smoothing
      const dx = bird.targetX - bird.container.x;
      const dy = bird.targetY - bird.container.y;
      
      // Apply smoothing
      bird.container.x += dx * this.smoothing;
      bird.container.y += dy * this.smoothing;
      
      // Update particle emitter positions
      bird.trail.setX(bird.container.x);
      bird.trail.setY(bird.container.y);
      if (bird.dustEmitter) {
        bird.dustEmitter.setX(bird.container.x);
        bird.dustEmitter.setY(bird.container.y + 5);
      }
      
      // Store last position for velocity calculation
      bird.lastX = bird.container.x;
      bird.lastY = bird.container.y;
    }
  }
  
  public removeBird(id: string) {
    const bird = this.birds.get(id);
    if (bird) {
      bird.trail.stop();
      bird.trail.destroy();
      bird.dustEmitter?.stop();
      bird.dustEmitter?.destroy();
      bird.container.destroy();
      this.birds.delete(id);
    }
  }
  
  public cleanup() {
    for (const bird of this.birds.values()) {
      bird.trail.stop();
      bird.trail.destroy();
      bird.dustEmitter?.stop();
      bird.dustEmitter?.destroy();
      bird.container.destroy();
    }
    this.birds.clear();
  }
  
  private blendColors(color1: number, color2: number, ratio: number): number {
    const r1 = (color1 >> 16) & 0xFF;
    const g1 = (color1 >> 8) & 0xFF;
    const b1 = color1 & 0xFF;
    
    const r2 = (color2 >> 16) & 0xFF;
    const g2 = (color2 >> 8) & 0xFF;
    const b2 = color2 & 0xFF;
    
    const r = Math.round(r1 * (1 - ratio) + r2 * ratio);
    const g = Math.round(g1 * (1 - ratio) + g2 * ratio);
    const b = Math.round(b1 * (1 - ratio) + b2 * ratio);
    
    return (r << 16) | (g << 8) | b;
  }
  
  // Add cohesion-based particle effects
  public updateCohesionEffects(cohesion: number) {
    const highCohesion = cohesion > 0.7;
    
    for (const bird of this.birds.values()) {
      if (highCohesion && bird.sprite.visible) {
        // Add sparkle effect for high cohesion
        bird.trail.particleTint = 0xFFD700; // Golden color
        bird.trail.particleAlpha = 0.6;
      } else {
        bird.trail.particleTint = 0xFFFFFF; // White
        bird.trail.particleAlpha = 0.3;
      }
    }
  }
}