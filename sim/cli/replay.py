"""Replay system for deterministic simulation playback.

This module implements the replay functionality specified in CLAUDE.md,
allowing recorded simulations to be replayed with hash verification
to ensure deterministic behavior.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator, Tuple
import hashlib

import numpy as np

from ..core.agent import Agent, create_agent
from ..core.environment import Environment, create_test_environment
from ..core.physics import update_agent_physics, compute_flock_cohesion
from ..core.types import AgentID, RNG
from ..utils.logging import get_logger
from .run import compute_state_hash, RunResult


@dataclass
class ReplayMetadata:
    """Metadata extracted from a replay file.
    
    Attributes:
        level: Level identifier
        seed: Original simulation seed
        n_agents: Number of agents
        n_ticks: Total simulation ticks
        frame_hashes: List of (tick, hash) pairs for verification
        final_arrivals: Final arrival count
        final_losses: Final loss count
        final_protected_deaths: Final protected death count
    """
    level: str
    seed: int
    n_agents: int
    n_ticks: int
    frame_hashes: List[Tuple[int, str]]
    final_arrivals: int
    final_losses: int
    final_protected_deaths: int


@dataclass
class ReplayEvent:
    """Single event from a replay file.
    
    Attributes:
        tick: Simulation tick when event occurred
        event_type: Type of event
        data: Event-specific data
    """
    tick: int
    event_type: str
    data: Dict[str, Any]


class ReplayLoader:
    """Loads and parses replay files in JSONL format."""
    
    def __init__(self, file_path: str) -> None:
        """Initialize replay loader.
        
        Args:
            file_path: Path to JSONL replay file
        """
        self.file_path = Path(file_path)
        self.logger = get_logger()
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"Replay file not found: {file_path}")
    
    def load_metadata(self) -> ReplayMetadata:
        """Load metadata from the replay file.
        
        Returns:
            Replay metadata extracted from events
            
        Raises:
            ValueError: If replay file format is invalid
        """
        level = None
        seed = None
        n_agents = 0
        n_ticks = 0
        frame_hashes = []
        final_arrivals = 0
        final_losses = 0
        final_protected_deaths = 0
        
        with open(self.file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line.strip())
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON at line {line_num}: {e}")
                
                # Extract basic metadata from first event
                if level is None:
                    level = event.get('level')
                    seed = event.get('seed')
                
                # Track agent count from tick events
                if event.get('evt') == 'tick':
                    pop = event.get('pop', 0)
                    n_agents = max(n_agents, pop)
                    n_ticks = max(n_ticks, event.get('t', 0))
                
                # Extract frame hashes if present
                if 'frame_hashes' in event:
                    frame_hashes = event['frame_hashes']
                
                # Extract final results from simulation_end event
                if event.get('evt') == 'simulation_end':
                    final_arrivals = event.get('final_arrivals', 0)
                    final_losses = event.get('final_losses', 0)
                    final_protected_deaths = event.get('final_protected_deaths', 0)
        
        if level is None or seed is None:
            raise ValueError("Could not extract level and seed from replay file")
        
        return ReplayMetadata(
            level=level,
            seed=seed,
            n_agents=n_agents,
            n_ticks=n_ticks,
            frame_hashes=frame_hashes,
            final_arrivals=final_arrivals,
            final_losses=final_losses,
            final_protected_deaths=final_protected_deaths,
        )
    
    def load_events(self) -> Iterator[ReplayEvent]:
        """Load all events from the replay file.
        
        Yields:
            ReplayEvent objects in chronological order
        """
        with open(self.file_path, 'r') as f:
            for line in f:
                try:
                    event_data = json.loads(line.strip())
                    
                    event = ReplayEvent(
                        tick=event_data.get('t', 0),
                        event_type=event_data.get('evt', 'unknown'),
                        data=event_data,
                    )
                    
                    yield event
                except json.JSONDecodeError:
                    continue  # Skip invalid lines


def replay_simulation(
    replay_file: str,
    verify_hash: bool = True,
    fps_target: float = 60.0,
    headless: bool = True,
) -> RunResult:
    """Replay a recorded simulation from JSONL file.
    
    Args:
        replay_file: Path to JSONL replay file
        verify_hash: Whether to verify state hashes match original
        fps_target: Playback frame rate
        headless: Whether to run without visualization
        
    Returns:
        RunResult from the replayed simulation
        
    Raises:
        ValueError: If replay file is invalid or hashes don't match
    """
    logger = get_logger()
    start_time = time.time()
    
    # Load replay metadata
    loader = ReplayLoader(replay_file)
    metadata = loader.load_metadata()
    
    logger.info(
        "Starting replay",
        extra={
            "replay_file": replay_file,
            "level": metadata.level,
            "seed": metadata.seed,
            "n_agents": metadata.n_agents,
            "n_ticks": metadata.n_ticks,
            "verify_hash": verify_hash,
            "frame_hashes_available": len(metadata.frame_hashes),
        }
    )
    
    # Print seed for determinism tracking
    print(f"🎲 Replay seed: {metadata.seed}")
    
    # Initialize deterministic RNG with the same seed
    rng = np.random.default_rng(metadata.seed)
    physics_rng = np.random.default_rng(rng.integers(0, 2**31))
    
    # Create environment (must match original)
    environment = create_test_environment(rng)
    
    # Create agents (must match original)
    agents = []
    for i in range(metadata.n_agents):
        agent = create_agent(AgentID(i), rng=physics_rng)
        agents.append(agent)
    
    # Replay metrics
    cohesion_history = []
    frame_times = []
    arrivals = 0
    losses = 0
    protected_deaths = 0
    
    # Hash verification data
    hash_mismatches = []
    expected_hashes = {tick: hash_val for tick, hash_val in metadata.frame_hashes}
    
    # Target frame time for FPS limiting
    target_frame_time = 1.0 / fps_target
    
    # Load all events for processing
    events = list(loader.load_events())
    events.sort(key=lambda e: e.tick)  # Ensure chronological order
    
    # Replay simulation
    current_tick = 0
    event_index = 0
    
    while current_tick <= metadata.n_ticks and event_index < len(events):
        frame_start = time.time()
        
        # Process all events for this tick
        while (event_index < len(events) and 
               events[event_index].tick <= current_tick):
            event = events[event_index]
            
            # Update metrics based on event type
            if event.event_type == 'tick':
                pop = event.data.get('pop', 0)
                cohesion = event.data.get('C', 0.0)
                arrivals = event.data.get('arrivals', arrivals)
                losses = event.data.get('losses', losses)
                protected_deaths = event.data.get('protected_deaths', protected_deaths)
                
                cohesion_history.append(cohesion)
            
            elif event.event_type == 'arrival':
                # Mark agent as arrived (simplified)
                agent_id = event.data.get('agent_id')
                if agent_id is not None and agent_id < len(agents):
                    agents[agent_id].alive = False
            
            elif event.event_type in ['energy_loss', 'flock_collapse']:
                # Mark agent as lost (simplified)
                agent_id = event.data.get('agent_id')
                if agent_id is not None and agent_id < len(agents):
                    agents[agent_id].alive = False
            
            event_index += 1
        
        # Update physics (deterministic replay)
        dt = 1.0 / 30.0
        active_agents = [agent for agent in agents if agent.alive]
        
        if active_agents:
            update_agent_physics(active_agents, environment, dt, physics_rng)
        
        environment.update(dt)
        
        # Hash verification
        if verify_hash and current_tick in expected_hashes:
            current_hash = compute_state_hash(agents, environment, current_tick)
            expected_hash = expected_hashes[current_tick]
            
            if current_hash != expected_hash:
                hash_mismatches.append({
                    'tick': current_tick,
                    'expected': expected_hash,
                    'actual': current_hash,
                })
                
                if len(hash_mismatches) == 1:  # Log first mismatch
                    logger.error(
                        "Hash mismatch detected",
                        extra={
                            'tick': current_tick,
                            'expected_hash': expected_hash,
                            'actual_hash': current_hash,
                        }
                    )
        
        # FPS limiting
        frame_time = time.time() - frame_start
        frame_times.append(frame_time)
        
        if not headless and frame_time < target_frame_time:
            time.sleep(target_frame_time - frame_time)
        
        # Progress logging
        if current_tick % 1800 == 0 and current_tick > 0:
            progress = (current_tick / metadata.n_ticks) * 100
            logger.info(
                "Replay progress",
                extra={
                    "tick": current_tick,
                    "progress": f"{progress:.1f}%",
                    "active_agents": len(active_agents),
                    "hash_mismatches": len(hash_mismatches),
                }
            )
        
        current_tick += 1
    
    # Validate hash verification results
    if verify_hash and hash_mismatches:
        error_msg = f"Hash verification failed: {len(hash_mismatches)} mismatches"
        logger.error(error_msg, extra={"mismatches": hash_mismatches[:5]})  # Log first 5
        raise ValueError(error_msg)
    
    # Compute final metrics
    wall_time = time.time() - start_time
    avg_fps = len(frame_times) / sum(frame_times) if frame_times else 0.0
    cohesion_avg = float(np.mean(cohesion_history)) if cohesion_history else 0.0
    
    # Final state hash
    final_hash = compute_state_hash(agents, environment, current_tick - 1)
    
    logger.info(
        "Replay completed",
        extra={
            "wall_time": wall_time,
            "avg_fps": avg_fps,
            "final_arrivals": arrivals,
            "final_losses": losses,
            "final_protected_deaths": protected_deaths,
            "cohesion_avg": cohesion_avg,
            "final_hash": final_hash,
            "hash_verification": "passed" if not hash_mismatches else "failed",
            "hash_mismatches": len(hash_mismatches),
        }
    )
    
    return RunResult(
        state_hash=final_hash,
        arrivals=arrivals,
        losses=losses,
        cohesion_avg=cohesion_avg,
        avg_fps=avg_fps,
        wall_time=wall_time,
        events=None,  # Events not tracked during replay
    )


def verify_replay_determinism(
    level: str,
    seed: int,
    n_agents: int,
    n_ticks: int,
    temp_dir: Path,
) -> bool:
    """Verify that a simulation produces deterministic results.
    
    Runs the same simulation twice and compares the results to ensure
    deterministic behavior as required by CLAUDE.md.
    
    Args:
        level: Level to test
        seed: Random seed to use
        n_agents: Number of agents
        n_ticks: Number of ticks to run
        temp_dir: Directory for temporary files
        
    Returns:
        True if both runs produce identical results
    """
    from .run import run_simulation
    
    logger = get_logger()
    
    # Run first simulation
    replay_file_1 = temp_dir / f"test_replay_1_{seed}.jsonl"
    result_1 = run_simulation(
        level=level,
        n_agents=n_agents,
        n_ticks=n_ticks,
        seed=seed,
        headless=True,
        record_file=str(replay_file_1),
    )
    
    # Run second simulation with same parameters
    replay_file_2 = temp_dir / f"test_replay_2_{seed}.jsonl"
    result_2 = run_simulation(
        level=level,
        n_agents=n_agents,
        n_ticks=n_ticks,
        seed=seed,
        headless=True,
        record_file=str(replay_file_2),
    )
    
    # Compare results
    deterministic = (
        result_1.state_hash == result_2.state_hash and
        result_1.arrivals == result_2.arrivals and
        result_1.losses == result_2.losses and
        abs(result_1.cohesion_avg - result_2.cohesion_avg) < 1e-10
    )
    
    logger.info(
        "Determinism test completed",
        extra={
            "level": level,
            "seed": seed,
            "deterministic": deterministic,
            "hash_1": result_1.state_hash,
            "hash_2": result_2.state_hash,
            "arrivals_1": result_1.arrivals,
            "arrivals_2": result_2.arrivals,
        }
    )
    
    # Clean up test files
    replay_file_1.unlink(missing_ok=True)
    replay_file_2.unlink(missing_ok=True)
    
    return deterministic


def calculate_replay_hash(file_path: str) -> str:
    """Calculate hash of a replay file for integrity verification.
    
    Args:
        file_path: Path to replay file
        
    Returns:
        SHA-256 hash of the file contents
    """
    hasher = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    
    return hasher.hexdigest()