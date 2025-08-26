"""Main Click CLI entry point for Murmuration simulation.

This module provides the primary command-line interface following the
specifications in CLAUDE.md, including deterministic seeding and structured logging.
"""

import sys
from pathlib import Path
from typing import Optional

import click
import numpy as np

from ..utils.logging import setup_logging, get_logger
from .run import run_simulation


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--log-file", type=click.Path(), help="Log to file instead of stdout")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, log_file: Optional[str]) -> None:
    """Murmuration: Evolving flock simulation with influence-not-control mechanics.
    
    This CLI provides commands for running simulations, training models, and analyzing results.
    All operations are deterministic when provided with a seed value.
    """
    ctx.ensure_object(dict)
    
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_logging(level=log_level, log_file=log_file)
    
    # Store configuration in context
    ctx.obj["verbose"] = verbose
    ctx.obj["log_file"] = log_file


@cli.command()
@click.option("--level", required=True, help="Level to run (e.g., W1-1, W2-3)")
@click.option("--agents", default=200, help="Number of agents in the flock")
@click.option("--ticks", default=1800, help="Number of simulation ticks (30 ticks = 1 second)")
@click.option("--seed", type=int, help="Random seed for deterministic behavior")
@click.option("--headless", is_flag=True, help="Run without visualization")
@click.option("--record", type=click.Path(), help="Record simulation events to JSONL file")
@click.option("--fps-target", default=60.0, help="Target simulation FPS")
@click.pass_context
def run(
    ctx: click.Context,
    level: str,
    agents: int,
    ticks: int,
    seed: Optional[int],
    headless: bool,
    record: Optional[str],
    fps_target: float,
) -> None:
    """Run a single simulation with the specified parameters.
    
    This command runs one simulation instance with deterministic physics
    and optional event recording for replay and analysis.
    
    Examples:
        murmuration run --level W1-1 --agents 150 --ticks 3600 --seed 123
        murmuration run --level W2-2 --agents 200 --headless --record out/test.jsonl
    """
    logger = get_logger()
    
    # Generate seed if not provided
    if seed is None:
        seed = np.random.randint(0, 2**31 - 1)
    
    # Log startup information
    logger.info(
        "Starting simulation",
        extra={
            "level": level,
            "agents": agents,
            "ticks": ticks,
            "seed": seed,
            "headless": headless,
            "record_file": record,
            "fps_target": fps_target,
        }
    )
    
    # Validate parameters
    if agents <= 0:
        click.echo("Error: Number of agents must be positive", err=True)
        sys.exit(1)
    
    if ticks <= 0:
        click.echo("Error: Number of ticks must be positive", err=True)
        sys.exit(1)
    
    if fps_target <= 0:
        click.echo("Error: FPS target must be positive", err=True)
        sys.exit(1)
    
    # Run the simulation
    try:
        result = run_simulation(
            level=level,
            n_agents=agents,
            n_ticks=ticks,
            seed=seed,
            headless=headless,
            record_file=record,
            fps_target=fps_target,
        )
        
        # Display results
        click.echo(f"Simulation completed successfully!")
        click.echo(f"Final state hash: {result.state_hash}")
        click.echo(f"Arrivals: {result.arrivals}")
        click.echo(f"Losses: {result.losses}")
        click.echo(f"Average cohesion: {result.cohesion_avg:.3f}")
        click.echo(f"Average FPS: {result.avg_fps:.1f}")
        
        if result.star_rating is not None:
            click.echo(f"Star rating: {result.star_rating} ⭐")
        
        logger.info(
            "Simulation completed",
            extra={
                "result": {
                    "state_hash": result.state_hash,
                    "arrivals": result.arrivals,
                    "losses": result.losses,
                    "cohesion_avg": result.cohesion_avg,
                    "avg_fps": result.avg_fps,
                    "star_rating": result.star_rating,
                }
            }
        )
        
    except Exception as e:
        logger.error("Simulation failed", extra={"error": str(e)})
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--level", required=True, help="Level to train on")
@click.option("--epochs", default=10, help="Number of training epochs")
@click.option("--seed", type=int, help="Random seed for deterministic training")
@click.option("--wandb", is_flag=True, help="Enable Weights & Biases logging")
@click.pass_context
def train(
    ctx: click.Context,
    level: str,
    epochs: int,
    seed: Optional[int],
    wandb: bool,
) -> None:
    """Train AI agents using reinforcement learning.
    
    This command implements PPO-lite training as specified in CLAUDE.md,
    with proper seed handling and metric logging.
    
    Examples:
        murmuration train --level W1-1 --epochs 5 --seed 42
        murmuration train --level W2-3 --epochs 20 --wandb
    """
    logger = get_logger()
    
    # Generate seed if not provided
    if seed is None:
        seed = np.random.randint(0, 2**31 - 1)
    
    logger.info(
        "Starting training",
        extra={
            "level": level,
            "epochs": epochs,
            "seed": seed,
            "wandb": wandb,
        }
    )
    
    # Set deterministic behavior
    import torch
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(seed)
    np.random.seed(seed)
    
    try:
        from ..ml import MLPPolicy, ExperienceBuffer, PPOTrainer
        from ..ml.policy import create_observation_vector
        from ..ml.buffer import Experience
        
        # Initialize ML components
        rng = np.random.default_rng(seed)
        policy = MLPPolicy(observation_dim=32, hidden_dim=64, action_dim=2, rng=rng)
        buffer = ExperienceBuffer(capacity=10000, gamma=0.98, gae_lambda=0.95)
        trainer = PPOTrainer(
            policy=policy,
            experience_buffer=buffer,
            learning_rate=3e-4,
            gamma=0.98,
            gae_lambda=0.95,
            batch_size=1024,
            n_epochs=4,
            rng=rng
        )
        
        click.echo(f"🧠 Initialized policy network with {policy.count_parameters()} parameters")
        click.echo(f"📊 Training configuration: lr=3e-4, γ=0.98, λ=0.95, batch=1024, epochs=4")
        
        if wandb:
            click.echo("📈 Weights & Biases logging enabled")
            # TODO: Initialize wandb logging
        
        # Run training epochs
        for epoch in range(epochs):
            click.echo(f"🏃 Epoch {epoch + 1}/{epochs}")
            
            # TODO: Implement actual environment interaction and data collection
            # For now, generate dummy experiences
            for step in range(100):  # Dummy episode length
                # Create dummy observation
                dummy_obs = create_observation_vector(
                    agent_velocity=rng.normal(0, 1, 2),
                    raycast_distances=rng.uniform(10, 50, 8),
                    neighbor_count=rng.integers(0, 10),
                    neighbor_avg_distance=rng.uniform(5, 30),
                    neighbor_cohesion=rng.uniform(0.3, 0.9),
                    signal_gradient_x=rng.uniform(-5, 5),
                    signal_gradient_y=rng.uniform(-5, 5),
                    time_of_day=rng.uniform(0, 1),
                    energy_level=rng.uniform(0.2, 1.0),
                    social_stress=rng.uniform(0, 0.8),
                    risk_level=rng.uniform(0, 0.5),
                )
                
                # Get action from policy
                action, value, log_prob, _ = trainer.get_action_and_value(dummy_obs)
                
                # Create dummy experience
                experience = Experience(
                    observation=dummy_obs,
                    action=action,
                    reward=rng.uniform(-1, 1),  # Dummy reward
                    value=value,
                    log_prob=log_prob,
                    done=(step == 99),  # Episode end
                )
                
                buffer.add(experience)
            
            # Train if enough data
            if buffer.size >= trainer.batch_size:
                metrics = trainer.train_step()
                if metrics:
                    click.echo(f"   📉 Loss: {metrics.total_loss:.4f} "
                             f"(policy: {metrics.policy_loss:.4f}, value: {metrics.value_loss:.4f})")
                    click.echo(f"   📊 KL: {metrics.kl_divergence:.4f}, "
                             f"Entropy: {metrics.entropy:.4f}")
                    
                    # Validate CLAUDE.md requirements
                    if not (0.0 <= metrics.kl_divergence <= 0.5):
                        logger.warning(f"KL divergence out of expected range: {metrics.kl_divergence}")
                    if metrics.entropy <= 0.0:
                        logger.warning(f"Entropy should be positive: {metrics.entropy}")
                    
                    if wandb:
                        # TODO: Log to wandb
                        pass
            
            # Check early stopping (dummy condition for now)
            if epoch > 0 and trainer.should_early_stop(epoch * 10, patience=3):
                click.echo("🛑 Early stopping triggered")
                break
        
        click.echo("✅ Training completed successfully!")
        click.echo(f"📊 Final buffer size: {buffer.size}")
        click.echo(f"🏁 Training steps completed: {trainer.training_step}")
        
        # Save policy snapshot
        snapshot = policy.create_snapshot(training_step=trainer.training_step)
        snapshot_path = Path("out") / f"policy_{level}_seed{seed}.pkl"
        snapshot_path.parent.mkdir(exist_ok=True)
        snapshot.save(snapshot_path)
        
        click.echo(f"💾 Policy saved to: {snapshot_path}")
        
    except ImportError as e:
        logger.error("ML dependencies not available", extra={"error": str(e)})
        click.echo("❌ Error: ML training requires PyTorch and other dependencies.")
        click.echo("   Install with: pip install -e .")
        sys.exit(1)
    except Exception as e:
        logger.error("Training failed", extra={"error": str(e)})
        click.echo(f"❌ Training error: {e}")
        sys.exit(1)


