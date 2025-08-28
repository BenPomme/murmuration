#!/usr/bin/env python3
"""
Phase 2 Strategic Depth Validation and Balance Testing

This script validates all Phase 2 implementations:
- Team Alpha: Difficulty scaling, multi-leg journeys, population management
- Team Bravo: Moving storms, predator chases, hazard-trait interactions
- Team Charlie: Bird inspection, migration results
- Team Echo: Balance validation and strategic depth testing

Usage: python test_phase2_validation.py
"""

import sys
import os
import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple
import asyncio

# Add sim directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "sim"))

from sim.simulation_evolved import EvolvedSimulation, GameConfig, Breed
from sim.migration_system import MigrationManager, MigrationStatus
from sim.server import SimulationServer
from sim.utils.logging import get_logger

logger = get_logger("phase2_validation")

class Phase2Validator:
    """Comprehensive Phase 2 validation and testing."""
    
    def __init__(self):
        self.results = {
            "team_alpha": {},
            "team_bravo": {},
            "team_charlie": {},
            "team_echo": {},
            "overall_balance": {}
        }
        self.migration_manager = MigrationManager()
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run complete Phase 2 validation suite."""
        logger.info("🚀 Starting Phase 2 Strategic Depth Validation")
        
        # Team Alpha: Challenge Progression
        logger.info("📊 Testing Team Alpha: Challenge Progression")
        self.results["team_alpha"] = self.test_team_alpha()
        
        # Team Bravo: Advanced Hazard Systems
        logger.info("🌪️ Testing Team Bravo: Advanced Hazard Systems")
        self.results["team_bravo"] = self.test_team_bravo()
        
        # Team Charlie: Strategic Interface (basic validation)
        logger.info("📋 Testing Team Charlie: Strategic Interface")
        self.results["team_charlie"] = self.test_team_charlie()
        
        # Team Echo: Balance & Strategic Depth
        logger.info("⚖️ Testing Team Echo: Balance & Strategic Depth")
        self.results["team_echo"] = self.test_balance_and_strategy()
        
        # Generate final report
        self.generate_validation_report()
        
        return self.results
    
    def test_team_alpha(self) -> Dict[str, Any]:
        """Test Team Alpha: Challenge progression and population management."""
        results = {
            "difficulty_scaling": self.test_difficulty_scaling(),
            "multi_leg_journeys": self.test_multi_leg_journeys(), 
            "population_management": self.test_population_management()
        }
        return results
    
    def test_difficulty_scaling(self) -> Dict[str, Any]:
        """Test migration-based difficulty scaling."""
        logger.info("Testing difficulty scaling across migrations...")
        
        scaling_results = {}
        base_level = "W2-1"
        test_migrations = [1, 2, 3, 5, 8]  # Test various migration numbers
        
        for migration_num in test_migrations:
            # Create config with scaling
            config = GameConfig.from_level(base_level, seed=42, migration_number=migration_num)
            
            # Test hazard scaling
            hazard_count = len(config.level_hazards) if config.level_hazards else 0
            hazard_intensity = 0
            if config.level_hazards:
                hazard_intensity = np.mean([h.get('strength', h.get('danger', 1.0)) for h in config.level_hazards])
            
            scaling_results[f"migration_{migration_num}"] = {
                "hazard_count": hazard_count,
                "hazard_intensity": hazard_intensity,
                "beacon_budget": config.beacon_budget,
                "population": config.n_agents,
                "time_limit": config.time_limit_seconds
            }
            
        # Validate scaling progression
        first_migration = scaling_results["migration_1"]
        last_migration = scaling_results["migration_8"]
        
        intensity_increased = last_migration["hazard_intensity"] > first_migration["hazard_intensity"]
        budget_adjusted = last_migration["beacon_budget"] <= first_migration["beacon_budget"]
        
        return {
            "scaling_data": scaling_results,
            "intensity_progression": intensity_increased,
            "budget_limitation": budget_adjusted,
            "validation_passed": intensity_increased and budget_adjusted
        }
    
    def test_multi_leg_journeys(self) -> Dict[str, Any]:
        """Test multi-leg journey system."""
        logger.info("Testing multi-leg journey progression...")
        
        # Test journey creation and progression
        journey_tests = {}
        
        for journey_id in ["spring_coastal", "fall_mountain", "summer_desert", "winter_arctic"]:
            success = self.migration_manager.start_journey(journey_id, population=100)
            if success:
                journey_info = self.migration_manager.get_journey_progress()
                journey_tests[journey_id] = {
                    "created_successfully": True,
                    "total_legs": len(self.migration_manager.current_journey.legs),
                    "checkpoints": len(self.migration_manager.current_journey.checkpoints),
                    "total_distance": self.migration_manager.current_journey.total_distance,
                    "season": journey_info.get("season", "unknown")
                }
            else:
                journey_tests[journey_id] = {"created_successfully": False}
        
        # Test leg progression simulation
        test_journey = "spring_coastal"
        if self.migration_manager.start_journey(test_journey, population=100):
            leg_progression = []
            for i in range(4):  # Test 4 legs
                current_leg = self.migration_manager.get_current_leg()
                if current_leg:
                    leg_progression.append({
                        "leg_id": current_leg.leg_id,
                        "distance": current_leg.distance,
                        "difficulty": current_leg.difficulty_multiplier
                    })
                    # Simulate leg completion
                    survivors = max(50, 100 - i * 10)  # Gradual population decline
                    self.migration_manager.complete_leg(survivors)
                else:
                    break
        
        return {
            "journey_creation": journey_tests,
            "leg_progression": leg_progression,
            "progression_system_working": len(leg_progression) >= 3
        }
    
    def test_population_management(self) -> Dict[str, Any]:
        """Test breeding and population management between migrations."""
        logger.info("Testing population management and breeding...")
        
        # Create test simulation
        config = GameConfig.from_level("W1-1", seed=42)
        sim = EvolvedSimulation(config)
        
        # Simulate some survivors
        survivors = [agent for agent in sim.agents[:30] if agent.alive]  # Take first 30 as survivors
        
        # Test breeding system
        breeding_results = sim.breed_survivors(survivors, target_population=100)
        
        # Test next migration preparation
        next_config = GameConfig.from_level("W1-2", seed=43)
        sim.prepare_next_migration(breeding_results, next_config)
        
        return {
            "survivor_count": len(survivors),
            "offspring_generated": len(breeding_results),
            "population_restored": len(sim.agents),
            "generation_advanced": sim.breed.generation > 0,
            "genetic_diversity": len(set(f"{bp.get('parent_male_id', -1)}-{bp.get('parent_female_id', -1)}" for bp in breeding_results)),
            "breeding_system_functional": len(breeding_results) > 0 and len(sim.agents) > 0
        }
    
    def test_team_bravo(self) -> Dict[str, Any]:
        """Test Team Bravo: Advanced hazard systems."""
        results = {
            "moving_storms": self.test_moving_storms(),
            "predator_chases": self.test_predator_chases(),
            "hazard_trait_interactions": self.test_hazard_trait_interactions()
        }
        return results
    
    def test_moving_storms(self) -> Dict[str, Any]:
        """Test moving storm mechanics."""
        logger.info("Testing moving storm mechanics...")
        
        # Create simulation with storm
        config = GameConfig.from_level("W2-1", seed=42)  # Level with storms
        sim = EvolvedSimulation(config)
        
        # Find storm hazards
        storms = [h for h in sim.hazards if h.get('type') == 'storm']
        
        if not storms:
            return {"storms_found": False, "movement_test": False}
        
        # Test storm movement over time
        test_storm = storms[0]
        initial_pos = [test_storm.get('x', 0), test_storm.get('y', 0)]
        
        # Run simulation steps to test movement
        for _ in range(30):  # 30 ticks = 1 second
            sim.step()
        
        final_pos = [test_storm.get('x', 0), test_storm.get('y', 0)]
        moved_distance = np.linalg.norm(np.array(final_pos) - np.array(initial_pos))
        
        return {
            "storms_found": len(storms) > 0,
            "initial_position": initial_pos,
            "final_position": final_pos,
            "movement_distance": moved_distance,
            "storm_moved": moved_distance > 1.0,  # At least 1 pixel movement
            "predicted_path_available": 'predicted_path' in test_storm,
            "movement_system_working": moved_distance > 1.0 and 'predicted_path' in test_storm
        }
    
    def test_predator_chases(self) -> Dict[str, Any]:
        """Test predator chase mechanics."""
        logger.info("Testing predator chase mechanics...")
        
        # Create simulation with predators
        config = GameConfig.from_level("W1-2", seed=42)  # Level with predators
        sim = EvolvedSimulation(config)
        
        # Find predator hazards
        predators = [h for h in sim.hazards if h.get('type') == 'predator']
        
        if not predators:
            return {"predators_found": False, "chase_test": False}
        
        # Test predator targeting and movement
        test_predator = predators[0]
        initial_pos = [test_predator.get('x', 0), test_predator.get('y', 0)]
        
        # Run simulation to trigger predator behavior
        chase_initiated = False
        movement_detected = False
        
        for i in range(60):  # Run for 2 seconds
            sim.step()
            
            if test_predator.get('target_agent_id'):
                chase_initiated = True
            
            current_pos = [test_predator.get('x', 0), test_predator.get('y', 0)]
            if np.linalg.norm(np.array(current_pos) - np.array(initial_pos)) > 5.0:
                movement_detected = True
        
        return {
            "predators_found": len(predators) > 0,
            "chase_initiated": chase_initiated,
            "predator_moved": movement_detected,
            "exhaustion_system": test_predator.get('exhaustion_level', 0) >= 0,
            "chase_system_working": chase_initiated or movement_detected
        }
    
    def test_hazard_trait_interactions(self) -> Dict[str, Any]:
        """Test hazard-trait interaction system."""
        logger.info("Testing hazard-trait interactions...")
        
        # Create two simulations with different breed traits
        high_awareness_breed = Breed(name="HighAwareness", hazard_awareness=0.9, stress_resilience=0.8)
        low_awareness_breed = Breed(name="LowAwareness", hazard_awareness=0.2, stress_resilience=0.3)
        
        config_high = GameConfig.from_level("W2-1", seed=42, breed=high_awareness_breed)
        config_low = GameConfig.from_level("W2-1", seed=42, breed=low_awareness_breed)
        
        sim_high = EvolvedSimulation(config_high)
        sim_low = EvolvedSimulation(config_low)
        
        # Run both simulations for same duration
        steps = 180  # 3 seconds
        for _ in range(steps):
            sim_high.step()
            sim_low.step()
        
        # Compare outcomes
        high_survival = len([a for a in sim_high.agents if a.alive]) / len(sim_high.agents)
        low_survival = len([a for a in sim_low.agents if a.alive]) / len(sim_low.agents)
        
        high_stress = np.mean([a.stress for a in sim_high.agents if a.alive]) if any(a.alive for a in sim_high.agents) else 1.0
        low_stress = np.mean([a.stress for a in sim_low.agents if a.alive]) if any(a.alive for a in sim_low.agents) else 1.0
        
        return {
            "high_awareness_survival": high_survival,
            "low_awareness_survival": low_survival,
            "high_awareness_stress": high_stress,
            "low_awareness_stress": low_stress,
            "trait_impact_on_survival": high_survival > low_survival,
            "trait_impact_on_stress": high_stress < low_stress,
            "trait_interactions_working": high_survival > low_survival and high_stress < low_stress
        }
    
    def test_team_charlie(self) -> Dict[str, Any]:
        """Test Team Charlie: Strategic interface components."""
        logger.info("Testing strategic interface systems...")
        
        # Test bird inspection data structure
        config = GameConfig.from_level("W1-1", seed=42)
        sim = EvolvedSimulation(config)
        
        if not sim.agents:
            return {"interface_test": False, "error": "No agents available"}
        
        # Test bird inspection data generation (simulate what server would do)
        test_bird = sim.agents[0]
        neighbors = sim.get_neighbors(test_bird, radius=150)
        
        inspection_data = {
            "id": int(test_bird.id),
            "vital_stats": {
                "energy": float(test_bird.energy),
                "stress": float(test_bird.stress),
                "alive": test_bird.alive
            },
            "genetic_traits": {
                "hazard_detection": float(test_bird.hazard_detection),
                "beacon_response": float(test_bird.beacon_response)
            },
            "flock_dynamics": {
                "neighbors_count": len(neighbors)
            }
        }
        
        # Test flock statistics calculation
        alive_agents = [a for a in sim.agents if a.alive]
        if alive_agents:
            flock_stats = {
                "population": len(alive_agents),
                "average_energy": np.mean([a.energy for a in alive_agents]),
                "average_stress": np.mean([a.stress for a in alive_agents]),
                "cohesion_score": sim.calculate_cohesion(alive_agents)
            }
        else:
            flock_stats = {"population": 0}
        
        return {
            "bird_inspection_data": inspection_data,
            "flock_statistics": flock_stats,
            "interface_data_complete": all(k in inspection_data for k in ["id", "vital_stats", "genetic_traits", "flock_dynamics"]),
            "statistics_functional": flock_stats.get("population", 0) > 0
        }
    
    def test_balance_and_strategy(self) -> Dict[str, Any]:
        """Test overall game balance and strategic depth."""
        logger.info("Testing game balance and strategic depth...")
        
        # Test multiple scenarios for balance
        scenarios = {
            "easy_level": self.test_scenario("W1-1", migration_num=1),
            "medium_level": self.test_scenario("W2-1", migration_num=3),
            "hard_level": self.test_scenario("W3-1", migration_num=5),
        }
        
        # Calculate balance metrics
        survival_rates = [s["survival_rate"] for s in scenarios.values() if "survival_rate" in s]
        completion_rates = [s["completion_rate"] for s in scenarios.values() if "completion_rate" in s]
        
        # Strategic depth test - do beacons make a meaningful difference?
        strategy_test = self.test_beacon_strategy_impact()
        
        return {
            "scenario_results": scenarios,
            "survival_rate_range": [min(survival_rates), max(survival_rates)] if survival_rates else [0, 0],
            "completion_rate_range": [min(completion_rates), max(completion_rates)] if completion_rates else [0, 0],
            "difficulty_progression_appropriate": self.validate_difficulty_progression(scenarios),
            "strategic_depth": strategy_test,
            "balance_validated": len(survival_rates) > 0 and min(survival_rates) > 0.3 and max(survival_rates) < 0.95
        }
    
    def test_scenario(self, level: str, migration_num: int, duration_seconds: int = 60) -> Dict[str, Any]:
        """Test a specific scenario for balance."""
        try:
            config = GameConfig.from_level(level, seed=42, migration_number=migration_num)
            sim = EvolvedSimulation(config)
            
            # Run simulation
            steps = duration_seconds * 30  # 30 FPS
            for _ in range(steps):
                sim.step()
                if sim.game_over:
                    break
            
            alive_count = len([a for a in sim.agents if a.alive])
            survival_rate = alive_count / config.n_agents
            completion_rate = sim.arrivals / config.target_arrivals if config.target_arrivals > 0 else 0
            
            return {
                "level": level,
                "migration_number": migration_num,
                "survival_rate": survival_rate,
                "completion_rate": completion_rate,
                "game_completed": sim.game_over,
                "victory": sim.victory,
                "duration_ticks": sim.tick
            }
        except Exception as e:
            logger.error(f"Scenario test failed for {level}: {e}")
            return {"error": str(e)}
    
    def test_beacon_strategy_impact(self) -> Dict[str, Any]:
        """Test if beacon placement creates meaningful strategic decisions."""
        logger.info("Testing beacon strategy impact...")
        
        # Test with and without beacons
        config = GameConfig.from_level("W2-1", seed=42)
        
        # Simulation without beacons
        sim_no_beacons = EvolvedSimulation(config)
        for _ in range(1800):  # 1 minute
            sim_no_beacons.step()
            if sim_no_beacons.game_over:
                break
        
        # Simulation with strategic beacon placement
        sim_with_beacons = EvolvedSimulation(config)
        
        # Place beacons strategically (simulate good player decisions)
        if sim_with_beacons.hazards:
            hazard = sim_with_beacons.hazards[0]
            hazard_x, hazard_y = hazard.get('x', 1000), hazard.get('y', 600)
            
            # Place shelter beacon near hazard
            sim_with_beacons.place_beacon('shelter', hazard_x - 200, hazard_y)
            # Place thermal beacon for speed boost
            sim_with_beacons.place_beacon('thermal', 1500, 600)
        
        for _ in range(1800):  # 1 minute
            sim_with_beacons.step()
            if sim_with_beacons.game_over:
                break
        
        # Compare results
        no_beacon_survival = len([a for a in sim_no_beacons.agents if a.alive]) / len(sim_no_beacons.agents)
        beacon_survival = len([a for a in sim_with_beacons.agents if a.alive]) / len(sim_with_beacons.agents)
        
        return {
            "no_beacon_survival": no_beacon_survival,
            "with_beacon_survival": beacon_survival,
            "beacon_improvement": beacon_survival - no_beacon_survival,
            "meaningful_impact": beacon_survival > no_beacon_survival * 1.1,  # At least 10% improvement
            "strategic_depth_confirmed": beacon_survival > no_beacon_survival * 1.1
        }
    
    def validate_difficulty_progression(self, scenarios: Dict[str, Any]) -> bool:
        """Validate that difficulty progresses appropriately."""
        try:
            easy_survival = scenarios.get("easy_level", {}).get("survival_rate", 0)
            medium_survival = scenarios.get("medium_level", {}).get("survival_rate", 0)
            hard_survival = scenarios.get("hard_level", {}).get("survival_rate", 0)
            
            # Check if survival rates decrease with difficulty (allowing for some variance)
            progression_valid = easy_survival >= medium_survival * 0.8 and medium_survival >= hard_survival * 0.8
            
            return progression_valid and easy_survival > 0.4  # Minimum playability
        except:
            return False
    
    def generate_validation_report(self):
        """Generate comprehensive validation report."""
        logger.info("📊 Generating Phase 2 Validation Report")
        
        report = {
            "phase_2_validation_summary": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "overall_status": "PASS",  # Will be updated based on results
                "teams_validated": 4
            },
            "detailed_results": self.results
        }
        
        # Determine overall status
        critical_failures = []
        
        # Check Team Alpha
        if not self.results["team_alpha"]["difficulty_scaling"]["validation_passed"]:
            critical_failures.append("Difficulty scaling not working")
        if not self.results["team_alpha"]["multi_leg_journeys"]["progression_system_working"]:
            critical_failures.append("Multi-leg journey progression failed")
        if not self.results["team_alpha"]["population_management"]["breeding_system_functional"]:
            critical_failures.append("Population management system failed")
        
        # Check Team Bravo
        if not self.results["team_bravo"]["moving_storms"]["movement_system_working"]:
            critical_failures.append("Moving storm system not functional")
        if not self.results["team_bravo"]["hazard_trait_interactions"]["trait_interactions_working"]:
            critical_failures.append("Hazard-trait interactions not working properly")
        
        # Check Team Echo
        if not self.results["team_echo"]["balance_validated"]:
            critical_failures.append("Game balance issues detected")
        if not self.results["team_echo"]["strategic_depth"]["strategic_depth_confirmed"]:
            critical_failures.append("Strategic depth insufficient")
        
        report["phase_2_validation_summary"]["critical_failures"] = critical_failures
        report["phase_2_validation_summary"]["overall_status"] = "PASS" if not critical_failures else "FAIL"
        
        # Save report
        report_path = Path("phase2_validation_report.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"📋 Validation report saved to {report_path}")
        
        # Print summary
        status_emoji = "✅" if not critical_failures else "❌"
        print(f"\n{status_emoji} PHASE 2 VALIDATION {report['phase_2_validation_summary']['overall_status']}")
        print(f"Teams validated: {report['phase_2_validation_summary']['teams_validated']}/4")
        
        if critical_failures:
            print(f"❌ Critical failures ({len(critical_failures)}):")
            for failure in critical_failures:
                print(f"  - {failure}")
        else:
            print("✅ All systems functional and balanced")
            print("✅ Strategic depth confirmed")
            print("✅ Phase 2 implementation successful")

def main():
    """Run Phase 2 validation."""
    print("🚀 Murmuration Phase 2: Strategic Depth Validation")
    print("=" * 60)
    
    validator = Phase2Validator()
    results = validator.run_all_tests()
    
    print("\n🎯 Phase 2 validation completed!")
    return results

if __name__ == "__main__":
    main()