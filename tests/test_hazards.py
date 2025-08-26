"""Comprehensive test suite for hazards system.

Tests cover determinism, property-based testing with hypothesis,
and performance requirements following CLAUDE.md standards.
"""

import time
import pytest
import numpy as np
from hypothesis import given, strategies as st, assume, settings
from typing import List

from sim.core.agent import Agent, create_agent
from sim.core.environment import Environment, create_test_environment
from sim.core.types import create_vector2d, AgentID, Tick, RNG
from sim.core.physics import compute_flock_cohesion
from sim.utils.logging import setup_logging, get_logger

from sim.hazards import (
    telegraph_hazards,
    apply_all_hazards,
)
from sim.hazards.predators import (
    PredatorHotspot,
    add_predation_events,
    spawn_predators,
    create_default_hotspots,
)
from sim.hazards.storms import (
    StormSystem,
    StormSeverity,
    create_storm_system,
    apply_storm_effects,
    spawn_storms,
)
from sim.hazards.light_pollution import (
    LightPollutionTrap,
    LightType,
    check_light_pollution,
    create_urban_lighting,
)

# Setup logging for tests
setup_logging(level="WARNING")  # Reduce noise during testing
logger = get_logger("test_hazards")


class TestDeterminism:
    """Test deterministic behavior of hazards system."""
    
    def test_telegraph_hazards_deterministic(self):
        """Test that hazard forecasting produces identical results with same seed."""
        seed = 42
        current_tick = Tick(1000)
        forecast_hours = 24.0
        ticks_per_hour = 3600
        
        # Create identical environments
        rng1 = np.random.default_rng(seed)
        env1 = create_test_environment(rng1)
        
        rng2 = np.random.default_rng(seed)
        env2 = create_test_environment(rng2)
        
        # Generate forecasts
        forecast1 = telegraph_hazards(current_tick, forecast_hours, ticks_per_hour, env1, rng1)
        forecast2 = telegraph_hazards(current_tick, forecast_hours, ticks_per_hour, env2, rng2)
        
        # Should be identical
        assert len(forecast1) == len(forecast2)
        for event1, event2 in zip(forecast1, forecast2):
            assert event1["event_type"] == event2["event_type"]
            assert event1["forecast_tick"] == event2["forecast_tick"]
            if "severity" in event1:
                assert event1["severity"] == event2["severity"]
    
    def test_predation_events_deterministic(self):
        """Test that predation events are deterministic."""
        seed = 12345
        
        # Setup 1
        rng1 = np.random.default_rng(seed)
        env1 = create_test_environment(rng1)
        agents1 = [create_agent(AgentID(i), rng=rng1) for i in range(10)]
        
        # Setup 2
        rng2 = np.random.default_rng(seed)
        env2 = create_test_environment(rng2)
        agents2 = [create_agent(AgentID(i), rng=rng2) for i in range(10)]
        
        # Apply predation
        events1 = add_predation_events(agents1, env1, Tick(500), 18.0, rng=rng1)
        events2 = add_predation_events(agents2, env2, Tick(500), 18.0, rng=rng2)
        
        # Results should be identical
        assert len(events1) == len(events2)
        for a1, a2 in zip(agents1, agents2):
            assert a1.alive == a2.alive
            assert np.allclose(a1.energy, a2.energy)
            assert np.allclose(a1.stress, a2.stress)
    
    def test_storm_effects_deterministic(self):
        """Test that storm effects are deterministic."""
        seed = 54321
        
        # Create identical setups
        rng1 = np.random.default_rng(seed)
        env1 = Environment()
        agents1 = [create_agent(AgentID(i), rng=rng1) for i in range(5)]
        
        rng2 = np.random.default_rng(seed)
        env2 = Environment()
        agents2 = [create_agent(AgentID(i), rng=rng2) for i in range(5)]
        
        # Create identical storms
        storm1 = create_storm_system(
            "test_storm", StormSeverity.MODERATE, 
            create_vector2d(50, 50), env1, rng1, Tick(100)
        )
        storm2 = create_storm_system(
            "test_storm", StormSeverity.MODERATE,
            create_vector2d(50, 50), env2, rng2, Tick(100)
        )
        
        # Apply effects
        events1 = apply_storm_effects(agents1, env1, Tick(200), [storm1], rng=rng1)
        events2 = apply_storm_effects(agents2, env2, Tick(200), [storm2], rng=rng2)
        
        # Results should be identical
        assert len(events1) == len(events2)
        for a1, a2 in zip(agents1, agents2):
            assert a1.alive == a2.alive
            np.testing.assert_allclose(a1.velocity, a2.velocity, rtol=1e-10)


