import Phaser from 'phaser';

export class UIScene extends Phaser.Scene {
  private hudContainer!: Phaser.GameObjects.Container;
  // Beacon system removed - replaced with path drawing
  private telemetryPanel!: Phaser.GameObjects.Container;
  private destinationPanel!: Phaser.GameObjects.Container;
  private controlsPanel!: Phaser.GameObjects.Container;
  private geneticsPanel!: Phaser.GameObjects.Container; // NEW: Genetics statistics panel
  private levelPanel?: Phaser.GameObjects.Container; // NEW: Level start panel
  private planningPanel?: Phaser.GameObjects.Container; // NEW: Path planning panel
  
  // Panel visibility states
  private telemetryVisible = true;
  private controlsVisible = false;
  private geneticsVisible = true; // NEW: Genetics panel visibility
  private isCompletionPanel = false; // Track if level panel is showing completion
  private isPlanningPhase = false; // Track if planning phase is active
  
  // Current game state references
  private gameData: any = {};
  
  // UI Elements
  // Beacon system completely removed - using path drawing instead
  
  constructor() {
    super({ key: 'UIScene' });
  }

  create() {
    // Initialize HUD container that stays fixed to camera
    this.hudContainer = this.add.container(0, 0);
    this.hudContainer.setScrollFactor(0); // Always stay on screen
    
    // Setup responsive scaling
    this.scale.on('resize', this.handleResize, this);
    
    // Create UI components
    this.createDestinationPanel();
    this.createTelemetryPanel();
    this.createGeneticsPanel(); // NEW: Add genetics panel
    // Beacon panel removed - using path drawing system instead
    this.createPlanningPanel(); // NEW: Path planning panel
    this.createControlsPanel();
    this.createLevelPanel(); // NEW: Level start panel
    
    // Setup input handlers
    this.setupInputHandlers();

    // Event listeners for planning phase coordination
    this.events.on('startMigration', () => {
      // Notify GameScene to end planning phase
      this.scene.get('GameScene')?.events.emit('endPlanningPhase');
    });

    this.events.on('showPlanningPhase', () => {
      this.showPlanningPanel();
    });

    this.events.on('hidePlanningPhase', () => {
      this.hidePlanningPanel();
    });
    
    // Initial resize to position elements
    this.handleResize();
  }

  private createDestinationPanel() {
    // REDESIGNED: Thin top bar for destination info
    const panelWidth = 500;
    const panelHeight = 40;
    
    const panel = this.add.container(0, 10);
    
    // Background - more translucent for elegance
    const bg = this.add.graphics();
    bg.fillStyle(0x001133, 0.75);
    bg.lineStyle(1, 0x44aaff, 0.8);
    bg.fillRoundedRect(-panelWidth/2, 0, panelWidth, panelHeight, 8);
    bg.strokeRoundedRect(-panelWidth/2, 0, panelWidth, panelHeight, 8);
    panel.add(bg);
    
    // Title
    const title = this.createCrispText(0, 15, 'DESTINATION', {
      fontSize: '14px',
      color: '#44aaff',
      align: 'center'
    });
    title.setOrigin(0.5, 0);
    panel.add(title);
    
    // Status text (will be updated with game data)
    const status = this.createCrispText(0, 35, 'Distance: --- | Alive: --- | Day: ---', {
      fontSize: '12px',
      color: '#ffffff',
      align: 'center'
    });
    status.setOrigin(0.5, 0);
    panel.add(status);
    panel.setData('statusText', status);
    
    this.destinationPanel = panel;
    this.hudContainer.add(panel);
  }

  private createTelemetryPanel() {
    // REDESIGNED: Narrow left sidebar that doesn't block gameplay
    const panelWidth = 200;
    const panelHeight = 160;
    
    // FORCE positioning to left edge immediately
    const panel = this.add.container(100, 130); // Left edge positioning
    
    // Background - more translucent for elegance
    const bg = this.add.graphics();
    bg.fillStyle(0x001133, 0.75);
    bg.lineStyle(1, 0x44aaff, 0.8);
    bg.fillRoundedRect(0, 0, panelWidth, panelHeight, 8);
    bg.strokeRoundedRect(0, 0, panelWidth, panelHeight, 8);
    panel.add(bg);
    
    // Header with collapse button
    const header = this.add.container(0, 0);
    const headerBg = this.add.graphics();
    headerBg.fillStyle(0x44aaff, 0.2);
    headerBg.fillRoundedRect(0, 0, panelWidth, 30, 8);
    header.add(headerBg);
    
    const title = this.createCrispText(15, 8, 'FLOCK TELEMETRY', {
      fontSize: '14px',
      color: '#44aaff',
      fontStyle: 'bold'
    });
    title.setOrigin(0, 0);
    header.add(title);
    
    const toggleBtn = this.createCrispText(panelWidth - 25, 8, '▼', {
      fontSize: '14px',
      color: '#44aaff'
    });
    toggleBtn.setOrigin(0, 0);
    toggleBtn.setInteractive({ useHandCursor: true });
    toggleBtn.on('pointerdown', () => this.toggleTelemetryPanel());
    header.add(toggleBtn);
    panel.setData('toggleBtn', toggleBtn);
    
    panel.add(header);
    
    // Content area (will hold telemetry data)
    const content = this.add.container(0, 35);
    this.createTelemetryContent(content, panelWidth);
    panel.add(content);
    panel.setData('content', content);
    
    this.telemetryPanel = panel;
    this.hudContainer.add(panel);
  }

