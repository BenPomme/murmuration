export class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000;
  private isConnecting = false;
  private messageQueue: string[] = [];
  
  private onMessageCallback?: (data: any) => void;
  private onConnectionChangeCallback?: (connected: boolean) => void;

  constructor(private url: string = 'ws://localhost:8765') {
    console.log('🔌 WebSocket client initialized, will connect to:', this.url);
  }

  public connect(): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return Promise.resolve();
    }

    this.isConnecting = true;
    console.log('🚀 Attempting WebSocket connection to:', this.url);
    
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);
        
        this.ws.onopen = () => {
          console.log('✅ WebSocket connected to Python server successfully!');
          console.log('📊 Connection state changed: CONNECTED');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          
          // Send queued messages
          while (this.messageQueue.length > 0) {
            const message = this.messageQueue.shift();
            if (message && this.ws?.readyState === WebSocket.OPEN) {
              this.ws.send(message);
            }
          }
          
          console.log('📡 Calling onConnectionChangeCallback with true');
          this.onConnectionChangeCallback?.(true);
          resolve();
        };
        
        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.onMessageCallback?.(data);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };
        
        this.ws.onerror = (error) => {
          console.error('❌ WebSocket connection error:', error);
          console.error('Attempted to connect to:', this.url);
          this.isConnecting = false;
          reject(error);
        };
        
        this.ws.onclose = () => {
          console.log('❌ WebSocket disconnected');
          console.log('📊 Connection state changed: DISCONNECTED');
          this.isConnecting = false;
          console.log('📡 Calling onConnectionChangeCallback with false');
          this.onConnectionChangeCallback?.(false);
          this.attemptReconnect();
        };
        
      } catch (error) {
        this.isConnecting = false;
        reject(error);
      }
    });
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      
      console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      
      setTimeout(() => {
        this.connect().catch(() => {
          // Connection failed, will try again
        });
      }, delay);
    }
  }

  public send(message: any): void {
    const messageStr = JSON.stringify(message);
    console.log('📤 Attempting to send message:', message);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('📤 Sending message via open WebSocket:', messageStr);
      this.ws.send(messageStr);
    } else {
      console.log('❌ WebSocket not open, queueing message. State:', this.ws?.readyState);
      // Queue message for when connection is restored
      this.messageQueue.push(messageStr);
      
      // Attempt to connect if not already connecting
      if (!this.isConnecting) {
        this.connect().catch(() => {
          // Connection failed, message will remain queued
        });
      }
    }
  }

  public onMessage(callback: (data: any) => void): void {
    this.onMessageCallback = callback;
  }

  public onConnectionChange(callback: (connected: boolean) => void): void {
    this.onConnectionChangeCallback = callback;
  }

  public isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  public disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  // Game-specific message helpers matching Python server protocol
  public loadLevel(levelIndex: number): void {
    // Convert level index to level ID format expected by server
    const levelIds = ['W1-1', 'W1-2', 'W2-1', 'W2-2', 'W3-1'];
    const levelId = levelIds[levelIndex] || 'W1-1';
    
    this.send({
      type: 'load_level',
      level: levelId
    });
  }

  public placeBeacon(type: string, x: number, y: number): void {
    console.log('🌐 WebSocketClient.placeBeacon called:', { type, x, y });
    console.log('🌐 WebSocket readyState:', this.ws?.readyState);
    this.send({
      type: 'place_beacon',
      beacon: {
        type: type,
        x: x,
        y: y
      }
    });
    console.log('🌐 place_beacon message sent');
  }

  public removeBeacon(beaconId: string): void {
    this.send({
      type: 'remove_beacon',
      id: beaconId
    });
  }

  public setSpeed(speed: number): void {
    this.send({
      type: 'set_speed',
      speed: speed
    });
  }

  public pauseGame(): void {
    this.send({
      type: 'set_speed',
      speed: 0
    });
  }

  public resumeGame(): void {
    this.send({
      type: 'set_speed',
      speed: 1.0
    });
  }

  public activatePulse(): void {
    this.send({
      type: 'activate_pulse',
      pulse: {
        type: 'emergency',
        strength: 100
      }
    });
  }
}