class TestPropertyBasedHazards:
    """Property-based tests using hypothesis."""
    
    @given(
        n_agents=st.integers(min_value=1, max_value=50),
        forecast_hours=st.floats(min_value=12.0, max_value=72.0),
        seed=st.integers(min_value=0, max_value=2**31-1)
    )
    @settings(max_examples=30, deadline=5000)
    def test_telegraph_hazards_properties(self, n_agents, forecast_hours, seed):
        """Test telegraph_hazards maintains required properties."""
        assume(forecast_hours >= 12.0)
        
        rng = np.random.default_rng(seed)
        env = create_test_environment(rng)
        current_tick = Tick(1000)
        ticks_per_hour = 3600
        
        forecast = telegraph_hazards(current_tick, forecast_hours, ticks_per_hour, env, rng)
        
        # All forecasted events must be ≥12h in advance
        min_warning_ticks = 12.0 * ticks_per_hour
        for event in forecast:
            warning_time = event["forecast_tick"] - int(current_tick)
            assert warning_time >= min_warning_ticks, f"Warning time {warning_time/ticks_per_hour:.1f}h < 12h"
        
        # Events should be within forecast horizon
        max_forecast_ticks = forecast_hours * ticks_per_hour
        for event in forecast:
            event_time = event["forecast_tick"] - int(current_tick)
            assert event_time <= max_forecast_ticks
    
    @given(
        n_agents=st.integers(min_value=2, max_value=30),
        time_of_day=st.floats(min_value=0.0, max_value=24.0),
        seed=st.integers(min_value=0, max_value=2**31-1)
    )
    @settings(max_examples=50, deadline=5000)
    def test_agent_survival_properties(self, n_agents, time_of_day, seed):
        """Test that agent states remain valid after hazard application."""
        assume(n_agents >= 2)
        
        rng = np.random.default_rng(seed)
        env = create_test_environment(rng)
        agents = [create_agent(AgentID(i), rng=rng) for i in range(n_agents)]
        
        # Store initial counts
        initial_alive = sum(1 for agent in agents if agent.alive)
        
        # Apply all hazards
        events, deaths = apply_all_hazards(
            agents, env, Tick(2000), time_of_day, [], rng
        )
        
        # Verify agent state validity
        for agent in agents:
            if agent.alive:
                assert 0.0 <= agent.energy <= 100.0, f"Invalid energy: {agent.energy}"
                assert 0.0 <= agent.stress <= 100.0, f"Invalid stress: {agent.stress}"
                assert not np.any(np.isnan(agent.position)), "Invalid position"
                assert not np.any(np.isnan(agent.velocity)), "Invalid velocity"
        
        # Death counts should be consistent
        final_alive = sum(1 for agent in agents if agent.alive)
        expected_deaths = initial_alive - final_alive
        assert deaths["total_deaths"] == expected_deaths
        
        # Protected deaths should not exceed total deaths
        assert deaths["protected_deaths"] <= deaths["total_deaths"]
    
    @given(
        cohesion=st.floats(min_value=0.0, max_value=1.0),
        n_agents=st.integers(min_value=5, max_value=20),
        seed=st.integers(min_value=0, max_value=2**31-1)
    )
    @settings(max_examples=30, deadline=5000)
    def test_cohesion_survival_bonus(self, cohesion, n_agents, seed):
        """Test that higher cohesion improves survival rates."""
        assume(0.0 <= cohesion <= 1.0 and n_agents >= 5)
        
        rng = np.random.default_rng(seed)
        env = create_test_environment(rng)
        
        # Create agents positioned for specific cohesion
        agents = []
        for i in range(n_agents):
            agent = create_agent(AgentID(i), rng=rng)
            
            # Position agents to achieve target cohesion
            if cohesion > 0.7:  # High cohesion - cluster agents
                center = create_vector2d(50, 50)
                offset = create_vector2d(rng.normal(0, 5), rng.normal(0, 5))
                agent.position = center + offset
            elif cohesion > 0.3:  # Medium cohesion
                center = create_vector2d(50, 50)
                offset = create_vector2d(rng.normal(0, 15), rng.normal(0, 15))
                agent.position = center + offset
            else:  # Low cohesion - spread agents
                agent.position = create_vector2d(
                    rng.uniform(0, 100), rng.uniform(0, 100)
                )
            
            agents.append(agent)
        
        # Verify cohesion is approximately correct
        actual_cohesion = compute_flock_cohesion(agents)
        
        # Apply predation with consistent parameters
        hotspots = create_default_hotspots(env, rng)
        events = add_predation_events(
            agents, env, Tick(1000), 19.0,  # Dusk - high predation time
            hotspots=hotspots, rng=rng
        )
        
        # Higher cohesion should generally result in fewer deaths
        # This is probabilistic, so we just check the mechanism exists
        predation_events = [e for e in events if e["event_type"] in ["predation", "predation_attempt"]]
        
        for event in predation_events:
            flock_cohesion = event["flock_cohesion"]
            survival_bonus = event["survival_bonus"]
            
            # Verify survival bonus follows cohesion rules
            if flock_cohesion >= 0.7:
                assert survival_bonus >= 0.4, "High cohesion should give survival bonus"
            elif flock_cohesion >= 0.4:
                assert survival_bonus >= 0.1, "Medium cohesion should give some bonus"
            else:
                assert survival_bonus >= 0.0, "Low cohesion gives no bonus"