  private createTelemetryContent(container: Phaser.GameObjects.Container, panelWidth: number) {
    const metrics = [
      { label: 'Population', key: 'population', color: '#00ff88' },
      { label: 'Cohesion', key: 'cohesion', color: '#44aaff' },
      { label: 'Average Energy', key: 'energy', color: '#ffaa44' },
      { label: 'Stress Level', key: 'stress', color: '#ff4444' }
    ];
    
    metrics.forEach((metric, index) => {
      const y = index * 35 + 10;
      
      // Label
      const label = this.createCrispText(15, y, metric.label + ':', {
        fontSize: '12px',
        color: '#cccccc'
      });
      label.setOrigin(0, 0);
      container.add(label);
      
      // Value text
      const valueText = this.createCrispText(120, y, '---', {
        fontSize: '12px',
        color: metric.color,
        fontStyle: 'bold'
      });
      valueText.setOrigin(0, 0);
      container.add(valueText);
      container.setData(metric.key + 'Text', valueText);
      
      // Progress bar for percentage metrics
      if (['cohesion', 'energy', 'stress'].includes(metric.key)) {
        const barBg = this.add.graphics();
        barBg.fillStyle(0x333333, 0.8);
        barBg.fillRect(15, y + 15, panelWidth - 40, 8);
        container.add(barBg);
        
        const progressBar = this.add.graphics();
        progressBar.fillStyle(parseInt(metric.color.replace('#', '0x')), 0.8);
        container.add(progressBar);
        container.setData(metric.key + 'Bar', progressBar);
      }
    });
  }

  private createGeneticsPanel() {
    // REDESIGNED: Narrow right sidebar for genetics
    const panelWidth = 240;
    const panelHeight = 220;
    
    // FORCE positioning to right edge immediately  
    const panel = this.add.container(1040, 130); // Right edge positioning (assuming 1280 width)
    
    // Background
    const bg = this.add.graphics();
    bg.fillStyle(0x1a0d33, 0.9); // Darker purple for genetics
    bg.lineStyle(2, 0xaa44ff, 0.8);
    bg.fillRoundedRect(0, 0, panelWidth, panelHeight, 8);
    bg.strokeRoundedRect(0, 0, panelWidth, panelHeight, 8);
    panel.add(bg);
    
    // Header with collapse button
    const header = this.add.container(0, 0);
    const headerBg = this.add.graphics();
    headerBg.fillStyle(0xaa44ff, 0.2);
    headerBg.fillRoundedRect(5, 5, panelWidth - 10, 30, 5);
    header.add(headerBg);
    
    const headerText = this.createCrispText(15, 20, 'GENETICS', {
      fontSize: '14px',
      color: '#aa44ff',
      fontStyle: 'bold'
    });
    headerText.setOrigin(0, 0.5);
    header.add(headerText);
    
    // Collapse button
    const collapseBtn = this.createCrispText(panelWidth - 20, 20, '−', {
      fontSize: '18px',
      color: '#aa44ff'
    });
    collapseBtn.setOrigin(0.5);
    collapseBtn.setInteractive({ cursor: 'pointer' });
    collapseBtn.on('pointerdown', () => {
      this.geneticsVisible = !this.geneticsVisible;
      const content = panel.getData('content');
      if (content) {
        content.setVisible(this.geneticsVisible);
        collapseBtn.setText(this.geneticsVisible ? '−' : '+');
      }
    });
    header.add(collapseBtn);
    panel.add(header);
    
    // Main content area
    const content = this.add.container(0, 40);
    
    // Migration info
    const migrationText = this.createCrispText(15, 10, 'Migration 1 - Leg 1/3', {
      fontSize: '12px',
      color: '#ffffff',
      fontStyle: 'bold'
    });
    content.add(migrationText);
    content.setData('migrationText', migrationText);
    
    // Generation info
    const generationText = this.createCrispText(15, 30, 'Generation: 0', {
      fontSize: '12px',
      color: '#ffdd44'
    });
    content.add(generationText);
    content.setData('generationText', generationText);
    
    // Population breakdown
    const populationBreakdown = this.createCrispText(15, 50, '♂ 50  ♀ 50', {
      fontSize: '12px',
      color: '#cccccc'
    });
    content.add(populationBreakdown);
    content.setData('populationBreakdown', populationBreakdown);
    
    // Genetic diversity
    const diversityText = this.createCrispText(15, 70, 'Genetic Diversity: 0.0', {
      fontSize: '11px',
      color: '#88ff88'
    });
    content.add(diversityText);
    content.setData('diversityText', diversityText);
    
    // Average traits header
    const traitsHeader = this.createCrispText(15, 95, 'Average Traits:', {
      fontSize: '11px',
      color: '#aa44ff',
      fontStyle: 'bold'
    });
    content.add(traitsHeader);
    
    // Trait bars
    const traitNames = [
      'Hazard Awareness',
      'Energy Efficiency', 
      'Flock Cohesion',
      // Beacon sensitivity removed - using path-based system
      'Stress Resilience',
      'Leadership'
    ];
    
    const traitKeys = [
      'avg_hazard_awareness',
      'avg_energy_efficiency',
      'avg_flock_cohesion',
      // avg_beacon_sensitivity removed - using path-based system
      'avg_stress_resilience',
      'avg_leadership'
    ];
    
    for (let i = 0; i < traitNames.length; i++) {
      const yPos = 115 + i * 20;
      
      // Trait name
      const traitName = traitNames[i] || `Trait ${i}`;
      const traitLabel = this.createCrispText(15, yPos, traitName, {
        fontSize: '10px',
        color: '#cccccc'
      });
      content.add(traitLabel);
      
      // Trait bar background
      const barBg = this.add.graphics();
      barBg.fillStyle(0x333333, 0.5);
      barBg.fillRect(150, yPos - 6, 120, 12);
      content.add(barBg);
      
      // Trait bar (will be updated with actual values)
      const traitBar = this.add.graphics();
      traitBar.fillStyle(this.getTraitColor(i), 0.8);
      traitBar.fillRect(150, yPos - 6, 60, 12); // Default 50%
      content.add(traitBar);
      content.setData(traitKeys[i] + '_bar', traitBar);
      
      // Trait percentage text
      const traitValue = this.createCrispText(275, yPos, '50%', {
        fontSize: '9px',
        color: '#ffffff'
      });
      traitValue.setOrigin(1, 0);
      content.add(traitValue);
      content.setData(traitKeys[i] + '_text', traitValue);
    }
    
    // Leadership leaderboard
    const leaderHeader = this.createCrispText(15, 240, 'Flock Leaders:', {
      fontSize: '11px',
      color: '#ffdd44',
      fontStyle: 'bold'
    });
    content.add(leaderHeader);
    
    const leaderText = this.createCrispText(15, 255, 'No leaders yet...', {
      fontSize: '9px',
      color: '#cccccc'
    });
    content.add(leaderText);
    content.setData('leaderText', leaderText);
    
    panel.add(content);
    panel.setData('content', content);
    
    this.geneticsPanel = panel;
    this.hudContainer.add(panel);
  }

