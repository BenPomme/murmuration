/**
 * OverlayControls component for managing view overlays, speed controls, pulses, and minimap
 * Provides accessible controls for game visualization and interaction
 */

import React, { useCallback, useState } from 'react';
import type { 
  GameState, 
  GameSettings, 
  GameSpeed, 
  OverlayType, 
  Vector2D 
} from '../types/game';
import { PULSE_TYPES } from '../types/game';

interface OverlayControlsProps {
  readonly gameState: GameState | null;
  readonly settings: GameSettings;
  readonly onToggleOverlay?: (overlayType: OverlayType) => void;
  readonly onSetSpeed?: (speed: GameSpeed) => void;
  readonly onActivatePulse?: (pulseTypeId: string, position: Vector2D) => void;
  readonly onToggleMinimap?: () => void;
  readonly className?: string;
}

interface OverlayButtonProps {
  readonly overlayType: OverlayType;
  readonly isActive: boolean;
  readonly onToggle: (overlayType: OverlayType) => void;
  readonly disabled?: boolean;
}

function OverlayButton({ overlayType, isActive, onToggle, disabled = false }: OverlayButtonProps): JSX.Element {
  const getOverlayInfo = (type: OverlayType): { name: string; description: string; icon: string; shortcut: string } => {
    switch (type) {
      case 'wind':
        return { 
          name: 'Wind', 
          description: 'Show wind field vectors',
          icon: '💨',
          shortcut: 'W'
        };
      case 'risk':
        return { 
          name: 'Risk', 
          description: 'Show predator risk heatmap',
          icon: '⚠️',
          shortcut: 'R'
        };
      case 'light':
        return { 
          name: 'Light', 
          description: 'Show beacon light influence',
          icon: '💡',
          shortcut: 'L'
        };
      case 'paths':
        return { 
          name: 'Paths', 
          description: 'Show agent movement paths',
          icon: '📍',
          shortcut: 'P'
        };
      case 'heatmap':
        return { 
          name: 'Heatmap', 
          description: 'Show population density',
          icon: '🔥',
          shortcut: 'H'
        };
      default:
        return { name: type, description: '', icon: '?', shortcut: '' };
    }
  };

  const info = getOverlayInfo(overlayType);

  const handleClick = useCallback(() => {
    if (!disabled) {
      onToggle(overlayType);
    }
  }, [overlayType, onToggle, disabled]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleClick();
    }
  }, [handleClick]);

  return (
    <button
      className={`overlay-button ${isActive ? 'overlay-button--active' : ''} ${disabled ? 'overlay-button--disabled' : ''}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      disabled={disabled}
      title={`${info.name}: ${info.description} (Shortcut: ${info.shortcut})`}
      aria-label={`${info.name} overlay ${isActive ? 'enabled' : 'disabled'}. ${info.description}`}
      aria-pressed={isActive}
    >
      <span className="overlay-button-icon" aria-hidden="true">{info.icon}</span>
      <span className="overlay-button-text">{info.name}</span>
      <span className="overlay-button-shortcut" aria-hidden="true">{info.shortcut}</span>
    </button>
  );
}

interface SpeedControlProps {
  readonly currentSpeed: GameSpeed;
  readonly onSetSpeed: (speed: GameSpeed) => void;
}

function SpeedControl({ currentSpeed, onSetSpeed }: SpeedControlProps): JSX.Element {
  const speedOptions: { speed: GameSpeed; label: string; icon: string; description: string }[] = [
    { speed: 0, label: 'Pause', icon: '⏸️', description: 'Pause simulation' },
    { speed: 1, label: '1x', icon: '▶️', description: 'Normal speed' },
    { speed: 2, label: '2x', icon: '⏩', description: 'Double speed' },
    { speed: 4, label: '4x', icon: '⏭️', description: 'Quadruple speed' }
  ];

  const handleSpeedChange = useCallback((speed: GameSpeed) => {
    onSetSpeed(speed);
  }, [onSetSpeed]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent, speed: GameSpeed) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleSpeedChange(speed);
    }
  }, [handleSpeedChange]);

  return (
    <div className="speed-control" role="group" aria-labelledby="speed-control-heading">
      <h3 id="speed-control-heading" className="control-heading">Speed</h3>
      <div className="speed-buttons">
        {speedOptions.map(({ speed, label, icon, description }) => (
          <button
            key={speed}
            className={`speed-button ${currentSpeed === speed ? 'speed-button--active' : ''}`}
            onClick={() => handleSpeedChange(speed)}
            onKeyDown={(e) => handleKeyDown(e, speed)}
            title={description}
            aria-label={`Set speed to ${label}. ${description}`}
            aria-pressed={currentSpeed === speed}
          >
            <span className="speed-button-icon" aria-hidden="true">{icon}</span>
            <span className="speed-button-text">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

interface PulseControlProps {
  readonly gameState: GameState | null;
  readonly onActivatePulse: (pulseTypeId: string, position: Vector2D) => void;
}

function PulseControl({ gameState, onActivatePulse }: PulseControlProps): JSX.Element {
  const [selectedPulse, setSelectedPulse] = useState<string | null>(null);
  const [isWaitingForClick, setIsWaitingForClick] = useState(false);

  const isPulseAvailable = useCallback((pulseTypeId: string): boolean => {
    if (!gameState) return false;

    const pulseType = PULSE_TYPES.find(type => type.id === pulseTypeId);
    if (!pulseType) return false;

    // Check if pulse is on cooldown
    const activePulse = gameState.activePulses.find(pulse => pulse.type.id === pulseTypeId);
    if (activePulse) {
      const now = gameState.tick;
      const cooldownEndTick = activePulse.expiresAt + (pulseType.cooldownHours * 60 * 60 * 60); // Assuming 60 ticks/second
      return now >= cooldownEndTick;
    }

    return true;
  }, [gameState]);

  const getCooldownRemaining = useCallback((pulseTypeId: string): number => {
    if (!gameState) return 0;

    const pulseType = PULSE_TYPES.find(type => type.id === pulseTypeId);
    if (!pulseType) return 0;

    const activePulse = gameState.activePulses.find(pulse => pulse.type.id === pulseTypeId);
    if (!activePulse) return 0;

    const now = gameState.tick;
    const cooldownEndTick = activePulse.expiresAt + (pulseType.cooldownHours * 60 * 60 * 60);
    const remainingTicks = Math.max(0, cooldownEndTick - now);
    
    return remainingTicks / (60 * 60 * 60); // Convert to hours
  }, [gameState]);

  const handlePulseSelect = useCallback((pulseTypeId: string) => {
    if (!isPulseAvailable(pulseTypeId)) return;

    setSelectedPulse(pulseTypeId);
    setIsWaitingForClick(true);

    // Add event listener for canvas click
    const handleCanvasClick = (event: Event) => {
      const target = event.target as HTMLElement;
      const gameCanvas = document.querySelector('.game-canvas') as HTMLCanvasElement;
      
      if (gameCanvas && (target === gameCanvas || gameCanvas.contains(target))) {
        const rect = gameCanvas.getBoundingClientRect();
        const clientX = 'clientX' in event ? (event as MouseEvent).clientX : 0;
        const clientY = 'clientY' in event ? (event as MouseEvent).clientY : 0;
        
        const canvasPosition = {
          x: clientX - rect.left,
          y: clientY - rect.top
        };
        
        // Convert to world coordinates
        const worldPosition = {
          x: (canvasPosition.x / rect.width) * 2000, // WORLD_WIDTH
          y: (canvasPosition.y / rect.height) * 1200  // WORLD_HEIGHT
        };
        
        onActivatePulse(pulseTypeId, worldPosition);
        
        setSelectedPulse(null);
        setIsWaitingForClick(false);
        document.removeEventListener('click', handleCanvasClick);
      } else {
        // Clicked outside canvas, cancel
        setSelectedPulse(null);
        setIsWaitingForClick(false);
        document.removeEventListener('click', handleCanvasClick);
      }
    };

    document.addEventListener('click', handleCanvasClick);
  }, [isPulseAvailable, onActivatePulse]);

  const getPulseIcon = (pulseTypeId: string): string => {
    switch (pulseTypeId) {
      case 'festival': return '🎉';
      case 'scout': return '🔍';
      default: return '⚡';
    }
  };

  return (
    <div className="pulse-control" role="group" aria-labelledby="pulse-control-heading">
      <h3 id="pulse-control-heading" className="control-heading">Pulses</h3>
      <div className="pulse-buttons">
        {PULSE_TYPES.map(pulseType => {
          const available = isPulseAvailable(pulseType.id);
          const cooldown = getCooldownRemaining(pulseType.id);
          
          return (
            <button
              key={pulseType.id}
              className={`pulse-button ${selectedPulse === pulseType.id ? 'pulse-button--selected' : ''} ${!available ? 'pulse-button--disabled' : ''}`}
              onClick={() => handlePulseSelect(pulseType.id)}
              disabled={!available}
              title={`${pulseType.name}: ${pulseType.description}${!available ? ` (Cooldown: ${cooldown.toFixed(1)}h)` : ''}`}
              aria-label={`${pulseType.name}. ${pulseType.description}. ${!available ? `On cooldown for ${cooldown.toFixed(1)} hours` : 'Click to select, then click on map to activate'}`}
            >
              <span className="pulse-button-icon" aria-hidden="true">
                {getPulseIcon(pulseType.id)}
              </span>
              <div className="pulse-button-info">
                <span className="pulse-button-name">{pulseType.name}</span>
                {!available && cooldown > 0 && (
                  <span className="pulse-button-cooldown">{cooldown.toFixed(1)}h</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
      
      {isWaitingForClick && (
        <div className="pulse-instruction" role="status" aria-live="polite">
          Click on the map to place {selectedPulse} pulse
        </div>
      )}
    </div>
  );
}

interface MinimapControlProps {
  readonly showMinimap: boolean;
  readonly onToggle: () => void;
}

function MinimapControl({ showMinimap, onToggle }: MinimapControlProps): JSX.Element {
  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onToggle();
    }
  }, [onToggle]);

  return (
    <div className="minimap-control">
      <button
        className={`minimap-button ${showMinimap ? 'minimap-button--active' : ''}`}
        onClick={onToggle}
        onKeyDown={handleKeyDown}
        title="Toggle minimap visibility"
        aria-label={`Minimap ${showMinimap ? 'visible' : 'hidden'}. Click to toggle`}
        aria-pressed={showMinimap}
      >
        <span className="minimap-button-icon" aria-hidden="true">🗺️</span>
        <span className="minimap-button-text">Minimap</span>
      </button>
    </div>
  );
}

export function OverlayControls({
  gameState,
  settings,
  onToggleOverlay,
  onSetSpeed,
  onActivatePulse,
  onToggleMinimap,
  className = ''
}: OverlayControlsProps): JSX.Element {
  const overlayTypes: OverlayType[] = ['wind', 'risk', 'light', 'paths', 'heatmap'];

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!onToggleOverlay || event.ctrlKey || event.altKey || event.metaKey) return;

    const key = event.key.toLowerCase();
    switch (key) {
      case 'w':
        event.preventDefault();
        onToggleOverlay('wind');
        break;
      case 'r':
        event.preventDefault();
        onToggleOverlay('risk');
        break;
      case 'l':
        event.preventDefault();
        onToggleOverlay('light');
        break;
      case 'p':
        event.preventDefault();
        onToggleOverlay('paths');
        break;
      case 'h':
        event.preventDefault();
        onToggleOverlay('heatmap');
        break;
      case ' ':
        event.preventDefault();
        if (onSetSpeed) {
          const newSpeed: GameSpeed = settings.speed === 0 ? 1 : 0;
          onSetSpeed(newSpeed);
        }
        break;
      case '1':
      case '2':
      case '3':
      case '4':
        event.preventDefault();
        if (onSetSpeed) {
          const speed = key === '1' ? 1 : key === '2' ? 2 : key === '3' ? 4 : 0;
          onSetSpeed(speed as GameSpeed);
        }
        break;
    }
  }, [onToggleOverlay, onSetSpeed, settings.speed]);

  React.useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div 
      className={`overlay-controls ${className}`}
      role="toolbar"
      aria-label="Game controls and overlays"
    >
      {/* Overlay Toggles */}
      <div className="overlay-section" role="group" aria-labelledby="overlay-section-heading">
        <h3 id="overlay-section-heading" className="control-heading">Overlays</h3>
        <div className="overlay-buttons">
          {overlayTypes.map(overlayType => (
            <OverlayButton
              key={overlayType}
              overlayType={overlayType}
              isActive={settings.overlays.includes(overlayType)}
              onToggle={onToggleOverlay || (() => {})}
              disabled={!onToggleOverlay}
            />
          ))}
        </div>
      </div>

      {/* Speed Control */}
      {onSetSpeed && (
        <SpeedControl
          currentSpeed={settings.speed}
          onSetSpeed={onSetSpeed}
        />
      )}

      {/* Pulse Control */}
      {onActivatePulse && (
        <PulseControl
          gameState={gameState}
          onActivatePulse={onActivatePulse}
        />
      )}

      {/* Minimap Control */}
      {onToggleMinimap && (
        <MinimapControl
          showMinimap={settings.showMinimap}
          onToggle={onToggleMinimap}
        />
      )}

      <style jsx>{`
        .overlay-controls {
          display: flex;
          align-items: center;
          gap: 2rem;
          padding: 1rem;
          background: rgba(15, 15, 35, 0.9);
          border-top: 1px solid rgba(255, 255, 255, 0.1);
          color: white;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          user-select: none;
          min-height: 80px;
        }

        .control-heading {
          margin: 0 0 0.5rem 0;
          font-size: 0.9rem;
          font-weight: 500;
          color: #D1D5DB;
        }

        .overlay-section {
          flex: 1;
        }

        .overlay-buttons {
          display: flex;
          gap: 0.5rem;
          flex-wrap: wrap;
        }

        .overlay-button {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 0.75rem;
          background: rgba(255, 255, 255, 0.1);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 6px;
          color: white;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 0.8rem;
        }

        .overlay-button:hover:not(.overlay-button--disabled) {
          background: rgba(255, 255, 255, 0.2);
          transform: translateY(-1px);
        }

        .overlay-button:focus {
          outline: none;
          box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.5);
        }

        .overlay-button--active {
          background: #8B5CF6;
          border-color: #7C3AED;
        }

        .overlay-button--disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .overlay-button-text {
          font-weight: 500;
        }

        .overlay-button-shortcut {
          font-size: 0.7rem;
          opacity: 0.7;
          margin-left: 0.25rem;
        }

        .speed-control {
          min-width: 200px;
        }

        .speed-buttons {
          display: flex;
          gap: 0.25rem;
        }

        .speed-button {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 0.5rem;
          background: rgba(255, 255, 255, 0.1);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 4px;
          color: white;
          cursor: pointer;
          transition: all 0.2s ease;
          min-width: 45px;
          font-size: 0.8rem;
        }

        .speed-button:hover {
          background: rgba(255, 255, 255, 0.2);
        }

        .speed-button:focus {
          outline: none;
          box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.5);
        }

        .speed-button--active {
          background: #8B5CF6;
          border-color: #7C3AED;
        }

        .speed-button-icon {
          font-size: 1rem;
          margin-bottom: 0.25rem;
        }

        .speed-button-text {
          font-weight: 500;
        }

        .pulse-control {
          min-width: 150px;
        }

        .pulse-buttons {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .pulse-button {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.5rem;
          background: rgba(255, 255, 255, 0.1);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 4px;
          color: white;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 0.8rem;
        }

        .pulse-button:hover:not(.pulse-button--disabled) {
          background: rgba(255, 255, 255, 0.2);
        }

        .pulse-button:focus {
          outline: none;
          box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.5);
        }

        .pulse-button--selected {
          background: #FBBF24;
          border-color: #F59E0B;
          color: black;
        }

        .pulse-button--disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .pulse-button-icon {
          font-size: 1.1rem;
        }

        .pulse-button-info {
          flex: 1;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .pulse-button-name {
          font-weight: 500;
        }

        .pulse-button-cooldown {
          font-size: 0.7rem;
          opacity: 0.8;
        }

        .pulse-instruction {
          margin-top: 0.5rem;
          font-size: 0.8rem;
          color: #FBBF24;
          font-style: italic;
        }

        .minimap-control {
          min-width: 80px;
        }

        .minimap-button {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 0.5rem;
          background: rgba(255, 255, 255, 0.1);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 4px;
          color: white;
          cursor: pointer;
          transition: all 0.2s ease;
          width: 100%;
          font-size: 0.8rem;
        }

        .minimap-button:hover {
          background: rgba(255, 255, 255, 0.2);
        }

        .minimap-button:focus {
          outline: none;
          box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.5);
        }

        .minimap-button--active {
          background: #8B5CF6;
          border-color: #7C3AED;
        }

        .minimap-button-icon {
          font-size: 1.1rem;
          margin-bottom: 0.25rem;
        }

        .minimap-button-text {
          font-weight: 500;
        }

        /* Accessibility improvements */
        @media (prefers-reduced-motion: reduce) {
          .overlay-button,
          .speed-button,
          .pulse-button,
          .minimap-button {
            transition: none;
          }
          
          .overlay-button:hover:not(.overlay-button--disabled) {
            transform: none;
          }
        }

        @media (prefers-high-contrast: high) {
          .overlay-controls {
            background: black;
            border-color: white;
          }
          
          .overlay-button,
          .speed-button,
          .pulse-button,
          .minimap-button {
            background: #333;
            border-color: white;
          }
          
          .overlay-button--active,
          .speed-button--active,
          .minimap-button--active {
            background: white;
            color: black;
          }
        }

        /* Responsive layout */
        @media (max-width: 768px) {
          .overlay-controls {
            flex-direction: column;
            align-items: stretch;
            gap: 1rem;
          }
          
          .overlay-buttons {
            justify-content: center;
          }
          
          .speed-buttons {
            justify-content: center;
          }
        }
      `}</style>
    </div>
  );
}