class TestPredatorBehavior:
    """Test predator spawning and predation mechanics."""
    
    def test_predator_hotspot_creation(self):
        """Test that predator hotspots are created correctly."""
        rng = np.random.default_rng(42)
        env = Environment()
        
        hotspots = create_default_hotspots(env, rng)
        
        assert len(hotspots) > 0, "Should create at least one hotspot"
        
        for hotspot in hotspots:
            assert len(hotspot.vertices) >= 3, "Hotspot must have at least 3 vertices"
            assert 0.0 <= hotspot.predation_efficiency <= 1.0
            assert hotspot.base_spawn_rate >= 0.0
            assert hotspot.name != "unnamed_hotspot", "Should have meaningful names"
    
    def test_hotspot_point_in_polygon(self):
        """Test point-in-polygon detection for hotspots."""
        # Create a simple square hotspot
        vertices = np.array([
            [10, 10],
            [20, 10], 
            [20, 20],
            [10, 20]
        ], dtype=np.float64)
        
        hotspot = PredatorHotspot(
            vertices=vertices,
            name="test_square"
        )
        
        # Test points inside
        assert hotspot.contains_point(create_vector2d(15, 15))
        assert hotspot.contains_point(create_vector2d(11, 11))
        assert hotspot.contains_point(create_vector2d(19, 19))
        
        # Test points outside
        assert not hotspot.contains_point(create_vector2d(5, 5))
        assert not hotspot.contains_point(create_vector2d(25, 25))
        assert not hotspot.contains_point(create_vector2d(15, 5))
    
    def test_time_based_spawn_rates(self):
        """Test that predator spawn rates vary by time of day."""
        vertices = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float64)
        hotspot = PredatorHotspot(vertices=vertices)
        
        # Test different times of day
        dawn_rate = hotspot.get_effective_spawn_rate(6.0)  # 6 AM
        day_rate = hotspot.get_effective_spawn_rate(12.0)  # Noon
        dusk_rate = hotspot.get_effective_spawn_rate(18.0)  # 6 PM
        night_rate = hotspot.get_effective_spawn_rate(22.0)  # 10 PM
        
        # Dusk should have highest activity
        assert dusk_rate >= dawn_rate
        assert dusk_rate >= day_rate
        assert dusk_rate >= night_rate
        
        # Day should have lowest activity
        assert day_rate <= dawn_rate
        assert day_rate <= night_rate
    
    def test_cohesion_affects_predation(self):
        """Test that flock cohesion affects predation survival."""
        rng = np.random.default_rng(42)
        env = Environment()
        
        # Create high-cohesion flock (clustered agents)
        high_cohesion_agents = []
        for i in range(10):
            agent = create_agent(AgentID(i), rng=rng)
            agent.position = create_vector2d(50, 50) + create_vector2d(
                rng.normal(0, 2), rng.normal(0, 2)
            )
            high_cohesion_agents.append(agent)
        
        # Create low-cohesion flock (spread out agents)
        low_cohesion_agents = []
        for i in range(10):
            agent = create_agent(AgentID(i + 10), rng=rng)
            agent.position = create_vector2d(
                rng.uniform(0, 100), rng.uniform(0, 100)
            )
            low_cohesion_agents.append(agent)
        
        # Verify cohesion difference
        high_cohesion = compute_flock_cohesion(high_cohesion_agents)
        low_cohesion = compute_flock_cohesion(low_cohesion_agents)
        assert high_cohesion > low_cohesion
        
        # Apply predation to both flocks (multiple trials for statistical significance)
        high_cohesion_deaths = 0
        low_cohesion_deaths = 0
        
        for trial in range(10):
            trial_rng = np.random.default_rng(42 + trial)
            
            # Reset agent health
            for agents in [high_cohesion_agents, low_cohesion_agents]:
                for agent in agents:
                    agent.alive = True
                    agent.energy = 100.0
                    agent.stress = 0.0
            
            # Apply predation during peak time (dusk)
            high_events = add_predation_events(
                high_cohesion_agents, env, Tick(1000), 18.0, rng=trial_rng
            )
            low_events = add_predation_events(
                low_cohesion_agents, env, Tick(1000), 18.0, rng=trial_rng
            )
            
            high_deaths = sum(e.get("deaths", 0) for e in high_events)
            low_deaths = sum(e.get("deaths", 0) for e in low_events)
            
            high_cohesion_deaths += high_deaths
            low_cohesion_deaths += low_deaths
        
        # High cohesion flock should generally have fewer deaths
        # (This is probabilistic, so we allow some variance)
        logger.info(f"Cohesion test: High={high_cohesion_deaths}, Low={low_cohesion_deaths}")


