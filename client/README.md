# Murmuration Client

A Phaser 3 + TypeScript game client for the Murmuration evolution game.

## Features

- ✅ **Phaser 3.86+** - Latest stable version with comprehensive TypeScript support
- ✅ **TypeScript 5+** - Strict mode enabled with comprehensive type checking
- ✅ **Vite** - Fast development server with hot-reload
- ✅ **ESLint + Prettier** - Code quality and formatting tools configured
- ✅ **Vitest** - Fast unit testing framework
- ✅ **Playwright** - End-to-end testing for multiple browsers
- ✅ **Scene System** - Modular Phaser scene architecture
- ✅ **Asset Loading** - Type-safe asset management system
- ✅ **WebSocket Support** - Real-time communication with game server

## Project Structure

```
/client/
├── src/
│   ├── scenes/          # Phaser scene classes
│   ├── systems/         # Game systems and managers  
│   ├── types/           # TypeScript type definitions
│   ├── utils/           # Utility functions and helpers
│   ├── config/          # Configuration files
│   └── main.ts          # Application entry point
├── assets/
│   ├── sprites/         # Image assets
│   └── sounds/          # Audio assets
├── tests/               # Unit tests
├── e2e/                # End-to-end tests
└── dist/               # Build output
```

## Development Commands

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Run tests
npm run test
npm run e2e

# Code quality
npm run lint
npm run format
npm run type-check
```

## Configuration

### TypeScript
- Strict mode enabled
- Path mapping configured (`@/*` → `src/*`)
- Comprehensive type checking with `noUncheckedIndexedAccess`

### Vite
- Hot module replacement
- Optimized Phaser bundling
- Asset processing
- Development proxy support

### ESLint
- TypeScript-aware rules
- Prettier integration
- Game development best practices

## Scene Architecture

The game uses a modular scene system:

1. **LoadingScene** - Asset loading with progress indication
2. **MenuScene** - Main menu and navigation
3. **GameScene** - Core gameplay with real-time updates

Each scene follows the Phaser lifecycle and includes proper TypeScript typing.

## Asset Management

Assets are managed through a type-safe manifest system:
- Centralized asset configuration
- Loading progress tracking
- Error handling and fallbacks
- Development vs production asset paths

## WebSocket Integration

Real-time communication with the Python simulation server:
- Automatic reconnection
- Message type safety
- Connection state management
- Heartbeat support

## Testing Strategy

- **Unit Tests**: Core utilities and game logic
- **E2E Tests**: Full gameplay workflows
- **Visual Regression**: UI consistency checks
- **Performance Tests**: Frame rate and memory usage

## Build Output

- Optimized Phaser bundle (separate chunk)
- Source maps for debugging
- Gzip compression
- Static asset optimization

## Development Notes

- Game server should be running on `ws://localhost:8765` for development
- Hot-reload works for code changes but requires refresh for asset updates  
- Debug mode enabled automatically in development builds
- Performance monitoring available via browser dev tools

## Browser Support

- Chrome 88+
- Firefox 78+
- Safari 14+
- Edge 88+

Mobile browsers supported with touch controls.