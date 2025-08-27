import Phaser from 'phaser';

export class UIScene extends Phaser.Scene {
  private hudContainer!: Phaser.GameObjects.Container;
  private beaconPanel!: Phaser.GameObjects.Container;
  private telemetryPanel!: Phaser.GameObjects.Container;
  private destinationPanel!: Phaser.GameObjects.Container;
  private controlsPanel!: Phaser.GameObjects.Container;
  
  // Panel visibility states
  private telemetryVisible = true;
  private controlsVisible = false;
  
  // Current game state references
  private gameData: any = {};
  
  // UI Elements
  private beaconButtons: Map<string, Phaser.GameObjects.Container> = new Map();
  private selectedBeaconType: string | null = null;
  
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
    this.createBeaconPanel();
    this.createControlsPanel();
    
    // Setup input handlers
    this.setupInputHandlers();
    
    // Initial resize to position elements
    this.handleResize();
  }

  private createDestinationPanel() {
    // Top-center destination marker
    const panelWidth = 300;
    const panelHeight = 60;
    
    const panel = this.add.container(0, 10);
    
    // Background
    const bg = this.add.graphics();
    bg.fillStyle(0x001133, 0.85);
    bg.lineStyle(2, 0x44aaff, 0.7);
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
    // Left panel with collapsible telemetry
    const panelWidth = 280;
    const panelHeight = 200;
    
    const panel = this.add.container(0, 0); // Position set in handleResize
    
    // Background
    const bg = this.add.graphics();
    bg.fillStyle(0x001133, 0.85);
    bg.lineStyle(2, 0x44aaff, 0.7);
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

  private createBeaconPanel() {
    // Bottom beacon panel with large icon buttons
    const panelWidth = 400;
    const panelHeight = 80;
    
    const panel = this.add.container(0, 0); // Will be positioned in handleResize
    
    // Background
    const bg = this.add.graphics();
    bg.fillStyle(0x001133, 0.85);
    bg.lineStyle(2, 0x44aaff, 0.7);
    bg.fillRoundedRect(-panelWidth/2, -panelHeight, panelWidth, panelHeight, 8);
    bg.strokeRoundedRect(-panelWidth/2, -panelHeight, panelWidth, panelHeight, 8);
    panel.add(bg);
    
    // Beacon buttons
    const beacons = [
      { type: 'food', icon: '🍯', color: 0x88ff88, label: 'FOOD' },
      { type: 'shelter', icon: '🏠', color: 0x8888ff, label: 'SHELTER' },  
      { type: 'thermal', icon: '💨', color: 0xff8888, label: 'THERMAL' }
    ];
    
    const buttonWidth = 100;
    const buttonSpacing = 120;
    const startX = -(beacons.length - 1) * buttonSpacing / 2;
    
    beacons.forEach((beacon, index) => {
      const x = startX + index * buttonSpacing;
      const button = this.createBeaconButton(beacon, x, -40, buttonWidth);
      panel.add(button);
      this.beaconButtons.set(beacon.type, button);
    });
    
    // Clear selection button
    const clearBtn = this.createClearButton(panelWidth/2 - 30, -40);
    panel.add(clearBtn);
    
    this.beaconPanel = panel;
    this.hudContainer.add(panel);
  }

  private createBeaconButton(beacon: any, x: number, y: number, width: number): Phaser.GameObjects.Container {
    const button = this.add.container(x, y);
    
    // Background
    const bg = this.add.graphics();
    bg.fillStyle(beacon.color, 0.3);
    bg.lineStyle(2, beacon.color, 0.6);
    bg.fillRoundedRect(-width/2, -25, width, 50, 8);
    bg.strokeRoundedRect(-width/2, -25, width, 50, 8);
    button.add(bg);
    button.setData('bg', bg);
    
    // Icon (larger for better visibility)
    const icon = this.createCrispText(0, -8, beacon.icon, {
      fontSize: '24px'
    });
    icon.setOrigin(0.5, 0.5);
    button.add(icon);
    
    // Label
    const label = this.createCrispText(0, 12, beacon.label, {
      fontSize: '10px',
      color: '#ffffff',
      fontStyle: 'bold'
    });
    label.setOrigin(0.5, 0.5);
    button.add(label);
    
    // Usage counter (will be updated based on game state)
    const counter = this.createCrispText(width/2 - 8, -20, 'x3', {
      fontSize: '10px',
      color: '#ffff00',
      backgroundColor: 'rgba(0,0,0,0.5)',
      padding: { x: 4, y: 2 }
    });
    counter.setOrigin(1, 0);
    button.add(counter);
    button.setData('counter', counter);
    
    // Interaction
    button.setSize(width, 50);
    button.setInteractive({ useHandCursor: true });
    button.on('pointerover', () => {
      bg.clear();
      bg.fillStyle(beacon.color, 0.5);
      bg.lineStyle(2, beacon.color, 0.8);
      bg.fillRoundedRect(-width/2, -25, width, 50, 8);
      bg.strokeRoundedRect(-width/2, -25, width, 50, 8);
    });
    button.on('pointerout', () => {
      if (this.selectedBeaconType !== beacon.type) {
        bg.clear();
        bg.fillStyle(beacon.color, 0.3);
        bg.lineStyle(2, beacon.color, 0.6);
        bg.fillRoundedRect(-width/2, -25, width, 50, 8);
        bg.strokeRoundedRect(-width/2, -25, width, 50, 8);
      }
    });
    button.on('pointerdown', () => {
      this.selectBeaconType(beacon.type);
    });
    
    return button;
  }

  private createClearButton(x: number, y: number): Phaser.GameObjects.Container {
    const button = this.add.container(x, y);
    
    const bg = this.add.graphics();
    bg.fillStyle(0x666666, 0.8);
    bg.lineStyle(2, 0x999999, 0.8);
    bg.fillRoundedRect(-20, -15, 40, 30, 4);
    bg.strokeRoundedRect(-20, -15, 40, 30, 4);
    button.add(bg);
    
    const icon = this.createCrispText(0, 0, '✕', {
      fontSize: '16px',
      color: '#ffffff'
    });
    icon.setOrigin(0.5, 0.5);
    button.add(icon);
    
    button.setSize(40, 30);
    button.setInteractive({ useHandCursor: true });
    button.on('pointerover', () => {
      bg.clear();
      bg.fillStyle(0x888888, 0.9);
      bg.lineStyle(2, 0xbbbbbb, 0.9);
      bg.fillRoundedRect(-20, -15, 40, 30, 4);
      bg.strokeRoundedRect(-20, -15, 40, 30, 4);
    });
    button.on('pointerout', () => {
      bg.clear();
      bg.fillStyle(0x666666, 0.8);
      bg.lineStyle(2, 0x999999, 0.8);
      bg.fillRoundedRect(-20, -15, 40, 30, 4);
      bg.strokeRoundedRect(-20, -15, 40, 30, 4);
    });
    button.on('pointerdown', () => {
      this.clearBeaconSelection();
    });
    
    return button;
  }

  private createControlsPanel() {
    // Right panel with collapsible controls (default collapsed)
    const panelWidth = 250;
    const panelHeight = 300;
    
    const panel = this.add.container(0, 80); // Will be positioned in handleResize
    panel.setVisible(this.controlsVisible);
    
    // Background
    const bg = this.add.graphics();
    bg.fillStyle(0x001133, 0.85);
    bg.lineStyle(2, 0x44aaff, 0.7);
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

Beacons:
• Click beacon type to select
• Click world to place
• Right-click to cancel

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
      this.clearBeaconSelection();
    });
  }

  private handleResize = () => {
    const { width, height } = this.scale.gameSize;
    
    // Position destination panel at top-center
    this.destinationPanel.setPosition(width / 2, 10);
    
    // Position beacon panel at bottom-center
    this.beaconPanel.setPosition(width / 2, height - 20);
    
    // Position telemetry panel at left edge
    if (this.telemetryPanel) {
      this.telemetryPanel.setPosition(10, 80);
    }
    
    // Position controls panel at right edge (avoid overlap with telemetry)
    if (this.controlsPanel) {
      this.controlsPanel.setPosition(width - 260, 80);
    }
  };

  private selectBeaconType(type: string) {
    // Clear previous selection
    this.beaconButtons.forEach((button, buttonType) => {
      if (buttonType !== type) {
        const bg = button.getData('bg');
        const color = this.getBeaconColor(buttonType);
        bg.clear();
        bg.fillStyle(color, 0.3);
        bg.lineStyle(2, color, 0.6);
        bg.fillRoundedRect(-50, -25, 100, 50, 8);
        bg.strokeRoundedRect(-50, -25, 100, 50, 8);
      }
    });
    
    // Highlight selected button
    const selectedButton = this.beaconButtons.get(type);
    if (selectedButton) {
      const bg = selectedButton.getData('bg');
      const color = this.getBeaconColor(type);
      bg.clear();
      bg.fillStyle(color, 0.7);
      bg.lineStyle(3, color, 1.0);
      bg.fillRoundedRect(-50, -25, 100, 50, 8);
      bg.strokeRoundedRect(-50, -25, 100, 50, 8);
    }
    
    this.selectedBeaconType = type;
    
    // Change cursor and emit selection event
    this.input.setDefaultCursor('crosshair');
    this.events.emit('beaconSelected', { type });
  }

  private clearBeaconSelection() {
    this.selectedBeaconType = null;
    this.input.setDefaultCursor('default');
    
    // Reset all button styles
    this.beaconButtons.forEach((button, type) => {
      const bg = button.getData('bg');
      const color = this.getBeaconColor(type);
      bg.clear();
      bg.fillStyle(color, 0.3);
      bg.lineStyle(2, color, 0.6);
      bg.fillRoundedRect(-50, -25, 100, 50, 8);
      bg.strokeRoundedRect(-50, -25, 100, 50, 8);
    });
    
    this.events.emit('beaconCleared');
  }

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

  private getBeaconColor(type: string): number {
    const colors = {
      'food': 0x88ff88,
      'shelter': 0x8888ff,
      'thermal': 0xff8888
    };
    return colors[type as keyof typeof colors] || 0xffffff;
  }

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
    
    // Update beacon counters
    if (data.beacon_budget !== undefined) {
      this.updateBeaconCounters(data.beacon_budget);
    }
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

  private updateBeaconCounters(budget: number) {
    this.beaconButtons.forEach((button) => {
      const counter = button.getData('counter');
      if (counter) {
        counter.setText(`x${budget}`);
        counter.setVisible(budget > 0);
      }
    });
  }

  // Getters for integration with GameScene
  public getSelectedBeaconType(): string | null {
    return this.selectedBeaconType;
  }

  public clearSelection() {
    this.clearBeaconSelection();
  }
}