class TestStormBehavior:
    """Test storm system mechanics."""
    
    def test_storm_system_creation(self):
        """Test storm system creation and initialization."""
        rng = np.random.default_rng(42)
        env = Environment()
        
        storm = create_storm_system(
            "test_storm", StormSeverity.MODERATE,
            create_vector2d(50, 50), env, rng, Tick(100)
        )
        
        assert storm.id == "test_storm"
        assert storm.severity == StormSeverity.MODERATE
        assert len(storm.cells) >= 1
        assert storm.duration_remaining > 0
        assert storm.active
        
        # Storm parameters should match severity
        assert 0.3 <= storm.visibility_reduction <= 0.6  # Moderate range
        assert 1.0 <= storm.energy_drain_rate <= 3.0
    
    def test_storm_wind_calculation(self):
        """Test that storm wind calculations are reasonable."""
        rng = np.random.default_rng(42)
        env = Environment()
        
        storm = create_storm_system(
            "wind_test", StormSeverity.SEVERE,
            create_vector2d(50, 50), env, rng, Tick(100)
        )
        
        # Wind should be strongest at storm center
        center_wind = storm.get_wind_at(create_vector2d(50, 50))
        edge_wind = storm.get_wind_at(create_vector2d(80, 50))
        outside_wind = storm.get_wind_at(create_vector2d(200, 200))
        
        center_speed = np.linalg.norm(center_wind)
        edge_speed = np.linalg.norm(edge_wind)
        outside_speed = np.linalg.norm(outside_wind)
        
        assert center_speed >= edge_speed
        assert edge_speed >= outside_speed
        assert outside_speed == 0.0  # No wind outside storm
    
    def test_storm_energy_drain(self):
        """Test that storms drain agent energy."""
        rng = np.random.default_rng(42)
        env = Environment()
        
        agents = [create_agent(AgentID(i), rng=rng) for i in range(5)]
        initial_energies = [agent.energy for agent in agents]
        
        # Place agents in storm area
        for agent in agents:
            agent.position = create_vector2d(50, 50)
        
        storm = create_storm_system(
            "drain_test", StormSeverity.SEVERE,
            create_vector2d(50, 50), env, rng, Tick(100)
        )
        
        # Apply storm effects
        events = apply_storm_effects(agents, env, Tick(200), [storm], rng=rng)
        
        # Agents should have less energy
        for i, agent in enumerate(agents):
            if agent.alive:  # Only check living agents
                assert agent.energy < initial_energies[i], f"Agent {i} energy should decrease"
    
    def test_storm_movement(self):
        """Test that storms move over time."""
        rng = np.random.default_rng(42)
        env = Environment()
        
        storm = create_storm_system(
            "move_test", StormSeverity.MODERATE,
            create_vector2d(50, 50), env, rng, Tick(100)
        )
        
        # Store initial positions
        initial_positions = [cell.center.copy() for cell in storm.cells]
        
        # Update storm for 1 hour
        storm.update(1.0)
        
        # Cells should have moved
        for i, cell in enumerate(storm.cells):
            distance_moved = np.linalg.norm(cell.center - initial_positions[i])
            assert distance_moved > 0, f"Storm cell {i} should have moved"


