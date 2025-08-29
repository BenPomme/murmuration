# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Murmuration is a strategic multi-generational migration game where players guide bird flocks through dangerous journeys using environmental influence, not direct control. Players navigate A→B→C→D→Z migration legs, managing energy, hazards, and genetic evolution across generations.

**📖 For detailed game mechanics and rules, see [GAME_RULES.md](./GAME_RULES.md)**

## Core Architecture

### Simulation Engine (`sim/`)
- **`simulation_evolved.py`**: Strategic migration simulation with 4-leg journeys (A→B→C→D→Z)
- **`server.py`**: WebSocket server with manual migration progression and level completion handling
- **`migration_system.py`**: Multi-leg journey management and progression tracking
- **Agent System**: 100 birds with individual genetics, energy management, and survival mechanics
- **Environmental Food System**: Visible food havens requiring strategic routing decisions

### Modern Client (`client/`)
- **TypeScript + Phaser 3**: Strategic migration game client with edge-positioned UI panels
- **`GameScene.ts`**: Bird flocking, environmental food sites, hazard visualization with sprite integration
- **`UIScene.ts`**: Level progression panels, genetics tracking, beacon controls with clean layout
- **`WebSocketClient.ts`**: Auto-reconnecting client with migration progression message handling
- **Asset System**: Custom sprite integration (`client/assets/sprites/`) with procedural fallbacks

### Key Game Mechanics

1. **Strategic Migration System**:
   - 4-leg journeys: A→B→C→D→Z progression with manual advancement
   - Environmental food sites requiring strategic detours for energy restoration
   - Natural victory conditions (any arrivals = success, all deaths = failure)
   - Proper survivor transfer between migration legs

2. **Environmental Hazards**:
   - Tornadoes: Rotating sprite visuals, energy drain, confusion effects
   - Predators: Chase mechanics with increased stress generation (40% vs 25%)
   - Distance-based energy consumption forcing food site usage

3. **Wind Beacon System** (replaced food beacons):
   - Wind Up/Down: Localized effects (80-unit radius) with contact-based influence
   - Tiered effectiveness: Direct contact (>0.7) vs cohesion-based following (0.3-0.7)
   - Budget system: 4-5 beacons maximum per level with automatic clearing

4. **Genetics & Evolution**:
   - 6 traits: hazard_awareness, energy_efficiency, flock_cohesion, beacon_sensitivity, stress_resilience, leadership
   - Breed evolution between migrations based on survival performance
   - Generation tracking with proper UI display (Migration X - Leg Y/4)

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
- **Strategic Migration System**: Complete A→B→C→D→Z journey progression with manual advancement
- **Environmental Food System**: Visible green food circles at strategic locations requiring detours
- **Natural Victory/Failure**: Dynamic completion based on actual arrivals, proper failure panels with retry
- **Professional UI**: Edge-positioned panels (left: telemetry, right: genetics, bottom: beacons)
- **Wind Beacon Strategy**: Localized wind effects with contact-based influence and budget limits
- **Sprite Integration**: Custom tornado sprites, bird graphics, and UI assets with fallback system
- **Population Management**: Accurate 100-bird populations with proper survivor tracking
- **Level Progression**: Completion panels, continue buttons, and proper state management

### Architecture Decisions
- **Migration Progression**: Manual A→B→C→D→Z advancement with completion panels and survivor tracking
- **UI Layout**: Edge-positioned panels to avoid gameplay blocking, elegant transparency design
- **Victory Logic**: Natural completion (no healthy birds left OR 60+ seconds) vs arbitrary thresholds
- **Beacon Strategy**: Wind-based influence system with localized contact effects and budget limits
- **Asset Pipeline**: Custom sprite integration with procedural fallbacks for missing assets
- **Level State**: Proper pause/resume flow, victory protection, and crash prevention
- **Performance Target**: 100 agents @ 30Hz server updates with stable WebSocket communication

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

## Current Phase Status

### ✅ PHASE 1 COMPLETE: Strategic Foundation
- Manual migration progression (A→B→C→D→Z structure) 
- Environmental food system with visible strategic placement
- Professional UI layout with edge-positioned panels
- Natural victory/failure conditions with proper end panels
- Wind beacon strategy system with budget management
- Population management with accurate survivor tracking

### 🎯 READY FOR PHASE 2: Strategic Depth
- Difficulty scaling across migrations
- Multi-leg journey templates with procedural generation  
- Advanced hazard behaviors (moving storms, predator chases)
- Enhanced player decision-making tools and feedback

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