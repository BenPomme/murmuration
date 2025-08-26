"""PPO-lite training implementation for Murmuration agents.

This module implements the Proximal Policy Optimization (PPO) algorithm
as specified in CLAUDE.md with the following hyperparameters:
- Learning rate: 3e-4
- Discount factor (γ): 0.98  
- GAE lambda (λ): 0.95
- Batch size: 1024
- Training epochs: 4
- Additional guardrails: action clamping, reward clipping, NaN detection, gradient clipping
"""

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    from torch.distributions import Normal
except ImportError:
    # Use mock for testing
    import sys
    sys.path.insert(0, '/Users/benjamin.pommeraud/Desktop/Murmuration')
    import mock_torch as torch
    nn = torch.nn
    optim = torch.optim
    Normal = torch.distributions.Normal
    # Mock F module
    class F:
        @staticmethod
        def mse_loss(input, target, reduction='mean'):
            if hasattr(input, 'data'):
                input_data = input.data
            else:
                input_data = input
            if hasattr(target, 'data'):
                target_data = target.data
            else:
                target_data = target
            diff = input_data - target_data
            loss_val = torch.tensor(diff ** 2).mean().item() if reduction == 'mean' else torch.tensor(diff ** 2).sum().item()
            return torch.tensor(loss_val)
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List
import time

from .policy import MLPPolicy
from .buffer import ExperienceBuffer, TrajectoryBatch, Experience
from ..core.types import RNG
from ..utils.logging import get_logger

logger = get_logger()


@dataclass
class TrainingMetrics:
    """Metrics collected during PPO training.
    
    These metrics are used for monitoring training progress and
    implementing early stopping criteria as specified in CLAUDE.md.
    """
    epoch: int
    policy_loss: float
    value_loss: float
    entropy_loss: float
    total_loss: float
    kl_divergence: float
    entropy: float
    explained_variance: float
    grad_norm: float
    learning_rate: float
    arrivals: int
    cohesion_avg: float
    losses: int
    fps: float
    reward_mean: float
    reward_std: float
    
    def to_dict(self) -> Dict[str, float]:
        """Convert metrics to dictionary for logging.
        
        Returns:
            Dictionary of metric name to value
        """
        return {
            "epoch": self.epoch,
            "policy_loss": self.policy_loss,
            "value_loss": self.value_loss,
            "entropy_loss": self.entropy_loss,
            "total_loss": self.total_loss,
            "kl_divergence": self.kl_divergence,
            "entropy": self.entropy,
            "explained_variance": self.explained_variance,
            "grad_norm": self.grad_norm,
            "learning_rate": self.learning_rate,
            "arrivals": self.arrivals,
            "cohesion_avg": self.cohesion_avg,
            "losses": self.losses,
            "fps": self.fps,
            "reward_mean": self.reward_mean,
            "reward_std": self.reward_std,
        }


class ValueNetwork(nn.Module):
    """Value function network for PPO training.
    
    Separate network for value estimation, using same architecture
    as policy network but with single output.
    """
    
    def __init__(
        self,
        observation_dim: int = 32,
        hidden_dim: int = 64,
        rng: Optional[RNG] = None,
    ):
        """Initialize value network.
        
        Args:
            observation_dim: Input observation dimension
            hidden_dim: Hidden layer dimension
            rng: Random number generator for initialization
        """
        super().__init__()
        
        if rng is None:
            rng = np.random.default_rng()
        
        self.observation_dim = observation_dim
        self.hidden_dim = hidden_dim
        
        # Network layers (same as policy but single output)
        self.fc1 = nn.Linear(observation_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, 1)
        
        # Initialize weights
        self._initialize_weights(rng)
    
    def _initialize_weights(self, rng: RNG) -> None:
        """Initialize weights using Xavier initialization."""
        for layer in [self.fc1, self.fc2, self.fc3]:
            fan_in, fan_out = layer.weight.shape[1], layer.weight.shape[0]
            std = np.sqrt(2.0 / (fan_in + fan_out))
            
            with torch.no_grad():
                weights = rng.normal(0.0, std, layer.weight.shape).astype(np.float32)
                layer.weight.copy_(torch.from_numpy(weights))
                layer.bias.zero_()
    
    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """Forward pass through value network.
        
        Args:
            observations: Batch of observations
            
        Returns:
            Value estimates [batch_size, 1]
        """
        x = torch.tanh(self.fc1(observations))
        x = torch.tanh(self.fc2(x))
        values = self.fc3(x)
        
        # Check for NaNs (guardrail)
        if torch.isnan(values).any():
            logger.error("NaN detected in value network output")
            raise ValueError("NaN detected in value network forward pass")
        
        return values