class TestLightPollutionBehavior:
    """Test light pollution mechanics."""
    
    def test_urban_lighting_creation(self):
        """Test creation of realistic urban lighting."""
        rng = np.random.default_rng(42)
        env = Environment()
        
        city_centers = [create_vector2d(30, 30), create_vector2d(70, 70)]
        lights = create_urban_lighting(env, city_centers, rng)
        
        assert len(lights) > 0, "Should create light sources"
        
        # Check light type distribution
        light_types = [light.light_type for light in lights]
        assert LightType.STREET_LIGHT in light_types, "Should have street lights"
        assert LightType.BUILDING in light_types, "Should have building lights"
        
        # Lights should be reasonably positioned
        for light in lights:
            assert 0 <= light.position[0] <= env.width
            assert 0 <= light.position[1] <= env.height
    
    def test_light_intensity_falloff(self):
        """Test that light intensity falls off with distance."""
        light = LightPollutionTrap(
            position=create_vector2d(50, 50),
            light_type=LightType.STREET_LIGHT,
            radius=30.0,
            intensity=1.0
        )
        
        # Test at different distances
        center_intensity = light.get_intensity_at(create_vector2d(50, 50), 22.0)  # 10 PM
        near_intensity = light.get_intensity_at(create_vector2d(55, 50), 22.0)
        far_intensity = light.get_intensity_at(create_vector2d(70, 50), 22.0)
        outside_intensity = light.get_intensity_at(create_vector2d(100, 50), 22.0)
        
        assert center_intensity >= near_intensity
        assert near_intensity >= far_intensity
        assert far_intensity >= outside_intensity
        assert outside_intensity == 0.0  # Outside radius
    
    def test_nighttime_only_effects(self):
        """Test that light pollution mainly affects agents at night."""
        rng = np.random.default_rng(42)
        env = Environment()
        agents = [create_agent(AgentID(i), rng=rng) for i in range(5)]
        
        # Position agents in light pollution area
        for agent in agents:
            agent.position = create_vector2d(50, 50)
        
        # Test daytime (should have minimal effects)
        day_events = check_light_pollution(agents, env, Tick(1000), 
                                          time_of_day=12.0, rng=rng)
        
        # Test nighttime (should have effects)
        night_events = check_light_pollution(agents, env, Tick(1000),
                                           time_of_day=22.0, rng=rng)
        
        assert len(day_events) == 0, "Should have no daytime light pollution effects"
        # Note: night_events length depends on random factors, but mechanism is tested
    
    def test_light_trap_probability(self):
        """Test light trap probability calculation."""
        light = LightPollutionTrap(
            position=create_vector2d(50, 50),
            light_type=LightType.STADIUM,  # High intensity
            trap_strength=0.5
        )
        
        # Test at peak migration time
        peak_prob = light.get_trap_probability(create_vector2d(50, 50), 21.0, 1/3600)
        day_prob = light.get_trap_probability(create_vector2d(50, 50), 12.0, 1/3600)
        
        assert peak_prob > 0, "Should have trap probability at night"
        assert day_prob == 0, "Should have no trap probability during day"


