# Murmuration

An "influence-not-control" evolution sandbox where players guide migratory micro-bird flocks using environmental signals. Agents learn across seasons via lightweight ML.

## Quick Start

```bash
# Install development environment
make dev

# Run smoke test
make sim-smoke

# Run tests
make test

# Start client dev server
cd client && npm run dev
```

## Project Structure

```
/ sim/                 # Python: env, physics, hazards, RL, evolution
/ client/              # React+Canvas/WebGL UI
/ levels/              # JSON contracts (campaign + test fixtures)
/ configs/             # YAML/JSON: training, sim, CI acceptance thresholds
/ tests/               # pytest, hypothesis, golden replays, Playwright
/ scripts/             # CLI entrypoints (bootstrap, run, train, bench)
/ docs/                # design docs, diagrams
/ experiments/         # notebooks, ablations (no prod code)
```

## Core Systems

- **Agents**: 80-300 birds with energy, stress, genome, and social memory
- **Environment**: 2D world with wind, food, risk fields, and player beacons
- **Machine Learning**: PPO-lite within seasons, neuroevolution between seasons
- **Determinism**: Fixed RNG seeds for reproducible simulations

## Development

See [CLAUDE.md](CLAUDE.md) for comprehensive development guidelines and quality standards.

### Key Commands

- `make lint` - Run Python/TypeScript linters
- `make type` - Run type checkers
- `make test` - Run unit tests
- `make accept` - Run acceptance suite
- `make bench` - Performance benchmark

## Design Documents

- [Full Game & Tech Design Doc](murmuration_full_game_tech_design_doc_v_0.md)
- [Quality & Automation Playbook](CLAUDE.md)

## License

Copyright 2024. All rights reserved.