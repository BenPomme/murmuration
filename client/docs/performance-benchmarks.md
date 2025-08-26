# Performance Benchmarks and Targets

This document defines performance standards, benchmarking procedures, and optimization guidelines for the Murmuration client application.

## Performance Targets

### Core Performance Requirements

| Metric | Target | Measurement Method | Acceptance Criteria |
|--------|--------|-------------------|-------------------|
| **Initial Load Time** | < 3.0s | Time to Interactive | 95th percentile |
| **Level Load Time** | < 2.0s | Game state ready | Average |
| **Frame Rate (Light Load)** | > 55 FPS | 50 agents, 5s average | Minimum |
| **Frame Rate (Medium Load)** | > 45 FPS | 150 agents, 5s average | Minimum |
| **Frame Rate (Heavy Load)** | > 30 FPS | 300 agents, 5s average | Minimum |
| **Frame Time** | < 16.67ms | Per frame processing | 95th percentile |
| **Memory Usage (Peak)** | < 200MB | During heavy gameplay | Maximum |
| **Memory Growth** | < 50MB | Over 10 minutes gameplay | Per session |
| **WebSocket Latency** | < 100ms | Round-trip message | Average |
| **Canvas Render Time** | < 10ms | Single frame render | 95th percentile |

### Device-Specific Targets

#### Desktop (High-end)
- **CPU**: Intel i5-8400 / AMD Ryzen 5 2600 or better
- **RAM**: 8GB or more
- **GPU**: Discrete graphics or Intel UHD 630+
- **Target FPS**: 60 FPS with 300 agents
- **Memory Budget**: 250MB peak

#### Desktop (Mid-range)
- **CPU**: Intel i3-7100 / AMD Ryzen 3 1200
- **RAM**: 4GB minimum
- **GPU**: Intel HD 620 or equivalent
- **Target FPS**: 45 FPS with 200 agents
- **Memory Budget**: 150MB peak

#### Mobile (High-end)
- **Device**: iPhone 12+ / Samsung Galaxy S21+
- **RAM**: 6GB or more
- **Target FPS**: 45 FPS with 150 agents
- **Memory Budget**: 100MB peak
- **Battery Impact**: < 20% per hour

#### Mobile (Mid-range)
- **Device**: iPhone SE 2020 / Samsung Galaxy A52
- **RAM**: 3GB minimum
- **Target FPS**: 30 FPS with 100 agents
- **Memory Budget**: 80MB peak
- **Battery Impact**: < 30% per hour

## Benchmarking Procedures

### Automated Performance Testing

#### Unit Test Performance Benchmarks

```typescript
// Example: Rendering performance test
describe('Rendering Performance', () => {
  it('renders 100 agents within 50ms', async () => {
    const gameState = createMockGameState({
      agents: Array.from({ length: 100 }, createMockAgent)
    });
    
    const { duration } = await measurePerformance(() => {
      render(<GameCanvas gameState={gameState} />);
    }, 50); // 50ms budget
    
    expect(duration).toBeLessThan(50);
    
    // Report to benchmark tracking
    reportBenchmark('render_100_agents', duration);
  });
});
```

#### E2E Performance Testing

```typescript
// Example: Full workflow performance
test('complete level workflow under 30 seconds', async ({ page }) => {
  const startTime = Date.now();
  
  await page.goto('/');
  await page.click('[data-testid="start-level-W1-1"]');
  
  // Speed up to complete quickly
  await page.click('[data-testid="speed-4x"]');
  
  // Complete level
  await expect(page.locator('[data-testid="level-complete"]')).toBeVisible();
  
  const totalTime = Date.now() - startTime;
  expect(totalTime).toBeLessThan(30000);
});
```

### Manual Benchmarking Protocol

#### Pre-Benchmark Setup

1. **Clean Environment**
   - Fresh browser instance
   - Clear cache and storage
   - Close unnecessary applications
   - Ensure stable network connection

2. **Measurement Tools**
   - Chrome DevTools Performance tab
   - WebPageTest for loading metrics
   - Lighthouse for comprehensive audits
   - Custom performance monitoring

3. **Test Scenarios**
   - Light load: 50 agents, minimal beacons
   - Medium load: 150 agents, 3-5 beacons
   - Heavy load: 300 agents, 10+ beacons
   - Stress test: Maximum supported configuration

#### Benchmarking Steps

