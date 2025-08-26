# Murmuration Testing Guide

This comprehensive guide covers all aspects of testing the Murmuration client application, from unit tests to end-to-end workflows.

## Table of Contents

- [Testing Philosophy](#testing-philosophy)
- [Test Types and Structure](#test-types-and-structure)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Performance Testing](#performance-testing)
- [Accessibility Testing](#accessibility-testing)
- [CI/CD Integration](#cicd-integration)
- [Troubleshooting](#troubleshooting)

## Testing Philosophy

Our testing approach follows these principles:

1. **Test Pyramid**: More unit tests, fewer integration tests, selective E2E tests
2. **Test-Driven Development**: Write tests first when adding new features
3. **Coverage Goals**: >90% unit test coverage, 100% critical path coverage
4. **Performance First**: All tests include performance expectations
5. **Accessibility By Design**: Every component tested for a11y compliance
6. **Real-World Scenarios**: E2E tests mirror actual user workflows

## Test Types and Structure

### Directory Structure

```
client/
├── src/
│   ├── __tests__/              # Unit tests alongside source
│   │   ├── components/         # Component tests
│   │   ├── hooks/             # Hook tests  
│   │   ├── types/             # Type tests
│   │   ├── integration/       # Integration tests
│   │   ├── visual/            # Visual regression tests
│   │   └── performance/       # Performance tests
│   └── test-utils/            # Testing utilities
│       ├── mocks.ts           # Mock implementations
│       ├── test-utils.tsx     # Custom render functions
│       └── performance-monitor.ts # Performance utilities
├── tests/
│   └── e2e/                   # End-to-end tests
│       ├── game-workflows.spec.ts
│       ├── performance-e2e.spec.ts
│       └── accessibility.spec.ts
└── docs/
    └── testing-guide.md       # This file
```

### Test Categories

#### 1. Unit Tests (`src/__tests__/`)

**Purpose**: Test individual components and functions in isolation
**Tools**: Vitest, React Testing Library, Custom mocks
**Coverage Target**: >90%

```typescript
// Example: Component unit test
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import GameCanvas from '../../components/GameCanvas';
import { createMockGameState } from '../../test-utils/mocks';

describe('GameCanvas Component', () => {
  it('renders agents correctly', () => {
    const gameState = createMockGameState({
      agents: [createMockAgent({ id: 'test-agent' })]
    });
    
    render(<GameCanvas gameState={gameState} />);
    expect(screen.getByRole('img')).toBeInTheDocument();
  });
});
```

#### 2. Integration Tests (`src/__tests__/integration/`)

**Purpose**: Test component interactions and data flow
**Tools**: Vitest, Mock WebSocket server
**Coverage Target**: All major workflows

```typescript
// Example: WebSocket integration test
describe('WebSocket Integration', () => {
  it('handles full duplex communication', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000'));
    
    await waitFor(() => {
      expect(result.current.connectionState).toBe('connected');
    });
    
    // Test command sending and state updates
    act(() => {
      result.current.placeBeacon('food', { x: 100, y: 200 });
    });
    
    // Verify server response handling
    expect(result.current.gameState?.beacons).toHaveLength(1);
  });
});
```

#### 3. Visual Regression Tests (`src/__tests__/visual/`)

**Purpose**: Ensure UI consistency across changes
**Tools**: Canvas comparison utilities
**Coverage Target**: All visual components

```typescript
// Example: Visual regression test
describe('Visual Regression Tests', () => {
  it('renders game state consistently', async () => {
    const gameState = createMockGameState();
    const { container } = render(<GameCanvas gameState={gameState} />);
    
    const currentImage = mockTakeScreenshot(container);
    const baselineImage = mockLoadBaseline('empty-game-state');
    
    const comparison = compareCanvases(currentImage, baselineImage, 0.01);
    expect(comparison.match).toBe(true);
  });
});
```

#### 4. Performance Tests (`src/__tests__/performance/`)

**Purpose**: Ensure application meets performance requirements
**Tools**: Custom FPS monitoring, memory tracking
**Coverage Target**: All performance-critical operations

```typescript
// Example: Performance test
describe('Performance Tests', () => {
  it('maintains 30+ FPS with 200+ agents', async () => {
    const gameState = createMockGameState({
      agents: Array.from({ length: 200 }, createMockAgent)
    });
    
    const { duration } = await measurePerformance(() => {
      render(<GameCanvas gameState={gameState} />);
    }, 100);
    
    expect(duration).toBeLessThan(100);
  });
});
```

#### 5. End-to-End Tests (`tests/e2e/`)

**Purpose**: Test complete user workflows in real browser
**Tools**: Playwright
**Coverage Target**: All critical user paths

```typescript
// Example: E2E test
test('completes level workflow', async ({ page }) => {
  await page.goto('/');
  await page.click('[data-testid="start-level-W1-1"]');
  
  // Place beacon
  await page.click('[data-testid="beacon-type-food"]');
  await page.click('.game-canvas', { position: { x: 400, y: 300 } });
  
  // Verify completion
  await expect(page.locator('[data-testid="level-complete"]')).toBeVisible();
});
```

## Running Tests

### Local Development

```bash
# Run all unit tests
npm run test

# Run tests in watch mode
npm run test:watch

# Run with coverage report
npm run test:coverage

# Run specific test file
npm run test -- GameCanvas.test.tsx

# Run E2E tests
npm run e2e

# Run E2E tests in headed mode (see browser)
npm run e2e:headed

# Run performance tests only
npm run test -- --run src/__tests__/performance/

# Run accessibility tests
npm run e2e -- tests/e2e/accessibility.spec.ts
```

### CI/CD Environment

Tests automatically run on:
- **Push to main/develop**: Full test suite
- **Pull Requests**: Full test suite + cross-browser
- **Nightly**: Performance regression tests
- **Weekly**: Accessibility audits

### Test Commands Reference

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `npm run test` | Run all unit tests | Development, CI |
| `npm run test:coverage` | Generate coverage report | Before commits |
| `npm run e2e` | Run E2E tests | Integration testing |
| `npm run e2e:debug` | Debug E2E with browser open | Debugging failures |
| `npm run test:performance` | Run performance benchmarks | Performance validation |
| `npm run test:visual` | Run visual regression | UI consistency checks |

## Writing Tests

### Best Practices

#### 1. Test Naming Convention

```typescript
describe('Component/Feature Name', () => {
  describe('specific functionality', () => {
    it('should behavior when condition', () => {
      // Test implementation
    });
  });
});
```

#### 2. Arrange-Act-Assert Pattern

```typescript
it('should update agent positions efficiently', () => {
  // Arrange
  const initialState = createMockGameState({ agents: [...] });
  const { rerender } = render(<GameCanvas gameState={initialState} />);
  
  // Act
  const updatedState = createMockGameState({ tick: 1, agents: [...] });
  rerender(<GameCanvas gameState={updatedState} />);
  
  // Assert
  expect(mockPixiApplication.stage.addChild).toHaveBeenCalled();
});
```

#### 3. Use Custom Test Utilities

```typescript
import { renderWithProviders, createMockAgent } from '../test-utils/test-utils';

// Use custom render for components that need providers
const { result } = renderWithProviders(
  <GameCanvas gameState={gameState} />,
  { initialGameState: mockState }
);
```

#### 4. Mock External Dependencies

```typescript
// Mock PIXI.js
vi.mock('pixi.js', () => ({
  Application: vi.fn(() => mockPixiApplication),
  Graphics: vi.fn(() => mockPixiGraphics),
}));

// Mock WebSocket
vi.stubGlobal('WebSocket', MockWebSocket);
```

### Testing React Components

#### Component Props Testing

```typescript
describe('BeaconPanel', () => {
  it('renders all beacon types', () => {
    const gameState = createMockGameState();
    render(<BeaconPanel gameState={gameState} />);
    
    BEACON_TYPES.forEach(beaconType => {
      expect(screen.getByText(beaconType.name)).toBeInTheDocument();
    });
  });
  
  it('handles beacon selection', async () => {
    const onSelectBeacon = vi.fn();
    render(
      <BeaconPanel 
        gameState={createMockGameState()} 
        onSelectBeacon={onSelectBeacon}
      />
    );
    
    await userEvent.click(screen.getByText('Food Beacon'));
    expect(onSelectBeacon).toHaveBeenCalledWith('food');
  });
});
```

#### State Management Testing

```typescript
describe('useWebSocket Hook', () => {
  it('manages connection state correctly', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000'));
    
    expect(result.current.connectionState).toBe('connecting');
    
    await waitFor(() => {
      expect(result.current.connectionState).toBe('connected');
    });
  });
});
```

### Testing Game Logic

#### Game State Validation

```typescript
describe('Game State Validation', () => {
  it('validates agent energy bounds', () => {
    const agent = createMockAgent({ energy: 150 }); // Invalid
    
    // In real implementation, this should throw or clamp
    expect(() => validateAgent(agent)).toThrow('Energy out of bounds');
  });
});
```

#### Physics System Testing

```typescript
describe('Physics System', () => {
  it('calculates agent movement correctly', () => {
    const agent = createMockAgent({ 
      position: { x: 0, y: 0 },
      velocity: { x: 1, y: 1 }
    });
    
    const newPosition = calculateNextPosition(agent, 1000); // 1 second
    
    expect(newPosition).toEqual({ x: 1, y: 1 });
  });
});
```

### Performance Test Guidelines

#### FPS Testing

```typescript
describe('FPS Performance', () => {
  it('maintains target FPS under load', async () => {
    const heavyLoad = createMockGameState({
      agents: Array.from({ length: 300 }, createMockAgent)
    });
    
    const fpsMonitor = new FPSMonitor();
    fpsMonitor.start();
    
    render(<GameCanvas gameState={heavyLoad} />);
    
    await waitForFrames(60); // 1 second at 60 FPS
    
    fpsMonitor.stop();
    
    expect(fpsMonitor.getAverageFPS()).toBeGreaterThan(30);
  });
});
```

#### Memory Leak Testing

```typescript
describe('Memory Management', () => {
  it('cleans up resources on unmount', () => {
    const { unmount } = render(<GameCanvas gameState={gameState} />);
    
    unmount();
    
    expect(mockPixiApplication.destroy).toHaveBeenCalled();
  });
});
```

### Accessibility Test Guidelines

#### Screen Reader Testing

```typescript
describe('Screen Reader Support', () => {
  it('provides meaningful aria-labels', () => {
    render(<GameCanvas gameState={gameState} />);
    
    const canvas = screen.getByRole('img');
    expect(canvas).toHaveAttribute('aria-label');
    expect(canvas.getAttribute('aria-label')).toContain('population');
  });
});
```

#### Keyboard Navigation Testing

```typescript
describe('Keyboard Navigation', () => {
  it('supports full keyboard interaction', async () => {
    render(<BeaconPanel gameState={gameState} />);
    
    // Tab to first beacon
    await userEvent.keyboard('{Tab}');
    expect(screen.getByText('Light Beacon')).toHaveFocus();
    
    // Select with Enter
    await userEvent.keyboard('{Enter}');
    expect(onSelectBeacon).toHaveBeenCalledWith('light');
  });
});
```

## Performance Testing

### Benchmarking Standards

Our performance targets:

| Metric | Target | Measurement |
|--------|---------|-------------|
| Initial Load | < 3s | Time to interactive |
| FPS (100 agents) | > 55 | Average over 5s |
| FPS (300 agents) | > 30 | Average over 5s |
| Memory Usage | < 200MB | Peak during gameplay |
| Frame Time | < 16.67ms | 60 FPS requirement |

### Running Performance Tests

```bash
# Run performance test suite
npm run test:performance

# Run with detailed metrics
npm run test:performance -- --reporter=verbose

# Run specific performance test
npm run test -- --run performance.test.ts::FPS
```

### Writing Performance Tests

```typescript
import { measurePerformance, FPSMonitor } from '../test-utils/performance-monitor';

describe('Rendering Performance', () => {
  it('renders 200 agents within budget', async () => {
    const agents = Array.from({ length: 200 }, createMockAgent);
    const gameState = createMockGameState({ agents });
    
    const { duration } = await measurePerformance(() => {
      render(<GameCanvas gameState={gameState} />);
    }, 100); // 100ms budget
    
    expect(duration).toBeLessThan(100);
    console.log(`200 agents rendered in ${duration.toFixed(2)}ms`);
  });
});
```

### Performance Monitoring in Production

```typescript
import { ProductionPerformanceMonitor } from '../test-utils/performance-monitor';

// Initialize in production code
const perfMonitor = new ProductionPerformanceMonitor(300, (metrics) => {
  // Send metrics to monitoring service
  analytics.track('performance_metrics', metrics);
});

perfMonitor.start();
```

## Accessibility Testing

### WCAG 2.1 AA Compliance

Our accessibility standards:

- **Contrast Ratio**: Minimum 4.5:1 for normal text
- **Touch Targets**: Minimum 44x44 pixels
- **Keyboard Navigation**: All functionality accessible via keyboard
- **Screen Reader**: Full compatibility with NVDA, JAWS, VoiceOver
- **Focus Management**: Clear focus indicators and logical tab order

### Automated Accessibility Testing

```typescript
import { checkColorContrast, checkTouchTargetSize } from '../test-utils/test-utils';

describe('Accessibility Compliance', () => {
  it('meets color contrast requirements', () => {
    render(<BeaconPanel gameState={gameState} />);
    
    const buttons = screen.getAllByRole('button');
    buttons.forEach(button => {
      const styles = window.getComputedStyle(button);
      expect(checkColorContrast(
        styles.color, 
        styles.backgroundColor
      )).toBe(true);
    });
  });
  
  it('has adequate touch targets', () => {
    render(<BeaconPanel gameState={gameState} />);
    
    const interactiveElements = screen.getAllByRole('button');
    interactiveElements.forEach(element => {
      expect(checkTouchTargetSize(element)).toBe(true);
    });
  });
});
```

### Manual Accessibility Testing Checklist

Before release, manually verify:

- [ ] Tab navigation works throughout the application
- [ ] Screen reader announces all important state changes
- [ ] Focus is managed properly in modals and overlays
- [ ] All images have appropriate alt text
- [ ] Form controls have associated labels
- [ ] Error messages are announced to screen readers
- [ ] High contrast mode works correctly
- [ ] Reduced motion preferences are respected

## CI/CD Integration

### GitHub Actions Workflows

Our CI/CD pipeline includes:

1. **ci-cd.yml**: Main testing pipeline
2. **performance-monitoring.yml**: Nightly performance regression tests
3. **accessibility-audit.yml**: Weekly accessibility compliance checks

### Pipeline Stages

1. **Code Quality**: Linting, TypeScript checking
2. **Unit Tests**: Component and utility function tests
3. **Integration Tests**: WebSocket and cross-component tests
4. **Visual Regression**: Screenshot comparison tests
5. **E2E Tests**: Full user workflow testing
6. **Performance Tests**: Benchmarking and regression detection
7. **Accessibility Audits**: WCAG compliance and screen reader testing
8. **Cross-browser Testing**: Chrome, Firefox, Safari compatibility
9. **Mobile Testing**: Responsive design and touch interaction

### Quality Gates

Code cannot be merged unless:

- [ ] All unit tests pass (>90% coverage)
- [ ] Integration tests pass
- [ ] Performance regression check passes
- [ ] No accessibility violations (critical/serious)
- [ ] Cross-browser E2E tests pass
- [ ] Build succeeds without errors

## Troubleshooting

### Common Issues

#### Test Timeouts

```typescript
// Increase timeout for slow tests
test('slow integration test', async ({ page }) => {
  // ... test code
}, { timeout: 60000 }); // 60 second timeout
```

#### Mock Issues

```typescript
// Clear mocks between tests
beforeEach(() => {
  vi.clearAllMocks();
});

// Reset global mocks
afterEach(() => {
  vi.unstubAllGlobals();
});
```

#### WebSocket Connection Issues

```typescript
// Ensure proper cleanup
afterEach(() => {
  if (mockWs) {
    mockWs.close();
  }
});
```

#### Performance Test Flakiness

```typescript
// Use consistent test environment
beforeEach(() => {
  setupTestEnvironment();
  
  // Ensure consistent timing
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});
```

### Debug Tools

#### Visual Test Debugging

```bash
# Run single visual test with comparison images
npm run test -- --run visual-regression.test.ts::specific-test

# Generate new baseline images
npm run test:visual -- --update-baselines
```

#### E2E Test Debugging

```bash
# Run with browser visible
npm run e2e:headed

# Run with Playwright inspector
npm run e2e -- --debug

# Generate trace files
npm run e2e -- --trace=on
```

#### Performance Debugging

```typescript
// Add detailed logging
const { duration, result } = await measurePerformance(() => {
  console.log('Starting performance test');
  const component = render(<GameCanvas gameState={gameState} />);
  console.log('Render completed');
  return component;
});

console.log(`Performance test completed in ${duration}ms`);
```

### Getting Help

1. **Check the test output**: Most failures include detailed error messages
2. **Review artifacts**: CI uploads test results, screenshots, and reports
3. **Run locally**: Reproduce issues in your development environment
4. **Use debug modes**: Run tests with debugging enabled
5. **Check documentation**: This guide and component-specific docs
6. **Team resources**: Ask in team channels or create GitHub issues

---

## Quick Reference

### Test Commands
```bash
npm run test                    # Unit tests
npm run test:coverage          # Coverage report
npm run e2e                    # E2E tests
npm run test:performance       # Performance tests
npm run test:visual           # Visual regression
```

### Key Files
- `src/test-utils/mocks.ts` - Mock implementations
- `src/test-utils/test-utils.tsx` - Testing utilities
- `playwright.config.ts` - E2E test configuration
- `vite.config.ts` - Unit test configuration

### Quality Standards
- Unit test coverage: >90%
- Performance: 30+ FPS with 300 agents
- Accessibility: WCAG 2.1 AA compliance
- Cross-browser: Chrome, Firefox, Safari support