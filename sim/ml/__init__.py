"""Machine Learning module for Murmuration.

This module implements the PPO-lite training system, neuroevolution, and population-based training
as specified in CLAUDE.md. Key components:

- Policy networks: MLP with deterministic forward passes
- PPO-lite training: Lightweight implementation with proper guardrails
- Experience buffers: Efficient storage and sampling for training
- Neuroevolution: ES and PBT between seasons for hyperparameter tuning
- Policy snapshots: Deterministic saving/loading with RNG states

All operations maintain deterministic behavior through proper RNG handling.
"""

from .policy import MLPPolicy, PolicySnapshot
from .buffer import ExperienceBuffer
from .ppo import PPOTrainer, TrainingMetrics
from .evolution import NeuroEvolution, PopulationBasedTraining

__all__ = [
    "MLPPolicy",
    "PolicySnapshot", 
    "ExperienceBuffer",
    "PPOTrainer",
    "TrainingMetrics",
    "NeuroEvolution",
    "PopulationBasedTraining",
]