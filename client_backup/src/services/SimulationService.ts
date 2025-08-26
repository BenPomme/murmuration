/**
 * Simulation service for managing game state and communication with Python backend
 * Provides a clean interface between UI components and WebSocket connection
 */

import type { 
  GameState, 
  GameSettings, 
  Level, 
  OutgoingMessage, 
  IncomingMessage,
  Vector2D,
  GameSpeed,
  OverlayType,
  BEACON_TYPES,
  PULSE_TYPES
} from '../types/game';

export interface SimulationServiceConfig {
  readonly websocketUrl?: string;
  readonly ticksPerSecond?: number;
}

export interface SimulationServiceCallbacks {
  readonly onGameStateUpdate?: (state: GameState) => void;
  readonly onLevelLoad?: (level: Level) => void;
  readonly onError?: (error: string) => void;
  readonly onConnectionChange?: (connected: boolean) => void;
}

export class SimulationService {
  private websocket: WebSocket | null = null;
  private currentGameState: GameState | null = null;
  private currentLevel: Level | null = null;
  private gameSettings: GameSettings;
  private callbacks: SimulationServiceCallbacks;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private readonly config: Required<SimulationServiceConfig>;

  constructor(
    config: SimulationServiceConfig = {},
    callbacks: SimulationServiceCallbacks = {}
  ) {
    this.config = {
      websocketUrl: 'ws://localhost:8765',
      ticksPerSecond: 60,
      ...config
    };

    this.callbacks = callbacks;
    this.gameSettings = {
      overlays: [],
      speed: 1,
      showMinimap: true,
      accessibilityMode: false,
      reducedMotion: false,
      highContrast: false
    };
  }

  // Connection management
  public connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.websocket?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      try {
        this.websocket = new WebSocket(this.config.websocketUrl);

        this.websocket.onopen = () => {
          this.reconnectAttempts = 0;
          this.callbacks.onConnectionChange?.(true);
          resolve();
        };

        this.websocket.onmessage = (event) => {
          this.handleMessage(event);
        };

        this.websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.callbacks.onError?.('WebSocket connection error');
          reject(new Error('WebSocket connection failed'));
        };