  private getTraitColor(index: number): number {
    // Different colors for different traits
    const colors = [
      0xff4444, // Hazard Awareness - Red
      0x44ff44, // Energy Efficiency - Green
      0x4444ff, // Flock Cohesion - Blue
      0xffaa44, // Beacon Sensitivity - Orange
      0xaa44ff, // Stress Resilience - Purple
      0xffdd44  // Leadership - Gold
    ];
    return colors[index] || 0xffffff;
  }

  // Beacon system completely removed - replaced with path drawing system

  private createPlanningPanel() {
    const panelWidth = 400;
    const panelHeight = 200;

    const panel = this.add.container(0, 0); // Will be positioned in handleResize
    panel.setVisible(false); // Initially hidden

    // Background
    const bg = this.add.graphics();
    bg.fillStyle(0x002244, 0.9);
    bg.lineStyle(2, 0x44aaff, 0.8);
    bg.fillRoundedRect(-panelWidth/2, -panelHeight/2, panelWidth, panelHeight, 12);
    bg.strokeRoundedRect(-panelWidth/2, -panelHeight/2, panelWidth, panelHeight, 12);
    panel.add(bg);

    // Title
    const title = this.createCrispText(0, -panelHeight/2 + 25, 'PLAN YOUR MIGRATION ROUTE', {
      fontSize: '16px',
      color: '#44aaff',
      fontStyle: 'bold'
    });
    title.setOrigin(0.5, 0.5);
    panel.add(title);

    // Instructions
    const instructions = [
      '• Click and drag to draw your migration path',
      '• Path must start near your flock',
      '• Path must end at the destination',
      '• Right-click to clear and redraw',
      '• Longer paths consume more energy'
    ];

    instructions.forEach((instruction, index) => {
      const yPos = -panelHeight/2 + 50 + index * 18;
      const text = this.createCrispText(-panelWidth/2 + 20, yPos, instruction, {
        fontSize: '12px',
        color: '#ffffff'
      });
      panel.add(text);
    });

    // Start Migration Button - properly centered
    const buttonWidth = 150;
    const buttonHeight = 40;
    const buttonY = panelHeight/2 - buttonHeight - 15; // Button position relative to panel center
    
    // Button background
    const buttonBg = this.add.graphics();
    buttonBg.fillStyle(0x00aa44, 0.8);
    buttonBg.lineStyle(2, 0x44ff88, 0.9);
    buttonBg.fillRoundedRect(-buttonWidth/2, buttonY, buttonWidth, buttonHeight, 8);
    buttonBg.strokeRoundedRect(-buttonWidth/2, buttonY, buttonWidth, buttonHeight, 8);
    panel.add(buttonBg);

    // Button text - centered in button
    const buttonText = this.createCrispText(0, buttonY + buttonHeight/2, 'START MIGRATION', {
      fontSize: '14px',
      color: '#ffffff',
      fontStyle: 'bold'
    });
    buttonText.setOrigin(0.5, 0.5);
    panel.add(buttonText);

    // Make button interactive with correct bounds
    const buttonContainer = this.add.container(0, buttonY + buttonHeight/2);
    buttonContainer.setSize(buttonWidth, buttonHeight);
    buttonContainer.setInteractive({ useHandCursor: true, hitArea: new Phaser.Geom.Rectangle(-buttonWidth/2, -buttonHeight/2, buttonWidth, buttonHeight), hitAreaCallback: Phaser.Geom.Rectangle.Contains });

    buttonContainer.on('pointerover', () => {
      buttonBg.clear();
      buttonBg.fillStyle(0x00cc55, 0.9);
      buttonBg.lineStyle(2, 0x66ff99, 1.0);
      buttonBg.fillRoundedRect(-buttonWidth/2, -buttonHeight/2, buttonWidth, buttonHeight, 8);
      buttonBg.strokeRoundedRect(-buttonWidth/2, -buttonHeight/2, buttonWidth, buttonHeight, 8);
    });

    buttonContainer.on('pointerout', () => {
      buttonBg.clear();
      buttonBg.fillStyle(0x00aa44, 0.8);
      buttonBg.lineStyle(2, 0x44ff88, 0.9);
      buttonBg.fillRoundedRect(-buttonWidth/2, -buttonHeight/2, buttonWidth, buttonHeight, 8);
      buttonBg.strokeRoundedRect(-buttonWidth/2, -buttonHeight/2, buttonWidth, buttonHeight, 8);
    });

    buttonContainer.on('pointerdown', () => {
      this.startMigration();
    });

    panel.add(buttonContainer);
    buttonContainer.setData('bg', buttonBg);
    buttonContainer.setData('text', buttonText);

    this.planningPanel = panel;
    this.hudContainer.add(panel);
  }

  private createControlsPanel() {
    // REDESIGNED: Compact controls at top-right corner
    const panelWidth = 220;
    const panelHeight = 250;
    
    const panel = this.add.container(1060, 400); // Top-right corner
    panel.setVisible(this.controlsVisible);
    
    // Background - more translucent for elegance
    const bg = this.add.graphics();
    bg.fillStyle(0x001133, 0.75);
    bg.lineStyle(1, 0x44aaff, 0.8);
    bg.fillRoundedRect(0, 0, panelWidth, panelHeight, 8);
    bg.strokeRoundedRect(0, 0, panelWidth, panelHeight, 8);
    panel.add(bg);
    
    // Header
    const header = this.add.container(0, 0);
    const headerBg = this.add.graphics();
    headerBg.fillStyle(0x44aaff, 0.2);
    headerBg.fillRoundedRect(0, 0, panelWidth, 30, 8);
    header.add(headerBg);
    
    const title = this.createCrispText(15, 8, 'CONTROLS', {
      fontSize: '14px',
      color: '#44aaff',
      fontStyle: 'bold'
    });
    title.setOrigin(0, 0);
    header.add(title);
    
    panel.add(header);
    
    // Controls content
    const controlsText = `
Camera:
• WASD - Pan camera
• Mouse Wheel - Zoom
• V - Follow flock
• C - Frame all

Path Drawing (Coming Soon):
• Click and drag to draw migration route
• Route must start near flock and end at destination
• Right-click to clear path
• Path length affects energy consumption

Other:
• SPACE - Pause/Resume
• H - Toggle this panel
• ESC - Main menu
    `.trim();
    
    const content = this.createCrispText(15, 45, controlsText, {
      fontSize: '11px',
      color: '#cccccc',
      lineSpacing: 4
    });
    content.setOrigin(0, 0);
    panel.add(content);
    
    // Store reference for toggling
    this.controlsPanel = panel;
    this.hudContainer.add(panel);
  }

