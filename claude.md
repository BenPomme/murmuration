# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Murmuration is an "influence-not-control" evolution game where players guide bird flocks through hazards using environmental beacons. The flock evolves across generations, learning from survival experiences.

## Core Architecture

### Simulation Engine (`sim/`)
- **`simulation_evolved.py`**: Main game loop with breed evolution, hazard behaviors, and flock dynamics
- **`simulation_game.py`**: Legacy game simulation (being phased out for evolved version)
- **`server.py`**: WebSocket server managing client connections and game state with ping/pong heartbeats
- **Agent System**: Birds have energy, stress, hazard detection, and beacon response traits
- **Breed Evolution**: Traits improve based on survival rates and hazard encounters

### Modern Client (`client/`)
- **TypeScript + Phaser 3**: Real-time game client with 1280x720 canvas, WebGL rendering
- **`GameScene.ts`**: Main game scene handling bird flocks, beacon placement, hazard visualization
- **`WebSocketClient.ts`**: Auto-reconnecting WebSocket client with message queuing and heartbeat
- **`AudioManager.ts`**: Procedural audio system for UI feedback and ambient sounds
- **Vite Build System**: Fast HMR development with optimized Phaser bundling

### Key Game Mechanics
1. **Hazards with Distinct Behaviors**:
   - Tornadoes: Confusion effect, 10% kill chance, energy drain
   - Predators: Direct pursuit, 20% kill chance, triggers flock panic
   - Graduated danger zones (outer/middle/inner) with visual feedback

2. **Beacons** (player-placed influencers):
   - Food: Energy restoration + attraction
   - Shelter: Stress reduction + slowing
   - Thermal: Forward boost + energy

3. **Evolution System**:
   - 5 evolvable traits: hazard_awareness, energy_efficiency, flock_cohesion, beacon_sensitivity, stress_resilience
   - Breeds evolve based on performance each level
   - Save/load breed data as JSON

## Common Development Commands

```bash
# Setup development environment (recommended)
make dev

# Alternative manual setup
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .[dev]
cd client && npm install

# Run the game server
python -m sim.server

# Run client development server (Vite + TypeScript)
cd client && npm run dev

# Testing and quality checks
make test           # Python unit tests
make lint           # Python + TypeScript linting
make type           # Python + TypeScript type checking
make accept         # Full acceptance test suite
make sim-smoke      # 150 agents @ 60Hz performance test

# Client-specific commands
cd client
npm run build       # Production build
npm run test        # Vitest unit tests
npm run e2e         # Playwright end-to-end tests
npm run format      # Prettier formatting
```

## Current Implementation Status

### Working Features
- **Python Backend**: WebSocket server with real-time game state updates, stable connections with ping/pong heartbeat
- **TypeScript Client**: Modern Phaser 3 game client with 1280x720 resolution, real-time bird flocking visualization
- **9 Playable Levels**: Varying difficulty (levels/levels.json) from training (W1) to expert (W4)
- **Evolution System**: Breed persistence across levels with trait evolution based on survival performance  
- **Multiple UIs**: Legacy HTML demos (`demo_*.html`) + modern TypeScript/Phaser client (`client/`)
- **Hazard System**: Distinct tornado/predator behaviors with graduated danger zones and visual feedback
- **Beacon Placement**: UI-based beacon selection with immediate visual feedback (Food, Shelter, Thermal types)
- **Audio System**: Procedural Web Audio API sounds for UI feedback and ambient audio
- **Emergency Pulse**: Server-side emergency abilities for flock guidance

### Architecture Decisions
- **RNG Determinism**: Pass `np.random.Generator` explicitly, never use global random
- **State Management**: Complete reset between level attempts via `reset()` method
- **Performance Target**: 300 agents @ 60Hz (currently optimized for 100-200)
- **Networking**: JSON over WebSocket with automatic reconnection, ping_interval=20s, ping_timeout=10s
- **Coordinate System**: 2000x1200 game world, scaled to 1280x720 client canvas
- **Client Architecture**: Event-driven Phaser scenes with WebSocket message handling
- **Asset Loading**: Procedural graphics as fallback, external sprites for enhanced visuals

## Code Quality Standards

### Python
- Black formatting (line length 100)
- Type hints required for public functions
- Structured JSON logging via `get_logger()`
- No global state for RNG
- Docstrings for all classes and public methods

### TypeScript/JavaScript
- ESLint + Prettier with TypeScript strict mode
- Explicit type definitions for WebSocket message protocols
- Event-driven architecture for Phaser scene communication
- Modular config system (`config/gameConfig.ts`, `config/assets.ts`)
- No console.log in production - use proper debugging tools

### Game Balance
- Hazards must be escapable but challenging
- Energy drain balanced with beacon restoration
- Evolution improvements capped to prevent overpowered breeds
- Level progression from training (W1) to expert (W4)

## Testing Approach

### Unit Tests (`tests/`)
- Physics: Reynolds boids, energy decay, collision
- Beacons: Influence fields, placement, removal  
- Hazards: Spawn rates, damage calculations
- ML: PPO-lite convergence, reward shaping

### Integration Tests
- WebSocket message handling
- Level loading and reset
- Breed evolution across levels
- Save/load functionality

### Manual Testing Checklist
- [ ] Birds respond to all beacon types
- [ ] Hazards deal appropriate damage
- [ ] Level progression works
- [ ] Breed traits evolve correctly
- [ ] UI controls are accessible

## Known Issues & TODOs

1. **Performance**: Large flocks (>200) may cause frame drops
2. **ML Training**: PPO-lite and neuroevolution stubs need implementation
3. **Client-Server Communication**: Beacon placement events need to properly trigger server simulation updates
4. **Connection Status**: UI connection status display doesn't always reflect actual WebSocket state
5. **Testing Coverage**: Need more integration tests for evolution system and client-server interaction

## File Structure

```
/sim/
  core/           # Agent, types, physics fundamentals
  hazards/        # Hazard implementations (storms, predators)
  beacons/        # Beacon influence system
  ml/             # PPO-lite, neuroevolution (stubs)
  cli/            # Command-line interface
  server.py       # WebSocket server with heartbeat support
  simulation_evolved.py  # Main game simulation
  
/client/          # TypeScript + Phaser 3 game client
  src/
    GameScene.ts  # Main game scene with bird flocks and beacon placement
    WebSocketClient.ts  # Auto-reconnecting WebSocket client
    AudioManager.ts     # Procedural Web Audio API system
    config/       # Game configuration (resolution, networking, assets)
    types/        # TypeScript interfaces for game state and messages
  
/levels/          # Level definitions (JSON)
/tests/           # Python test suite + client E2E tests
/demo_*.html      # Legacy HTML game UIs
```

## Debugging Tips

### Python Server
- Server logs JSON to stdout - pipe through `jq` for readability
- Check `agent.alive`, `agent.energy`, and `agent.stress` for death causes
- Hazard `danger_zones` array controls damage gradients
- Breed traits are 0-1 normalized (except energy_efficiency which is a multiplier)
- WebSocket connection logs show "Client connected/disconnected" with client count

### TypeScript Client
- Use browser DevTools console to see WebSocket connection status and message debugging
- GameScene event logging shows beacon placement attempts and UI interactions
- WebSocket client logs connection state changes and automatic reconnection attempts
- Check `client/src/config/gameConfig.ts` for coordinate system and networking settings
- Phaser game object debugging: `this.game.scene.scenes[0]` in console to access GameScene

## Security Considerations

- No eval/exec in simulation code
- WebSocket server binds to localhost only by default
- No external API calls without explicit configuration
- Input validation on all client messages