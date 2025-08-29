# Murmuration Game Rules

## Overview
Murmuration is a strategic bird migration game where players guide flocks through dangerous journeys using path drawing and environmental awareness.

## Core Mechanics

### 1. Flock Dynamics

#### Leadership System
- **5 Leader Birds**: First 5 birds are designated as leaders
- **Leaders**: Follow the drawn path directly with strong attraction forces
- **Followers**: Use flocking behavior to stay with the group
  - Strong cohesion forces (1.5x)
  - Strong alignment forces (1.0x)
  - Leaders have weaker flocking (0.3x cohesion, 0.2x alignment)

#### Spawning
- Leaders spawn in inner 30% of start zone
- Followers spawn in 20-60% of start zone
- All birds start with similar velocity direction for initial cohesion
- 50% male (blue), 50% female (pink) distribution

### 2. Path Following

#### Path Drawing Phase
- Players draw migration path during planning phase
- Path submission starts the migration
- No path forces applied until path is drawn

#### Path Mechanics
- Leaders follow waypoints with 40-unit detection radius
- Lookahead blending: 70% current waypoint + 30% lookahead for smooth curves
- Path continuation: Birds project trajectory forward at path end
- Destination blending: 70% trajectory + 30% destination pull

#### Speed Control
- Base speed: 100-150 units/second
- Leader minimum speed: 30 units/second (prevents stopping)
- Stress speed boost: +10% speed per 10% stress
- Anti-stuck mechanism: Random push if velocity < 10

### 3. Energy System

#### Energy Depletion
Base energy consumption has three components:

1. **Distance-based**: `(speed / 100) * 0.5% per second`
   - At 100 units/s: 0.5% per second
   - At 150 units/s: 0.75% per second

2. **Time-based**: `0.25% per second` (1% every 4 seconds)
   - Simulates metabolic consumption
   - Active even when stationary

3. **Stress multiplier**: `(1 + stress/100)`
   - At 20% stress: 20% faster energy depletion
   - At 50% stress: 50% faster energy depletion

Total energy loss = `(distance + time) * stress_multiplier`

### 4. Stress System

#### Stress Sources

1. **Hazard Zones**
   - Storms (150 unit radius): +1% stress per second
   - Predators (100 unit radius): +1% stress per second
   - Predators move and bounce off boundaries

2. **Distance from Leaders** (followers only)
   - >200 units from nearest leader: +0.5% per 100 units per second
   - Encourages flock cohesion

3. **Safe Zone Recovery**
   - When near 3+ birds and not in hazard: -1% stress per second
   - Promotes flocking behavior

#### Stress Effects
- **Energy**: Increases consumption by stress percentage
- **Speed**: Increases max speed by 10% per 10% stress
- **Behavior**: Stressed birds try to regroup faster

### 5. Hazard System

#### Storm Hazards
- Radius: 150 units
- Effect: +1% stress per second when inside
- Static position

#### Predator Hazards
- Radius: 100 units
- Effect: +1% stress per second when inside
- Movement: 20 units/second in random direction
- Bounces off map boundaries

#### Spawning
- 2-4 hazards per level
- Placed in middle 60% of map (x: 400-1600, y: 200-1000)
- Away from start and destination zones

### 6. Victory Conditions

#### Level Success
- Any birds reaching destination = success
- 50% arrival triggers immediate victory
- All birds dead = failure

#### Migration Progression
- 4 legs per migration (A→B→C→D→Z)
- Survivors continue to next leg
- Gender and leader status preserved between legs

### 7. Flocking Behavior

#### Cohesion
- Attraction to center of nearby birds
- Radius: 120 units

#### Alignment
- Match velocity of nearby birds
- Helps maintain group direction

#### Separation
- Avoid collision with very close birds
- Radius: 30 units
- Strong repulsion force (10x)

#### Initial Phase Boost
- 2x flocking forces when no path is set
- Ensures birds stay together at start

## Strategic Elements

### Path Planning
- Balance direct routes vs. avoiding hazards
- Consider energy conservation
- Plan for flock cohesion

### Stress Management
- Keep followers near leaders
- Avoid hazards when possible
- Use safe zones for recovery

### Energy Conservation
- Minimize distance traveled
- Reduce stress to slow depletion
- Balance speed vs. energy consumption

## Technical Parameters

### World
- Size: 2000 x 1200 units
- Start zone: (200, 600, radius: 100)
- Destination: (1800, 600, radius: 150)

### Simulation
- Tick rate: 30 FPS
- Birds: 100 total (5 leaders, 95 followers)
- Initial energy: 100%
- Max stress: 100%