  private createCrispText(x: number, y: number, text: string, style: Phaser.Types.GameObjects.Text.TextStyle): Phaser.GameObjects.Text {
    const resolution = window.devicePixelRatio || 1;
    const crispStyle = {
      ...style,
      resolution: resolution,
      padding: { x: 2, y: 2 },
      ...style
    };
    return this.add.text(x, y, text, crispStyle);
  }

  private setupInputHandlers() {
    // Keyboard shortcuts
    const keys = this.input.keyboard!.addKeys('H,ESC') as any;
    
    keys.H.on('down', () => {
      this.toggleControlsPanel();
    });
    
    keys.ESC.on('down', () => {
      // Beacon selection clearing removed - using path drawing
    });
  }

  private handleResize = () => {
    const { width, height } = this.scale.gameSize;
    
    // COMPLETELY NEW LAYOUT: All panels positioned at screen edges, not covering gameplay
    
    // Top bar: Destination info (thin strip across top)
    this.destinationPanel.setPosition(width / 2, 5);
    
    // Bottom bar: Beacon controls (thin strip across bottom)
    // Beacon panel removed - using path drawing system
    // Planning panel (center screen during planning phase)
    if (this.planningPanel) {
      this.planningPanel.setPosition(width / 2, height / 2);
    }

    // Left sidebar: Telemetry (narrow, full height)
    if (this.telemetryPanel) {
      this.telemetryPanel.setPosition(5, 50);
      this.telemetryPanel.setAlpha(0.95);
    }
    
    // Right sidebar: Genetics (narrow, offset from top)  
    if (this.geneticsPanel) {
      this.geneticsPanel.setPosition(width - 285, 50);
      this.geneticsPanel.setAlpha(0.95);
    }
    
    // Controls panel: Top-right corner when visible
    if (this.controlsPanel) {
      this.controlsPanel.setPosition(width - 255, 80);
      this.controlsPanel.setAlpha(0.98);
    }
  };

  // Beacon selection methods removed - using path drawing system

  private toggleTelemetryPanel() {
    this.telemetryVisible = !this.telemetryVisible;
    
    const content = this.telemetryPanel.getData('content');
    const toggleBtn = this.telemetryPanel.getData('toggleBtn');
    
    content.setVisible(this.telemetryVisible);
    toggleBtn.setText(this.telemetryVisible ? '▼' : '▶');
    
    // Adjust panel height
    const bg = this.telemetryPanel.list[0] as Phaser.GameObjects.Graphics;
    bg.clear();
    const panelHeight = this.telemetryVisible ? 200 : 35;
    bg.fillStyle(0x001133, 0.85);
    bg.lineStyle(2, 0x44aaff, 0.7);
    bg.fillRoundedRect(0, 0, 280, panelHeight, 8);
    bg.strokeRoundedRect(0, 0, 280, panelHeight, 8);
  }

  private toggleControlsPanel() {
    this.controlsVisible = !this.controlsVisible;
    if (this.controlsPanel) {
      this.controlsPanel.setVisible(this.controlsVisible);
    }
  }

