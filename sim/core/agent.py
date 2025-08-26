"""Agent dataclass and related functionality.

This module defines the Agent class representing individual birds in the flock,
including their state (position, velocity, energy, stress) and social memory.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np

from .types import (
    Position,
    Velocity,
    AgentID,
    Genome,
    SocialMemory,
    create_vector2d,
)


@dataclass
class Agent:
    """Represents a single agent (bird) in the flock simulation.
    
    Each agent maintains its physical state, energy levels, stress indicators,
    genetic information, and social memory of nearby agents.
    
    Attributes:
        id: Unique identifier for this agent
        position: Current position in 2D space
        velocity: Current velocity vector
        energy: Current energy level (0.0 to 100.0)
        stress: Current stress level (0.0 to 100.0)
        genome: Genetic parameters affecting behavior
        social_memory: Memory of interactions with other agents
        alive: Whether the agent is still active in the simulation
    """
    
    id: AgentID
    position: Position
    velocity: Velocity
    energy: float = 100.0
    stress: float = 0.0
    genome: Genome = field(default_factory=lambda: np.zeros(16, dtype=np.float64))
    social_memory: SocialMemory = field(default_factory=dict)
    alive: bool = True
    hazard_detection: float = 0.5  # How well they detect dangers (0-1)
    beacon_response: float = 1.0  # How well they respond to beacons (0-1)
    
    def __post_init__(self) -> None:
        """Validate agent state after initialization."""
        if not isinstance(self.position, np.ndarray) or self.position.shape != (2,):
            raise ValueError("Position must be a 2D numpy array")
        if not isinstance(self.velocity, np.ndarray) or self.velocity.shape != (2,):
            raise ValueError("Velocity must be a 2D numpy array")
        if not (0.0 <= self.energy <= 100.0):
            raise ValueError("Energy must be between 0.0 and 100.0")
        if not (0.0 <= self.stress <= 100.0):
            raise ValueError("Stress must be between 0.0 and 100.0")
    
    def update_energy(self, delta: float) -> None:
        """Update agent's energy level, clamping to valid range.
        
        Args:
            delta: Change in energy (can be positive or negative)
        """
        self.energy = np.clip(self.energy + delta, 0.0, 100.0)
    
    def update_stress(self, delta: float) -> None:
        """Update agent's stress level, clamping to valid range.
        
        Args:
            delta: Change in stress (can be positive or negative)
        """
        self.stress = np.clip(self.stress + delta, 0.0, 100.0)
    
    def remember_agent(self, other_id: AgentID, interaction_strength: float) -> None:
        """Record or update memory of interaction with another agent.
        
        Args:
            other_id: ID of the other agent
            interaction_strength: Strength of the interaction (0.0 to 1.0)
        """
        interaction_strength = np.clip(interaction_strength, 0.0, 1.0)
        if other_id in self.social_memory:
            # Exponential decay of old memory with new interaction
            self.social_memory[other_id] = (
                0.9 * self.social_memory[other_id] + 0.1 * interaction_strength
            )
        else:
            self.social_memory[other_id] = interaction_strength
    
    def forget_agent(self, other_id: AgentID) -> None:
        """Remove an agent from social memory.
        
        Args:
            other_id: ID of the agent to forget
        """
        self.social_memory.pop(other_id, None)
    
    def get_speed(self) -> float:
        """Get current speed (magnitude of velocity vector).
        
        Returns:
            Speed as a scalar value
        """
        return float(np.linalg.norm(self.velocity))
    
    def get_memory_strength(self, other_id: AgentID) -> float:
        """Get memory strength for a specific agent.
        
        Args:
            other_id: ID of the other agent
            
        Returns:
            Memory strength (0.0 to 1.0), or 0.0 if not remembered
        """
        return self.social_memory.get(other_id, 0.0)
    
    def decay_social_memory(self, decay_rate: float = 0.01) -> None:
        """Apply exponential decay to all social memories.
        
        Args:
            decay_rate: Rate of memory decay per simulation step
        """
        # Remove agents with very weak memories and decay the rest
        to_remove = []
        for agent_id, strength in self.social_memory.items():
            new_strength = strength * (1.0 - decay_rate)
            if new_strength < 0.01:  # Threshold for forgetting
                to_remove.append(agent_id)
            else:
                self.social_memory[agent_id] = new_strength
        
        for agent_id in to_remove:
            del self.social_memory[agent_id]
    
    def is_exhausted(self) -> bool:
        """Check if agent is exhausted (very low energy).
        
        Returns:
            True if energy is below critical threshold
        """
        return self.energy < 10.0
    
    def is_stressed(self) -> bool:
        """Check if agent is highly stressed.
        
        Returns:
            True if stress is above high threshold
        """
        return self.stress > 70.0


def create_agent(
    agent_id: AgentID,
    position: Optional[Position] = None,
    velocity: Optional[Velocity] = None,
    rng: Optional[np.random.Generator] = None,
) -> Agent:
    """Factory function to create a new agent with optional randomization.
    
    Args:
        agent_id: Unique identifier for the agent
        position: Starting position (random if None)
        velocity: Starting velocity (zero if None)
        rng: Random number generator for initialization
        
    Returns:
        New Agent instance
    """
    if rng is None:
        rng = np.random.default_rng()
    
    if position is None:
        # Random position in [0, 100] x [0, 100] square
        position = create_vector2d(
            rng.uniform(0, 100), 
            rng.uniform(0, 100)
        )
    
    if velocity is None:
        velocity = create_vector2d(0.0, 0.0)
    
    # Random genome with values in [-1, 1]
    genome = rng.uniform(-1.0, 1.0, 16).astype(np.float64)
    
    return Agent(
        id=agent_id,
        position=position,
        velocity=velocity,
        energy=rng.uniform(80.0, 100.0),  # Start with high energy
        stress=rng.uniform(0.0, 20.0),    # Start with low stress
        genome=genome,
    )