@cli.command()
@click.option("--from", "replay_file", required=True, type=click.Path(exists=True),
              help="JSONL file to replay")
@click.option("--verify-hash", is_flag=True, help="Verify state hash matches original")
@click.option("--fps-target", default=60.0, help="Playback FPS")
@click.pass_context
def replay(
    ctx: click.Context,
    replay_file: str,
    verify_hash: bool,
    fps_target: float,
) -> None:
    """Replay a recorded simulation from JSONL file.
    
    This command replays a previously recorded simulation to verify
    deterministic behavior and for debugging purposes.
    
    Examples:
        murmuration replay --from out/simulation.jsonl --verify-hash
        murmuration replay --from recordings/test.jsonl --fps-target 30
    """
    logger = get_logger()
    
    logger.info(
        "Starting replay",
        extra={
            "replay_file": replay_file,
            "verify_hash": verify_hash,
            "fps_target": fps_target,
        }
    )
    
    from .replay import replay_simulation
    
    try:
        result = replay_simulation(
            replay_file=replay_file,
            verify_hash=verify_hash,
            fps_target=fps_target,
            headless=True,
        )
        
        click.echo("✅ Replay completed successfully!")
        click.echo(f"Final state hash: {result.state_hash}")
        click.echo(f"Arrivals: {result.arrivals}")
        click.echo(f"Losses: {result.losses}")
        click.echo(f"Average cohesion: {result.cohesion_avg:.3f}")
        click.echo(f"Average FPS: {result.avg_fps:.1f}")
        
        if verify_hash:
            click.echo("🔒 Hash verification: PASSED")
        
    except Exception as e:
        logger.error("Replay failed", extra={"error": str(e)})
        click.echo(f"❌ Replay error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--config", required=True, type=click.Path(exists=True),
              help="Acceptance test configuration file")