  private createLevelPanel() {
    // REDESIGNED: Clean center overlay that doesn't interfere with other UI
    const panelWidth = 350;
    const panelHeight = 260;
    
    // Ensure we destroy any existing panel first to prevent overlays
    if (this.levelPanel) {
      this.levelPanel?.destroy();
      this.levelPanel = null as any;
    }
    
    const panel = this.add.container(this.scale.width / 2, this.scale.height / 2);
    
    // Semi-transparent backdrop
    const backdrop = this.add.graphics();
    backdrop.fillStyle(0x000000, 0.7);
    backdrop.fillRect(-this.scale.width / 2, -this.scale.height / 2, this.scale.width, this.scale.height);
    panel.add(backdrop);
    
    // Main panel background
    const bg = this.add.graphics();
    bg.fillStyle(0x1a1a2e, 0.95);
    bg.lineStyle(3, 0x44aaff, 1.0);
    bg.fillRoundedRect(-panelWidth / 2, -panelHeight / 2, panelWidth, panelHeight, 15);
    bg.strokeRoundedRect(-panelWidth / 2, -panelHeight / 2, panelWidth, panelHeight, 15);
    panel.add(bg);
    
    // Level title
    const levelTitle = this.createCrispText(0, -100, 'LEVEL 1', {
      fontSize: '28px',
      color: '#44aaff',
      fontStyle: 'bold'
    });
    levelTitle.setOrigin(0.5);
    panel.add(levelTitle);
    panel.setData('levelTitle', levelTitle);
    
    // Subtitle
    const subtitle = this.createCrispText(0, -65, 'Migration Leg A-B', {
      fontSize: '16px',
      color: '#88ccff',
    });
    subtitle.setOrigin(0.5);
    panel.add(subtitle);
    panel.setData('subtitle', subtitle);
    
    // Population info
    const populationInfo = this.add.container(0, -10);
    
    const popTitle = this.createCrispText(0, -20, 'Your Flock:', {
      fontSize: '18px',
      color: '#ffffff',
      fontStyle: 'bold'
    });
    popTitle.setOrigin(0.5);
    populationInfo.add(popTitle);
    
    const maleCount = this.createCrispText(-80, 10, '50 Males', {
      fontSize: '16px',
      color: '#4488ff'
    });
    maleCount.setOrigin(0.5);
    populationInfo.add(maleCount);
    panel.setData('maleCount', maleCount);
    
    const femaleCount = this.createCrispText(80, 10, '50 Females', {
      fontSize: '16px',
      color: '#ff88aa'
    });
    femaleCount.setOrigin(0.5);
    populationInfo.add(femaleCount);
    panel.setData('femaleCount', femaleCount);
    
    panel.add(populationInfo);
    
    // REDESIGNED: Larger, more reliable start button
    const startButton = this.add.container(0, 70);
    const buttonBg = this.add.graphics();
    buttonBg.fillStyle(0x44aa44, 0.9);
    buttonBg.lineStyle(3, 0x66cc66, 1.0);
    buttonBg.fillRoundedRect(-100, -25, 200, 50, 10);
    buttonBg.strokeRoundedRect(-100, -25, 200, 50, 10);
    startButton.add(buttonBg);
    
    const buttonText = this.createCrispText(0, 0, 'START LEVEL', {
      fontSize: '18px',
      color: '#ffffff',
      fontStyle: 'bold'
    });
    buttonText.setOrigin(0.5);
    startButton.add(buttonText);
    
    // MUCH larger clickable area for reliability
    startButton.setSize(220, 70);
    startButton.setInteractive(new Phaser.Geom.Rectangle(-110, -35, 220, 70), Phaser.Geom.Rectangle.Contains);
    startButton.on('pointerdown', () => {
      // Get current button text to determine action
      const buttonText = startButton.list.find((child: any) => child.type === 'Text');
      const buttonTextStr = buttonText ? (buttonText as any).text : '';
      
      if (buttonTextStr.includes('CONTINUE')) {
        console.log('🎮 CONTINUE TO NEXT LEG button clicked!');
        this.hideLevelPanel();
        this.isCompletionPanel = false;
        console.log('🎮 Emitting continueToNextLeg event...');
        this.events.emit('continueToNextLeg');
      } else if (buttonTextStr.includes('RETRY')) {
        console.log('🔄 RETRY LEVEL button clicked!');
        this.hideLevelPanel();
        console.log('🔄 Emitting startLevel event for retry...');
        this.events.emit('startLevel');
      } else {
        console.log('🎮 START LEVEL button clicked!');
        this.hideLevelPanel();
        console.log('🎮 Emitting startLevel event...');
        this.events.emit('startLevel');
      }
    });
    
    // Add hover effect
    startButton.on('pointerover', () => {
      buttonBg.clear();
      buttonBg.fillStyle(0x55bb55, 0.9);
      buttonBg.lineStyle(2, 0x77dd77, 1.0);
      buttonBg.fillRoundedRect(-80, -20, 160, 40, 8);
      buttonBg.strokeRoundedRect(-80, -20, 160, 40, 8);
    });
    
    startButton.on('pointerout', () => {
      buttonBg.clear();
      buttonBg.fillStyle(0x44aa44, 0.8);
      buttonBg.lineStyle(2, 0x66cc66, 1.0);
      buttonBg.fillRoundedRect(-80, -20, 160, 40, 8);
      buttonBg.strokeRoundedRect(-80, -20, 160, 40, 8);
    });
    
    panel.add(startButton);
    
    this.levelPanel = panel;
    this.levelPanel?.setVisible(false); // Hidden by default
    
    // Ensure hudContainer exists before adding
    if (this.hudContainer) {
      this.hudContainer.add(panel);
    } else {
      console.warn('⚠️ hudContainer not initialized, adding panel directly to scene');
      // Add directly to scene if hudContainer not ready
      this.add.existing(panel);
    }
  }

  private hideLevelPanel() {
    if (this.levelPanel) {
      this.levelPanel?.setVisible(false);
    }
  }

  public showLevelPanel(levelNumber: number, maleCount: number, femaleCount: number, legName: string = '') {
    console.log('🎮 UIScene.showLevelPanel called:', { levelNumber, maleCount, femaleCount, legName });
    
    // If panel was used for completion before, destroy it to reset state
    if (this.isCompletionPanel && this.levelPanel) {
      this.levelPanel?.destroy();
      this.levelPanel = null as any;
      this.isCompletionPanel = false;
    }

    // Create new level panel if it doesn't exist
    if (!this.levelPanel) {
      this.createLevelPanel();
    }

    // Reset completion panel flag
    this.isCompletionPanel = false;

    // Ensure panel exists before proceeding
    if (!this.levelPanel) {
      console.error('Failed to create level panel');
      return;
    }
    
    // Update level title
    const levelTitle = this.levelPanel?.getData('levelTitle');
    if (levelTitle) {
      levelTitle.setText(`MIGRATION LEG ${levelNumber}`);
    }
    
    // Update subtitle
    const subtitle = this.levelPanel?.getData('subtitle');
    if (subtitle && legName) {
      subtitle.setText(legName);
    }
    
    // Update male count
    const maleCountText = this.levelPanel?.getData('maleCount');
    if (maleCountText) {
      maleCountText.setText(`${maleCount} Males`);
    }
    
    // Update female count
    const femaleCountText = this.levelPanel?.getData('femaleCount');
    if (femaleCountText) {
      femaleCountText.setText(`${femaleCount} Females`);
    }
    
    this.levelPanel?.setVisible(true);
  }

  // getBeaconColor method removed - beacon system replaced

  // Public methods for updating UI from game state
  public updateGameData(data: any) {
    this.gameData = { ...this.gameData, ...data };
    
    // Update destination panel
    if (this.destinationPanel) {
      const statusText = this.destinationPanel.getData('statusText');
      if (statusText && data.destination && data.agents) {
        const distance = Math.round(Math.sqrt(
          Math.pow(data.destination[0] - (data.agents[0]?.x || 0), 2) +
          Math.pow(data.destination[1] - (data.agents[0]?.y || 0), 2)
        ));
        const alive = data.population || 0;
        const day = data.season?.day || 0;
        
        statusText.setText(`Distance: ${distance} | Alive: ${alive} | Day: ${day}`);
      }
    }
    
    // Update telemetry panel
    if (this.telemetryPanel && this.telemetryVisible) {
      this.updateTelemetryData(data);
    }
    
    // NEW: Update genetics panel
    if (this.geneticsPanel && this.geneticsVisible) {
      this.updateGeneticsData(data);
    }
    
    // Beacon budget removed - using path-based system
  }