        this.websocket.onclose = () => {
          this.callbacks.onConnectionChange?.(false);
          this.handleDisconnection();
        };

      } catch (error) {
        this.callbacks.onError?.('Failed to create WebSocket connection');
        reject(error);
      }
    });
  }

  public disconnect(): void {
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent reconnection
  }

  private handleDisconnection(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * this.reconnectAttempts;
      
      setTimeout(() => {
        this.connect().catch((error) => {
          console.error('Reconnection failed:', error);
        });
      }, delay);
    } else {
      this.callbacks.onError?.('Connection lost. Max reconnection attempts exceeded.');
    }
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message = JSON.parse(event.data) as IncomingMessage;

      switch (message.type) {
        case 'game_state':
          this.currentGameState = message.payload;
          this.callbacks.onGameStateUpdate?.(message.payload);
          break;

        case 'level':
          this.currentLevel = message.payload;
          this.callbacks.onLevelLoad?.(message.payload);
          break;

        case 'error':
          this.callbacks.onError?.(message.payload.message);
          break;

        default:
          console.warn('Unknown message type:', message);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
      this.callbacks.onError?.('Failed to parse server message');
    }
  }

  private sendMessage(message: OutgoingMessage): void {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      this.callbacks.onError?.('Cannot send command - not connected to simulation');
      return;
    }

    try {
      this.websocket.send(JSON.stringify(message));
    } catch (error) {
      console.error('Failed to send message:', error);
      this.callbacks.onError?.('Failed to send command to simulation');
    }
  }

  // Game state accessors
  public getGameState(): GameState | null {
    return this.currentGameState;
  }

  public getLevel(): Level | null {
    return this.currentLevel;
  }

  public getGameSettings(): GameSettings {
    return this.gameSettings;
  }

  // Beacon management
  public placeBeacon(beaconTypeId: string, position: Vector2D): void {
    // Validate beacon type
    const beaconType = BEACON_TYPES.find(type => type.id === beaconTypeId);
    if (!beaconType) {
      this.callbacks.onError?.(`Invalid beacon type: ${beaconTypeId}`);
      return;
    }

    // Check budget
    if (this.currentGameState && this.currentGameState.beaconBudgetRemaining < beaconType.cost) {
      this.callbacks.onError?.('Insufficient beacon budget');
      return;
    }

    this.sendMessage({
      type: 'place_beacon',
      beaconTypeId,
      position
    });
  }

  public removeBeacon(beaconId: string): void {
    if (!this.currentGameState?.beacons.find(beacon => beacon.id === beaconId)) {
      this.callbacks.onError?.(`Beacon not found: ${beaconId}`);
      return;
    }

    this.sendMessage({
      type: 'remove_beacon',
      beaconId
    });
  }

  // Pulse management
  public activatePulse(pulseTypeId: string, position: Vector2D): void {
    const pulseType = PULSE_TYPES.find(type => type.id === pulseTypeId);
    if (!pulseType) {
      this.callbacks.onError?.(`Invalid pulse type: ${pulseTypeId}`);
      return;
    }

    this.sendMessage({
      type: 'activate_pulse',
      pulseTypeId,
      position
    });
  }

  // Game control
  public setSpeed(speed: GameSpeed): void {
    this.gameSettings = {
      ...this.gameSettings,
      speed
    };

    this.sendMessage({
      type: 'set_speed',
      speed
    });
  }

  public togglePause(): void {
    const newSpeed: GameSpeed = this.gameSettings.speed === 0 ? 1 : 0;
    this.setSpeed(newSpeed);
  }

  // UI settings
  public toggleOverlay(overlayType: OverlayType): void {
    const overlays = this.gameSettings.overlays.includes(overlayType)
      ? this.gameSettings.overlays.filter(type => type !== overlayType)
      : [...this.gameSettings.overlays, overlayType];

    this.gameSettings = {
      ...this.gameSettings,
      overlays
    };
  }

  public setOverlays(overlays: readonly OverlayType[]): void {
    this.gameSettings = {
      ...this.gameSettings,
      overlays
    };
  }

  public toggleMinimap(): void {
    this.gameSettings = {
      ...this.gameSettings,
      showMinimap: !this.gameSettings.showMinimap
    };
  }

  public setAccessibilityMode(enabled: boolean): void {
    this.gameSettings = {
      ...this.gameSettings,
      accessibilityMode: enabled
    };
  }

  public setReducedMotion(enabled: boolean): void {
    this.gameSettings = {
      ...this.gameSettings,
      reducedMotion: enabled
    };
  }

  public setHighContrast(enabled: boolean): void {
    this.gameSettings = {
      ...this.gameSettings,
      highContrast: enabled
    };
  }

  // Utility methods
  public isConnected(): boolean {
    return this.websocket?.readyState === WebSocket.OPEN ?? false;
  }

  public getConnectionState(): string {
    if (!this.websocket) return 'disconnected';
    
    switch (this.websocket.readyState) {
      case WebSocket.CONNECTING: return 'connecting';
      case WebSocket.OPEN: return 'connected';
      case WebSocket.CLOSING: return 'closing';
      case WebSocket.CLOSED: return 'disconnected';
      default: return 'unknown';
    }
  }

  public getAvailableBeaconTypes(): typeof BEACON_TYPES {
    return BEACON_TYPES;
  }

  public getAvailablePulseTypes(): typeof PULSE_TYPES {
    return PULSE_TYPES;
  }

  // Calculate derived metrics
  public getGameProgress(): number {
    if (!this.currentGameState || !this.currentLevel) return 0;
    
    const { gameDay } = this.currentGameState;
    const { timeLimit } = this.currentLevel.targets;
    
    return Math.min(gameDay / timeLimit, 1);
  }

  public getBeaconDecayStrength(beaconId: string): number {
    if (!this.currentGameState) return 0;
    
    const beacon = this.currentGameState.beacons.find(b => b.id === beaconId);
    if (!beacon) return 0;
    
    const ticksElapsed = this.currentGameState.tick - beacon.placedAt;
    const daysElapsed = ticksElapsed / (this.config.ticksPerSecond * 60 * 60 * 24);
    const beaconType = BEACON_TYPES.find(type => type.id === beacon.type.id);
    
    if (!beaconType) return 0;
    
    // Exponential decay: strength = e^(-t/halfLife)
    return Math.exp(-daysElapsed / beaconType.halfLifeDays);
  }

  public canPlaceBeacon(beaconTypeId: string): boolean {
    if (!this.currentGameState) return false;
    
    const beaconType = BEACON_TYPES.find(type => type.id === beaconTypeId);
    if (!beaconType) return false;
    
    return this.currentGameState.beaconBudgetRemaining >= beaconType.cost;
  }

  public canActivatePulse(pulseTypeId: string): boolean {
    if (!this.currentGameState) return false;
    
    const pulseType = PULSE_TYPES.find(type => type.id === pulseTypeId);
    if (!pulseType) return false;
    
    // Check if pulse is on cooldown
    const activePulse = this.currentGameState.activePulses.find(
      pulse => pulse.type.id === pulseTypeId
    );
    
    if (activePulse) {
      const cooldownEndTick = activePulse.expiresAt + (pulseType.cooldownHours * 60 * 60 * this.config.ticksPerSecond);
      return this.currentGameState.tick >= cooldownEndTick;
    }
    
    return true;
  }
}