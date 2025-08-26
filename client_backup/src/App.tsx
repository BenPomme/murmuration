import React, { useEffect, useState, useCallback } from 'react';
import { GameCanvas } from './components/GameCanvas';
import { HUD } from './components/HUD';
import { BeaconPanel } from './components/BeaconPanel';
import { OverlayControls } from './components/OverlayControls';
import { SimulationService } from './services/SimulationService';
import type { 
  GameState, 
  Level, 
  GameSettings, 
  GameSpeed, 
  OverlayType, 
  Vector2D 
} from './types/game';

interface AppProps {
  // Future props can be added here
}

function App({}: AppProps): JSX.Element {
  // Game state
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [level, setLevel] = useState<Level | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // UI settings
  const [settings, setSettings] = useState<GameSettings>({
    overlays: [],
    speed: 1,
    showMinimap: true,
    accessibilityMode: false,
    reducedMotion: false,
    highContrast: false
  });

  // Simulation service instance
  const [simulationService] = useState(() => 
    new SimulationService(
      {
        websocketUrl: 'ws://localhost:8765',
        ticksPerSecond: 60
      },
      {
        onGameStateUpdate: setGameState,
        onLevelLoad: setLevel,
        onError: setError,
        onConnectionChange: setIsConnected
      }
    )
  );

  // Initialize connection
  useEffect(() => {
    const initConnection = async () => {
      try {
        await simulationService.connect();
      } catch (err) {
        console.error('Failed to connect to simulation:', err);
      }
    };

    initConnection();

    return () => {
      simulationService.disconnect();
    };
  }, [simulationService]);

  // Handle canvas clicks
  const handleCanvasClick = useCallback((position: Vector2D) => {
    // Canvas clicks are handled by drag-to-place or pulse activation
    console.log('Canvas clicked at:', position);
  }, []);

  // Handle agent clicks  
  const handleAgentClick = useCallback((agent: GameState['agents'][number]) => {
    console.log('Agent clicked:', agent.id);
    // Could show agent details or select agent for tracking
  }, []);

  // Handle beacon clicks
  const handleBeaconClick = useCallback((beacon: GameState['beacons'][number]) => {
    console.log('Beacon clicked:', beacon.id);
    // Could show beacon details or select for removal
  }, []);

  // Beacon management
  const handlePlaceBeacon = useCallback((beaconTypeId: string, position: Vector2D) => {
    simulationService.placeBeacon(beaconTypeId, position);
  }, [simulationService]);

  const handleRemoveBeacon = useCallback((beaconId: string) => {
    simulationService.removeBeacon(beaconId);
  }, [simulationService]);

  // Pulse management
  const handleActivatePulse = useCallback((pulseTypeId: string, position: Vector2D) => {
    simulationService.activatePulse(pulseTypeId, position);
  }, [simulationService]);

  // UI controls
  const handleToggleOverlay = useCallback((overlayType: OverlayType) => {
    simulationService.toggleOverlay(overlayType);
    setSettings(simulationService.getGameSettings());
  }, [simulationService]);

  const handleSetSpeed = useCallback((speed: GameSpeed) => {
    simulationService.setSpeed(speed);
    setSettings(simulationService.getGameSettings());
  }, [simulationService]);

  const handleToggleMinimap = useCallback(() => {
    simulationService.toggleMinimap();
    setSettings(simulationService.getGameSettings());
  }, [simulationService]);

  // Error handling
  const handleDismissError = useCallback(() => {
    setError(null);
  }, []);

  // Connection status component
  const ConnectionStatus = () => (
    <div 
      className={`connection-status connection-status--${isConnected ? 'connected' : 'disconnected'}`}
      role="status"
      aria-live="polite"
    >
      <span className="connection-indicator" aria-hidden="true">
        {isConnected ? '🟢' : '🔴'}
      </span>
      <span className="connection-text">
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );

  return (
    <div className="app" id="main-content">
      {/* Error banner */}
      {error && (
        <div className="error-banner" role="alert">
          <span className="error-message">{error}</span>
          <button 
            className="error-dismiss"
            onClick={handleDismissError}
            aria-label="Dismiss error message"
          >
            ×
          </button>
        </div>
      )}

      {/* Game container */}
      <div className="game-container">
        {/* HUD overlay - contains top bar and right panel */}
        <HUD 
          gameState={gameState}
          targets={level?.targets || null}
          className="game-hud"
        />

        {/* Main game canvas */}
        <div className="game-main">
          <GameCanvas
            gameState={gameState}
            mapData={level?.mapData || null}
            settings={settings}
            onCanvasClick={handleCanvasClick}
            onAgentClick={handleAgentClick}
            onBeaconClick={handleBeaconClick}
            className="game-canvas"
          />
        </div>

        {/* Left beacon panel */}
        <BeaconPanel
          gameState={gameState}
          onPlaceBeacon={handlePlaceBeacon}
          onRemoveBeacon={handleRemoveBeacon}
          className="game-beacon-panel"
        />

        {/* Bottom controls */}
        <OverlayControls
          gameState={gameState}
          settings={settings}
          onToggleOverlay={handleToggleOverlay}
          onSetSpeed={handleSetSpeed}
          onActivatePulse={handleActivatePulse}
          onToggleMinimap={handleToggleMinimap}
          className="game-controls"
        />

        {/* Connection status */}
        <div className="connection-status-container">
          <ConnectionStatus />
        </div>
      </div>

      <style jsx>{`
        .app {
          width: 100vw;
          height: 100vh;
          overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0F0F23;
          color: white;
        }

        .error-banner {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          background: rgba(248, 113, 113, 0.9);
          color: white;
          padding: 0.75rem 1rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
          z-index: 1000;
          backdrop-filter: blur(4px);
        }

        .error-message {
          font-weight: 500;
        }

        .error-dismiss {
          background: none;
          border: none;
          color: white;
          font-size: 1.5rem;
          cursor: pointer;
          padding: 0 0.5rem;
          border-radius: 2px;
          transition: background-color 0.2s ease;
        }

        .error-dismiss:hover {
          background: rgba(255, 255, 255, 0.2);
        }

        .error-dismiss:focus {
          outline: none;
          box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.5);
        }

        .game-container {
          position: relative;
          width: 100%;
          height: 100%;
          display: grid;
          grid-template-areas:
            "hud hud hud"
            "beacon main main"
            "controls controls controls";
          grid-template-rows: auto 1fr auto;
          grid-template-columns: 300px 1fr auto;
          gap: 0;
        }

        .game-hud {
          grid-area: hud;
          position: relative;
          z-index: 10;
        }

        .game-main {
          grid-area: main;
          position: relative;
          background: #0F0F23;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
        }

        .game-canvas {
          width: 100%;
          height: 100%;
          max-width: 1200px;
          max-height: 800px;
        }

        .game-beacon-panel {
          grid-area: beacon;
          position: relative;
          z-index: 5;
          margin: 1rem 0 1rem 1rem;
        }

        .game-controls {
          grid-area: controls;
          position: relative;
          z-index: 5;
        }

        .connection-status-container {
          position: fixed;
          bottom: 1rem;
          right: 1rem;
          z-index: 20;
        }

        .connection-status {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 0.75rem;
          border-radius: 20px;
          font-size: 0.8rem;
          font-weight: 500;
          backdrop-filter: blur(4px);
          transition: all 0.2s ease;
        }

        .connection-status--connected {
          background: rgba(34, 197, 94, 0.2);
          border: 1px solid rgba(34, 197, 94, 0.3);
          color: #22C55E;
        }

        .connection-status--disconnected {
          background: rgba(248, 113, 113, 0.2);
          border: 1px solid rgba(248, 113, 113, 0.3);
          color: #F87171;
        }

        .connection-indicator {
          font-size: 0.7rem;
        }

        .connection-text {
          white-space: nowrap;
        }

        /* Responsive design for smaller screens */
        @media (max-width: 1200px) {
          .game-container {
            grid-template-areas:
              "hud"
              "main"
              "beacon"
              "controls";
            grid-template-rows: auto 1fr auto auto;
            grid-template-columns: 1fr;
          }

          .game-beacon-panel {
            margin: 0 1rem 1rem 1rem;
          }
        }

        @media (max-width: 768px) {
          .game-container {
            gap: 0.5rem;
          }

          .game-beacon-panel {
            margin: 0 0.5rem;
          }

          .connection-status-container {
            bottom: 0.5rem;
            right: 0.5rem;
          }
        }

        /* High contrast mode support */
        @media (prefers-high-contrast: high) {
          .app {
            background: black;
          }

          .game-main {
            background: black;
          }

          .error-banner {
            background: red;
            color: white;
          }

          .connection-status--connected {
            background: green;
            color: white;
          }

          .connection-status--disconnected {
            background: red;
            color: white;
          }
        }

        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {
          .error-dismiss,
          .connection-status {
            transition: none;
          }
        }

        /* Focus management for accessibility */
        .game-container:focus-within .game-canvas {
          outline: 2px solid #8B5CF6;
          outline-offset: 4px;
          border-radius: 4px;
        }

        /* Skip links for keyboard navigation */
        .skip-link {
          position: absolute;
          top: -40px;
          left: 6px;
          background: #8B5CF6;
          color: white;
          padding: 8px;
          text-decoration: none;
          border-radius: 4px;
          z-index: 1000;
          transition: top 0.2s ease;
        }

        .skip-link:focus {
          top: 6px;
        }
      `}</style>
    </div>
  );
}

export default App