1. **Initial Load Benchmark**
   ```bash
   # Run Lighthouse audit
   lighthouse http://localhost:3000 --output=json --chrome-flags="--headless"
   
   # Key metrics:
   # - First Contentful Paint
   # - Largest Contentful Paint  
   # - Time to Interactive
   # - Cumulative Layout Shift
   ```

2. **Runtime Performance Benchmark**
   ```typescript
   // Enable performance monitoring
   const monitor = new ProductionPerformanceMonitor();
   monitor.start();
   
   // Run test scenario for 5 minutes
   // Record FPS, memory, render times
   
   const report = monitor.generateReport();
   console.log(report);
   ```

3. **Memory Profiling**
   ```javascript
   // Chrome DevTools Memory tab
   // 1. Record heap snapshots at intervals
   // 2. Check for memory leaks
   // 3. Analyze object retention
   // 4. Verify garbage collection
   ```

4. **Network Performance**
   ```bash
   # Simulate various network conditions
   # - Fast 3G: 1.6 Mbps down, 750 Kbps up, 300ms latency
   # - Slow 3G: 400 Kbps down, 400 Kbps up, 400ms latency
   # - 4G: 9 Mbps down, 9 Mbps up, 170ms latency
   ```

## Performance Analysis Framework

### Key Performance Indicators (KPIs)

#### Rendering Performance
- **Frames Per Second (FPS)**: Smoothness of animation
- **Frame Time**: Time to render single frame
- **Draw Calls**: Number of GPU operations
- **Vertex Count**: Geometry complexity

#### Memory Performance
- **Heap Usage**: JavaScript memory consumption
- **GPU Memory**: Texture and buffer usage
- **Object Count**: Number of active game objects
- **Garbage Collection**: Frequency and duration

#### Network Performance
- **Connection Time**: WebSocket establishment
- **Message Latency**: Round-trip time
- **Throughput**: Messages per second
- **Reconnection Time**: Recovery from disconnection

#### User Experience
- **Time to Interactive**: When user can interact
- **Input Latency**: Response to user actions
- **Loading States**: Perceived performance
- **Error Recovery**: Graceful degradation

### Performance Monitoring Dashboard

```typescript
interface PerformanceMetrics {
  // Rendering
  avgFPS: number;
  minFPS: number;
  maxFrameTime: number;
  droppedFrames: number;
  
  // Memory
  heapUsed: number;
  heapTotal: number;
  memoryGrowth: number;
  gcFrequency: number;
  
  // Network
  wsLatency: number;
  wsReconnects: number;
  messageRate: number;
  
  // Game State
  agentCount: number;
  beaconCount: number;
  levelDifficulty: number;
  
  // Environment
  deviceSpecs: DeviceInfo;
  browserInfo: BrowserInfo;
  timestamp: number;
}
```

### Regression Detection

#### Automated Regression Testing

```typescript
describe('Performance Regression Tests', () => {
  it('detects FPS regression', async () => {
    const currentFPS = await measureGameplayFPS();
    const baselineFPS = await loadPerformanceBaseline('fps');
    
    const regressionThreshold = 0.1; // 10%
    const change = (currentFPS - baselineFPS) / baselineFPS;
    
    if (change < -regressionThreshold) {
      throw new Error(`FPS regression detected: ${(change * 100).toFixed(1)}%`);
    }
    
    // Update baseline if improvement
    if (change > 0.05) {
      await updatePerformanceBaseline('fps', currentFPS);
    }
  });
});
```

#### Performance Budget Monitoring

```yaml
# performance-budget.yml
budgets:
  initial-load:
    firstContentfulPaint: 1500ms
    timeToInteractive: 3000ms
    totalSize: 2MB
    
  runtime:
    fps-light: 55
    fps-medium: 45  
    fps-heavy: 30
    memory-peak: 200MB
    
  network:
    websocket-latency: 100ms
    reconnection-time: 2s
```

## Optimization Strategies

### Rendering Optimizations

#### Agent Rendering
```typescript
// Use object pooling for agents
class AgentPool {
  private pool: PixiAgent[] = [];
  private active: Set<PixiAgent> = new Set();
  
  acquire(): PixiAgent {
    const agent = this.pool.pop() || new PixiAgent();
    this.active.add(agent);
    return agent;
  }
  
  release(agent: PixiAgent): void {
    this.active.delete(agent);
    agent.reset();
    this.pool.push(agent);
  }
}
```

