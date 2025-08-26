"""Common type definitions for the Murmuration simulation.

This module defines fundamental types used throughout the simulation system,
ensuring type safety and consistency across all components.
"""

from typing import NewType, Dict, List, Any, TypeAlias
import numpy as np
import numpy.typing as npt

# Fundamental numeric types
Float = float
Int = int

# Spatial types
Vector2D: TypeAlias = npt.NDArray[np.float64]  # Shape (2,) - [x, y]
Position: TypeAlias = Vector2D
Velocity: TypeAlias = Vector2D

# Array types for multiple agents
Positions: TypeAlias = npt.NDArray[np.float64]  # Shape (N, 2)
Velocities: TypeAlias = npt.NDArray[np.float64]  # Shape (N, 2)

# Agent identifiers
AgentID = NewType("AgentID", int)

# Time and simulation
Tick = NewType("Tick", int)
Timestamp = NewType("Timestamp", float)

# Environment field types
Field2D: TypeAlias = npt.NDArray[np.float64]  # Shape (height, width)

# Genetic information
Genome: TypeAlias = npt.NDArray[np.float64]  # Shape (gene_count,)

# Social memory representation
SocialMemory: TypeAlias = Dict[AgentID, float]

# Scoring types
StarRating = NewType("StarRating", int)  # 0, 1, 2, or 3 stars

# Event logging
EventData: TypeAlias = Dict[str, Any]

# Random number generation
RNG: TypeAlias = np.random.Generator


def create_vector2d(x: float, y: float) -> Vector2D:
    """Create a 2D vector from x, y coordinates.
    
    Args:
        x: X coordinate
        y: Y coordinate
        
    Returns:
        2D numpy array representing the vector
    """
    return np.array([x, y], dtype=np.float64)


def create_positions_array(n_agents: int) -> Positions:
    """Create an empty positions array for n agents.
    
    Args:
        n_agents: Number of agents
        
    Returns:
        Positions array initialized to zeros
    """
    return np.zeros((n_agents, 2), dtype=np.float64)


def create_velocities_array(n_agents: int) -> Velocities:
    """Create an empty velocities array for n agents.
    
    Args:
        n_agents: Number of agents
        
    Returns:
        Velocities array initialized to zeros
    """
    return np.zeros((n_agents, 2), dtype=np.float64)