  private updateTelemetryData(data: any) {
    const content = this.telemetryPanel.getData('content');
    if (!content) return;
    
    // Update population
    const populationText = content.getData('populationText');
    if (populationText && data.population !== undefined) {
      populationText.setText(data.population.toString());
    }
    
    // Update cohesion
    const cohesionText = content.getData('cohesionText');
    const cohesionBar = content.getData('cohesionBar');
    if (cohesionText && data.cohesion !== undefined) {
      const cohesion = Math.round(data.cohesion * 100);
      cohesionText.setText(`${cohesion}%`);
      
      if (cohesionBar) {
        cohesionBar.clear();
        cohesionBar.fillStyle(0x44aaff, 0.8);
        cohesionBar.fillRect(15, 0, (245 * data.cohesion), 8);
      }
    }
    
    // Update energy (calculated from agents)
    if (data.agents && data.agents.length > 0) {
      const avgEnergy = data.agents.reduce((sum: number, agent: any) => sum + (agent.energy || 0), 0) / data.agents.length;
      const energyText = content.getData('energyText');
      const energyBar = content.getData('energyBar');
      
      if (energyText) {
        energyText.setText(`${Math.round(avgEnergy)}%`);
      }
      if (energyBar) {
        energyBar.clear();
        energyBar.fillStyle(0xffaa44, 0.8);
        energyBar.fillRect(15, 0, (245 * avgEnergy / 100), 8);
      }
    }
    
    // Update stress (calculated from agents)
    if (data.agents && data.agents.length > 0) {
      const avgStress = data.agents.reduce((sum: number, agent: any) => sum + (agent.stress || 0), 0) / data.agents.length;
      const stressText = content.getData('stressText');
      const stressBar = content.getData('stressBar');
      
      if (stressText) {
        stressText.setText(`${Math.round(avgStress)}%`);
      }
      if (stressBar) {
        stressBar.clear();
        stressBar.fillStyle(0xff4444, 0.8);
        stressBar.fillRect(15, 0, (245 * avgStress / 100), 8);
      }
    }
  }

  private updateGeneticsData(data: any) {
    const content = this.geneticsPanel.getData('content');
    if (!content) return;
    
    // Update migration info
    const migrationText = content.getData('migrationText');
    if (migrationText && data.migration_id && data.current_leg && data.total_legs) {
      migrationText.setText(`Migration ${data.migration_id} - Leg ${data.current_leg}/${data.total_legs}`);
    }
    
    // Update generation
    const generationText = content.getData('generationText');
    if (generationText && data.generation !== undefined) {
      generationText.setText(`Generation: ${data.generation}`);
    }
    
    // Update population breakdown
    const populationBreakdown = content.getData('populationBreakdown');
    if (populationBreakdown && data.males !== undefined && data.females !== undefined) {
      populationBreakdown.setText(`♂ ${data.males}  ♀ ${data.females}`);
    }
    
    // Update genetic diversity
    const diversityText = content.getData('diversityText');
    if (diversityText && data.population_stats?.genetic_diversity !== undefined) {
      const diversity = (data.population_stats.genetic_diversity * 100).toFixed(1);
      diversityText.setText(`Genetic Diversity: ${diversity}%`);
    }
    
    // Update trait bars
    const traitKeys = [
      'avg_hazard_awareness',
      'avg_energy_efficiency',
      'avg_flock_cohesion',
      // avg_beacon_sensitivity removed - using path-based system
      'avg_stress_resilience',
      'avg_leadership'
    ];
    
    if (data.population_stats) {
      traitKeys.forEach((traitKey, index) => {
        const traitBar = content.getData(traitKey + '_bar');
        const traitText = content.getData(traitKey + '_text');
        
        if (traitBar && traitText && data.population_stats[traitKey] !== undefined) {
          const value = data.population_stats[traitKey];
          const percentage = Math.round(value * 100);
          const barWidth = Math.max(2, 120 * value); // Minimum 2px bar
          
          // Update bar
          traitBar.clear();
          traitBar.fillStyle(this.getTraitColor(index), 0.8);
          traitBar.fillRect(150, 115 + index * 20 - 6, barWidth, 12);
          
          // Update text
          traitText.setText(`${percentage}%`);
        }
      });
    }
    
    // Update leadership leaderboard
    const leaderText = content.getData('leaderText');
    if (leaderText && data.leadership_leaders && data.leadership_leaders.length > 0) {
      const leaders = data.leadership_leaders.slice(0, 3); // Top 3
      const leaderStrings = leaders.map((leader: any) => {
        const gender = leader.gender === 'male' ? '♂' : '♀';
        const percentage = Math.round(leader.lead_percentage);
        return `${gender}${leader.id} (${percentage}%)`;
      });
      leaderText.setText(leaderStrings.join('  '));
    } else if (leaderText) {
      leaderText.setText('No leaders yet...');
    }
  }

  // Beacon counter methods removed - using path drawing system

  // Beacon-related methods removed - using path drawing system

  // Path planning methods
  private startMigration() {
    console.log('🚀 Starting migration from planning panel');
    this.events.emit('startMigration');
    this.hidePlanningPanel();
  }

  public showPlanningPanel() {
    console.log('📝 Showing planning panel');
    if (this.isPlanningPhase) return; // Avoid reopening if already active
    this.isPlanningPhase = true;

    if (this.planningPanel) {
      this.planningPanel.setVisible(true);
    }

    // Hide other panels during planning
    if (this.telemetryPanel) this.telemetryPanel.setVisible(false);
    if (this.geneticsPanel) this.geneticsPanel.setVisible(false);
    if (this.controlsPanel) this.controlsPanel.setVisible(false);
  }

