"""Star scoring implementation per CLAUDE.md specification.

This module implements the scoring system for Murmuration levels,
calculating star ratings (0-3) based on performance metrics and targets.
"""

from dataclasses import dataclass
from typing import Optional

from .core.types import StarRating


@dataclass
class LevelTargets:
    """Target metrics for a level that determine scoring thresholds.
    
    These targets define the minimum requirements for completion and
    the surplus thresholds needed for higher star ratings.
    
    Attributes:
        time_limit_days: Maximum allowed simulation days
        arrivals_min: Minimum number of agents that must arrive
        cohesion_avg_min: Minimum average cohesion score
        beacon_budget_max: Maximum number of beacons allowed
        losses_max: Maximum number of agent losses allowed
        protected_deaths_max: Maximum protected agent deaths (some levels only)
    """
    time_limit_days: int
    arrivals_min: int
    cohesion_avg_min: float
    beacon_budget_max: int
    losses_max: int
    protected_deaths_max: Optional[int] = None


@dataclass  
class SimulationResult:
    """Results from a completed simulation run.
    
    Contains all metrics needed for star rating calculation,
    including whether basic targets were met and detailed performance data.
    
    Attributes:
        met_all_targets: Whether all basic completion targets were met
        days_used: Actual simulation time in days
        arrivals: Number of agents that successfully arrived
        cohesion_avg: Average cohesion score throughout simulation
        beacons_used: Number of beacons actually used
        losses: Total number of agent losses
        protected_deaths: Number of protected agent deaths (if applicable)
    """
    met_all_targets: bool
    days_used: float
    arrivals: int
    cohesion_avg: float
    beacons_used: int
    losses: int
    protected_deaths: Optional[int] = None


def calculate_surplus_percentage(actual: float, target: float) -> float:
    """Calculate surplus percentage over target.
    
    Args:
        actual: Actual achieved value
        target: Target/minimum required value
        
    Returns:
        Surplus as a percentage (e.g., 0.15 for 15% surplus)
    """
    if target <= 0:
        return 0.0
    return max(0.0, (actual - target) / target)


def count_surplus_metrics(result: SimulationResult, targets: LevelTargets, threshold: float = 0.10) -> int:
    """Count how many metrics achieved surplus over targets.
    
    According to game spec:
    - 3-star rating requires ≥10% surplus on ≥2 metrics
    - 2-star rating requires ≥5% surplus on ≥1 metric
    
    Args:
        result: Simulation results
        targets: Level target thresholds
        threshold: Minimum surplus percentage (default 10%)
        
    Returns:
        Number of metrics with surplus above threshold
    """
    surplus_count = 0
    surplus_threshold = threshold
    
    # Check arrivals surplus
    arrivals_surplus = calculate_surplus_percentage(result.arrivals, targets.arrivals_min)
    if arrivals_surplus >= surplus_threshold:
        surplus_count += 1
    
    # Check cohesion surplus
    cohesion_surplus = calculate_surplus_percentage(result.cohesion_avg, targets.cohesion_avg_min)
    if cohesion_surplus >= surplus_threshold:
        surplus_count += 1
    
    # Check time efficiency surplus (finishing early)
    if result.days_used < targets.time_limit_days:
        time_surplus = calculate_surplus_percentage(
            targets.time_limit_days - result.days_used, 
            targets.time_limit_days * 0.2  # 20% of time limit as reference
        )
        if time_surplus >= surplus_threshold:
            surplus_count += 1
    
    # Check losses efficiency surplus (fewer losses than allowed)
    if result.losses < targets.losses_max:
        losses_surplus = calculate_surplus_percentage(
            targets.losses_max - result.losses,
            targets.losses_max * 0.3  # 30% of loss limit as reference
        )
        if losses_surplus >= surplus_threshold:
            surplus_count += 1
    
    # Check protected deaths surplus (if applicable)
    if (targets.protected_deaths_max is not None and 
        result.protected_deaths is not None and
        result.protected_deaths < targets.protected_deaths_max):
        protected_surplus = calculate_surplus_percentage(
            targets.protected_deaths_max - result.protected_deaths,
            targets.protected_deaths_max * 0.3  # 30% of limit as reference
        )
        if protected_surplus >= surplus_threshold:
            surplus_count += 1
    
    return surplus_count


def has_unused_beacon(result: SimulationResult, targets: LevelTargets) -> bool:
    """Check if at least one beacon was left unused.
    
    Args:
        result: Simulation results
        targets: Level targets including beacon budget
        
    Returns:
        True if at least one beacon was unused
    """
    return result.beacons_used < targets.beacon_budget_max


