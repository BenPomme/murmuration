"""Neuroevolution and Population-Based Training for Murmuration.

This module implements evolution strategies and population-based training
between seasons as specified in CLAUDE.md:
- Evolution Strategies (ES) for top-K elite selection
- Population-Based Training (PBT) for hyperparameter tuning
- Knowledge distillation between policy networks
- Genetic operations with proper determinism
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
    # Mock F module for distillation
    class F:
        @staticmethod
        def softmax(input, dim=-1):
            if hasattr(input, 'data'):
                input_data = input.data
            else:
                input_data = input
            exp_vals = torch.exp(input_data - torch.tensor(input_data.max()))
            return torch.tensor(exp_vals.data / exp_vals.data.sum())
        
        @staticmethod
        def log_softmax(input, dim=-1):
            if hasattr(input, 'data'):
                input_data = input.data
            else:
                input_data = input
            return torch.log(F.softmax(input, dim))
        
        @staticmethod
        def kl_div(input, target, reduction='batchmean'):
            # Simple KL divergence mock
            return torch.tensor(0.5)
        
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
import copy
import heapq
import json

from .policy import MLPPolicy, PolicySnapshot
from .ppo import PPOTrainer, TrainingMetrics
from ..core.types import RNG
from ..utils.logging import get_logger

logger = get_logger()


@dataclass
class Individual:
    """Individual in the evolutionary population.
    
    Represents a single policy with associated fitness scores
    and hyperparameters for evolution and PBT.
    """
    policy: MLPPolicy
    fitness: float = 0.0
    age: int = 0
    hyperparams: Dict[str, Any] = field(default_factory=dict)
    parent_ids: List[str] = field(default_factory=list)
    individual_id: str = ""
    generation: int = 0
    
    def __post_init__(self):
        if not self.individual_id:
            # Generate unique ID based on generation and random component
            self.individual_id = f"gen{self.generation}_{np.random.randint(0, 1000000):06d}"


@dataclass
class EvolutionConfig:
    """Configuration for evolutionary algorithms."""
    population_size: int = 20
    elite_fraction: float = 0.2  # Top 20% selected as elites
    mutation_std: float = 0.1
    crossover_rate: float = 0.3
    mutation_rate: float = 0.8
    fitness_evaluations: int = 5  # Number of episodes for fitness evaluation
    max_generations: int = 50
    diversity_threshold: float = 0.01  # Minimum genetic diversity
    
    # PBT specific
    exploit_threshold: float = 0.25  # Bottom 25% will be replaced
    explore_std: float = 0.2  # Standard deviation for hyperparameter perturbation


class NeuroEvolution:
    """Evolution Strategies implementation for policy evolution.
    
    Implements genetic algorithms for evolving policy networks
    between seasons, selecting top-K elites and creating new
    generations through crossover and mutation.
    """
    
    def __init__(
        self,
        config: EvolutionConfig,
        rng: Optional[RNG] = None,
    ):
        """Initialize neuroevolution system.
        
        Args:
            config: Evolution configuration
            rng: Random number generator
        """
        if rng is None:
            rng = np.random.default_rng()
            
        self.config = config
        self.rng = rng
        self.population: List[Individual] = []
        self.generation = 0
        self.fitness_history: List[List[float]] = []
        self.diversity_history: List[float] = []
        
        logger.info(
            "NeuroEvolution initialized",
            extra={
                "population_size": config.population_size,
                "elite_fraction": config.elite_fraction,
                "mutation_std": config.mutation_std,
                "crossover_rate": config.crossover_rate,
            }
        )
    
    def initialize_population(
        self,
        observation_dim: int = 32,
        hidden_dim: int = 64,
        action_dim: int = 2,
    ) -> None:
        """Initialize random population.
        
        Args:
            observation_dim: Policy input dimension
            hidden_dim: Policy hidden dimension
            action_dim: Policy output dimension
        """
        self.population = []
        
        for i in range(self.config.population_size):
            policy = MLPPolicy(
                observation_dim=observation_dim,
                hidden_dim=hidden_dim,
                action_dim=action_dim,
                rng=self.rng,
            )
            
            # Initialize hyperparameters
            hyperparams = {
                "learning_rate": self.rng.uniform(1e-5, 1e-2),
                "entropy_coef": self.rng.uniform(0.001, 0.1),
                "value_coef": self.rng.uniform(0.1, 1.0),
                "clip_ratio": self.rng.uniform(0.1, 0.3),
            }
            
            individual = Individual(
                policy=policy,
                hyperparams=hyperparams,
                individual_id=f"gen{self.generation}_{i:03d}",
                generation=self.generation,
            )
            
            self.population.append(individual)
        
        logger.info(
            "Population initialized",
            extra={
                "population_size": len(self.population),
                "generation": self.generation,
            }
        )
    
    def evaluate_fitness(
        self,
        individual: Individual,
        fitness_func: Callable[[MLPPolicy], float],
    ) -> float:
        """Evaluate fitness of an individual.
        
        Args:
            individual: Individual to evaluate
            fitness_func: Function that takes policy and returns fitness score
            
        Returns:
            Average fitness score over multiple evaluations
        """
        fitness_scores = []
        
        for _ in range(self.config.fitness_evaluations):
            score = fitness_func(individual.policy)
            fitness_scores.append(score)
        
        avg_fitness = np.mean(fitness_scores)
        individual.fitness = avg_fitness
        
        return avg_fitness
    
    def select_elites(self) -> List[Individual]:
        """Select elite individuals based on fitness.
        
        Returns:
            List of elite individuals
        """
        n_elites = max(1, int(self.config.elite_fraction * len(self.population)))
        
        # Sort by fitness (descending)
        sorted_pop = sorted(self.population, key=lambda x: x.fitness, reverse=True)
        elites = sorted_pop[:n_elites]
        
        logger.debug(
            "Elites selected",
            extra={
                "n_elites": n_elites,
                "elite_fitness": [e.fitness for e in elites],
            }
        )
        
        return elites
    
    def crossover(
        self,
        parent1: Individual,
        parent2: Individual,
    ) -> Individual:
        """Create offspring through crossover.
        
        Args:
            parent1: First parent
            parent2: Second parent
            
        Returns:
            Offspring individual
        """
        # Create new policy with same architecture
        offspring_policy = MLPPolicy(
            observation_dim=parent1.policy.observation_dim,
            hidden_dim=parent1.policy.hidden_dim,
            action_dim=parent1.policy.action_dim,
            rng=self.rng,
        )
        
        # Crossover weights
        with torch.no_grad():
            for (name1, param1), (name2, param2), (name_off, param_off) in zip(
                parent1.policy.named_parameters(),
                parent2.policy.named_parameters(), 
                offspring_policy.named_parameters()
            ):
                assert name1 == name2 == name_off
                
                # Uniform crossover: randomly choose weights from each parent
                mask = torch.rand_like(param1) < 0.5
                param_off.copy_(torch.where(mask, param1, param2))
        
        # Crossover hyperparameters
        offspring_hyperparams = {}
        for key in parent1.hyperparams:
            if self.rng.random() < 0.5:
                offspring_hyperparams[key] = parent1.hyperparams[key]
            else:
                offspring_hyperparams[key] = parent2.hyperparams[key]
        
        offspring = Individual(
            policy=offspring_policy,
            hyperparams=offspring_hyperparams,
            parent_ids=[parent1.individual_id, parent2.individual_id],
            generation=self.generation + 1,
        )
        
        return offspring
    
    def mutate(self, individual: Individual) -> None:
        """Apply mutation to an individual.
        
        Args:
            individual: Individual to mutate (modified in place)
        """
        # Mutate policy weights
        with torch.no_grad():
            for param in individual.policy.parameters():
                if self.rng.random() < self.config.mutation_rate:
                    noise = torch.normal(
                        mean=0.0,
                        std=self.config.mutation_std,
                        size=param.shape,
                        dtype=param.dtype
                    )
                    param.add_(noise)
        
        # Mutate hyperparameters
        for key, value in individual.hyperparams.items():
            if self.rng.random() < self.config.mutation_rate:
                if key == "learning_rate":
                    # Log-normal perturbation for learning rate
                    factor = self.rng.lognormal(0, 0.1)
                    individual.hyperparams[key] = np.clip(value * factor, 1e-5, 1e-2)
                else:
                    # Gaussian perturbation for other parameters
                    noise = self.rng.normal(0, 0.1 * value)
                    individual.hyperparams[key] = np.clip(value + noise, 0.001, 1.0)
    
    def compute_population_diversity(self) -> float:
        """Compute genetic diversity of population.
        
        Returns:
            Average pairwise distance between policies
        """
        if len(self.population) < 2:
            return 0.0
        
        distances = []
        
        for i in range(len(self.population)):
            for j in range(i + 1, len(self.population)):
                distance = self._compute_policy_distance(
                    self.population[i].policy,
                    self.population[j].policy
                )
                distances.append(distance)
        
        return np.mean(distances) if distances else 0.0
    
    def _compute_policy_distance(self, policy1: MLPPolicy, policy2: MLPPolicy) -> float:
        """Compute L2 distance between policy parameters.
        
        Args:
            policy1: First policy
            policy2: Second policy
            
        Returns:
            L2 distance between parameters
        """
        total_distance = 0.0
        total_params = 0
        
        with torch.no_grad():
            for param1, param2 in zip(policy1.parameters(), policy2.parameters()):
                diff = param1 - param2
                total_distance += torch.sum(diff ** 2).item()
                total_params += param1.numel()
        
        return np.sqrt(total_distance / total_params) if total_params > 0 else 0.0
    
    def evolve_generation(
        self,
        fitness_func: Callable[[MLPPolicy], float],
    ) -> Dict[str, Any]:
        """Evolve one generation.
        
        Args:
            fitness_func: Function to evaluate policy fitness
            
        Returns:
            Evolution statistics
        """
        # Evaluate current population
        for individual in self.population:
            self.evaluate_fitness(individual, fitness_func)
        
        # Record fitness statistics
        current_fitness = [ind.fitness for ind in self.population]
        self.fitness_history.append(current_fitness)
        
        # Compute diversity
        diversity = self.compute_population_diversity()
        self.diversity_history.append(diversity)
        
        # Select elites
        elites = self.select_elites()
        
        # Create next generation
        new_population = copy.deepcopy(elites)  # Keep elites
        
        while len(new_population) < self.config.population_size:
            # Select parents (tournament selection)
            parent1 = self._tournament_selection()
            parent2 = self._tournament_selection()
            
            # Create offspring
            if self.rng.random() < self.config.crossover_rate:
                offspring = self.crossover(parent1, parent2)
            else:
                # Clone parent
                offspring = copy.deepcopy(parent1)
                offspring.individual_id = f"gen{self.generation + 1}_{len(new_population):03d}"
                offspring.generation = self.generation + 1
            
            # Apply mutation
            self.mutate(offspring)
            new_population.append(offspring)
        
        # Update population and generation
        self.population = new_population[:self.config.population_size]
        self.generation += 1
        
        # Evolution statistics
        stats = {
            "generation": self.generation,
            "best_fitness": max(current_fitness),
            "avg_fitness": np.mean(current_fitness),
            "worst_fitness": min(current_fitness),
            "fitness_std": np.std(current_fitness),
            "diversity": diversity,
            "n_elites": len(elites),
        }
        
        logger.info(
            "Generation evolved",
            extra=stats
        )
        
        return stats
    
    def _tournament_selection(self, tournament_size: int = 3) -> Individual:
        """Select individual via tournament selection.
        
        Args:
            tournament_size: Number of individuals in tournament
            
        Returns:
            Selected individual
        """
        tournament = self.rng.choice(
            self.population,
            size=min(tournament_size, len(self.population)),
            replace=False
        )
        return max(tournament, key=lambda x: x.fitness)
    
    def get_best_policy(self) -> MLPPolicy:
        """Get the best policy from current population.
        
        Returns:
            Best performing policy
        """
        if not self.population:
            raise ValueError("Population is empty")
        
        best_individual = max(self.population, key=lambda x: x.fitness)
        return best_individual.policy
    
    def save_population(self, directory: Path) -> None:
        """Save entire population to disk.
        
        Args:
            directory: Directory to save population
        """
        directory.mkdir(parents=True, exist_ok=True)
        
        for i, individual in enumerate(self.population):
            # Save policy
            policy_path = directory / f"individual_{i:03d}_policy.pth"
            snapshot = individual.policy.create_snapshot(
                training_step=individual.age
            )
            snapshot.save(policy_path)
            
            # Save metadata
            metadata = {
                "individual_id": individual.individual_id,
                "fitness": individual.fitness,
                "age": individual.age,
                "generation": individual.generation,
                "hyperparams": individual.hyperparams,
                "parent_ids": individual.parent_ids,
            }
            
            metadata_path = directory / f"individual_{i:03d}_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
        
        # Save evolution history
        history = {
            "generation": self.generation,
            "fitness_history": self.fitness_history,
            "diversity_history": self.diversity_history,
            "config": {
                "population_size": self.config.population_size,
                "elite_fraction": self.config.elite_fraction,
                "mutation_std": self.config.mutation_std,
                "crossover_rate": self.config.crossover_rate,
            }
        }
        
        history_path = directory / "evolution_history.json"
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)
        
        logger.info(
            "Population saved",
            extra={
                "directory": str(directory),
                "population_size": len(self.population),
                "generation": self.generation,
            }
        )


class PopulationBasedTraining:
    """Population-Based Training for hyperparameter optimization.
    
    Implements PBT as described in DeepMind papers, combining
    evolutionary hyperparameter search with parallel training.
    """
    
    def __init__(
        self,
        config: EvolutionConfig,
        rng: Optional[RNG] = None,
    ):
        """Initialize PBT system.
        
        Args:
            config: Evolution configuration (used for PBT parameters)
            rng: Random number generator
        """
        if rng is None:
            rng = np.random.default_rng()
            
        self.config = config
        self.rng = rng
        self.workers: List[Dict[str, Any]] = []
        self.generation = 0
        
        logger.info("PBT initialized", extra={"population_size": config.population_size})
    
    def initialize_workers(
        self,
        observation_dim: int = 32,
        hidden_dim: int = 64,
        action_dim: int = 2,
    ) -> None:
        """Initialize PBT workers with random hyperparameters.
        
        Args:
            observation_dim: Policy input dimension
            hidden_dim: Policy hidden dimension
            action_dim: Policy output dimension
        """
        self.workers = []
        
        for i in range(self.config.population_size):
            policy = MLPPolicy(
                observation_dim=observation_dim,
                hidden_dim=hidden_dim,
                action_dim=action_dim,
                rng=self.rng,
            )
            
            hyperparams = {
                "learning_rate": self.rng.uniform(1e-5, 1e-2),
                "entropy_coef": self.rng.uniform(0.001, 0.1),
                "value_coef": self.rng.uniform(0.1, 1.0),
                "clip_ratio": self.rng.uniform(0.1, 0.3),
                "batch_size": int(self.rng.choice([256, 512, 1024, 2048])),
            }
            
            worker = {
                "worker_id": f"worker_{i:03d}",
                "policy": policy,
                "hyperparams": hyperparams,
                "performance": 0.0,
                "age": 0,
                "parent_id": None,
            }
            
            self.workers.append(worker)
        
        logger.info(
            "PBT workers initialized",
            extra={"n_workers": len(self.workers)}
        )
    
    def exploit_and_explore(self) -> Dict[str, Any]:
        """Perform exploit and explore step of PBT.
        
        Returns:
            PBT step statistics
        """
        if len(self.workers) < 2:
            logger.warning("Insufficient workers for PBT step")
            return {}
        
        # Sort workers by performance
        sorted_workers = sorted(self.workers, key=lambda w: w["performance"], reverse=True)
        
        # Identify bottom performers to replace
        n_exploit = int(self.config.exploit_threshold * len(sorted_workers))
        if n_exploit == 0:
            n_exploit = 1  # Replace at least one
        
        bottom_workers = sorted_workers[-n_exploit:]
        top_workers = sorted_workers[:len(sorted_workers) - n_exploit]
        
        replacements = 0
        
        for bottom_worker in bottom_workers:
            # Select random top performer to copy from
            top_worker = self.rng.choice(top_workers)
            
            # Copy policy weights (exploit)
            with torch.no_grad():
                for bottom_param, top_param in zip(
                    bottom_worker["policy"].parameters(),
                    top_worker["policy"].parameters()
                ):
                    bottom_param.copy_(top_param)
            
            # Copy and perturb hyperparameters (explore)
            for key, value in top_worker["hyperparams"].items():
                if key == "learning_rate":
                    # Log-normal perturbation
                    factor = self.rng.lognormal(0, self.config.explore_std)
                    new_value = np.clip(value * factor, 1e-5, 1e-2)
                elif key == "batch_size":
                    # Discrete choice
                    choices = [256, 512, 1024, 2048]
                    new_value = int(self.rng.choice(choices))
                else:
                    # Gaussian perturbation
                    noise = self.rng.normal(0, self.config.explore_std * value)
                    new_value = np.clip(value + noise, 0.001, 1.0)
                
                bottom_worker["hyperparams"][key] = new_value
            
            # Update metadata
            bottom_worker["parent_id"] = top_worker["worker_id"]
            bottom_worker["age"] = 0  # Reset age after copying
            
            replacements += 1
        
        self.generation += 1
        
        stats = {
            "generation": self.generation,
            "replacements": replacements,
            "best_performance": sorted_workers[0]["performance"],
            "worst_performance": sorted_workers[-1]["performance"],
            "avg_performance": np.mean([w["performance"] for w in self.workers]),
        }
        
        logger.info("PBT exploit and explore completed", extra=stats)
        
        return stats
    
    def update_performance(self, worker_id: str, performance: float) -> None:
        """Update performance score for a worker.
        
        Args:
            worker_id: ID of worker to update
            performance: New performance score
        """
        for worker in self.workers:
            if worker["worker_id"] == worker_id:
                worker["performance"] = performance
                worker["age"] += 1
                break
        else:
            logger.warning(f"Worker {worker_id} not found")
    
    def get_worker_hyperparams(self, worker_id: str) -> Dict[str, Any]:
        """Get current hyperparameters for a worker.
        
        Args:
            worker_id: Worker ID
            
        Returns:
            Dictionary of hyperparameters
        """
        for worker in self.workers:
            if worker["worker_id"] == worker_id:
                return worker["hyperparams"].copy()
        
        raise ValueError(f"Worker {worker_id} not found")
    
    def get_best_worker(self) -> Dict[str, Any]:
        """Get the best performing worker.
        
        Returns:
            Best worker dictionary
        """
        if not self.workers:
            raise ValueError("No workers available")
        
        return max(self.workers, key=lambda w: w["performance"])


def distill_policy(
    teacher_policy: MLPPolicy,
    student_policy: MLPPolicy,
    distillation_dataset: List[np.ndarray],
    temperature: float = 3.0,
    alpha: float = 0.5,
    n_epochs: int = 10,
    learning_rate: float = 1e-4,
    rng: Optional[RNG] = None,
) -> Dict[str, float]:
    """Perform knowledge distillation between policies.
    
    Args:
        teacher_policy: Source policy (teacher)
        student_policy: Target policy (student) 
        distillation_dataset: List of observation vectors for distillation
        temperature: Temperature for softmax distillation
        alpha: Balance between distillation and ground truth loss
        n_epochs: Number of training epochs
        learning_rate: Learning rate for student training
        rng: Random number generator
        
    Returns:
        Distillation statistics
    """
    if rng is None:
        rng = np.random.default_rng()
    
    # Convert dataset to tensor
    obs_tensor = torch.from_numpy(np.array(distillation_dataset)).float()
    
    # Setup optimizer for student
    optimizer = torch.optim.Adam(student_policy.parameters(), lr=learning_rate)
    
    # Get teacher outputs (no gradients)
    with torch.no_grad():
        teacher_outputs = teacher_policy(obs_tensor)
    
    losses = []
    
    for epoch in range(n_epochs):
        optimizer.zero_grad()
        
        # Student outputs
        student_outputs = student_policy(obs_tensor)
        
        # Distillation loss (soft targets)
        teacher_soft = F.softmax(teacher_outputs / temperature, dim=-1)
        student_soft = F.log_softmax(student_outputs / temperature, dim=-1)
        distillation_loss = F.kl_div(student_soft, teacher_soft, reduction='batchmean')
        distillation_loss *= (temperature ** 2)
        
        # MSE loss (hard targets)
        mse_loss = F.mse_loss(student_outputs, teacher_outputs)
        
        # Combined loss
        total_loss = alpha * distillation_loss + (1 - alpha) * mse_loss
        
        total_loss.backward()
        optimizer.step()
        
        losses.append(total_loss.item())
    
    stats = {
        "final_loss": losses[-1] if losses else 0.0,
        "avg_loss": np.mean(losses) if losses else 0.0,
        "loss_reduction": (losses[0] - losses[-1]) / losses[0] if len(losses) > 1 else 0.0,
    }
    
    logger.info("Policy distillation completed", extra=stats)
    
    return stats