class PPOTrainer:
    """PPO-lite trainer implementation.
    
    Implements Proximal Policy Optimization with the specific hyperparameters
    and guardrails required by CLAUDE.md.
    """
    
    def __init__(
        self,
        policy: MLPPolicy,
        experience_buffer: ExperienceBuffer,
        learning_rate: float = 3e-4,
        gamma: float = 0.98,
        gae_lambda: float = 0.95,
        batch_size: int = 1024,
        n_epochs: int = 4,
        clip_ratio: float = 0.2,
        entropy_coef: float = 0.01,
        value_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        target_kl: float = 0.01,
        rng: Optional[RNG] = None,
    ):
        """Initialize PPO trainer.
        
        Args:
            policy: Policy network to train
            experience_buffer: Experience buffer for sampling
            learning_rate: Adam learning rate
            gamma: Discount factor
            gae_lambda: GAE lambda parameter
            batch_size: Mini-batch size for training
            n_epochs: Number of training epochs per update
            clip_ratio: PPO clipping parameter
            entropy_coef: Entropy loss coefficient
            value_coef: Value loss coefficient
            max_grad_norm: Maximum gradient norm for clipping
            target_kl: Target KL divergence for early stopping
            rng: Random number generator
        """
        if rng is None:
            rng = np.random.default_rng()
        
        self.policy = policy
        self.experience_buffer = experience_buffer
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.batch_size = batch_size
        self.n_epochs = n_epochs
        self.clip_ratio = clip_ratio
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        self.max_grad_norm = max_grad_norm
        self.target_kl = target_kl
        self.rng = rng
        
        # Create value network
        self.value_net = ValueNetwork(
            observation_dim=policy.observation_dim,
            hidden_dim=policy.hidden_dim,
            rng=rng,
        )
        
        # Optimizers
        self.policy_optimizer = optim.Adam(policy.parameters(), lr=learning_rate)
        self.value_optimizer = optim.Adam(self.value_net.parameters(), lr=learning_rate)
        
        # Training state
        self.training_step = 0
        self.early_stop_count = 0
        self.best_arrivals = 0
        
        # Enable deterministic algorithms
        torch.use_deterministic_algorithms(True)
        
        logger.info(
            "PPO trainer initialized",
            extra={
                "learning_rate": learning_rate,
                "gamma": gamma,
                "gae_lambda": gae_lambda,
                "batch_size": batch_size,
                "n_epochs": n_epochs,
                "clip_ratio": clip_ratio,
                "entropy_coef": entropy_coef,
                "value_coef": value_coef,
                "max_grad_norm": max_grad_norm,
                "target_kl": target_kl,
            }
        )
    
    def get_value_estimate(self, observation: np.ndarray) -> float:
        """Get value estimate for a single observation.
        
        Args:
            observation: Observation vector
            
        Returns:
            Value estimate
        """
        with torch.no_grad():
            obs_tensor = torch.from_numpy(observation).float().unsqueeze(0)
            value = self.value_net(obs_tensor).item()
        return value
    
    def get_action_and_value(
        self,
        observation: np.ndarray,
        deterministic: bool = False,
    ) -> Tuple[np.ndarray, float, float, Dict[str, float]]:
        """Get action, value, and log probability from observation.
        
        Args:
            observation: Observation vector
            deterministic: Whether to use deterministic action selection
            
        Returns:
            Tuple of (action, value_estimate, log_prob, info_dict)
        """
        with torch.no_grad():
            obs_tensor = torch.from_numpy(observation).float().unsqueeze(0)
            
            # Get policy output and value
            action_mean = self.policy(obs_tensor)
            value = self.value_net(obs_tensor).item()
            
            if deterministic:
                action = action_mean.squeeze(0).numpy()
                log_prob = 0.0  # Not used for deterministic actions
            else:
                # Create action distribution (assume fixed std for simplicity)
                action_std = 0.1
                dist = Normal(action_mean, action_std)
                action_tensor = dist.sample()
                log_prob = dist.log_prob(action_tensor).sum().item()
                action = action_tensor.squeeze(0).numpy()
            
            # Clamp actions to reasonable range (guardrail)
            action = np.clip(action, -5.0, 5.0)
            
            info = {
                "value_estimate": value,
                "action_magnitude": float(np.linalg.norm(action)),
            }
            
            return action.astype(np.float64), value, log_prob, info
    
    def compute_policy_loss(self, batch: TrajectoryBatch) -> Tuple[torch.Tensor, Dict[str, float]]:
        """Compute PPO policy loss.
        
        Args:
            batch: Training batch
            
        Returns:
            Tuple of (loss_tensor, info_dict)
        """
        obs_tensor = torch.from_numpy(batch.observations).float()
        actions_tensor = torch.from_numpy(batch.actions).float()
        old_log_probs_tensor = torch.from_numpy(batch.log_probs).float()
        advantages_tensor = torch.from_numpy(batch.advantages).float()
        
        # Get current policy outputs
        action_mean = self.policy(obs_tensor)
        
        # Compute new log probabilities (assume fixed std)
        action_std = 0.1
        dist = Normal(action_mean, action_std)
        new_log_probs = dist.log_prob(actions_tensor).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1).mean()
        
        # Compute ratio and surrogate losses
        ratio = torch.exp(new_log_probs - old_log_probs_tensor)
        surr1 = ratio * advantages_tensor
        surr2 = torch.clamp(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio) * advantages_tensor
        
        policy_loss = -torch.min(surr1, surr2).mean()
        entropy_loss = -entropy * self.entropy_coef
        
        total_loss = policy_loss + entropy_loss
        
        # Compute KL divergence for monitoring
        with torch.no_grad():
            kl_div = (old_log_probs_tensor - new_log_probs).mean().item()
        
        info = {
            "policy_loss": policy_loss.item(),
            "entropy_loss": entropy_loss.item(),
            "entropy": entropy.item(),
            "kl_divergence": kl_div,
        }
        
        return total_loss, info
    
    def compute_value_loss(self, batch: TrajectoryBatch) -> torch.Tensor:
        """Compute value function loss.
        
        Args:
            batch: Training batch
            
        Returns:
            Value loss tensor
        """
        obs_tensor = torch.from_numpy(batch.observations).float()
        returns_tensor = torch.from_numpy(batch.returns).float()
        
        # Get value predictions
        value_preds = self.value_net(obs_tensor).squeeze(-1)
        
        # MSE loss
        value_loss = F.mse_loss(value_preds, returns_tensor)
        
        return value_loss
    
    def update_networks(self, batch: TrajectoryBatch) -> Dict[str, float]:
        """Update policy and value networks.
        
        Args:
            batch: Training batch
            
        Returns:
            Dictionary of training metrics
        """
        metrics = {}
        
        # Compute losses
        policy_loss, policy_info = self.compute_policy_loss(batch)
        value_loss = self.compute_value_loss(batch)
        
        # Update policy network
        self.policy_optimizer.zero_grad()
        policy_loss.backward()
        
        # Gradient clipping (guardrail)
        policy_grad_norm = torch.nn.utils.clip_grad_norm_(
            self.policy.parameters(),
            self.max_grad_norm
        ).item()
        
        # Check for NaN gradients (guardrail)
        for param in self.policy.parameters():
            if param.grad is not None and torch.isnan(param.grad).any():
                logger.error("NaN gradient detected in policy network")
                raise ValueError("NaN gradient in policy network")
        
        self.policy_optimizer.step()
        
        # Update value network
        self.value_optimizer.zero_grad()
        value_loss.backward()
        
        # Gradient clipping
        value_grad_norm = torch.nn.utils.clip_grad_norm_(
            self.value_net.parameters(),
            self.max_grad_norm
        ).item()
        
        # Check for NaN gradients
        for param in self.value_net.parameters():
            if param.grad is not None and torch.isnan(param.grad).any():
                logger.error("NaN gradient detected in value network")
                raise ValueError("NaN gradient in value network")
        
        self.value_optimizer.step()
        
        # Collect metrics
        metrics.update(policy_info)
        metrics["value_loss"] = value_loss.item()
        metrics["total_loss"] = policy_loss.item() + value_loss.item()
        metrics["policy_grad_norm"] = policy_grad_norm
        metrics["value_grad_norm"] = value_grad_norm
        metrics["grad_norm"] = max(policy_grad_norm, value_grad_norm)
        
        return metrics
    
    def train_step(self) -> Optional[TrainingMetrics]:
        """Perform one training step using buffered experiences.
        
        Returns:
            Training metrics if successful, None if insufficient data
        """
        if self.experience_buffer.size < self.batch_size:
            logger.warning(
                "Insufficient data for training",
                extra={
                    "buffer_size": self.experience_buffer.size,
                    "required": self.batch_size,
                }
            )
            return None
        
        start_time = time.time()
        
        # Prepare buffer
        self.experience_buffer.compute_advantages_and_returns()
        self.experience_buffer.normalize_advantages()
        
        # Get all data
        full_batch = self.experience_buffer.get_all_data()
        
        # Training metrics accumulator
        epoch_metrics: List[Dict[str, float]] = []
        
        # Train for multiple epochs
        for epoch in range(self.n_epochs):
            # Shuffle data
            shuffled_batch = full_batch.shuffle(self.rng)
            
            # Train on mini-batches
            batch_metrics: List[Dict[str, float]] = []
            for mini_batch in shuffled_batch.split(self.batch_size):
                metrics = self.update_networks(mini_batch)
                batch_metrics.append(metrics)
            
            # Average metrics across mini-batches
            if batch_metrics:
                avg_metrics = {
                    key: np.mean([m[key] for m in batch_metrics])
                    for key in batch_metrics[0].keys()
                }
                epoch_metrics.append(avg_metrics)
            
            # Check KL divergence for early stopping
            if epoch_metrics:
                current_kl = epoch_metrics[-1]["kl_divergence"]
                if current_kl > self.target_kl:
                    logger.info(
                        "Early stopping due to KL divergence",
                        extra={
                            "current_kl": current_kl,
                            "target_kl": self.target_kl,
                            "epoch": epoch,
                        }
                    )
                    break
        
        # Average metrics across epochs
        if not epoch_metrics:
            logger.error("No training metrics collected")
            return None
        
        final_metrics = {
            key: np.mean([m[key] for m in epoch_metrics])
            for key in epoch_metrics[0].keys()
        }
        
        # Additional metrics
        buffer_stats = self.experience_buffer.get_stats()
        training_time = time.time() - start_time
        
        # Create training metrics object
        training_metrics = TrainingMetrics(
            epoch=self.training_step,
            policy_loss=final_metrics["policy_loss"],
            value_loss=final_metrics["value_loss"],
            entropy_loss=final_metrics["entropy_loss"],
            total_loss=final_metrics["total_loss"],
            kl_divergence=final_metrics["kl_divergence"],
            entropy=final_metrics["entropy"],
            explained_variance=0.0,  # TODO: Compute explained variance
            grad_norm=final_metrics["grad_norm"],
            learning_rate=self.learning_rate,
            arrivals=0,  # Will be filled in by evaluation
            cohesion_avg=0.0,  # Will be filled in by evaluation
            losses=0,  # Will be filled in by evaluation
            fps=0.0,  # Will be filled in by evaluation
            reward_mean=buffer_stats["reward_mean"],
            reward_std=buffer_stats["reward_std"],
        )
        
        self.training_step += 1
        
        logger.info(
            "Training step completed",
            extra={
                "training_step": self.training_step,
                "training_time": training_time,
                "metrics": training_metrics.to_dict(),
            }
        )
        
        return training_metrics
    
    def should_early_stop(self, current_arrivals: int, patience: int = 3) -> bool:
        """Check if training should stop early due to plateau.
        
        Args:
            current_arrivals: Current evaluation arrivals
            patience: Number of evaluations to wait for improvement
            
        Returns:
            True if training should stop early
        """
        if current_arrivals > self.best_arrivals:
            self.best_arrivals = current_arrivals
            self.early_stop_count = 0
            return False
        else:
            self.early_stop_count += 1
            
            if self.early_stop_count >= patience:
                logger.info(
                    "Early stopping triggered",
                    extra={
                        "best_arrivals": self.best_arrivals,
                        "current_arrivals": current_arrivals,
                        "patience": patience,
                    }
                )
                return True
            
            return False
    
    def save_checkpoint(self, path: str) -> None:
        """Save training checkpoint.
        
        Args:
            path: Path to save checkpoint
        """
        checkpoint = {
            "policy_state_dict": self.policy.state_dict(),
            "value_net_state_dict": self.value_net.state_dict(),
            "policy_optimizer_state_dict": self.policy_optimizer.state_dict(),
            "value_optimizer_state_dict": self.value_optimizer.state_dict(),
            "training_step": self.training_step,
            "best_arrivals": self.best_arrivals,
            "early_stop_count": self.early_stop_count,
            "rng_state": self.rng.bit_generator.state,
        }
        
        torch.save(checkpoint, path)
        logger.info("Training checkpoint saved", extra={"path": path})
    
    def load_checkpoint(self, path: str) -> None:
        """Load training checkpoint.
        
        Args:
            path: Path to load checkpoint from
        """
        checkpoint = torch.load(path)
        
        self.policy.load_state_dict(checkpoint["policy_state_dict"])
        self.value_net.load_state_dict(checkpoint["value_net_state_dict"])
        self.policy_optimizer.load_state_dict(checkpoint["policy_optimizer_state_dict"])
        self.value_optimizer.load_state_dict(checkpoint["value_optimizer_state_dict"])
        
        self.training_step = checkpoint["training_step"]
        self.best_arrivals = checkpoint["best_arrivals"]
        self.early_stop_count = checkpoint["early_stop_count"]
        
        # Restore RNG state
        self.rng.bit_generator.state = checkpoint["rng_state"]
        
        logger.info("Training checkpoint loaded", extra={"path": path})