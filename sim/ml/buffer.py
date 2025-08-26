"""Experience replay buffer for PPO training.

This module implements efficient storage and sampling of experience tuples
for PPO-lite training as specified in CLAUDE.md. Features include:

- Circular buffer with fixed capacity
- Batch sampling with GAE computation  
- Reward normalization and clipping (guardrails)
- Memory-efficient storage using NumPy arrays
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Iterator
import warnings

from ..core.types import RNG
from ..utils.logging import get_logger

logger = get_logger()


@dataclass
class Experience:
    """Single experience tuple for RL training.
    
    Contains all information needed for PPO updates including
    observations, actions, rewards, values, and episode metadata.
    """
    observation: np.ndarray
    action: np.ndarray
    reward: float
    value: float
    log_prob: float
    done: bool
    next_observation: Optional[np.ndarray] = None
    advantage: Optional[float] = None
    return_value: Optional[float] = None
    
    def __post_init__(self):
        """Validate experience data after initialization."""
        if self.observation.shape != (32,):
            raise ValueError(f"Expected observation shape (32,), got {self.observation.shape}")
        if self.action.shape != (2,):
            raise ValueError(f"Expected action shape (2,), got {self.action.shape}")


@dataclass 
class TrajectoryBatch:
    """Batch of trajectories for training.
    
    Contains arrays of experiences organized for efficient
    vectorized operations during PPO updates.
    """
    observations: np.ndarray      # Shape: [batch_size, obs_dim]
    actions: np.ndarray          # Shape: [batch_size, action_dim]
    rewards: np.ndarray          # Shape: [batch_size]
    values: np.ndarray           # Shape: [batch_size]
    log_probs: np.ndarray        # Shape: [batch_size]
    advantages: np.ndarray       # Shape: [batch_size]
    returns: np.ndarray          # Shape: [batch_size]
    dones: np.ndarray           # Shape: [batch_size] (boolean)
    
    def __len__(self) -> int:
        return len(self.observations)
    
    def shuffle(self, rng: RNG) -> "TrajectoryBatch":
        """Shuffle the batch randomly.
        
        Args:
            rng: Random number generator
            
        Returns:
            New shuffled batch
        """
        indices = rng.permutation(len(self))
        
        return TrajectoryBatch(
            observations=self.observations[indices],
            actions=self.actions[indices],
            rewards=self.rewards[indices],
            values=self.values[indices],
            log_probs=self.log_probs[indices],
            advantages=self.advantages[indices],
            returns=self.returns[indices],
            dones=self.dones[indices],
        )
    
    def split(self, batch_size: int) -> Iterator["TrajectoryBatch"]:
        """Split into smaller batches.
        
        Args:
            batch_size: Size of each mini-batch
            
        Yields:
            Mini-batches of the specified size
        """
        n_samples = len(self)
        for start_idx in range(0, n_samples, batch_size):
            end_idx = min(start_idx + batch_size, n_samples)
            
            yield TrajectoryBatch(
                observations=self.observations[start_idx:end_idx],
                actions=self.actions[start_idx:end_idx],
                rewards=self.rewards[start_idx:end_idx],
                values=self.values[start_idx:end_idx],
                log_probs=self.log_probs[start_idx:end_idx],
                advantages=self.advantages[start_idx:end_idx],
                returns=self.returns[start_idx:end_idx],
                dones=self.dones[start_idx:end_idx],
            )


class ExperienceBuffer:
    """Circular buffer for storing and sampling experiences.
    
    This buffer stores experience tuples and computes advantages using
    Generalized Advantage Estimation (GAE) as required for PPO training.
    """
    
    def __init__(
        self,
        capacity: int = 10000,
        observation_dim: int = 32,
        action_dim: int = 2,
        gamma: float = 0.98,
        gae_lambda: float = 0.95,
        reward_clip: float = 10.0,
        value_clip: float = 50.0,
    ):
        """Initialize the experience buffer.
        
        Args:
            capacity: Maximum number of experiences to store
            observation_dim: Dimension of observation vectors
            action_dim: Dimension of action vectors
            gamma: Discount factor for returns
            gae_lambda: GAE lambda parameter
            reward_clip: Maximum absolute reward value (guardrail)
            value_clip: Maximum absolute value estimate (guardrail)
        """
        self.capacity = capacity
        self.observation_dim = observation_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.reward_clip = reward_clip
        self.value_clip = value_clip
        
        # Pre-allocate arrays for efficiency
        self.observations = np.zeros((capacity, observation_dim), dtype=np.float32)
        self.actions = np.zeros((capacity, action_dim), dtype=np.float32)
        self.rewards = np.zeros(capacity, dtype=np.float32)
        self.values = np.zeros(capacity, dtype=np.float32)
        self.log_probs = np.zeros(capacity, dtype=np.float32)
        self.dones = np.zeros(capacity, dtype=bool)
        self.advantages = np.zeros(capacity, dtype=np.float32)
        self.returns = np.zeros(capacity, dtype=np.float32)
        
        # Buffer state
        self.size = 0
        self.ptr = 0
        self.episode_start_indices: List[int] = []
        
        # Statistics for reward normalization
        self.reward_mean = 0.0
        self.reward_std = 1.0
        self.reward_count = 0
        
        logger.debug(
            "Experience buffer initialized",
            extra={
                "capacity": capacity,
                "observation_dim": observation_dim,
                "action_dim": action_dim,
                "gamma": gamma,
                "gae_lambda": gae_lambda,
            }
        )
    
    def add(self, experience: Experience) -> None:
        """Add a single experience to the buffer.
        
        Args:
            experience: Experience tuple to add
        """
        # Validate experience
        if np.isnan(experience.reward) or np.isinf(experience.reward):
            logger.error("Invalid reward detected", extra={"reward": experience.reward})
            raise ValueError("Invalid reward: NaN or infinity")
        
        if np.any(np.isnan(experience.observation)) or np.any(np.isinf(experience.observation)):
            logger.error("Invalid observation detected")
            raise ValueError("Invalid observation: contains NaN or infinity")
        
        if np.any(np.isnan(experience.action)) or np.any(np.isinf(experience.action)):
            logger.error("Invalid action detected")
            raise ValueError("Invalid action: contains NaN or infinity")
        
        # Apply reward clipping (guardrail)
        clipped_reward = np.clip(experience.reward, -self.reward_clip, self.reward_clip)
        if abs(clipped_reward - experience.reward) > 1e-6:
            logger.warning(
                "Reward clipped",
                extra={
                    "original": experience.reward,
                    "clipped": clipped_reward,
                }
            )
        
        # Apply value clipping (guardrail)  
        clipped_value = np.clip(experience.value, -self.value_clip, self.value_clip)
        if abs(clipped_value - experience.value) > 1e-6:
            logger.warning(
                "Value estimate clipped",
                extra={
                    "original": experience.value,
                    "clipped": clipped_value,
                }
            )
        
        # Store experience
        self.observations[self.ptr] = experience.observation
        self.actions[self.ptr] = experience.action
        self.rewards[self.ptr] = clipped_reward
        self.values[self.ptr] = clipped_value
        self.log_probs[self.ptr] = experience.log_prob
        self.dones[self.ptr] = experience.done
        
        # Track episode boundaries
        if experience.done:
            self.episode_start_indices.append(self.ptr + 1 if self.ptr + 1 < self.capacity else 0)
        
        # Update buffer state
        self.ptr = (self.ptr + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)
        
        # Update reward statistics for normalization
        self._update_reward_stats(clipped_reward)
    
    def _update_reward_stats(self, reward: float) -> None:
        """Update running reward statistics for normalization.
        
        Args:
            reward: New reward value
        """
        self.reward_count += 1
        delta = reward - self.reward_mean
        self.reward_mean += delta / self.reward_count
        
        if self.reward_count > 1:
            delta2 = reward - self.reward_mean
            # Use Welford's online variance algorithm
            variance = ((self.reward_count - 2) * self.reward_std**2 + delta * delta2) / (self.reward_count - 1)
            self.reward_std = max(np.sqrt(variance), 1e-8)  # Prevent division by zero
    
    def compute_advantages_and_returns(self, next_value: float = 0.0) -> None:
        """Compute advantages and returns using Generalized Advantage Estimation.
        
        This implements the GAE algorithm as required for PPO training,
        computing both advantage estimates and return values.
        
        Args:
            next_value: Value estimate for state after the last stored experience
        """
        if self.size == 0:
            logger.warning("Cannot compute advantages: buffer is empty")
            return
        
        # Get valid range of experiences
        if self.size < self.capacity:
            # Buffer not full, use all experiences
            start_idx = 0
            end_idx = self.size
            experiences_indices = list(range(start_idx, end_idx))
        else:
            # Buffer full, handle circular indexing
            if self.ptr == 0:
                experiences_indices = list(range(0, self.capacity))
            else:
                experiences_indices = list(range(self.ptr, self.capacity)) + list(range(0, self.ptr))
        
        n_steps = len(experiences_indices)
        if n_steps == 0:
            return
        
        # Extract values and rewards in chronological order
        values = np.zeros(n_steps + 1)
        rewards = np.zeros(n_steps)
        dones = np.zeros(n_steps, dtype=bool)
        
        for i, idx in enumerate(experiences_indices):
            values[i] = self.values[idx]
            rewards[i] = self.rewards[idx]
            dones[i] = self.dones[idx]
        
        values[-1] = next_value
        
        # Compute GAE advantages
        advantages = np.zeros(n_steps)
        gae = 0.0
        
        for step in reversed(range(n_steps)):
            if dones[step]:
                delta = rewards[step] - values[step]
                gae = delta
            else:
                delta = rewards[step] + self.gamma * values[step + 1] - values[step]
                gae = delta + self.gamma * self.gae_lambda * gae
            
            advantages[step] = gae
        
        # Compute returns
        returns = advantages + values[:-1]
        
        # Store computed values back to buffer
        for i, idx in enumerate(experiences_indices):
            self.advantages[idx] = advantages[i]
            self.returns[idx] = returns[i]
        
        logger.debug(
            "Advantages and returns computed",
            extra={
                "n_steps": n_steps,
                "advantage_mean": float(np.mean(advantages)),
                "advantage_std": float(np.std(advantages)),
                "return_mean": float(np.mean(returns)),
                "return_std": float(np.std(returns)),
            }
        )
    
    def normalize_advantages(self) -> None:
        """Normalize advantages to have zero mean and unit variance.
        
        This stabilizes PPO training by ensuring advantages are properly scaled.
        """
        if self.size == 0:
            return
        
        # Get valid advantages
        if self.size < self.capacity:
            valid_advantages = self.advantages[:self.size]
        else:
            valid_advantages = self.advantages
        
        # Normalize
        adv_mean = np.mean(valid_advantages)
        adv_std = np.std(valid_advantages)
        
        if adv_std > 1e-8:  # Avoid division by zero
            if self.size < self.capacity:
                self.advantages[:self.size] = (self.advantages[:self.size] - adv_mean) / adv_std
            else:
                self.advantages = (self.advantages - adv_mean) / adv_std
        else:
            logger.warning("Advantage standard deviation too small for normalization")
    
    def sample_batch(self, batch_size: int, rng: RNG) -> TrajectoryBatch:
        """Sample a batch of experiences for training.
        
        Args:
            batch_size: Number of experiences to sample
            rng: Random number generator
            
        Returns:
            Batch of experiences ready for training
            
        Raises:
            ValueError: If batch size is larger than buffer size
        """
        if batch_size > self.size:
            raise ValueError(
                f"Cannot sample {batch_size} experiences from buffer of size {self.size}"
            )
        
        # Sample indices
        if self.size < self.capacity:
            # Buffer not full
            valid_indices = np.arange(self.size)
        else:
            # Buffer full
            valid_indices = np.arange(self.capacity)
        
        sampled_indices = rng.choice(valid_indices, size=batch_size, replace=False)
        
        # Extract batch data
        return TrajectoryBatch(
            observations=self.observations[sampled_indices].copy(),
            actions=self.actions[sampled_indices].copy(),
            rewards=self.rewards[sampled_indices].copy(),
            values=self.values[sampled_indices].copy(),
            log_probs=self.log_probs[sampled_indices].copy(),
            advantages=self.advantages[sampled_indices].copy(),
            returns=self.returns[sampled_indices].copy(),
            dones=self.dones[sampled_indices].copy(),
        )
    
    def get_all_data(self) -> TrajectoryBatch:
        """Get all stored experiences as a batch.
        
        Returns:
            All experiences in the buffer
        """
        if self.size == 0:
            # Return empty batch
            return TrajectoryBatch(
                observations=np.empty((0, self.observation_dim)),
                actions=np.empty((0, self.action_dim)),
                rewards=np.empty(0),
                values=np.empty(0),
                log_probs=np.empty(0),
                advantages=np.empty(0),
                returns=np.empty(0),
                dones=np.empty(0, dtype=bool),
            )
        
        if self.size < self.capacity:
            # Buffer not full
            return TrajectoryBatch(
                observations=self.observations[:self.size].copy(),
                actions=self.actions[:self.size].copy(),
                rewards=self.rewards[:self.size].copy(),
                values=self.values[:self.size].copy(),
                log_probs=self.log_probs[:self.size].copy(),
                advantages=self.advantages[:self.size].copy(),
                returns=self.returns[:self.size].copy(),
                dones=self.dones[:self.size].copy(),
            )
        else:
            # Buffer full
            return TrajectoryBatch(
                observations=self.observations.copy(),
                actions=self.actions.copy(),
                rewards=self.rewards.copy(),
                values=self.values.copy(),
                log_probs=self.log_probs.copy(),
                advantages=self.advantages.copy(),
                returns=self.returns.copy(),
                dones=self.dones.copy(),
            )
    
    def clear(self) -> None:
        """Clear the buffer and reset all statistics."""
        self.size = 0
        self.ptr = 0
        self.episode_start_indices.clear()
        self.reward_mean = 0.0
        self.reward_std = 1.0
        self.reward_count = 0
        
        logger.debug("Experience buffer cleared")
    
    def get_stats(self) -> Dict[str, float]:
        """Get buffer statistics for monitoring.
        
        Returns:
            Dictionary containing buffer statistics
        """
        if self.size == 0:
            return {
                "buffer_size": 0,
                "capacity_used": 0.0,
                "reward_mean": 0.0,
                "reward_std": 1.0,
                "n_episodes": 0,
            }
        
        return {
            "buffer_size": self.size,
            "capacity_used": self.size / self.capacity,
            "reward_mean": self.reward_mean,
            "reward_std": self.reward_std,
            "n_episodes": len(self.episode_start_indices),
            "avg_episode_length": self.size / max(len(self.episode_start_indices), 1),
        }