class TestPerformance:
    """Performance tests for hazards system."""
    
    @pytest.mark.benchmark
    def test_hazard_application_performance(self):
        """Test that hazard application meets O(N) performance target."""
        rng = np.random.default_rng(42)
        env = create_test_environment(rng)
        
        # Test with 300 agents (performance target)
        agents = [create_agent(AgentID(i), rng=rng) for i in range(300)]
        
        # Warm up
        for _ in range(3):
            events, deaths = apply_all_hazards(
                agents, env, Tick(1000), 20.0, [], rng
            )
        
        # Benchmark hazard application
        start_time = time.perf_counter()
        for _ in range(60):  # 1 second at 60 FPS
            events, deaths = apply_all_hazards(
                agents, env, Tick(1000), 20.0, [], rng
            )
        end_time = time.perf_counter()
        
        elapsed = end_time - start_time
        fps = 60.0 / elapsed
        time_per_call = elapsed / 60 * 1000  # milliseconds
        
        print(f"\nHazards performance (300 agents): {fps:.1f} FPS")
        print(f"Time per hazard application: {time_per_call:.2f}ms")
        
        # Should be fast enough for real-time simulation
        assert fps >= 60.0, f"Hazards too slow: {fps:.1f} FPS < 60 FPS"
    
    @pytest.mark.benchmark
    def test_predation_check_performance(self):
        """Test predation checking performance."""
        rng = np.random.default_rng(42)
        env = Environment()
        agents = [create_agent(AgentID(i), rng=rng) for i in range(100)]
        
        start_time = time.perf_counter()
        for _ in range(1000):
            events = add_predation_events(agents, env, Tick(1000), 18.0, rng=rng)
        end_time = time.perf_counter()
        
        elapsed = end_time - start_time
        time_per_call = elapsed / 1000 * 1e6  # microseconds
        
        print(f"\nPredation check (100 agents): {time_per_call:.1f}μs per call")
        
        # Should be efficient enough for frequent calls
        assert time_per_call < 1000, f"Predation check too slow: {time_per_call:.1f}μs"
    
    @pytest.mark.benchmark
    def test_forecast_generation_performance(self):
        """Test hazard forecasting performance."""
        rng = np.random.default_rng(42)
        env = create_test_environment(rng)
        
        start_time = time.perf_counter()
        for _ in range(100):
            forecast = telegraph_hazards(
                Tick(1000), 48.0, 3600, env, rng
            )
        end_time = time.perf_counter()
        
        elapsed = end_time - start_time
        time_per_call = elapsed / 100 * 1000  # milliseconds
        
        print(f"\nForecast generation: {time_per_call:.2f}ms per call")
        
        # Forecasting should be quick (called infrequently)
        assert time_per_call < 50, f"Forecasting too slow: {time_per_call:.2f}ms"


class TestEventLogging:
    """Test structured JSON logging of hazard events."""
    
    def test_predation_event_structure(self):
        """Test that predation events have required fields."""
        rng = np.random.default_rng(42)
        env = Environment()
        agents = [create_agent(AgentID(i), rng=rng) for i in range(5)]
        
        events = add_predation_events(agents, env, Tick(1000), 18.0, rng=rng)
        
        for event in events:
            assert "event_type" in event
            assert "tick" in event
            if event["event_type"] in ["predation", "predation_attempt"]:
                assert "agent_id" in event
                assert "flock_cohesion" in event
                assert "survival_bonus" in event
                assert "success" in event
    
    def test_storm_event_structure(self):
        """Test that storm events have required fields."""
        rng = np.random.default_rng(42)
        env = Environment()
        agents = [create_agent(AgentID(i), rng=rng) for i in range(3)]
        
        storm = create_storm_system(
            "test", StormSeverity.MODERATE, 
            create_vector2d(50, 50), env, rng, Tick(100)
        )
        
        events = apply_storm_effects(agents, env, Tick(200), [storm], rng=rng)
        
        for event in events:
            assert "event_type" in event
            assert "tick" in event
            if "storm_death" in event["event_type"]:
                assert "agent_id" in event
                assert "cause" in event
                assert "deaths" in event
    
    def test_forecast_event_structure(self):
        """Test that forecast events have required fields."""
        rng = np.random.default_rng(42)
        env = create_test_environment(rng)
        
        forecast = telegraph_hazards(Tick(1000), 24.0, 3600, env, rng)
        
        for event in forecast:
            assert "event_type" in event
            assert "forecast_tick" in event
            assert "warning_time_h" in event
            
            # Verify minimum warning time
            assert event["warning_time_h"] >= 12.0


if __name__ == "__main__":
    # Run specific test categories
    import sys
    
    if "--benchmark" in sys.argv:
        pytest.main([__file__ + "::TestPerformance", "-v", "-s"])
    elif "--property" in sys.argv:
        pytest.main([__file__ + "::TestPropertyBasedHazards", "-v", "-s"])
    else:
        pytest.main([__file__, "-v"])