"""Performance benchmarking system for Murmuration simulation.

This module implements the benchmarking functionality specified in CLAUDE.md,
targeting ≥300 agents @ 60Hz performance requirements.
"""

import time
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import json
from pathlib import Path

import numpy as np
import psutil

from ..core.agent import Agent, create_agent
from ..core.environment import Environment, create_test_environment
from ..core.physics import update_agent_physics, compute_flock_cohesion
from ..core.types import AgentID, RNG
from ..utils.logging import get_logger
from .run import run_simulation


@dataclass
class BenchmarkResult:
    """Results from a performance benchmark.
    
    Attributes:
        level: Level that was benchmarked
        n_agents: Number of agents used
        duration_seconds: Benchmark duration in seconds
        total_ticks: Total simulation ticks executed
        avg_fps: Average frames per second achieved
        min_fps: Minimum FPS during benchmark
        max_fps: Maximum FPS during benchmark
        fps_std: Standard deviation of FPS measurements
        memory_peak_mb: Peak memory usage in megabytes
        memory_avg_mb: Average memory usage in megabytes
        cpu_avg_percent: Average CPU usage percentage
        meets_target: Whether performance meets CLAUDE.md requirements
        target_fps: Target FPS requirement
    """
    level: str
    n_agents: int
    duration_seconds: float
    total_ticks: int
    avg_fps: float
    min_fps: float
    max_fps: float
    fps_std: float
    memory_peak_mb: float
    memory_avg_mb: float
    cpu_avg_percent: float
    meets_target: bool
    target_fps: float = 60.0


class PerformanceMonitor:
    """Monitors performance metrics during simulation."""
    
    def __init__(self) -> None:
        """Initialize performance monitor."""
        self.fps_history: List[float] = []
        self.memory_history: List[float] = []
        self.cpu_history: List[float] = []
        self.frame_times: List[float] = []
        self.process = psutil.Process()
        
    def start_frame(self) -> float:
        """Mark the start of a frame.
        
        Returns:
            Timestamp when frame started
        """
        return time.time()
    
    def end_frame(self, start_time: float) -> None:
        """Mark the end of a frame and record metrics.
        
        Args:
            start_time: Timestamp from start_frame()
        """
        frame_time = time.time() - start_time
        self.frame_times.append(frame_time)
        
        # Calculate instantaneous FPS
        if frame_time > 0:
            fps = 1.0 / frame_time
            self.fps_history.append(fps)
        
        # Sample system metrics (not every frame to reduce overhead)
        if len(self.frame_times) % 30 == 0:  # Every 30 frames
            memory_mb = self.process.memory_info().rss / (1024 * 1024)
            self.memory_history.append(memory_mb)
            
            cpu_percent = self.process.cpu_percent()
            self.cpu_history.append(cpu_percent)
    
    def get_metrics(self) -> Dict[str, float]:
        """Get current performance metrics.
        
        Returns:
            Dictionary of performance metrics
        """
        if not self.fps_history:
            return {}
        
        return {
            'avg_fps': statistics.mean(self.fps_history),
            'min_fps': min(self.fps_history),
            'max_fps': max(self.fps_history),
            'fps_std': statistics.stdev(self.fps_history) if len(self.fps_history) > 1 else 0.0,
            'memory_peak_mb': max(self.memory_history) if self.memory_history else 0.0,
            'memory_avg_mb': statistics.mean(self.memory_history) if self.memory_history else 0.0,
            'cpu_avg_percent': statistics.mean(self.cpu_history) if self.cpu_history else 0.0,
        }


