"""Policy network implementation for Murmuration agents.

This module implements the MLP policy network as specified in CLAUDE.md:
- Architecture: input→64→64→2 with Tanh activations
- Output: acceleration vector (2D)
- Input: observation vector (~32 dimensions)
- Deterministic forward passes with proper RNG handling
"""

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except ImportError:
    # Use mock for testing
    import sys
    sys.path.insert(0, '/Users/benjamin.pommeraud/Desktop/Murmuration')
    import mock_torch as torch
    nn = torch.nn
    F = torch  # Mock F functions directly in torch
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import pickle
import hashlib

from ..core.types import RNG
from ..utils.logging import get_logger

logger = get_logger()


@dataclass
class PolicySnapshot:
    """Deterministic policy snapshot with weights and RNG states.
    
    This class encapsulates everything needed to exactly reproduce
    a policy state, including network weights and random number generator states.
    """
    weights: Dict[str, torch.Tensor]
    torch_rng_state: torch.Tensor
    numpy_rng_state: Dict[str, Any]
    policy_config: Dict[str, Any]
    training_step: int
    checksum: str
    
    def save(self, path: Path) -> None:
        """Save policy snapshot to disk.
        
        Args:
            path: Path to save the snapshot
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            pickle.dump(self, f)
            
        logger.info(
            "Policy snapshot saved",
            extra={
                "path": str(path),
                "training_step": self.training_step,
                "checksum": self.checksum,
            }
        )
    
    @classmethod
    def load(cls, path: Path) -> "PolicySnapshot":
        """Load policy snapshot from disk.
        
        Args:
            path: Path to load the snapshot from
            
        Returns:
            Loaded policy snapshot
            
        Raises:
            FileNotFoundError: If snapshot file doesn't exist
            ValueError: If snapshot is corrupted
        """
        if not path.exists():
            raise FileNotFoundError(f"Policy snapshot not found: {path}")
            
        with open(path, 'rb') as f:
            snapshot = pickle.load(f)
            
        if not isinstance(snapshot, cls):
            raise ValueError(f"Invalid snapshot format in {path}")
            
        logger.info(
            "Policy snapshot loaded",
            extra={
                "path": str(path),
                "training_step": snapshot.training_step,
                "checksum": snapshot.checksum,
            }
        )
        
        return snapshot


class MLPPolicy(nn.Module):
    """Multi-layer perceptron policy network.
    
    Architecture follows CLAUDE.md specification:
    - Input layer: observation_dim (typically ~32)
    - Hidden layers: 64 → 64 with Tanh activation
    - Output layer: 2 (acceleration vector)
    
    The network outputs raw acceleration values that will be clamped
    to action limits by the environment.
    """
    
    def __init__(
        self,
        observation_dim: int = 32,
        hidden_dim: int = 64,
        action_dim: int = 2,
        rng: Optional[RNG] = None,
    ):
        """Initialize the MLP policy network.
        
        Args:
            observation_dim: Dimension of observation vector
            hidden_dim: Hidden layer dimension
            action_dim: Output action dimension (should be 2)
            rng: Random number generator for weight initialization
        """
        super().__init__()
        
        if rng is None:
            rng = np.random.default_rng()
            
        self.observation_dim = observation_dim
        self.hidden_dim = hidden_dim
        self.action_dim = action_dim
        
        # Network layers
        self.fc1 = nn.Linear(observation_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, action_dim)
        
        # Initialize weights deterministically
        self._initialize_weights(rng)
        
        logger.debug(
            "MLP policy initialized",
            extra={
                "observation_dim": observation_dim,
                "hidden_dim": hidden_dim,
                "action_dim": action_dim,
                "total_params": self.count_parameters(),
            }
        )
    
    def _initialize_weights(self, rng: RNG) -> None:
        """Initialize network weights using Xavier/Glorot initialization.
        
        Args:
            rng: Random number generator for deterministic initialization
        """
        for layer in [self.fc1, self.fc2, self.fc3]:
            # Xavier initialization for weights
            fan_in, fan_out = layer.weight.shape[1], layer.weight.shape[0]
            std = np.sqrt(2.0 / (fan_in + fan_out))
            
            with torch.no_grad():
                weights = rng.normal(0.0, std, layer.weight.shape).astype(np.float32)
                layer.weight.copy_(torch.from_numpy(weights))
                
                # Zero bias initialization
                layer.bias.zero_()
    
    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        """Forward pass through the network.
        
        Args:
            observations: Batch of observations [batch_size, observation_dim]
            
        Returns:
            Action predictions [batch_size, action_dim]
        """
        # Input validation
        if observations.shape[-1] != self.observation_dim:
            raise ValueError(
                f"Expected observation dim {self.observation_dim}, "
                f"got {observations.shape[-1]}"
            )
        
        # Forward pass with Tanh activations
        x = torch.tanh(self.fc1(observations))
        x = torch.tanh(self.fc2(x))
        actions = self.fc3(x)  # No activation on output layer
        
        # Check for NaNs (guardrail)
        if torch.isnan(actions).any():
            logger.error("NaN detected in policy output")
            raise ValueError("NaN detected in policy forward pass")
        
        return actions
    
    def get_action(
        self,
        observation: np.ndarray,
        deterministic: bool = False,
        rng: Optional[RNG] = None,
    ) -> Tuple[np.ndarray, Dict[str, float]]:
        """Get action from observation with optional noise.
        
        Args:
            observation: Single observation vector
            deterministic: If True, return deterministic action
            rng: Random number generator for action noise
            
        Returns:
            Tuple of (action, info_dict) where info contains policy statistics
        """
        if observation.shape != (self.observation_dim,):
            raise ValueError(
                f"Expected observation shape ({self.observation_dim},), "
                f"got {observation.shape}"
            )
        
        with torch.no_grad():
            obs_tensor = torch.from_numpy(observation).float().unsqueeze(0)
            action_tensor = self.forward(obs_tensor)
            action = action_tensor.squeeze(0).numpy()
        
        # Add exploration noise if not deterministic
        if not deterministic and rng is not None:
            noise_std = 0.1  # Fixed noise standard deviation
            noise = rng.normal(0.0, noise_std, action.shape)
            action = action + noise
        
        # Compute policy statistics for logging
        info = {
            "action_magnitude": float(np.linalg.norm(action)),
            "action_x": float(action[0]),
            "action_y": float(action[1]),
        }
        
        return action.astype(np.float64), info
    
    def count_parameters(self) -> int:
        """Count total trainable parameters.
        
        Returns:
            Number of trainable parameters
        """
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
    
    def get_weights_checksum(self) -> str:
        """Compute checksum of current weights for verification.
        
        Returns:
            Hex string checksum of concatenated weights
        """
        weights_bytes = b""
        for param in self.parameters():
            weights_bytes += param.data.cpu().numpy().tobytes()
        return hashlib.sha256(weights_bytes).hexdigest()[:16]
    
    def create_snapshot(
        self,
        training_step: int = 0,
        torch_rng_state: Optional[torch.Tensor] = None,
        numpy_rng_state: Optional[Dict[str, Any]] = None,
    ) -> PolicySnapshot:
        """Create a policy snapshot for deterministic saving.
        
        Args:
            training_step: Current training step
            torch_rng_state: PyTorch RNG state (if None, uses current state)
            numpy_rng_state: NumPy RNG state (if None, uses current state)
            
        Returns:
            PolicySnapshot containing all necessary state information
        """
        # Get current RNG states if not provided
        if torch_rng_state is None:
            torch_rng_state = torch.get_rng_state()
        if numpy_rng_state is None:
            numpy_rng_state = np.random.get_state()
        
        # Extract model weights
        weights = {name: param.clone() for name, param in self.state_dict().items()}
        
        # Policy configuration
        policy_config = {
            "observation_dim": self.observation_dim,
            "hidden_dim": self.hidden_dim,
            "action_dim": self.action_dim,
            "architecture": "MLP",
        }
        
        # Compute checksum
        checksum = self.get_weights_checksum()
        
        return PolicySnapshot(
            weights=weights,
            torch_rng_state=torch_rng_state,
            numpy_rng_state=numpy_rng_state,
            policy_config=policy_config,
            training_step=training_step,
            checksum=checksum,
        )
    
    def load_snapshot(self, snapshot: PolicySnapshot) -> None:
        """Load policy from snapshot.
        
        Args:
            snapshot: Policy snapshot to load
            
        Raises:
            ValueError: If snapshot configuration doesn't match current policy
        """
        # Verify configuration compatibility
        config = snapshot.policy_config
        if (
            config.get("observation_dim") != self.observation_dim
            or config.get("hidden_dim") != self.hidden_dim
            or config.get("action_dim") != self.action_dim
        ):
            raise ValueError(
                f"Snapshot configuration mismatch: "
                f"expected ({self.observation_dim}, {self.hidden_dim}, {self.action_dim}), "
                f"got ({config.get('observation_dim')}, {config.get('hidden_dim')}, "
                f"{config.get('action_dim')})"
            )
        
        # Load weights
        self.load_state_dict(snapshot.weights)
        
        # Restore RNG states
        torch.set_rng_state(snapshot.torch_rng_state)
        np.random.set_state(snapshot.numpy_rng_state)
        
        # Verify checksum
        current_checksum = self.get_weights_checksum()
        if current_checksum != snapshot.checksum:
            logger.warning(
                "Checksum mismatch after loading snapshot",
                extra={
                    "expected": snapshot.checksum,
                    "actual": current_checksum,
                }
            )
        
        logger.info(
            "Policy snapshot loaded successfully",
            extra={
                "training_step": snapshot.training_step,
                "checksum": snapshot.checksum,
            }
        )


def create_observation_vector(
    agent_velocity: np.ndarray,
    raycast_distances: np.ndarray,
    neighbor_count: int,
    neighbor_avg_distance: float,
    neighbor_cohesion: float,
    signal_gradient_x: float,
    signal_gradient_y: float,
    time_of_day: float,
    energy_level: float,
    social_stress: float,
    risk_level: float,
) -> np.ndarray:
    """Create observation vector from agent state.
    
    This function constructs the ~32-dimensional observation vector
    as specified in CLAUDE.md from various agent and environment features.
    
    Args:
        agent_velocity: Agent's current velocity [vx, vy]
        raycast_distances: 8 raycast distance measurements
        neighbor_count: Number of nearby neighbors
        neighbor_avg_distance: Average distance to neighbors
        neighbor_cohesion: Local cohesion measure
        signal_gradient_x: Beacon signal gradient in X direction
        signal_gradient_y: Beacon signal gradient in Y direction
        time_of_day: Normalized time of day [0, 1]
        energy_level: Agent energy level [0, 1]
        social_stress: Social stress level [0, 1]
        risk_level: Environmental risk level [0, 1]
        
    Returns:
        Observation vector of shape (32,)
    """
    # Validate inputs
    if raycast_distances.shape != (8,):
        raise ValueError(f"Expected 8 raycast distances, got {raycast_distances.shape}")
    
    if agent_velocity.shape != (2,):
        raise ValueError(f"Expected velocity shape (2,), got {agent_velocity.shape}")
    
    # Normalize velocity (typical max speed ~5.0)
    velocity_norm = agent_velocity / 5.0
    
    # Normalize raycast distances (typical max range ~50.0)
    raycast_norm = raycast_distances / 50.0
    
    # Normalize neighbor distance (typical max ~30.0)
    neighbor_dist_norm = min(neighbor_avg_distance / 30.0, 1.0)
    
    # Normalize neighbor count (typical max ~20)
    neighbor_count_norm = min(neighbor_count / 20.0, 1.0)
    
    # Construct observation vector
    observation = np.concatenate([
        velocity_norm,  # [0:2] - agent velocity (normalized)
        raycast_norm,   # [2:10] - 8 raycast distances (normalized)
        [neighbor_count_norm],      # [10] - neighbor count (normalized)
        [neighbor_dist_norm],       # [11] - neighbor distance (normalized)  
        [neighbor_cohesion],        # [12] - neighbor cohesion [0, 1]
        [signal_gradient_x / 10.0], # [13] - beacon signal gradient X (normalized)
        [signal_gradient_y / 10.0], # [14] - beacon signal gradient Y (normalized)
        [time_of_day],             # [15] - time of day [0, 1]
        [energy_level],            # [16] - energy level [0, 1]
        [social_stress],           # [17] - social stress [0, 1]
        [risk_level],              # [18] - environmental risk [0, 1]
        # Padding to reach 32 dimensions with zeros
        np.zeros(13),              # [19:32] - reserved for future features
    ])
    
    # Ensure exact dimension
    assert observation.shape == (32,), f"Observation shape mismatch: {observation.shape}"
    
    # Clamp values to reasonable ranges (guardrail)
    observation = np.clip(observation, -10.0, 10.0)
    
    return observation.astype(np.float64)