def star_rating(result: SimulationResult, targets: LevelTargets) -> StarRating:
    """Calculate star rating (0-3) based on simulation results.
    
    Star rating logic per CLAUDE.md:
    - 0 stars: Failed to meet basic targets
    - 1 star: Met all basic targets
    - 2 stars: Met targets + either ≥2 surplus metrics OR ≥1 unused beacon
    - 3 stars: Met targets + ≥2 surplus metrics AND ≥1 unused beacon
    
    Args:
        result: Completed simulation results
        targets: Level target thresholds
        
    Returns:
        Star rating from 0 to 3
    """
    # 0 stars: Failed basic requirements
    if not result.met_all_targets:
        return StarRating(0)
    
    # Additional checks for basic targets
    if (result.arrivals < targets.arrivals_min or
        result.cohesion_avg < targets.cohesion_avg_min or
        result.losses > targets.losses_max or
        result.days_used > targets.time_limit_days or
        result.beacons_used > targets.beacon_budget_max):
        return StarRating(0)
    
    # Protected deaths check (if applicable)
    if (targets.protected_deaths_max is not None and
        result.protected_deaths is not None and
        result.protected_deaths > targets.protected_deaths_max):
        return StarRating(0)
    
    # Count surplus metrics at different thresholds
    surplus_10pct = count_surplus_metrics(result, targets, threshold=0.10)
    surplus_5pct = count_surplus_metrics(result, targets, threshold=0.05)
    unused_beacon = has_unused_beacon(result, targets)
    
    # 3 stars: ≥2 metrics with ≥10% surplus AND ≥1 unused beacon
    if surplus_10pct >= 2 and unused_beacon:
        return StarRating(3)
    
    # 2 stars: ≥1 metric with ≥5% surplus
    if surplus_5pct >= 1:
        return StarRating(2)
    
    # 1 star: Met basic targets but no surplus
    return StarRating(1)


def format_score_summary(result: SimulationResult, targets: LevelTargets, rating: StarRating) -> str:
    """Format a human-readable score summary.
    
    Args:
        result: Simulation results
        targets: Level targets
        rating: Calculated star rating
        
    Returns:
        Formatted summary string
    """
    lines = [
        f"⭐ {rating} Star{'s' if rating != 1 else ''}",
        "",
        "Performance:",
        f"  Arrivals: {result.arrivals}/{targets.arrivals_min} (target)",
        f"  Cohesion: {result.cohesion_avg:.3f}/{targets.cohesion_avg_min:.3f} (target)",
        f"  Time Used: {result.days_used:.1f}/{targets.time_limit_days} days",
        f"  Beacons Used: {result.beacons_used}/{targets.beacon_budget_max}",
        f"  Losses: {result.losses}/{targets.losses_max} (max)",
    ]
    
    if targets.protected_deaths_max is not None and result.protected_deaths is not None:
        lines.append(f"  Protected Deaths: {result.protected_deaths}/{targets.protected_deaths_max} (max)")
    
    # Show surplus analysis
    surplus_count = count_surplus_metrics(result, targets, threshold=0.10)
    unused_beacon = has_unused_beacon(result, targets)
    
    lines.extend([
        "",
        "Bonuses:",
        f"  Surplus Metrics (≥10%): {surplus_count}",
        f"  Unused Beacons: {1 if unused_beacon else 0}",
    ])
    
    # Show what's needed for higher ratings
    if rating < 3:
        lines.append("")
        if rating == 0:
            lines.append("For 1 star: Meet all basic targets")
        elif rating == 1:
            lines.append("For 2 stars: Achieve ≥2 surplus metrics OR leave ≥1 beacon unused")
            lines.append("For 3 stars: Achieve ≥2 surplus metrics AND leave ≥1 beacon unused")
        elif rating == 2:
            if surplus_count >= 2:
                lines.append("For 3 stars: Leave at least 1 beacon unused")
            elif unused_beacon:
                lines.append("For 3 stars: Achieve ≥2 metrics with 10%+ surplus")
            else:
                lines.append("For 3 stars: Achieve ≥2 surplus metrics AND leave ≥1 beacon unused")
    
    return "\n".join(lines)


def validate_targets(targets: LevelTargets) -> bool:
    """Validate that level targets are reasonable.
    
    Args:
        targets: Level targets to validate
        
    Returns:
        True if targets are valid
    """
    if targets.time_limit_days <= 0:
        return False
    if targets.arrivals_min <= 0:
        return False
    if not (0.0 <= targets.cohesion_avg_min <= 1.0):
        return False
    if targets.beacon_budget_max <= 0:
        return False
    if targets.losses_max < 0:
        return False
    if targets.protected_deaths_max is not None and targets.protected_deaths_max < 0:
        return False
    
    return True


# Example test function as shown in CLAUDE.md
def test_three_star_requires_two_surpluses_and_unused_beacon() -> None:
    """Test case from CLAUDE.md specification."""
    result = SimulationResult(
        met_all_targets=True,
        days_used=7.0,
        arrivals=176,
        cohesion_avg=0.75,
        beacons_used=3,
        losses=15,
    )
    
    targets = LevelTargets(
        time_limit_days=10,
        arrivals_min=160,
        cohesion_avg_min=0.68,
        beacon_budget_max=4,
        losses_max=20,
    )
    
    rating = star_rating(result, targets)
    assert rating == 3, f"Expected 3 stars, got {rating}"
    
    # Verify the surplus calculation
    surplus_count = count_surplus_metrics(result, targets)
    unused_beacon = has_unused_beacon(result, targets)
    
    assert surplus_count >= 2, f"Expected ≥2 surplus metrics, got {surplus_count}"
    assert unused_beacon, "Expected unused beacon"


if __name__ == "__main__":
    # Run the test
    test_three_star_requires_two_surpluses_and_unused_beacon()
    print("Test passed: 3-star scoring works correctly")