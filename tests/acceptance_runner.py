"""Acceptance test runner per CLAUDE.md spec."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml
import structlog

logger = structlog.get_logger()


class AcceptanceRunner:
    """Run acceptance tests for levels with thresholds."""

    def __init__(self, config_path: Path) -> None:
        """Initialize with config file."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.seeds = self.config["seeds"]
        self.levels = self.config["levels"]
        self.results: Dict[str, List[Dict[str, Any]]] = {}

    def run_level(self, level_id: str, seed: int) -> Dict[str, Any]:
        """Run a single level with given seed."""
        logger.info("running_level", level=level_id, seed=seed)
        
        # TODO: Actually run simulation
        # For now, return mock results
        return {
            "arrivals": 75,
            "cohesion_avg": 0.60,
            "losses": 15,
            "wall_time_s": 100,
            "protected_deaths": 0,
        }

    def check_thresholds(
        self, level_id: str, results: List[Dict[str, Any]]
    ) -> bool:
        """Check if results meet thresholds for >= 2/3 seeds."""
        thresholds = self.levels[level_id]
        passed_seeds = 0

        for result in results:
            passed = True
            
            if result["arrivals"] < thresholds.get("arrivals_min", 0):
                passed = False
            if result["cohesion_avg"] < thresholds.get("cohesion_avg_min", 0):
                passed = False
            if result["losses"] > thresholds.get("losses_max", float("inf")):
                passed = False
            if result["wall_time_s"] > thresholds.get("wall_time_s_max", float("inf")):
                passed = False
            if "protected_deaths_max" in thresholds:
                if result["protected_deaths"] > thresholds["protected_deaths_max"]:
                    passed = False

            if passed:
                passed_seeds += 1

        # Need >= 2/3 seeds to pass
        required = len(results) * 2 // 3
        return passed_seeds >= required

    def run(self) -> bool:
        """Run all acceptance tests."""
        all_passed = True

        for level_id in self.levels:
            logger.info("testing_level", level=level_id)
            level_results = []

            for seed in self.seeds:
                result = self.run_level(level_id, seed)
                level_results.append(result)

            self.results[level_id] = level_results
            passed = self.check_thresholds(level_id, level_results)

            if passed:
                logger.info("level_passed", level=level_id)
            else:
                logger.error("level_failed", level=level_id)
                all_passed = False

        return all_passed

    def print_summary(self) -> None:
        """Print test summary."""
        print("\n=== Acceptance Test Summary ===")
        for level_id, results in self.results.items():
            thresholds = self.levels[level_id]
            print(f"\n{level_id}:")
            print(f"  Thresholds: {thresholds}")
            print(f"  Results across seeds {self.seeds}:")
            for i, result in enumerate(results):
                print(f"    Seed {self.seeds[i]}: {result}")
            passed = self.check_thresholds(level_id, results)
            print(f"  Status: {'PASS' if passed else 'FAIL'}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run acceptance tests")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to acceptance config YAML",
    )
    args = parser.parse_args()

    runner = AcceptanceRunner(args.config)
    passed = runner.run()
    runner.print_summary()

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()