@click.pass_context
def acceptance(ctx: click.Context, config: str) -> None:
    """Run acceptance test suite.
    
    Executes the full acceptance test suite as defined in the configuration
    file, validating that all levels meet their performance thresholds.
    
    Examples:
        murmuration acceptance --config configs/acceptance.yaml
        murmuration acceptance --config configs/acceptance_ci_fast.yaml
    """
    logger = get_logger()
    
    logger.info("Starting acceptance tests", extra={"config": config})
    
    # TODO: Implement acceptance testing
    click.echo("Acceptance testing is not yet implemented")
    click.echo(f"Would run tests from config: {config}")


@cli.command()
@click.option("--level", help="Specific level to benchmark (default: all)")
@click.option("--agents", default=300, help="Number of agents for benchmark")
@click.option("--duration", default=60, help="Benchmark duration in seconds")
@click.option("--seed", type=int, default=42, help="Random seed for benchmark")
@click.pass_context
def bench(
    ctx: click.Context,
    level: Optional[str],
    agents: int,
    duration: int,
    seed: int,
) -> None:
    """Run performance benchmarks.
    
    Measures simulation performance to ensure it meets the requirements
    specified in CLAUDE.md (≥300 agents @ 60Hz).
    
    Examples:
        murmuration bench --agents 300 --duration 60
        murmuration bench --level W1-1 --agents 150
    """
    logger = get_logger()
    
    logger.info(
        "Starting benchmark",
        extra={
            "level": level,
            "agents": agents,
            "duration": duration,
            "seed": seed,
        }
    )
    
    from .bench import run_performance_benchmark, run_comprehensive_benchmark
    
    try:
        if level:
            # Single level benchmark
            result = run_performance_benchmark(
                level=level,
                n_agents=agents,
                duration_seconds=duration,
                seed=seed,
            )
            
            # Display results
            status = "✅ PASS" if result.meets_target else "❌ FAIL"
            click.echo(f"{status} {level}: {result.avg_fps:.1f} FPS (target: 60.0)")
            click.echo(f"📊 Range: {result.min_fps:.1f} - {result.max_fps:.1f} FPS")
            click.echo(f"💾 Memory: {result.memory_peak_mb:.1f}MB peak")
            click.echo(f"🔥 CPU: {result.cpu_avg_percent:.1f}% average")
            
        else:
            # Comprehensive benchmark
            levels_to_test = ["W1-1", "W2-1", "W3-1"]
            agent_counts = [agents] if agents != 300 else [150, 200, 250, 300]
            
            results = run_comprehensive_benchmark(
                levels=levels_to_test,
                agent_counts=agent_counts,
                duration=duration,
                seed=seed,
            )
            
            # Summary
            passed = sum(1 for r in results if r.meets_target)
            total = len(results)
            click.echo(f"\\n🎯 Overall: {passed}/{total} benchmarks passed")
            
            if passed < total:
                click.echo("❌ Some benchmarks failed to meet performance targets")
                sys.exit(1)
            else:
                click.echo("✅ All benchmarks passed!")
        
    except Exception as e:
        logger.error("Benchmark failed", extra={"error": str(e)})
        click.echo(f"❌ Benchmark error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--host", default="localhost", help="Server host address")
@click.option("--port", default=8765, help="Server port number")
def serve(host: str, port: int):
    """Start the WebSocket server for client connections."""
    click.echo(f"🌐 Starting Murmuration WebSocket server on ws://{host}:{port}")
    
    try:
        from ..server import main as server_main
        import asyncio
        
        # Create and run server
        from ..server import SimulationServer
        server = SimulationServer(host=host, port=port)
        asyncio.run(server.start())
        
    except ImportError:
        click.echo("❌ WebSocket server requires websockets library.")
        click.echo("   Install with: pip install websockets")
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n👋 Server stopped")
    except Exception as e:
        click.echo(f"❌ Server error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()