  public hidePlanningPanel() {
    console.log('🚀 Hiding planning panel');
    if (!this.isPlanningPhase) return; // Avoid redundant calls
    this.isPlanningPhase = false;

    if (this.planningPanel) {
      this.planningPanel.setVisible(false);
    }

    // Restore other panels
    if (this.telemetryPanel) this.telemetryPanel.setVisible(this.telemetryVisible);
    if (this.geneticsPanel) this.geneticsPanel.setVisible(this.geneticsVisible);
    if (this.controlsPanel) this.controlsPanel.setVisible(this.controlsVisible);
  }

  public showCompletionPanel(completionData: any) {
    console.log('🏆 UIScene.showCompletionPanel called:', completionData);
    
    // Mark this as a completion panel
    this.isCompletionPanel = true;
    
    // Create completion panel similar to level panel
    if (!this.levelPanel) {
      this.createLevelPanel(); // Reuse the level panel structure
    }
    
    // Update the panel content for completion
    const levelTitle = this.levelPanel?.getData('levelTitle');
    if (levelTitle) {
      levelTitle.setText('MIGRATION LEG COMPLETE!');
      levelTitle.setColor('#44ff44'); // Green for success
    }
    
    // Update subtitle with results
    const subtitle = this.levelPanel?.getData('subtitle');
    if (subtitle) {
      const survivalRate = Math.round(completionData.survival_rate * 100);
      subtitle.setText(`${completionData.survivors}/${completionData.total_started} birds survived (${survivalRate}%)`);
    }
    
    // Update population counts (survivors only)
    const maleCount = this.levelPanel?.getData('maleCount');
    const femaleCount = this.levelPanel?.getData('femaleCount');
    if (maleCount && femaleCount) {
      // Estimate gender split of survivors (roughly 50/50)
      const maleSurvivors = Math.floor(completionData.survivors / 2);
      const femaleSurvivors = completionData.survivors - maleSurvivors;
      maleCount.setText(`${maleSurvivors} Males Survived`);
      femaleCount.setText(`${femaleSurvivors} Females Survived`);
    }
    
    // Update button text and style for completion
    const startButton = this.levelPanel?.getData('startButton');
    if (startButton) {
      // Find the text element inside the button
      for (let child of startButton.list) {
        if (child.type === 'Text') {
          (child as any).setText('CONTINUE TO NEXT LEG');
        }
      }
      // Store reference to button text for later
      startButton.setData('buttonText', startButton.list.find((child: any) => child.type === 'Text'));
    }
    
    // Show the panel
    this.levelPanel?.setVisible(true);
  }

  public showFailurePanel(failureData: any) {
    console.log('💀 UIScene.showFailurePanel called:', failureData);
    
    // Mark this as a failure panel (reuse completion panel structure)
    this.isCompletionPanel = false; // This will be a retry, not continue
    
    // Create failure panel similar to completion panel
    if (!this.levelPanel) {
      this.createLevelPanel();
    }
    
    // Update the panel content for failure
    const levelTitle = this.levelPanel?.getData('levelTitle');
    if (levelTitle) {
      levelTitle.setText('MIGRATION FAILED');
      levelTitle.setColor('#ff4444'); // Red for failure
    }
    
    // Update subtitle with failure reason
    const subtitle = this.levelPanel?.getData('subtitle');
    if (subtitle) {
      subtitle.setText(`${failureData.reason} - ${failureData.losses} birds lost`);
    }
    
    // Update population counts (show losses)
    const maleCount = this.levelPanel?.getData('maleCount');
    const femaleCount = this.levelPanel?.getData('femaleCount');
    if (maleCount && femaleCount) {
      maleCount.setText(`${failureData.losses} Birds Lost`);
      femaleCount.setText(`${failureData.survivors} Survivors`);
    }
    
    // Change button to "RETRY LEVEL"
    this.updateButtonForFailure();
    
    // Show the panel
    this.levelPanel?.setVisible(true);
  }

  private updateButtonForFailure() {
    // Find the button and update text to "RETRY LEVEL"
    if (this.levelPanel?.list) {
      for (let child of this.levelPanel.list) {
        if (child.type === 'Container') {
          const container = child as Phaser.GameObjects.Container;
          for (let subChild of container.list) {
            if (subChild.type === 'Text' && ((subChild as any).text.includes('START') || (subChild as any).text.includes('CONTINUE'))) {
              // Found the button text - update it
              (subChild as any).setText('RETRY LEVEL');

                          // Update button background to red for retry
            const buttonBg = container.list[0];
            if (buttonBg && buttonBg.type === 'Graphics') {
                const graphics = buttonBg as Phaser.GameObjects.Graphics;
                graphics.clear();
                graphics.fillStyle(0xaa4444, 0.8);
                graphics.lineStyle(2, 0xcc6666, 1.0);
                graphics.fillRoundedRect(-100, -25, 200, 50, 10);
                graphics.strokeRoundedRect(-100, -25, 200, 50, 10);
              }
              return;
          }
        }
      }
    }
  }

  }

  public showCampaignCompletePanel(data: any) {
    console.log('🎉 UIScene.showCampaignCompletePanel called:', data);

    // Create campaign completion panel
    if (!this.levelPanel) {
      this.createLevelPanel();
    }

    // Mark this as a special completion panel
    this.isCompletionPanel = true;
    
    // Update the panel content for campaign completion
    const levelTitle = this.levelPanel?.getData('levelTitle');
    if (levelTitle) {
      levelTitle.setText('CAMPAIGN COMPLETE!');
      levelTitle.setColor('#ffdd44'); // Gold for ultimate success
    }

    // Update subtitle with final achievement
    const subtitle = this.levelPanel?.getData('subtitle');
    if (subtitle) {
      subtitle.setText(`All migration routes mastered!\n${data.final_survivors} birds reached final destination\nGeneration ${data.final_generation} achieved!`);
    }

    // Update population display
    const maleCount = this.levelPanel?.getData('maleCount');
    const femaleCount = this.levelPanel?.getData('femaleCount');
    if (maleCount && femaleCount) {
      const males = Math.floor(data.final_survivors / 2);
      const females = data.final_survivors - males;
      maleCount.setText(`♂ ${males}`);
      femaleCount.setText(`♀ ${females}`);
    }
    
    // Update button for new campaign or main menu
    const startButton = this.levelPanel?.getData('startButton');
    if (startButton) {
      const buttonText = startButton.getData('buttonText');
      if (buttonText) {
        buttonText.setText('NEW CAMPAIGN');
      }
    }

    // Show the panel
    this.levelPanel?.setVisible(true);
    this.levelPanel?.setAlpha(0);

    // Animate in with celebration
    this.tweens.add({
      targets: this.levelPanel,
      alpha: 1,
      duration: 500,
      ease: 'Power2'
    });
  }

