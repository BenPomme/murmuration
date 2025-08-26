/**
 * BeaconPanel component with drag-to-place functionality
 * Allows players to manage beacon inventory and place beacons on the map
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import type { BeaconType, GameState, Vector2D } from '../types/game';
import { BEACON_TYPES } from '../types/game';

interface BeaconPanelProps {
  readonly gameState: GameState | null;
  readonly onPlaceBeacon?: (beaconTypeId: string, position: Vector2D) => void;
  readonly onRemoveBeacon?: (beaconId: string) => void;
  readonly className?: string;
}

interface DragState {
  readonly isDragging: boolean;
  readonly beaconTypeId: string | null;
  readonly startPosition: Vector2D | null;
  readonly currentPosition: Vector2D | null;
}

interface BeaconSlotProps {
  readonly beaconType: BeaconType;
  readonly available: number;
  readonly onDragStart: (beaconTypeId: string, position: Vector2D) => void;
  readonly disabled?: boolean;
}

function BeaconSlot({ 
  beaconType, 
  available, 
  onDragStart, 
  disabled = false 
}: BeaconSlotProps): JSX.Element {
  const slotRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const handleMouseDown = useCallback((event: React.MouseEvent) => {
    if (disabled || available <= 0) return;

    event.preventDefault();
    setIsDragging(true);
    
    const rect = slotRef.current?.getBoundingClientRect();
    if (rect) {
      onDragStart(beaconType.id, { 
        x: event.clientX - rect.left, 
        y: event.clientY - rect.top 
      });
    }
  }, [beaconType.id, available, disabled, onDragStart]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (disabled || available <= 0) return;
    
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      const rect = slotRef.current?.getBoundingClientRect();
      if (rect) {
        onDragStart(beaconType.id, { 
          x: rect.width / 2, 
          y: rect.height / 2 
        });
      }
    }
  }, [beaconType.id, available, disabled, onDragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mouseup', handleMouseUp);
      return () => document.removeEventListener('mouseup', handleMouseUp);
    }
  }, [isDragging, handleMouseUp]);

  return (
    <div
      ref={slotRef}
      className={`beacon-slot ${disabled ? 'beacon-slot--disabled' : ''} ${isDragging ? 'beacon-slot--dragging' : ''}`}
      onMouseDown={handleMouseDown}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onKeyDown={handleKeyDown}
      tabIndex={disabled || available <= 0 ? -1 : 0}
      role="button"
      aria-label={`${beaconType.name}: ${beaconType.description}. Available: ${available}. Cost: ${beaconType.cost}. ${disabled ? 'Disabled' : available <= 0 ? 'None available' : 'Drag to place'}`}
      aria-describedby={`beacon-${beaconType.id}-details`}
    >
      <div className="beacon-slot-icon" style={{ backgroundColor: beaconType.color }}>
        {getBeaconIcon(beaconType.id)}
      </div>
      
      <div className="beacon-slot-info">
        <div className="beacon-slot-name">{beaconType.name}</div>
        <div className="beacon-slot-count">
          <span className={`count-number ${available <= 0 ? 'count-number--empty' : ''}`}>
            {available}
          </span>
          <span className="count-cost">Cost: {beaconType.cost}</span>
        </div>
      </div>

      {isHovered && !disabled && (
        <div 
          id={`beacon-${beaconType.id}-details`} 
          className="beacon-tooltip"
          role="tooltip"
        >
          <div className="tooltip-header">
            <strong>{beaconType.name}</strong>
          </div>
          <div className="tooltip-description">{beaconType.description}</div>
          <div className="tooltip-stats">
            <div>Radius: {beaconType.radius}m</div>
            <div>Duration: {beaconType.halfLifeDays}d half-life</div>
            <div>Cost: {beaconType.cost} beacon{beaconType.cost !== 1 ? 's' : ''}</div>
          </div>
          {available <= 0 && <div className="tooltip-warning">No beacons available</div>}
          {disabled && <div className="tooltip-warning">Insufficient budget</div>}
        </div>
      )}
    </div>
  );
}

function getBeaconIcon(beaconTypeId: string): string {
  switch (beaconTypeId) {
    case 'light': return '💡';
    case 'sound': return '🔊';
    case 'food': return '🌾';
    case 'wind': return '💨';
    default: return '📍';
  }
}

interface ActiveBeaconListProps {
  readonly beacons: readonly GameState['beacons'][number][];
  readonly onRemove: (beaconId: string) => void;
}

function ActiveBeaconList({ beacons, onRemove }: ActiveBeaconListProps): JSX.Element {
  if (beacons.length === 0) {
    return (
      <div className="active-beacons-empty" role="status">
        No active beacons
      </div>
    );
  }

  return (
    <div className="active-beacons-list" role="list">
      {beacons.map(beacon => {
        const beaconType = BEACON_TYPES.find(type => type.id === beacon.type.id);
        if (!beaconType) return null;

        const strengthPercentage = Math.round(beacon.strength * 100);
        
        return (
          <div 
            key={beacon.id}
            className="active-beacon-item"
            role="listitem"
          >
            <div className="beacon-item-info">
              <span className="beacon-item-icon" style={{ color: beaconType.color }}>
                {getBeaconIcon(beaconType.id)}
              </span>
              <div className="beacon-item-details">
                <div className="beacon-item-name">{beaconType.name}</div>
                <div className="beacon-item-strength">
                  Strength: {strengthPercentage}%
                </div>
              </div>
            </div>
            
            <button
              className="beacon-remove-button"
              onClick={() => onRemove(beacon.id)}
              aria-label={`Remove ${beaconType.name} beacon at ${Math.round(beacon.position.x)}, ${Math.round(beacon.position.y)}`}
              title="Remove beacon"
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function BeaconPanel({ 
  gameState, 
  onPlaceBeacon, 
  onRemoveBeacon,
  className = '' 
}: BeaconPanelProps): JSX.Element {
  const [dragState, setDragState] = useState<DragState>({
    isDragging: false,
    beaconTypeId: null,
    startPosition: null,
    currentPosition: null
  });

  const panelRef = useRef<HTMLDivElement>(null);

  const handleDragStart = useCallback((beaconTypeId: string, startPosition: Vector2D) => {
    setDragState({
      isDragging: true,
      beaconTypeId,
      startPosition,
      currentPosition: startPosition
    });
  }, []);

  const handleMouseMove = useCallback((event: MouseEvent) => {
    if (!dragState.isDragging) return;

    setDragState(prev => ({
      ...prev,
      currentPosition: { x: event.clientX, y: event.clientY }
    }));
  }, [dragState.isDragging]);

  const handleMouseUp = useCallback((event: MouseEvent) => {
    if (!dragState.isDragging || !dragState.beaconTypeId || !onPlaceBeacon) {
      setDragState({
        isDragging: false,
        beaconTypeId: null,
        startPosition: null,
        currentPosition: null
      });
      return;
    }

    // Check if the drop is on a valid target (game canvas)
    const target = document.elementFromPoint(event.clientX, event.clientY);
    const gameCanvas = document.querySelector('.game-canvas');
    
    if (gameCanvas && (target === gameCanvas || gameCanvas.contains(target))) {
      const canvasRect = gameCanvas.getBoundingClientRect();
      const canvasPosition = {
        x: event.clientX - canvasRect.left,
        y: event.clientY - canvasRect.top
      };
      
      // Convert to world coordinates (this should match GameCanvas conversion)
      const worldPosition = {
        x: (canvasPosition.x / canvasRect.width) * 2000, // WORLD_WIDTH
        y: (canvasPosition.y / canvasRect.height) * 1200  // WORLD_HEIGHT
      };
      
      onPlaceBeacon(dragState.beaconTypeId, worldPosition);
    }

    setDragState({
      isDragging: false,
      beaconTypeId: null,
      startPosition: null,
      currentPosition: null
    });
  }, [dragState, onPlaceBeacon]);

  useEffect(() => {
    if (dragState.isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [dragState.isDragging, handleMouseMove, handleMouseUp]);

  const getAvailableBeacons = useCallback((beaconType: BeaconType): number => {
    if (!gameState) return 0;
    
    const maxAffordable = Math.floor(gameState.beaconBudgetRemaining / beaconType.cost);
    return maxAffordable;
  }, [gameState]);

  const canAffordBeacon = useCallback((beaconType: BeaconType): boolean => {
    if (!gameState) return false;
    return gameState.beaconBudgetRemaining >= beaconType.cost;
  }, [gameState]);

  if (!gameState) {
    return (
      <div className={`beacon-panel beacon-panel--loading ${className}`} role="complementary" aria-label="Beacon controls">
        <div className="loading-message">Loading beacon controls...</div>
      </div>
    );
  }

  return (
    <div 
      ref={panelRef}
      className={`beacon-panel ${className}`} 
      role="complementary" 
      aria-label="Beacon controls"
    >
      <div className="beacon-panel-header">
        <h2 className="panel-title">Beacons</h2>
        <div className="budget-display" aria-live="polite">
          Budget: <span className="budget-amount">{gameState.beaconBudgetRemaining}</span>
        </div>
      </div>

      <div className="beacon-slots" role="region" aria-labelledby="available-beacons-heading">
        <h3 id="available-beacons-heading" className="section-heading">Available</h3>
        {BEACON_TYPES.map(beaconType => (
          <BeaconSlot
            key={beaconType.id}
            beaconType={beaconType}
            available={getAvailableBeacons(beaconType)}
            onDragStart={handleDragStart}
            disabled={!canAffordBeacon(beaconType)}
          />
        ))}
      </div>

      <div className="active-beacons" role="region" aria-labelledby="active-beacons-heading">
        <h3 id="active-beacons-heading" className="section-heading">
          Active ({gameState.beacons.length})
        </h3>
        <ActiveBeaconList 
          beacons={gameState.beacons}
          onRemove={onRemoveBeacon || (() => {})}
        />
      </div>

      {/* Drag preview */}
      {dragState.isDragging && dragState.currentPosition && (
        <div
          className="drag-preview"
          style={{
            position: 'fixed',
            left: dragState.currentPosition.x - 20,
            top: dragState.currentPosition.y - 20,
            pointerEvents: 'none',
            zIndex: 1000
          }}
          aria-hidden="true"
        >
          <div className="drag-preview-icon">
            {dragState.beaconTypeId && getBeaconIcon(dragState.beaconTypeId)}
          </div>
        </div>
      )}

      <style jsx>{`
        .beacon-panel {
          width: 280px;
          background: rgba(15, 15, 35, 0.95);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: white;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          user-select: none;
          max-height: calc(100vh - 40px);
          overflow-y: auto;
        }

        .beacon-panel--loading {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 200px;
        }

        .beacon-panel-header {
          padding: 1rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .panel-title {
          margin: 0;
          font-size: 1.2rem;
          font-weight: 600;
          color: #E5E7EB;
        }

        .budget-display {
          font-size: 0.9rem;
          color: #9CA3AF;
        }

        .budget-amount {
          font-weight: 600;
          color: #8B5CF6;
        }

        .beacon-slots {
          padding: 1rem;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .section-heading {
          margin: 0 0 1rem 0;
          font-size: 1rem;
          font-weight: 500;
          color: #D1D5DB;
        }

        .beacon-slot {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem;
          margin-bottom: 0.5rem;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 6px;
          cursor: grab;
          transition: all 0.2s ease;
          border: 2px solid transparent;
        }

        .beacon-slot:hover:not(.beacon-slot--disabled) {
          background: rgba(255, 255, 255, 0.1);
          transform: translateY(-1px);
        }

        .beacon-slot:focus {
          outline: none;
          border-color: #8B5CF6;
          box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2);
        }

        .beacon-slot--disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .beacon-slot--dragging {
          cursor: grabbing;
          transform: scale(0.95);
        }

        .beacon-slot-icon {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.2rem;
          color: white;
        }

        .beacon-slot-info {
          flex: 1;
        }

        .beacon-slot-name {
          font-weight: 500;
          color: #E5E7EB;
          margin-bottom: 0.25rem;
        }

        .beacon-slot-count {
          display: flex;
          justify-content: space-between;
          font-size: 0.8rem;
        }

        .count-number {
          color: #8B5CF6;
          font-weight: 600;
        }

        .count-number--empty {
          color: #F87171;
        }

        .count-cost {
          color: #9CA3AF;
        }

        .beacon-tooltip {
          position: absolute;
          right: 100%;
          top: 0;
          margin-right: 0.5rem;
          background: rgba(0, 0, 0, 0.9);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 6px;
          padding: 0.75rem;
          min-width: 200px;
          z-index: 100;
          font-size: 0.9rem;
        }

        .tooltip-header {
          color: #E5E7EB;
          margin-bottom: 0.5rem;
        }

        .tooltip-description {
          color: #9CA3AF;
          margin-bottom: 0.5rem;
        }

        .tooltip-stats {
          color: #D1D5DB;
          font-size: 0.8rem;
        }

        .tooltip-stats > div {
          margin-bottom: 0.25rem;
        }

        .tooltip-warning {
          color: #F87171;
          font-weight: 500;
          margin-top: 0.5rem;
        }

        .active-beacons {
          padding: 1rem;
        }

        .active-beacons-empty {
          color: #6B7280;
          font-style: italic;
          text-align: center;
          padding: 2rem;
        }

        .active-beacons-list {
          max-height: 300px;
          overflow-y: auto;
        }

        .active-beacon-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.5rem;
          margin-bottom: 0.5rem;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 4px;
        }

        .beacon-item-info {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .beacon-item-icon {
          font-size: 1rem;
        }

        .beacon-item-name {
          color: #E5E7EB;
          font-weight: 500;
        }

        .beacon-item-strength {
          color: #9CA3AF;
          font-size: 0.8rem;
        }

        .beacon-remove-button {
          background: none;
          border: none;
          color: #F87171;
          font-size: 1.2rem;
          cursor: pointer;
          padding: 0.25rem;
          border-radius: 2px;
          transition: background-color 0.2s ease;
        }

        .beacon-remove-button:hover {
          background: rgba(248, 113, 113, 0.2);
        }

        .beacon-remove-button:focus {
          outline: none;
          box-shadow: 0 0 0 2px rgba(248, 113, 113, 0.5);
        }

        .drag-preview {
          background: rgba(0, 0, 0, 0.8);
          border: 2px solid #8B5CF6;
          border-radius: 50%;
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.2rem;
        }

        .drag-preview-icon {
          filter: drop-shadow(0 0 4px rgba(139, 92, 246, 0.5));
        }

        .loading-message {
          color: #9CA3AF;
          font-style: italic;
        }

        /* Accessibility improvements */
        @media (prefers-reduced-motion: reduce) {
          .beacon-slot,
          .beacon-remove-button {
            transition: none;
          }
          
          .beacon-slot:hover:not(.beacon-slot--disabled) {
            transform: none;
          }
        }

        @media (prefers-high-contrast: high) {
          .beacon-panel {
            background: black;
            border-color: white;
          }
          
          .beacon-slot {
            background: #333;
            border-color: white;
          }
          
          .beacon-tooltip {
            background: black;
            border-color: white;
          }
        }

        /* Custom scrollbar for better visibility */
        .beacon-panel::-webkit-scrollbar,
        .active-beacons-list::-webkit-scrollbar {
          width: 6px;
        }

        .beacon-panel::-webkit-scrollbar-track,
        .active-beacons-list::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 3px;
        }

        .beacon-panel::-webkit-scrollbar-thumb,
        .active-beacons-list::-webkit-scrollbar-thumb {
          background: rgba(139, 92, 246, 0.5);
          border-radius: 3px;
        }

        .beacon-panel::-webkit-scrollbar-thumb:hover,
        .active-beacons-list::-webkit-scrollbar-thumb:hover {
          background: rgba(139, 92, 246, 0.7);
        }
      `}</style>
    </div>
  );
}