def run_performance_benchmark(
    level: str,
    n_agents: int,
    duration_seconds: float,
    seed: int = 42,
    target_fps: float = 60.0,
) -> BenchmarkResult:
    """Run a performance benchmark on the simulation.
    
    Args:
        level: Level to benchmark
        n_agents: Number of agents to simulate
        duration_seconds: How long to run the benchmark
        seed: Random seed for reproducible benchmarks
        target_fps: Target FPS requirement
        
    Returns:
        Benchmark results with performance metrics
    """
    logger = get_logger()
    
    logger.info(
        "Starting performance benchmark",
        extra={
            "level": level,
            "n_agents": n_agents,
            "duration_seconds": duration_seconds,
            "seed": seed,
            "target_fps": target_fps,
        }
    )
    
    # Print seed for determinism tracking
    print(f"🎲 Benchmark seed: {seed}")
    
    # Initialize deterministic RNG
    rng = np.random.default_rng(seed)
    physics_rng = np.random.default_rng(rng.integers(0, 2**31))
    
    # Create environment and agents
    environment = create_test_environment(rng)
    agents = []
    for i in range(n_agents):
        agent = create_agent(AgentID(i), rng=physics_rng)
        agents.append(agent)
    
    # Initialize performance monitoring
    monitor = PerformanceMonitor()
    
    # Benchmark loop
    start_time = time.time()
    tick = 0
    dt = 1.0 / 30.0  # Physics timestep
    
    print(f"🏃 Running benchmark: {n_agents} agents for {duration_seconds}s...")
    
    while time.time() - start_time < duration_seconds:
        frame_start = monitor.start_frame()
        
        # Update physics
        active_agents = [agent for agent in agents if agent.alive]
        if not active_agents:
            break  # Early termination if no agents remain
        
        update_agent_physics(active_agents, environment, dt, physics_rng)
        environment.update(dt)
        
        # Compute some metrics (similar to real simulation load)
        cohesion = compute_flock_cohesion(active_agents)
        
        # Simulate some arrival/loss logic
        if tick % 100 == 0:  # Every ~3 seconds
            for agent in active_agents[:5]:  # Mark some agents as arrived
                if agent.position[0] >= environment.width - 5:
                    agent.alive = False
        
        monitor.end_frame(frame_start)
        tick += 1
        
        # Progress update
        if tick % 1800 == 0:  # Every minute
            elapsed = time.time() - start_time
            progress = (elapsed / duration_seconds) * 100
            current_metrics = monitor.get_metrics()
            current_fps = current_metrics.get('avg_fps', 0.0)
            
            print(f"⏱️  Progress: {progress:.1f}% | FPS: {current_fps:.1f} | Active: {len(active_agents)}")
    
    # Calculate final metrics
    total_time = time.time() - start_time
    metrics = monitor.get_metrics()
    
    avg_fps = metrics.get('avg_fps', 0.0)
    meets_target = avg_fps >= target_fps
    
    result = BenchmarkResult(
        level=level,
        n_agents=n_agents,
        duration_seconds=total_time,
        total_ticks=tick,
        avg_fps=avg_fps,
        min_fps=metrics.get('min_fps', 0.0),
        max_fps=metrics.get('max_fps', 0.0),
        fps_std=metrics.get('fps_std', 0.0),
        memory_peak_mb=metrics.get('memory_peak_mb', 0.0),
        memory_avg_mb=metrics.get('memory_avg_mb', 0.0),
        cpu_avg_percent=metrics.get('cpu_avg_percent', 0.0),
        meets_target=meets_target,
        target_fps=target_fps,
    )
    
    # Log results
    status = "✅ PASS" if meets_target else "❌ FAIL"
    print(f"{status} Average FPS: {avg_fps:.1f} (target: {target_fps})")
    print(f"📊 Min: {result.min_fps:.1f} | Max: {result.max_fps:.1f} | StdDev: {result.fps_std:.1f}")
    print(f"💾 Memory Peak: {result.memory_peak_mb:.1f}MB | Avg: {result.memory_avg_mb:.1f}MB")
    print(f"🔥 CPU Avg: {result.cpu_avg_percent:.1f}%")
    
    logger.info(
        "Benchmark completed",
        extra={
            "result": {
                "avg_fps": avg_fps,
                "meets_target": meets_target,
                "memory_peak_mb": result.memory_peak_mb,
                "cpu_avg_percent": result.cpu_avg_percent,
                "total_ticks": tick,
            }
        }
    )
    
    return result