#### Culling and LOD
```typescript
// Frustum culling for off-screen agents
function cullOffScreenAgents(agents: Agent[], viewport: Rectangle): Agent[] {
  return agents.filter(agent => 
    viewport.contains(agent.position.x, agent.position.y)
  );
}

// Level of detail based on distance
function getLODLevel(agent: Agent, camera: Camera): number {
  const distance = Vector2.distance(agent.position, camera.position);
  if (distance > 1000) return 0; // Lowest detail
  if (distance > 500) return 1;   // Medium detail
  return 2; // Full detail
}
```

#### Efficient Updates
```typescript
// Batch canvas updates
class CanvasRenderer {
  private dirtyRegions: Rectangle[] = [];
  
  markDirty(region: Rectangle): void {
    this.dirtyRegions.push(region);
  }
  
  render(): void {
    // Only redraw dirty regions
    this.dirtyRegions.forEach(region => {
      this.renderRegion(region);
    });
    this.dirtyRegions.length = 0;
  }
}
```

### Memory Optimizations

#### Object Reuse
```typescript
// Reuse vectors and other frequently created objects
const tempVector = new Vector2();

function updatePosition(agent: Agent): void {
  tempVector.set(agent.velocity.x, agent.velocity.y);
  tempVector.multiplyScalar(deltaTime);
  agent.position.add(tempVector);
}
```

#### Efficient Data Structures
```typescript
// Use TypedArrays for large datasets
class AgentManager {
  private positions: Float32Array;
  private velocities: Float32Array;
  private energies: Float32Array;
  
  constructor(maxAgents: number) {
    this.positions = new Float32Array(maxAgents * 2);  // x, y pairs
    this.velocities = new Float32Array(maxAgents * 2);
    this.energies = new Float32Array(maxAgents);
  }
}
```

### Network Optimizations

#### Message Batching
```typescript
class MessageBatcher {
  private batch: OutgoingMessage[] = [];
  private batchTimer: number | null = null;
  
  send(message: OutgoingMessage): void {
    this.batch.push(message);
    
    if (!this.batchTimer) {
      this.batchTimer = setTimeout(() => {
        this.flush();
      }, 16); // 60 FPS
    }
  }
  
  private flush(): void {
    if (this.batch.length > 0) {
      this.websocket.send(JSON.stringify({ batch: this.batch }));
      this.batch.length = 0;
    }
    this.batchTimer = null;
  }
}
```

#### Delta Compression
```typescript
// Only send changed properties
function createDeltaUpdate(
  previous: GameState, 
  current: GameState
): Partial<GameState> {
  const delta: Partial<GameState> = {};
  
  if (previous.tick !== current.tick) {
    delta.tick = current.tick;
  }
  
  // Only include agents that changed
  const changedAgents = current.agents.filter((agent, index) => 
    !previous.agents[index] || 
    !isEqual(previous.agents[index], agent)
  );
  
  if (changedAgents.length > 0) {
    delta.agents = changedAgents;
  }
  
  return delta;
}
```

## Device-Specific Optimizations

### Mobile Optimizations

#### Touch Performance
```typescript
// Throttle touch events
let lastTouchTime = 0;
const TOUCH_THROTTLE = 16; // ~60 FPS

element.addEventListener('touchmove', (event) => {
  const now = performance.now();
  if (now - lastTouchTime >= TOUCH_THROTTLE) {
    handleTouchMove(event);
    lastTouchTime = now;
  }
});
```

#### Battery Optimization
```typescript
// Reduce performance on low battery
class PowerManager {
  private batteryLevel = 1.0;
  private isCharging = true;
  
  async initialize(): Promise<void> {
    if ('getBattery' in navigator) {
      const battery = await navigator.getBattery();
      this.batteryLevel = battery.level;
      this.isCharging = battery.charging;
    }
  }
  
  getPerformanceProfile(): PerformanceProfile {
    if (!this.isCharging && this.batteryLevel < 0.2) {
      return 'power-saver'; // Reduce FPS, agent count
    }
    return 'normal';
  }
}
```

### Low-End Device Adaptations

