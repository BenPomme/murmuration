"""Core simulation components.

This module contains the fundamental building blocks of the Murmuration simulation:
- Agent state and behavior
- Environment modeling
- Physics integration
- Common type definitions
"""

from .agent import Agent
from .environment import Environment
from .types import Position, Velocity, Vector2D

__all__ = ["Agent", "Environment", "Position", "Velocity", "Vector2D"]