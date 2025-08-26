"""Hazards system for the Murmuration simulation.

This module implements environmental hazards that challenge flock survival,
including predators, storms, and light pollution. All hazards are deterministic
given random number generator state, following CLAUDE.md standards.

Key features:
- Deterministic hazard spawning using Poisson processes
- Telegraph system for ≥12h advance warning of random hazards
- Protected zone tracking for separate death statistics
- Performance optimized for O(N) complexity per tick
- Structured JSON logging for all hazard events

Modules:
    predators: Predator spawning and predation events
    storms: Storm systems with wind shocks and visibility effects
    light_pollution: Urban light pollution navigation traps

Functions:
    telegraph_hazards: Generate forecast events ≥12h in advance
    apply_all_hazards: Main integration point for hazard effects
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from ..core.types import RNG, EventData, Position, Tick
from ..core.agent import Agent
from ..core.environment import Environment
from ..utils.logging import get_logger

from .predators import (
    add_predation_events,
    spawn_predators,
    PredatorHotspot,
    PredationEvent,
)
from .storms import (
    apply_storm_effects,
    spawn_storms,
    StormSystem,
    StormEvent,
)
from .light_pollution import (
    check_light_pollution,
    LightPollutionTrap,
    LightPollutionEvent,
)

# Module version and compatibility
__version__ = "1.0.0"
__all__ = [
    # Main functions
    "telegraph_hazards",
    "apply_all_hazards",
    
    # Predator module
    "add_predation_events",
    "spawn_predators", 
    "PredatorHotspot",
    "PredationEvent",
    
    # Storm module
    "apply_storm_effects",
    "spawn_storms",
    "StormSystem", 
    "StormEvent",
    
    # Light pollution module
    "check_light_pollution",
    "LightPollutionTrap",
    "LightPollutionEvent",
]

logger = get_logger("hazards")


def telegraph_hazards(
    current_tick: Tick,
    forecast_horizon_hours: float,
    ticks_per_hour: int,
    environment: Environment,
    rng: RNG,
) -> List[EventData]:
    """Generate forecast events for hazards ≥12h in advance.
    
    Creates deterministic forecasts for random hazards to satisfy the
    telegraphy requirement from CLAUDE.md. All random hazards must be
    announced at least 12 hours before they occur.
    
    Args:
        current_tick: Current simulation tick
        forecast_horizon_hours: Hours to forecast ahead (must be ≥12)
        ticks_per_hour: Simulation ticks per game hour
        environment: Environment to forecast hazards for
        rng: Random number generator for deterministic forecasting
        
    Returns:
        List of forecast events with timing and hazard details
        
    Raises:
        ValueError: If forecast_horizon_hours < 12.0
        
    Performance:
        O(H) where H is the number of forecast hours
        
    Example:
        >>> forecast = telegraph_hazards(
        ...     current_tick=Tick(1000),
        ...     forecast_horizon_hours=24.0,
        ...     ticks_per_hour=3600,
        ...     environment=env,
        ...     rng=rng
        ... )
        >>> print(f"Forecasting {len(forecast)} hazard events")
    """
    if forecast_horizon_hours < 12.0:
        raise ValueError(f"Forecast horizon must be ≥12h, got {forecast_horizon_hours}h")
    
    logger.info(
        "Generating hazard forecast",
        extra={
            "current_tick": int(current_tick),
            "forecast_hours": forecast_horizon_hours,
            "ticks_per_hour": ticks_per_hour,
        }
    )
    
    forecast_events: List[EventData] = []
    forecast_ticks = int(forecast_horizon_hours * ticks_per_hour)
    min_warning_ticks = int(12.0 * ticks_per_hour)  # 12 hour minimum
    
    # Create separate RNG streams for each hazard type to maintain determinism
    predator_rng = np.random.default_rng(rng.integers(0, 2**32))
    storm_rng = np.random.default_rng(rng.integers(0, 2**32))
    light_rng = np.random.default_rng(rng.integers(0, 2**32))
    
    # Forecast storm events (most critical for planning)
    for hour_offset in range(int(forecast_horizon_hours)):
        forecast_tick = current_tick + hour_offset * ticks_per_hour
        
        # Random storm check (low probability per hour)
        if storm_rng.random() < 0.05:  # 5% chance per hour
            storm_severity = storm_rng.choice(["mild", "moderate", "severe"], p=[0.6, 0.3, 0.1])
            storm_duration = storm_rng.uniform(0.5, 3.0)  # 30min to 3h
            
            forecast_events.append({
                "event_type": "storm_forecast",
                "forecast_tick": int(forecast_tick),
                "warning_time_h": hour_offset,
                "severity": storm_severity,
                "duration_h": storm_duration,
                "wind_speed_kph": storm_rng.uniform(20, 80),
                "visibility_reduction": storm_rng.uniform(0.2, 0.8),
            })
    
    # Forecast predator activity spikes (less frequent but dangerous)
    for day_offset in range(int(forecast_horizon_hours / 24) + 1):
        forecast_tick = current_tick + day_offset * 24 * ticks_per_hour
        
        # Predator activity varies by time of day (dawn/dusk peaks)
        if predator_rng.random() < 0.3:  # 30% chance of activity spike per day
            activity_peak = predator_rng.choice(["dawn", "dusk", "night"])
            intensity = predator_rng.uniform(1.5, 3.0)  # Multiplier on base spawn rate
            
            forecast_events.append({
                "event_type": "predator_forecast", 
                "forecast_tick": int(forecast_tick),
                "warning_time_h": day_offset * 24,
                "activity_peak": activity_peak,
                "intensity_multiplier": intensity,
                "duration_h": predator_rng.uniform(2.0, 6.0),
            })
    
    # Filter out events that don't meet minimum warning time
    valid_events = [
        event for event in forecast_events
        if event["forecast_tick"] - int(current_tick) >= min_warning_ticks
    ]
    
    logger.info(
        "Hazard forecast completed",
        extra={
            "total_events": len(forecast_events),
            "valid_events": len(valid_events),
            "filtered_short_notice": len(forecast_events) - len(valid_events),
        }
    )
    
    return valid_events


def apply_all_hazards(
    agents: List[Agent],
    environment: Environment,
    current_tick: Tick,
    time_of_day: float,
    protected_zones: List[Tuple[Position, float]],
    rng: RNG,
) -> Tuple[List[EventData], Dict[str, int]]:
    """Apply all hazard effects to agents and environment.
    
    Main integration point for the hazards system. Coordinates all hazard
    types and tracks deaths separately for protected vs unprotected areas.
    
    Args:
        agents: List of agents to affect (modified in-place)
        environment: Environment to modify with hazard effects
        current_tick: Current simulation tick for timing
        time_of_day: Time of day as float [0.0, 24.0) for day/night effects
        protected_zones: List of (center, radius) tuples for protected areas
        rng: Random number generator for deterministic hazard effects
        
    Returns:
        Tuple of (events_list, death_counts) where death_counts has keys:
        - "total_deaths": Total agent deaths from hazards
        - "protected_deaths": Deaths that occurred in protected zones
        - "predation_deaths": Deaths specifically from predators
        - "storm_deaths": Deaths from storm effects
        - "light_pollution_deaths": Deaths from navigation traps
        
    Performance:
        O(N) where N is the number of agents
        
    Example:
        >>> events, deaths = apply_all_hazards(
        ...     agents=flock, 
        ...     environment=env,
        ...     current_tick=Tick(5000),
        ...     time_of_day=18.5,  # 6:30 PM
        ...     protected_zones=[(park_center, 50.0)],
        ...     rng=rng
        ... )
        >>> logger.info(f"Hazards caused {deaths['total_deaths']} deaths")
    """
    all_events: List[EventData] = []
    death_counts = {
        "total_deaths": 0,
        "protected_deaths": 0, 
        "predation_deaths": 0,
        "storm_deaths": 0,
        "light_pollution_deaths": 0,
    }
    
    logger.debug(
        "Applying hazard effects",
        extra={
            "tick": int(current_tick),
            "time_of_day": time_of_day,
            "agent_count": len(agents),
            "protected_zones": len(protected_zones),
        }
    )
    
    # Track initial agent states for death detection
    initial_alive_count = sum(1 for agent in agents if agent.alive)
    
    # Create separate RNG streams for each hazard type
    predator_rng = np.random.default_rng(rng.integers(0, 2**32))
    storm_rng = np.random.default_rng(rng.integers(0, 2**32))
    light_rng = np.random.default_rng(rng.integers(0, 2**32))
    
    # Apply predator effects
    predation_events = add_predation_events(
        agents=agents,
        environment=environment,
        current_tick=current_tick,
        time_of_day=time_of_day,
        protected_zones=protected_zones,
        rng=predator_rng,
    )
    all_events.extend(predation_events)
    
    # Apply storm effects
    storm_events = apply_storm_effects(
        agents=agents,
        environment=environment,
        current_tick=current_tick,
        rng=storm_rng,
    )
    all_events.extend(storm_events)
    
    # Apply light pollution effects (mainly at night)
    if 19.0 <= time_of_day <= 6.0:  # Night hours (7 PM - 6 AM)
        light_pollution_events = check_light_pollution(
            agents=agents,
            environment=environment,
            current_tick=current_tick,
            light_intensity=0.8 if 20.0 <= time_of_day <= 4.0 else 0.4,
            rng=light_rng,
        )
        all_events.extend(light_pollution_events)
    
    # Count deaths by type and location
    final_alive_count = sum(1 for agent in agents if agent.alive)
    total_new_deaths = initial_alive_count - final_alive_count
    death_counts["total_deaths"] = total_new_deaths
    
    # Analyze death events to categorize them
    for event in all_events:
        if event.get("event_type") in ["predation", "predator_kill"]:
            death_counts["predation_deaths"] += event.get("deaths", 0)
        elif event.get("event_type") in ["storm_death", "wind_shear_death"]:
            death_counts["storm_deaths"] += event.get("deaths", 0) 
        elif event.get("event_type") in ["light_trap_death", "navigation_failure"]:
            death_counts["light_pollution_deaths"] += event.get("deaths", 0)
        
        # Check if deaths occurred in protected zones
        if "agent_position" in event and event.get("deaths", 0) > 0:
            agent_pos = np.array(event["agent_position"])
            for zone_center, zone_radius in protected_zones:
                distance = np.linalg.norm(agent_pos - np.array(zone_center))
                if distance <= zone_radius:
                    death_counts["protected_deaths"] += event.get("deaths", 0)
                    break
    
    logger.info(
        "Hazard effects applied",
        extra={
            "total_events": len(all_events),
            "initial_agents": initial_alive_count,
            "final_agents": final_alive_count,
            "deaths_by_type": {
                k: v for k, v in death_counts.items()
                if k.endswith("_deaths")
            },
            "protected_zone_deaths": death_counts["protected_deaths"],
        }
    )
    
    return all_events, death_counts


# Initialize module logger
logger.info("Hazards module initialized", extra={"version": __version__})