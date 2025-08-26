/**
 * HUD component displaying game telemetry and status information
 * Accessible design with ARIA labels and keyboard navigation
 */

import React from 'react';
import type { GameState, ContractTargets, WeatherForecast } from '../types/game';

interface HUDProps {
  readonly gameState: GameState | null;
  readonly targets: ContractTargets | null;
  readonly className?: string;
}

interface MetricDisplayProps {
  readonly label: string;
  readonly current: number;
  readonly target?: number;
  readonly max?: number;
  readonly unit?: string;
  readonly format?: 'integer' | 'percentage' | 'decimal';
  readonly status?: 'normal' | 'warning' | 'danger' | 'success';
}

function MetricDisplay({ 
  label, 
  current, 
  target, 
  max, 
  unit = '', 
  format = 'integer',
  status = 'normal'
}: MetricDisplayProps): JSX.Element {
  const formatValue = (value: number): string => {
    switch (format) {
      case 'percentage':
        return `${Math.round(value * 100)}%`;
      case 'decimal':
        return value.toFixed(2);
      case 'integer':
      default:
        return Math.round(value).toString();
    }
  };

  const getProgressPercentage = (): number => {
    if (target !== undefined) {
      return Math.min((current / target) * 100, 100);
    }
    if (max !== undefined) {
      return (current / max) * 100;
    }
    return 0;
  };

  const getStatusColor = (): string => {
    switch (status) {
      case 'success': return '#4ADE80';
      case 'warning': return '#FBBF24';
      case 'danger': return '#F87171';
      case 'normal':
      default: return '#8B5CF6';
    }
  };

  const statusText = (): string => {
    if (target !== undefined) {
      if (current >= target) return 'Target met';
      if (current >= target * 0.8) return 'Near target';
      return 'Below target';
    }
    return '';
  };

  return (
    <div className="metric-display" role="group" aria-labelledby={`metric-${label.replace(/\s+/g, '-').toLowerCase()}`}>
      <div className="metric-header">
        <span id={`metric-${label.replace(/\s+/g, '-').toLowerCase()}`} className="metric-label">
          {label}
        </span>
        {target !== undefined && (
          <span className="metric-target" aria-label={`Target: ${formatValue(target)}${unit}`}>
            Target: {formatValue(target)}{unit}
          </span>
        )}
      </div>
      
      <div className="metric-value-container">
        <span 
          className={`metric-value metric-value--${status}`}
          style={{ color: getStatusColor() }}
          aria-label={`Current value: ${formatValue(current)}${unit}. ${statusText()}`}
        >
          {formatValue(current)}{unit}
        </span>
        
        {(target !== undefined || max !== undefined) && (
          <div 
            className="metric-progress"
            role="progressbar"
            aria-valuenow={current}
            aria-valuemin={0}
            aria-valuemax={target || max || 100}
            aria-valuetext={`${formatValue(current)}${unit} of ${formatValue(target || max || 100)}${unit}`}
          >
            <div 
              className="metric-progress-fill"
              style={{
                width: `${Math.min(getProgressPercentage(), 100)}%`,
                backgroundColor: getStatusColor()
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

interface SeasonClockProps {
  readonly gameDay: number;
  readonly gameHour: number;
  readonly timeLimit: number;
}

function SeasonClock({ gameDay, gameHour, timeLimit }: SeasonClockProps): JSX.Element {
  const formatTime = (day: number, hour: number): string => {
    return `Day ${day}, ${hour.toString().padStart(2, '0')}:00`;
  };

  const getTimeStatus = (): 'normal' | 'warning' | 'danger' => {
    const timeUsed = gameDay / timeLimit;
    if (timeUsed >= 0.9) return 'danger';
    if (timeUsed >= 0.7) return 'warning';
    return 'normal';
  };

  const timeRemaining = timeLimit - gameDay;

  return (
    <div className="season-clock" role="timer" aria-live="polite">
      <div className="clock-display">
        <span className="clock-time" aria-label={`Current time: ${formatTime(gameDay, gameHour)}`}>
          {formatTime(gameDay, gameHour)}
        </span>
        <span 
          className={`clock-remaining clock-remaining--${getTimeStatus()}`}
          aria-label={`${timeRemaining} days remaining of ${timeLimit} day limit`}
        >
          {timeRemaining}d remaining
        </span>
      </div>
      
      <div 
        className="clock-progress"
        role="progressbar"
        aria-valuenow={gameDay}
        aria-valuemin={0}
        aria-valuemax={timeLimit}
        aria-valuetext={`Day ${gameDay} of ${timeLimit}`}
      >
        <div 
          className="clock-progress-fill"
          style={{ width: `${Math.min((gameDay / timeLimit) * 100, 100)}%` }}
        />
      </div>
    </div>
  );
}

interface WeatherDisplayProps {
  readonly wind: { readonly x: number; readonly y: number };
  readonly forecast: readonly WeatherForecast[];
}

function WeatherDisplay({ wind, forecast }: WeatherDisplayProps): JSX.Element {
  const getWindDirection = (): string => {
    const angle = Math.atan2(wind.y, wind.x) * (180 / Math.PI);
    const directions = ['E', 'NE', 'N', 'NW', 'W', 'SW', 'S', 'SE'];
    const index = Math.round(((angle + 360) % 360) / 45) % 8;
    return directions[index] || 'N';
  };

  const getWindStrength = (): number => {
    return Math.sqrt(wind.x * wind.x + wind.y * wind.y);
  };

  const getWindDescription = (): string => {
    const strength = getWindStrength();
    if (strength < 0.3) return 'Light';
    if (strength < 0.6) return 'Moderate';
    if (strength < 0.9) return 'Strong';
    return 'Very Strong';
  };

  const upcomingHazards = forecast.filter(f => f.hazardType).slice(0, 3);

  return (
    <div className="weather-display" role="region" aria-labelledby="weather-heading">
      <h3 id="weather-heading" className="weather-heading">Weather</h3>
      
      <div className="wind-info">
        <div 
          className="wind-indicator"
          aria-label={`Wind: ${getWindDescription()} ${getWindDirection()}, strength ${getWindStrength().toFixed(1)}`}
        >
          <div 
            className="wind-arrow"
            style={{
              transform: `rotate(${Math.atan2(wind.y, wind.x) * (180 / Math.PI)}deg)`
            }}
            aria-hidden="true"
          >
            →
          </div>
          <span className="wind-text">
            {getWindDescription()} {getWindDirection()}
          </span>
        </div>
      </div>

      {upcomingHazards.length > 0 && (
        <div className="forecast" role="region" aria-labelledby="forecast-heading">
          <h4 id="forecast-heading" className="forecast-heading">Upcoming Hazards</h4>
          <ul className="forecast-list" role="list">
            {upcomingHazards.map((hazard, index) => (
              <li 
                key={`${hazard.hour}-${hazard.hazardType}`}
                className="forecast-item"
                role="listitem"
              >
                <span className="forecast-time">+{hazard.hour}h</span>
                <span 
                  className={`forecast-hazard forecast-hazard--${hazard.hazardType}`}
                  aria-label={`${hazard.hazardType} intensity ${(hazard.hazardIntensity || 0 * 100).toFixed(0)}%`}
                >
                  {hazard.hazardType}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

interface StrikesDisplayProps {
  readonly strikes: number;
  readonly maxStrikes?: number;
}

function StrikesDisplay({ strikes, maxStrikes = 3 }: StrikesDisplayProps): JSX.Element {
  const getStrikesStatus = (): 'normal' | 'warning' | 'danger' => {
    if (strikes >= maxStrikes - 1) return 'danger';
    if (strikes >= maxStrikes - 2) return 'warning';
    return 'normal';
  };

  return (
    <div 
      className={`strikes-display strikes-display--${getStrikesStatus()}`}
      role="status"
      aria-live="polite"
      aria-label={`Contract strikes: ${strikes} of ${maxStrikes}`}
    >
      <span className="strikes-label">Strikes</span>
      <div className="strikes-indicators" aria-hidden="true">
        {Array.from({ length: maxStrikes }, (_, i) => (
          <div
            key={i}
            className={`strike-indicator ${i < strikes ? 'strike-indicator--active' : ''}`}
          />
        ))}
      </div>
      <span className="strikes-count" aria-hidden="true">
        {strikes}/{maxStrikes}
      </span>
    </div>
  );
}

export function HUD({ gameState, targets, className = '' }: HUDProps): JSX.Element {
  if (!gameState) {
    return (
      <div className={`hud hud--loading ${className}`} role="complementary" aria-label="Game HUD">
        <div className="loading-message" aria-live="polite">
          Connecting to simulation...
        </div>
      </div>
    );
  }

  const getMetricStatus = (current: number, target?: number): 'normal' | 'warning' | 'danger' | 'success' => {
    if (target === undefined) return 'normal';
    if (current >= target) return 'success';
    if (current >= target * 0.8) return 'warning';
    return 'danger';
  };

  return (
    <div className={`hud ${className}`} role="complementary" aria-label="Game HUD">
      {/* Top Bar */}
      <div className="hud-top-bar" role="banner">
        <SeasonClock 
          gameDay={gameState.gameDay} 
          gameHour={gameState.gameHour}
          timeLimit={targets?.timeLimit || 10}
        />
        
        <WeatherDisplay 
          wind={gameState.wind}
          forecast={gameState.forecast}
        />
        
        <StrikesDisplay strikes={gameState.strikes} />
      </div>

      {/* Right Panel - Telemetry */}
      <div className="hud-telemetry" role="region" aria-labelledby="telemetry-heading">
        <h2 id="telemetry-heading" className="telemetry-heading">Mission Status</h2>
        
        <div className="telemetry-metrics">
          <MetricDisplay
            label="Population"
            current={gameState.population}
            max={gameState.agents.length}
            status="normal"
          />
          
          <MetricDisplay
            label="Arrivals"
            current={gameState.arrivals}
            target={targets?.arrivalsMin}
            status={getMetricStatus(gameState.arrivals, targets?.arrivalsMin)}
          />
          
          <MetricDisplay
            label="Losses"
            current={gameState.deaths}
            max={targets?.lossesMax}
            status={targets?.lossesMax !== undefined && gameState.deaths > targets.lossesMax ? 'danger' : 'normal'}
          />
          
          <MetricDisplay
            label="Cohesion"
            current={gameState.cohesion}
            target={targets?.cohesionAvgMin}
            format="percentage"
            status={getMetricStatus(gameState.cohesion, targets?.cohesionAvgMin)}
          />
          
          <MetricDisplay
            label="Diversity"
            current={gameState.diversity}
            target={targets?.diversityMin}
            format="percentage"
            status={getMetricStatus(gameState.diversity, targets?.diversityMin)}
          />
          
          <MetricDisplay
            label="Beacon Budget"
            current={gameState.beaconBudgetRemaining}
            max={targets?.beaconBudgetMax}
            status={gameState.beaconBudgetRemaining === 0 ? 'warning' : 'normal'}
          />
        </div>
        
        {targets && (
          <div className="contract-summary" role="region" aria-labelledby="contract-heading">
            <h3 id="contract-heading" className="contract-heading">Contract Targets</h3>
            <div className="contract-progress">
              <div className="contract-status">
                {gameState.arrivals >= targets.arrivalsMin &&
                 gameState.cohesion >= targets.cohesionAvgMin &&
                 gameState.deaths <= targets.lossesMax &&
                 (!targets.diversityMin || gameState.diversity >= targets.diversityMin) ? (
                  <span className="contract-status--success" aria-label="All contract targets met">
                    ✓ All targets met
                  </span>
                ) : (
                  <span className="contract-status--pending" aria-label="Contract targets in progress">
                    ⧖ In progress
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .hud {
          position: relative;
          width: 100%;
          height: 100%;
          color: white;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          user-select: none;
        }

        .hud--loading {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .hud-top-bar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1rem;
          background: rgba(15, 15, 35, 0.9);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .hud-telemetry {
          position: absolute;
          top: 80px;
          right: 1rem;
          width: 280px;
          background: rgba(15, 15, 35, 0.95);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 1rem;
          max-height: calc(100vh - 120px);
          overflow-y: auto;
        }

        .telemetry-heading, .contract-heading, .weather-heading, .forecast-heading {
          margin: 0 0 1rem 0;
          font-size: 1.1rem;
          font-weight: 600;
          color: #E5E7EB;
        }

        .metric-display {
          margin-bottom: 1rem;
          padding: 0.5rem 0;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .metric-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.25rem;
        }

        .metric-label {
          font-size: 0.9rem;
          color: #9CA3AF;
        }

        .metric-target {
          font-size: 0.8rem;
          color: #6B7280;
        }

        .metric-value-container {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .metric-value {
          font-size: 1.2rem;
          font-weight: 600;
          min-width: 60px;
        }

        .metric-value--success { color: #4ADE80; }
        .metric-value--warning { color: #FBBF24; }
        .metric-value--danger { color: #F87171; }
        .metric-value--normal { color: #8B5CF6; }

        .metric-progress {
          flex: 1;
          height: 6px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 3px;
          overflow: hidden;
        }

        .metric-progress-fill {
          height: 100%;
          transition: width 0.3s ease;
        }

        .season-clock {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
        }

        .clock-display {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin-bottom: 0.25rem;
        }

        .clock-time {
          font-size: 1.1rem;
          font-weight: 600;
          color: #E5E7EB;
        }

        .clock-remaining {
          font-size: 0.9rem;
        }

        .clock-remaining--normal { color: #4ADE80; }
        .clock-remaining--warning { color: #FBBF24; }
        .clock-remaining--danger { color: #F87171; }

        .clock-progress {
          width: 200px;
          height: 4px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 2px;
          overflow: hidden;
        }

        .clock-progress-fill {
          height: 100%;
          background: #8B5CF6;
          transition: width 0.3s ease;
        }

        .weather-display {
          text-align: center;
        }

        .wind-info {
          margin-bottom: 0.5rem;
        }

        .wind-indicator {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .wind-arrow {
          font-size: 1.2rem;
          transition: transform 0.3s ease;
        }

        .wind-text {
          font-size: 0.9rem;
          color: #E5E7EB;
        }

        .forecast-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .forecast-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.25rem 0;
          font-size: 0.8rem;
        }

        .forecast-time {
          color: #9CA3AF;
        }

        .forecast-hazard {
          font-weight: 500;
        }

        .forecast-hazard--storm { color: #60A5FA; }
        .forecast-hazard--predator { color: #F87171; }
        .forecast-hazard--light_pollution { color: #FBBF24; }

        .strikes-display {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem;
          border-radius: 4px;
        }

        .strikes-display--normal { background: rgba(75, 85, 99, 0.3); }
        .strikes-display--warning { background: rgba(251, 191, 36, 0.2); }
        .strikes-display--danger { background: rgba(248, 113, 113, 0.2); }

        .strikes-label {
          font-size: 0.9rem;
          color: #E5E7EB;
        }

        .strikes-indicators {
          display: flex;
          gap: 0.25rem;
        }

        .strike-indicator {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: rgba(255, 255, 255, 0.2);
        }

        .strike-indicator--active {
          background: #F87171;
        }

        .strikes-count {
          font-size: 0.8rem;
          color: #9CA3AF;
        }

        .contract-summary {
          margin-top: 1.5rem;
          padding-top: 1rem;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .contract-status--success {
          color: #4ADE80;
          font-weight: 500;
        }

        .contract-status--pending {
          color: #FBBF24;
          font-weight: 500;
        }

        .loading-message {
          font-size: 1.1rem;
          color: #9CA3AF;
        }

        /* Accessibility improvements */
        @media (prefers-reduced-motion: reduce) {
          .metric-progress-fill,
          .clock-progress-fill,
          .wind-arrow {
            transition: none;
          }
        }

        @media (prefers-high-contrast: high) {
          .hud {
            background: black;
            color: white;
          }
          
          .hud-top-bar,
          .hud-telemetry {
            background: black;
            border-color: white;
          }
        }

        /* Focus styles for keyboard navigation */
        .hud:focus-within .metric-display,
        .hud:focus-within .season-clock,
        .hud:focus-within .weather-display,
        .hud:focus-within .strikes-display {
          outline: 2px solid #8B5CF6;
          outline-offset: 2px;
          border-radius: 4px;
        }
      `}</style>
    </div>
  );
}