```typescript
// Detect device capabilities
class DeviceDetector {
  static getDeviceClass(): 'low' | 'medium' | 'high' {
    const memory = (navigator as any).deviceMemory || 4;
    const cores = navigator.hardwareConcurrency || 2;
    
    if (memory <= 2 || cores <= 2) return 'low';
    if (memory <= 4 || cores <= 4) return 'medium';
    return 'high';
  }
  
  static getOptimalSettings(): GameSettings {
    const deviceClass = this.getDeviceClass();
    
    switch (deviceClass) {
      case 'low':
        return {
          maxAgents: 100,
          targetFPS: 30,
          particleEffects: false,
          backgroundComplexity: 'simple',
        };
      case 'medium':
        return {
          maxAgents: 200,
          targetFPS: 45,
          particleEffects: true,
          backgroundComplexity: 'medium',
        };
      case 'high':
        return {
          maxAgents: 300,
          targetFPS: 60,
          particleEffects: true,
          backgroundComplexity: 'high',
        };
    }
  }
}
```

## Performance Testing Infrastructure

### Continuous Performance Monitoring

```yaml
# .github/workflows/performance-monitoring.yml
name: Performance Monitoring

on:
  schedule:
    - cron: '0 2 * * *' # Daily at 2 AM

jobs:
  performance-baseline:
    runs-on: ubuntu-latest
    
    steps:
      - name: Run performance tests
        run: npm run test:performance
        
      - name: Compare with baseline
        run: |
          node scripts/compare-performance.js \
            --current=./performance-results.json \
            --baseline=./performance-baseline.json \
            --threshold=10
```

### Performance Dashboard

```typescript
// Performance monitoring service integration
class PerformanceTracker {
  private metrics: PerformanceMetrics[] = [];
  
  track(event: string, metrics: Record<string, number>): void {
    // Send to monitoring service (e.g., DataDog, New Relic)
    analytics.track('performance_metric', {
      event,
      timestamp: Date.now(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      ...metrics
    });
  }
  
  startSession(): void {
    this.track('session_start', {
      memory_limit: this.getMemoryLimit(),
      cpu_cores: navigator.hardwareConcurrency,
      device_pixel_ratio: window.devicePixelRatio,
    });
  }
  
  trackFrameRate(fps: number): void {
    this.track('frame_rate', { fps });
  }
  
  trackMemoryUsage(usage: MemoryInfo): void {
    this.track('memory_usage', {
      used: usage.usedJSHeapSize,
      total: usage.totalJSHeapSize,
      limit: usage.jsHeapSizeLimit,
    });
  }
}
```

## Performance Debugging Guide

### Common Performance Issues

#### Frame Rate Drops
1. **Identify bottlenecks**: Use Chrome DevTools Performance tab
2. **Check agent count**: Reduce if exceeding device capacity
3. **Optimize rendering**: Enable culling and LOD
4. **Profile scripts**: Look for expensive calculations
5. **Check memory**: Ensure no memory leaks

#### Memory Leaks
1. **Take heap snapshots**: Compare before/after gameplay
2. **Check event listeners**: Ensure proper cleanup
3. **Review object references**: Avoid circular references
4. **Monitor DOM nodes**: Clean up unused elements
5. **Profile allocations**: Find sources of memory growth

#### Network Issues
1. **Monitor WebSocket**: Check connection stability
2. **Measure latency**: Profile round-trip times
3. **Check message size**: Optimize payload size
4. **Test reconnection**: Verify recovery logic
5. **Simulate conditions**: Test with poor networks

### Profiling Tools

#### Chrome DevTools
- **Performance**: Record runtime performance
- **Memory**: Analyze heap usage and leaks
- **Network**: Monitor WebSocket traffic
- **Rendering**: Check paint and layout

#### Lighthouse
```bash
# Run comprehensive audit
lighthouse http://localhost:3000 \
  --output=html \
  --output-path=./lighthouse-report.html \
  --chrome-flags="--headless"
```

#### WebPageTest
```bash
# Test with various devices and networks
webpagetest http://localhost:3000 \
  --location=Dulles:Chrome \
  --connectivity=3G \
  --runs=3
```

## Conclusion

Performance is critical for the Murmuration game experience. By following these benchmarks and optimization strategies, we ensure:

- **Smooth Gameplay**: Consistent frame rates across devices
- **Responsive Interface**: Quick response to user interactions
- **Efficient Resource Usage**: Reasonable memory and battery consumption
- **Scalable Architecture**: Performance maintains as features are added
- **Quality Assurance**: Automated monitoring prevents regressions

Regular performance testing and optimization should be part of every development cycle, not an afterthought. The tools and processes defined in this document provide a foundation for maintaining high performance standards.