def run_comprehensive_benchmark(
    levels: Optional[List[str]] = None,
    agent_counts: Optional[List[int]] = None,
    duration: float = 60.0,
    seed: int = 42,
    output_file: Optional[str] = None,
) -> List[BenchmarkResult]:
    """Run comprehensive performance benchmarks across multiple configurations.
    
    Args:
        levels: List of levels to benchmark (default: ["W1-1", "W2-1", "W3-1"])
        agent_counts: List of agent counts to test (default: [150, 200, 250, 300])
        duration: Duration for each benchmark in seconds
        seed: Base random seed
        output_file: Optional file to save results to
        
    Returns:
        List of benchmark results
    """
    logger = get_logger()
    
    # Default configurations
    if levels is None:
        levels = ["W1-1", "W2-1", "W3-1"]
    if agent_counts is None:
        agent_counts = [150, 200, 250, 300]
    
    results = []
    total_benchmarks = len(levels) * len(agent_counts)
    
    print(f"🔥 Starting comprehensive benchmark: {total_benchmarks} configurations")
    print(f"📋 Levels: {levels}")
    print(f"👥 Agent counts: {agent_counts}")
    print(f"⏱️  Duration per test: {duration}s")
    
    benchmark_num = 0
    for level in levels:
        for n_agents in agent_counts:
            benchmark_num += 1
            print(f"\n[{benchmark_num}/{total_benchmarks}] Benchmarking {level} with {n_agents} agents...")
            
            # Use different seed for each benchmark to avoid bias
            benchmark_seed = seed + benchmark_num
            
            try:
                result = run_performance_benchmark(
                    level=level,
                    n_agents=n_agents,
                    duration_seconds=duration,
                    seed=benchmark_seed,
                )
                results.append(result)
                
                # Immediate feedback
                status = "✅" if result.meets_target else "❌"
                print(f"  {status} {result.avg_fps:.1f} FPS (target: 60.0)")
                
            except Exception as e:
                logger.error(f"Benchmark failed for {level} with {n_agents} agents: {e}")
                print(f"  ❌ ERROR: {e}")
    
    # Summary report
    print(f"\n{'='*60}")
    print("BENCHMARK SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for r in results if r.meets_target)
    total = len(results)
    
    print(f"Overall: {passed}/{total} benchmarks passed ({passed/total*100:.1f}%)")
    
    # Performance by agent count
    print(f"\nPerformance by agent count:")
    for n_agents in sorted(set(r.n_agents for r in results)):
        agent_results = [r for r in results if r.n_agents == n_agents]
        avg_fps = statistics.mean(r.avg_fps for r in agent_results)
        passed_count = sum(1 for r in agent_results if r.meets_target)
        
        status = "✅" if passed_count == len(agent_results) else "❌"
        print(f"  {n_agents:3d} agents: {avg_fps:6.1f} FPS avg | {passed_count}/{len(agent_results)} passed {status}")
    
    # Identify performance bottlenecks
    failed_results = [r for r in results if not r.meets_target]
    if failed_results:
        print(f"\\nPerformance issues detected:")
        for result in failed_results:
            print(f"  {result.level} @ {result.n_agents} agents: {result.avg_fps:.1f} FPS (need {result.target_fps})")
    
    # Save results if requested
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            benchmark_data = {
                'timestamp': time.time(),
                'summary': {
                    'total_benchmarks': total,
                    'passed': passed,
                    'pass_rate': passed / total if total > 0 else 0.0,
                },
                'results': [
                    {
                        'level': r.level,
                        'n_agents': r.n_agents,
                        'avg_fps': r.avg_fps,
                        'min_fps': r.min_fps,
                        'max_fps': r.max_fps,
                        'memory_peak_mb': r.memory_peak_mb,
                        'cpu_avg_percent': r.cpu_avg_percent,
                        'meets_target': r.meets_target,
                    }
                    for r in results
                ]
            }
            json.dump(benchmark_data, f, indent=2)
        
        print(f"\\n💾 Results saved to: {output_path}")
    
    logger.info(
        "Comprehensive benchmark completed",
        extra={
            "total_benchmarks": total,
            "passed": passed,
            "pass_rate": passed / total if total > 0 else 0.0,
        }
    )
    
    return results


def benchmark_specific_scenario(
    level: str,
    n_agents: int,
    duration: float = 300.0,  # 5 minutes for detailed analysis
    seed: int = 42,
) -> Dict[str, Any]:
    """Run detailed benchmark for a specific scenario.
    
    This provides more detailed analysis including performance over time,
    memory usage patterns, and system resource utilization.
    
    Args:
        level: Level to benchmark
        n_agents: Number of agents
        duration: Benchmark duration in seconds
        seed: Random seed
        
    Returns:
        Detailed benchmark analysis
    """
    logger = get_logger()
    
    print(f"🔬 Detailed benchmark: {level} with {n_agents} agents for {duration}s")
    
    result = run_performance_benchmark(
        level=level,
        n_agents=n_agents,
        duration_seconds=duration,
        seed=seed,
    )
    
    # Additional analysis
    analysis = {
        'basic_metrics': {
            'avg_fps': result.avg_fps,
            'min_fps': result.min_fps,
            'max_fps': result.max_fps,
            'fps_stability': result.fps_std,
            'meets_performance_target': result.meets_target,
        },
        'resource_usage': {
            'memory_peak_mb': result.memory_peak_mb,
            'memory_avg_mb': result.memory_avg_mb,
            'cpu_avg_percent': result.cpu_avg_percent,
        },
        'simulation_stats': {
            'total_ticks': result.total_ticks,
            'simulation_rate': result.total_ticks / result.duration_seconds,
        },
        'performance_grade': _calculate_performance_grade(result),
    }
    
    # Print detailed analysis
    print(f"\\n📊 DETAILED ANALYSIS")
    print(f"Performance Grade: {analysis['performance_grade']}")
    print(f"FPS Stability: {result.fps_std:.2f} (lower is better)")
    print(f"Simulation Rate: {analysis['simulation_stats']['simulation_rate']:.1f} ticks/second")
    
    return analysis


def _calculate_performance_grade(result: BenchmarkResult) -> str:
    """Calculate a letter grade for performance results.
    
    Args:
        result: Benchmark result to grade
        
    Returns:
        Letter grade (A+ to F)
    """
    score = 0
    
    # FPS score (60% weight)
    fps_ratio = result.avg_fps / result.target_fps
    if fps_ratio >= 1.2:  # 20% above target
        score += 60
    elif fps_ratio >= 1.0:  # Meets target
        score += 50
    elif fps_ratio >= 0.9:  # 90% of target
        score += 40
    elif fps_ratio >= 0.8:  # 80% of target
        score += 30
    elif fps_ratio >= 0.7:  # 70% of target
        score += 20
    else:  # Below 70% of target
        score += 10
    
    # Stability score (20% weight) - lower std dev is better
    if result.fps_std < 2.0:
        score += 20
    elif result.fps_std < 5.0:
        score += 15
    elif result.fps_std < 10.0:
        score += 10
    else:
        score += 5
    
    # Memory efficiency score (20% weight)
    if result.memory_peak_mb < 100:  # Less than 100MB
        score += 20
    elif result.memory_peak_mb < 200:  # Less than 200MB
        score += 15
    elif result.memory_peak_mb < 500:  # Less than 500MB
        score += 10
    else:
        score += 5
    
    # Convert score to grade
    if score >= 90:
        return "A+"
    elif score >= 85:
        return "A"
    elif score >= 80:
        return "B+"
    elif score >= 75:
        return "B"
    elif score >= 70:
        return "C+"
    elif score >= 65:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"