  public showMigrationResultsPanel(data: any) {
    console.log('📊 UIScene.showMigrationResultsPanel called:', data);

    // Create a new panel for results
    const panelWidth = 400;
    const panelHeight = 250;
    const panel = this.add.container(this.scale.width / 2, this.scale.height / 2);

    // Semi-transparent backdrop
    const backdrop = this.add.graphics();
    backdrop.fillStyle(0x000000, 0.7);
    backdrop.fillRect(-this.scale.width / 2, -this.scale.height / 2, this.scale.width, this.scale.height);
    panel.add(backdrop);

    // Main panel background
    const bg = this.add.graphics();
    bg.fillStyle(0x1a1a2e, 0.95);
    bg.lineStyle(3, 0x44aaff, 1.0);
    bg.fillRoundedRect(-panelWidth / 2, -panelHeight / 2, panelWidth, panelHeight, 15);
    bg.strokeRoundedRect(-panelWidth / 2, -panelHeight / 2, panelWidth, panelHeight, 15);
    panel.add(bg);

    // Title
    const title = this.createCrispText(0, -100, 'MIGRATION RESULTS', {
      fontSize: '28px',
      color: '#44aaff',
      fontStyle: 'bold'
    });
    title.setOrigin(0.5);
    panel.add(title);

    // Subtitle
    const subtitle = this.createCrispText(0, -65, `Leg ${data.current_leg}/${data.total_legs} Complete`, {
      fontSize: '16px',
      color: '#88ccff',
    });
    subtitle.setOrigin(0.5);
    panel.add(subtitle);

    // Population info
    const populationInfo = this.add.container(0, -10);

    const popTitle = this.createCrispText(0, -20, 'Your Flock:', {
      fontSize: '18px',
      color: '#ffffff',
      fontStyle: 'bold'
    });
    popTitle.setOrigin(0.5);
    populationInfo.add(popTitle);

    const maleCount = this.createCrispText(-80, 10, `${data.survivors} Males Survived`, {
      fontSize: '16px',
      color: '#4488ff'
    });
    maleCount.setOrigin(0.5);
    populationInfo.add(maleCount);

    const femaleCount = this.createCrispText(80, 10, `${data.survivors} Females Survived`, {
      fontSize: '16px',
      color: '#ff88aa'
    });
    femaleCount.setOrigin(0.5);
    populationInfo.add(femaleCount);

    panel.add(populationInfo);

    // Results summary
    const resultsText = `
Migration Route: ${data.route_length} units
Energy Consumed: ${data.energy_consumed}
Survival Rate: ${Math.round(data.survival_rate * 100)}%
Total Birds Lost: ${data.total_lost}
    `.trim();

    const resultsContent = this.createCrispText(0, 50, resultsText, {
      fontSize: '12px',
      color: '#cccccc',
      lineSpacing: 4
    });
    resultsContent.setOrigin(0.5, 0);
    panel.add(resultsContent);

    // Next button
    const nextButton = this.add.container(0, 100);
    const nextButtonBg = this.add.graphics();
    nextButtonBg.fillStyle(0x44aa44, 0.9);
    nextButtonBg.lineStyle(3, 0x66cc66, 1.0);
    nextButtonBg.fillRoundedRect(-100, -25, 200, 50, 10);
    nextButtonBg.strokeRoundedRect(-100, -25, 200, 50, 10);
    nextButton.add(nextButtonBg);

    const nextButtonText = this.createCrispText(0, 0, 'CONTINUE MIGRATION', {
      fontSize: '14px',
      color: '#ffffff',
      fontStyle: 'bold'
    });
    nextButtonText.setOrigin(0.5, 0.5);
    nextButton.add(nextButtonText);

    // Make button interactive
    nextButton.setSize(220, 70);
    nextButton.setInteractive(new Phaser.Geom.Rectangle(-110, -35, 220, 70), Phaser.Geom.Rectangle.Contains);
    nextButton.on('pointerdown', () => {
      this.hideMigrationResultsPanel();
      this.events.emit('continueMigration');
    });

    // Add hover effect
    nextButton.on('pointerover', () => {
      nextButtonBg.clear();
      nextButtonBg.fillStyle(0x55bb55, 0.9);
      nextButtonBg.lineStyle(2, 0x77dd77, 1.0);
      nextButtonBg.fillRoundedRect(-80, -20, 160, 40, 8);
      nextButtonBg.strokeRoundedRect(-80, -20, 160, 40, 8);
    });

    nextButton.on('pointerout', () => {
      nextButtonBg.clear();
      nextButtonBg.fillStyle(0x44aa44, 0.8);
      nextButtonBg.lineStyle(2, 0x66cc66, 1.0);
      nextButtonBg.fillRoundedRect(-80, -20, 160, 40, 8);
      nextButtonBg.strokeRoundedRect(-80, -20, 160, 40, 8);
    });

    panel.add(nextButton);

    // Ensure hudContainer exists before adding
    if (this.hudContainer) {
      this.hudContainer.add(panel);
    } else {
      console.warn('⚠️ hudContainer not initialized for migration results panel');
      // Add directly to scene if hudContainer not ready
      this.add.existing(panel);
    }
    panel.setVisible(true);
  }

  public hideMigrationResultsPanel() {
    if (this.hudContainer) {
      const panel = this.hudContainer.list.find(p => p.type === 'Container' && p.getData('isMigrationResultsPanel'));
      if (panel) {
        this.hudContainer.remove(panel);
      }
    }
  }
}