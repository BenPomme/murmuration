"""Comprehensive test suite for beacon system.

Tests cover determinism, invariant properties, performance benchmarks,
and property-based testing following CLAUDE.md standards.

Test Categories:
- Unit tests for beacon classes and field calculations
- Property-based tests for invariants
- Performance tests for O(N*B) complexity
- Integration tests for beacon and pulse managers
- Edge case and error handling tests
"""

import math
import pytest
import time
from hypothesis import given, strategies as st, assume, settings
from typing import List, Dict
import numpy as np

from sim.beacons.beacon import (
    Beacon,
    LightBeacon,
    SoundBeacon, 
    FoodScentBeacon,
    WindLureBeacon,
    BeaconType,
    BeaconManager,
    BEACON_SPECS,
    TICKS_PER_DAY,
)

from sim.beacons.pulse import (
    Pulse,
    FestivalPulse,
    ScoutingPing,
    PulseType,
    PulseManager,
    PULSE_SPECS,
    TICKS_PER_HOUR,
)

from sim.core.types import create_vector2d, Tick


class TestBeaconSpecs:
    """Test beacon specification constants."""
    
    def test_beacon_specs_exist(self):
        """Test that all beacon types have specifications."""
        for beacon_type in BeaconType:
            assert beacon_type in BEACON_SPECS
            spec = BEACON_SPECS[beacon_type]
            assert spec.radius > 0
            assert spec.cost > 0
            assert spec.half_life_days > 0
    
    def test_beacon_specs_match_design_doc(self):
        """Test beacon specs match design document requirements."""
        # Light Beacon: radius 150, cost 1, half-life 1.5 days
        light_spec = BEACON_SPECS[BeaconType.LIGHT]
        assert light_spec.radius == 150.0
        assert light_spec.cost == 1
        assert light_spec.half_life_days == 1.5
        
        # Sound Beacon: radius 180, cost 1, half-life 1.0 day  
        sound_spec = BEACON_SPECS[BeaconType.SOUND]
        assert sound_spec.radius == 180.0
        assert sound_spec.cost == 1
        assert sound_spec.half_life_days == 1.0
        
        # Food Scent: radius 120, cost 2, half-life 0.8 day
        food_spec = BEACON_SPECS[BeaconType.FOOD_SCENT]
        assert food_spec.radius == 120.0
        assert food_spec.cost == 2
        assert food_spec.half_life_days == 0.8
        
        # Wind Lure: radius 200, cost 2, half-life 1.0 day
        wind_spec = BEACON_SPECS[BeaconType.WIND_LURE]
        assert wind_spec.radius == 200.0
        assert wind_spec.cost == 2
        assert wind_spec.half_life_days == 1.0
    
    def test_decay_constant_calculation(self):
        """Test decay constant calculation from half-life."""
        spec = BEACON_SPECS[BeaconType.LIGHT]
        expected_tau = spec.half_life_days / math.log(2)
        assert abs(spec.decay_constant - expected_tau) < 1e-10


class TestBeacon:
    """Test base Beacon class functionality."""
    
    def test_beacon_creation(self):
        """Test beacon creation with valid parameters."""
        position = create_vector2d(100.0, 200.0)
        beacon = Beacon(BeaconType.LIGHT, position, Tick(1000), 1)
        
        assert beacon.beacon_type == BeaconType.LIGHT
        assert np.allclose(beacon.position, position)
        assert beacon.placed_at_tick == 1000
        assert beacon.beacon_id == 1
    
    def test_temporal_decay_at_placement(self):
        """Test temporal decay is 1.0 immediately after placement."""
        position = create_vector2d(0.0, 0.0)
        beacon = Beacon(BeaconType.LIGHT, position, Tick(1000), 1)
        
        decay = beacon.get_temporal_decay(Tick(1000))
        assert abs(decay - 1.0) < 1e-10
    
    def test_temporal_decay_after_half_life(self):
        """Test temporal decay is 0.5 after one half-life."""
        position = create_vector2d(0.0, 0.0)
        beacon = Beacon(BeaconType.LIGHT, position, Tick(1000), 1)
        
        half_life_ticks = int(1.5 * TICKS_PER_DAY)
        decay = beacon.get_temporal_decay(Tick(1000 + half_life_ticks))
        assert abs(decay - 0.5) < 0.01  # Allow small numerical error
    
    def test_distance_decay_at_center(self):
        """Test distance decay is 1.0 at beacon center."""
        position = create_vector2d(100.0, 200.0)
        beacon = Beacon(BeaconType.LIGHT, position, Tick(1000), 1)
        
        decay = beacon.get_distance_decay(position)
        assert abs(decay - 1.0) < 1e-10
    
    def test_distance_decay_exponential(self):
        """Test distance decay follows exponential formula."""
        center = create_vector2d(0.0, 0.0)
        beacon = Beacon(BeaconType.LIGHT, center, Tick(1000), 1)
        
        # Test at beacon radius
        test_pos = create_vector2d(150.0, 0.0)  # At radius distance
        decay = beacon.get_distance_decay(test_pos)
        expected = math.exp(-1.0)  # exp(-radius/radius) = exp(-1)
        assert abs(decay - expected) < 1e-10
    
    def test_field_strength_combines_decays(self):
        """Test field strength combines temporal and distance decay."""
        position = create_vector2d(0.0, 0.0)
        beacon = Beacon(BeaconType.SOUND, position, Tick(1000), 1)
        
        # Test at distance and time that gives known decay values
        test_pos = create_vector2d(180.0, 0.0)  # At radius
        half_life_ticks = int(1.0 * TICKS_PER_DAY)  # One half-life
        
        distance_decay = math.exp(-1.0)  # exp(-radius/radius)
        temporal_decay = 0.5  # After one half-life
        expected = distance_decay * temporal_decay
        
        strength = beacon.get_field_strength(test_pos, Tick(1000 + half_life_ticks))
        assert abs(strength - expected) < 0.01
    
    def test_beacon_expiry(self):
        """Test beacon expiry detection."""
        position = create_vector2d(0.0, 0.0)
        beacon = Beacon(BeaconType.LIGHT, position, Tick(1000), 1)
        
        # Should not be expired initially
        assert not beacon.is_expired(Tick(1000))
        
        # Should be expired after many half-lives
        far_future = Tick(1000 + 10 * int(1.5 * TICKS_PER_DAY))
        assert beacon.is_expired(far_future)
    
    @given(
        x=st.floats(-1000, 1000),
        y=st.floats(-1000, 1000), 
        tick=st.integers(0, 100000)
    )
    def test_field_strength_bounds(self, x, y, tick):
        """Property test: field strength always in [0, 1]."""
        position = create_vector2d(0.0, 0.0)
        beacon = Beacon(BeaconType.LIGHT, position, Tick(1000), 1)
        
        test_pos = create_vector2d(x, y)
        strength = beacon.get_field_strength(test_pos, Tick(1000 + tick))
        
        assert 0.0 <= strength <= 1.0


class TestSpecificBeaconTypes:
    """Test specific beacon type implementations."""
    
    def test_light_beacon_night_bonus(self):
        """Test light beacon provides night bonus."""
        position = create_vector2d(0.0, 0.0)
        beacon = LightBeacon(position, Tick(1000), 1)
        
        base_strength = beacon.get_field_strength(position, Tick(1000))
        day_attraction = beacon.get_attraction_strength(position, Tick(1000), False)
        night_attraction = beacon.get_attraction_strength(position, Tick(1000), True)
        
        assert night_attraction > day_attraction
        assert day_attraction == base_strength * 0.7
        assert night_attraction == base_strength * 1.5
    
    def test_sound_beacon_cohesion_boost(self):
        """Test sound beacon cohesion boost."""
        position = create_vector2d(0.0, 0.0)
        beacon = SoundBeacon(position, Tick(1000), 1)
        
        boost = beacon.get_cohesion_boost(position, Tick(1000))
        expected = beacon.get_field_strength(position, Tick(1000))
        assert abs(boost - expected) < 1e-10
    
    def test_food_scent_foraging_bias(self):
        """Test food scent beacon foraging bias."""
        position = create_vector2d(0.0, 0.0)
        beacon = FoodScentBeacon(position, Tick(1000), 1)
        
        bias = beacon.get_foraging_bias(position, Tick(1000))
        expected = beacon.get_field_strength(position, Tick(1000))
        assert abs(bias - expected) < 1e-10
    
    def test_wind_lure_boost(self):
        """Test wind lure beacon wind boost."""
        position = create_vector2d(0.0, 0.0)
        beacon = WindLureBeacon(position, Tick(1000), 1)
        
        boost = beacon.get_wind_boost(position, Tick(1000))
        expected = beacon.get_field_strength(position, Tick(1000))
        assert abs(boost - expected) < 1e-10


class TestBeaconManager:
    """Test BeaconManager functionality."""
    
    def test_manager_initialization(self):
        """Test beacon manager initializes correctly."""
        manager = BeaconManager(budget_limit=10)
        
        assert manager.budget_limit == 10
        assert manager.budget_used == 0
        assert len(manager.beacons) == 0
        assert manager.next_beacon_id == 1
    
    def test_budget_checking(self):
        """Test budget limit enforcement."""
        manager = BeaconManager(budget_limit=3)
        
        # Should be able to place cost-1 beacon
        assert manager.can_place_beacon(BeaconType.LIGHT)
        assert manager.can_place_beacon(BeaconType.SOUND)
        
        # Should be able to place cost-2 beacon
        assert manager.can_place_beacon(BeaconType.FOOD_SCENT)
        assert manager.can_place_beacon(BeaconType.WIND_LURE)
        
        # Place a cost-2 beacon
        position = create_vector2d(0.0, 0.0)
        beacon = manager.place_beacon(BeaconType.FOOD_SCENT, position, Tick(1000))
        assert beacon is not None
        assert manager.budget_used == 2
        
        # Should still be able to place cost-1 beacon
        assert manager.can_place_beacon(BeaconType.LIGHT)
        
        # Should NOT be able to place another cost-2 beacon
        assert not manager.can_place_beacon(BeaconType.FOOD_SCENT)
    
    def test_beacon_placement_and_removal(self):
        """Test beacon placement and removal."""
        manager = BeaconManager(budget_limit=10)
        position = create_vector2d(100.0, 200.0)
        
        # Place beacon
        beacon = manager.place_beacon(BeaconType.LIGHT, position, Tick(1000))
        assert beacon is not None
        assert len(manager.beacons) == 1
        assert manager.budget_used == 1
        assert manager.get_beacon_count() == 1
        assert manager.get_beacon_count(BeaconType.LIGHT) == 1
        
        # Remove beacon
        success = manager.remove_beacon(beacon.beacon_id)
        assert success
        assert len(manager.beacons) == 0
        assert manager.budget_used == 0
        assert manager.get_beacon_count() == 0
    
    def test_remove_nonexistent_beacon(self):
        """Test removing non-existent beacon fails gracefully."""
        manager = BeaconManager(budget_limit=10)
        
        success = manager.remove_beacon(999)
        assert not success
        assert len(manager.beacons) == 0
        assert manager.budget_used == 0
    
    def test_expired_beacon_cleanup(self):
        """Test automatic cleanup of expired beacons."""
        manager = BeaconManager(budget_limit=10)
        position = create_vector2d(0.0, 0.0)
        
        # Place beacon
        beacon = manager.place_beacon(BeaconType.LIGHT, position, Tick(1000))
        assert beacon is not None
        assert len(manager.beacons) == 1
        
        # Far in the future, beacon should be expired
        far_future = Tick(1000 + 100 * int(1.5 * TICKS_PER_DAY))
        removed_count = manager.cleanup_expired_beacons(far_future)
        
        assert removed_count == 1
        assert len(manager.beacons) == 0
        assert manager.budget_used == 0
    
    def test_field_contribution_calculation(self):
        """Test combined field contribution calculation."""
        manager = BeaconManager(budget_limit=10)
        center = create_vector2d(0.0, 0.0)
        
        # Place one of each beacon type
        light = manager.place_beacon(BeaconType.LIGHT, center, Tick(1000))
        sound = manager.place_beacon(BeaconType.SOUND, center, Tick(1000))
        food = manager.place_beacon(BeaconType.FOOD_SCENT, center, Tick(1000))
        wind = manager.place_beacon(BeaconType.WIND_LURE, center, Tick(1000))
        
        # Get contributions at center
        contrib = manager.get_combined_field_contribution(
            center, Tick(1000), is_night=True
        )
        
        # All contributions should be positive at center
        assert contrib["light_attraction"] > 0
        assert contrib["cohesion_boost"] > 0
        assert contrib["foraging_bias"] > 0
        assert contrib["wind_boost"] > 0
        
        # Light should be stronger at night
        day_contrib = manager.get_combined_field_contribution(
            center, Tick(1000), is_night=False
        )
        assert contrib["light_attraction"] > day_contrib["light_attraction"]
    
    def test_diminishing_returns_stacking(self):
        """Test diminishing returns for multiple beacons of same type."""
        manager = BeaconManager(budget_limit=10)
        center = create_vector2d(0.0, 0.0)
        
        # Place two light beacons at same position
        light1 = manager.place_beacon(BeaconType.LIGHT, center, Tick(1000))
        light2 = manager.place_beacon(BeaconType.LIGHT, center, Tick(1000))
        
        contrib = manager.get_combined_field_contribution(center, Tick(1000))
        
        # Should be less than 2x single beacon due to diminishing returns
        # With 0.7 diminishing factor: 1.0 + 1.0*0.7 = 1.7
        # But light has night/day multipliers, so exact value depends on calculation
        assert contrib["light_attraction"] > 0
        assert contrib["light_attraction"] < 2.0  # Less than perfect stacking
    
    def test_budget_info(self):
        """Test budget information reporting."""
        manager = BeaconManager(budget_limit=5)
        position = create_vector2d(0.0, 0.0)
        
        initial_info = manager.get_budget_info()
        assert initial_info["budget_used"] == 0
        assert initial_info["budget_limit"] == 5
        assert initial_info["budget_remaining"] == 5
        
        # Place beacon
        manager.place_beacon(BeaconType.FOOD_SCENT, position, Tick(1000))
        
        updated_info = manager.get_budget_info()
        assert updated_info["budget_used"] == 2
        assert updated_info["budget_limit"] == 5
        assert updated_info["budget_remaining"] == 3


class TestPulses:
    """Test pulse system functionality."""
    
    def test_pulse_specs_match_design_doc(self):
        """Test pulse specs match design document."""
        # Festival Pulse: radius 220, duration 12h, cooldown 24h
        festival_spec = PULSE_SPECS[PulseType.FESTIVAL]
        assert festival_spec.radius == 220.0
        assert festival_spec.duration_hours == 12.0
        assert festival_spec.cooldown_hours == 24.0
        
        # Scouting Ping: radius 200, duration 24h, no cooldown
        scout_spec = PULSE_SPECS[PulseType.SCOUTING]
        assert scout_spec.radius == 200.0
        assert scout_spec.duration_hours == 24.0
        assert scout_spec.cooldown_hours == 0.0
    
    def test_pulse_creation_and_activity(self):
        """Test pulse creation and activity checking."""
        position = create_vector2d(0.0, 0.0)
        pulse = FestivalPulse(position, Tick(1000), 1)
        
        # Should be active immediately
        assert pulse.is_active(Tick(1000))
        assert not pulse.is_expired(Tick(1000))
        
        # Should be active during duration
        mid_duration = Tick(1000 + pulse.spec.duration_ticks // 2)
        assert pulse.is_active(mid_duration)
        
        # Should be expired after duration
        after_duration = Tick(1000 + pulse.spec.duration_ticks + 1)
        assert not pulse.is_active(after_duration)
        assert pulse.is_expired(after_duration)
    
    def test_festival_pulse_reward_multiplier(self):
        """Test festival pulse reward multiplier."""
        center = create_vector2d(0.0, 0.0)
        pulse = FestivalPulse(center, Tick(1000), 1)
        
        # Inside radius should get multiplier
        inside_pos = create_vector2d(100.0, 0.0)  # Well within radius
        multiplier = pulse.get_reward_multiplier(inside_pos, Tick(1000))
        assert multiplier > 1.0
        
        # Outside radius should get no multiplier
        outside_pos = create_vector2d(300.0, 0.0)  # Beyond radius
        multiplier = pulse.get_reward_multiplier(outside_pos, Tick(1000))
        assert multiplier == 1.0
    
    def test_scouting_ping_fog_reveal(self):
        """Test scouting ping fog reveal."""
        center = create_vector2d(0.0, 0.0)
        pulse = ScoutingPing(center, Tick(1000), 1)
        
        # Inside radius should reveal fog
        inside_pos = create_vector2d(150.0, 0.0)  # Within radius
        assert pulse.reveals_fog_at(inside_pos, Tick(1000))
        
        # Outside radius should not reveal fog
        outside_pos = create_vector2d(250.0, 0.0)  # Beyond radius  
        assert not pulse.reveals_fog_at(outside_pos, Tick(1000))
    
    def test_pulse_effect_strength_binary(self):
        """Test pulse effect strength is binary (inside/outside radius)."""
        center = create_vector2d(0.0, 0.0)
        pulse = FestivalPulse(center, Tick(1000), 1)
        
        # Exactly at center should have full strength
        assert pulse.get_effect_strength(center, Tick(1000)) == 1.0
        
        # Just inside radius should have full strength
        inside_pos = create_vector2d(pulse.spec.radius - 1, 0.0)
        assert pulse.get_effect_strength(inside_pos, Tick(1000)) == 1.0
        
        # Just outside radius should have no effect
        outside_pos = create_vector2d(pulse.spec.radius + 1, 0.0)
        assert pulse.get_effect_strength(outside_pos, Tick(1000)) == 0.0


class TestPulseManager:
    """Test PulseManager functionality."""
    
    def test_manager_initialization(self):
        """Test pulse manager initializes correctly."""
        manager = PulseManager()
        
        assert len(manager.active_pulses) == 0
        assert len(manager.last_used) == 0
        assert all(count == 0 for count in manager.use_counts.values())
        assert manager.next_pulse_id == 1
    
    def test_pulse_activation_without_cooldown(self):
        """Test pulse activation when no cooldown constraints."""
        manager = PulseManager()
        position = create_vector2d(0.0, 0.0)
        
        # Should be able to activate initially
        assert manager.can_use_pulse(PulseType.SCOUTING, Tick(1000))
        
        pulse = manager.activate_pulse(PulseType.SCOUTING, position, Tick(1000))
        assert pulse is not None
        assert len(manager.active_pulses) == 1
        assert manager.use_counts[PulseType.SCOUTING] == 1
    
    def test_pulse_cooldown_enforcement(self):
        """Test pulse cooldown is properly enforced."""
        manager = PulseManager()
        position = create_vector2d(0.0, 0.0)
        
        # Activate festival pulse
        pulse1 = manager.activate_pulse(PulseType.FESTIVAL, position, Tick(1000))
        assert pulse1 is not None
        
        # Should not be able to activate again immediately
        assert not manager.can_use_pulse(PulseType.FESTIVAL, Tick(1001))
        
        pulse2 = manager.activate_pulse(PulseType.FESTIVAL, position, Tick(1001))
        assert pulse2 is None
        
        # Should be able to activate after cooldown
        cooldown_ticks = PULSE_SPECS[PulseType.FESTIVAL].cooldown_ticks
        future_tick = Tick(1000 + cooldown_ticks + 1)
        assert manager.can_use_pulse(PulseType.FESTIVAL, future_tick)
    
    def test_cooldown_remaining_calculation(self):
        """Test cooldown remaining calculation."""
        manager = PulseManager()
        position = create_vector2d(0.0, 0.0)
        
        # No cooldown initially
        assert manager.get_cooldown_remaining(PulseType.FESTIVAL, Tick(1000)) == 0
        
        # Activate pulse
        manager.activate_pulse(PulseType.FESTIVAL, position, Tick(1000))
        
        # Should have cooldown remaining
        cooldown_spec = PULSE_SPECS[PulseType.FESTIVAL].cooldown_ticks
        remaining = manager.get_cooldown_remaining(PulseType.FESTIVAL, Tick(1001))
        assert remaining == cooldown_spec - 1
    
    def test_expired_pulse_cleanup(self):
        """Test automatic cleanup of expired pulses."""
        manager = PulseManager()
        position = create_vector2d(0.0, 0.0)
        
        # Activate pulse
        pulse = manager.activate_pulse(PulseType.FESTIVAL, position, Tick(1000))
        assert pulse is not None
        assert len(manager.active_pulses) == 1
        
        # After duration, pulse should be cleaned up
        duration_ticks = PULSE_SPECS[PulseType.FESTIVAL].duration_ticks
        future_tick = Tick(1000 + duration_ticks + 1)
        
        removed_count = manager.cleanup_expired_pulses(future_tick)
        assert removed_count == 1
        assert len(manager.active_pulses) == 0
    
    def test_festival_multiplier_combination(self):
        """Test multiple festival pulses combine additively."""
        manager = PulseManager()
        position = create_vector2d(0.0, 0.0)
        
        # Activate first festival pulse (need to bypass cooldown for test)
        pulse1 = FestivalPulse(position, Tick(1000), 1)
        manager.active_pulses.append(pulse1)
        
        pulse2 = FestivalPulse(position, Tick(1000), 2)
        manager.active_pulses.append(pulse2)
        
        # Should get additive multipliers
        multiplier = manager.get_festival_multiplier(position, Tick(1000))
        
        # Each pulse adds 0.5 to base multiplier, so 1.0 + 0.5 + 0.5 = 2.0
        assert abs(multiplier - 2.0) < 0.1
    
    def test_fog_reveal_from_any_scout_pulse(self):
        """Test fog is revealed if any scout pulse covers the area."""
        manager = PulseManager()
        pos1 = create_vector2d(0.0, 0.0)
        pos2 = create_vector2d(300.0, 0.0)  # Far apart
        
        # Activate scout pulse at pos1
        pulse = manager.activate_pulse(PulseType.SCOUTING, pos1, Tick(1000))
        assert pulse is not None
        
        # Should reveal near pos1 but not pos2
        assert manager.is_fog_revealed(pos1, Tick(1000))
        assert not manager.is_fog_revealed(pos2, Tick(1000))
    
    def test_pulse_status_reporting(self):
        """Test comprehensive pulse status reporting."""
        manager = PulseManager()
        
        status = manager.get_pulse_status(Tick(1000))
        
        # Should have status for both pulse types
        assert "festival" in status
        assert "scouting" in status
        
        # Check festival status structure
        festival_status = status["festival"]
        assert "can_use" in festival_status
        assert "cooldown_remaining_ticks" in festival_status
        assert "use_count" in festival_status
        assert "active_count" in festival_status
        assert "spec" in festival_status
        
        # Initially should be able to use
        assert festival_status["can_use"]
        assert festival_status["cooldown_remaining_ticks"] == 0
        assert festival_status["use_count"] == 0
        assert festival_status["active_count"] == 0


class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.slow
    def test_beacon_manager_performance(self):
        """Test beacon manager scales O(N*B) for field calculations."""
        manager = BeaconManager(budget_limit=20)
        
        # Place multiple beacons
        for i in range(10):
            pos = create_vector2d(i * 100.0, i * 100.0)
            manager.place_beacon(BeaconType.LIGHT, pos, Tick(1000))
        
        # Time field contribution calculations
        test_positions = [create_vector2d(i * 50.0, i * 50.0) for i in range(100)]
        
        start_time = time.time()
        for pos in test_positions:
            contrib = manager.get_combined_field_contribution(pos, Tick(1000))
        end_time = time.time()
        
        # Should complete reasonably quickly
        elapsed = end_time - start_time
        assert elapsed < 0.1  # Less than 100ms for 100 positions × 10 beacons
    
    @pytest.mark.slow 
    def test_pulse_manager_performance(self):
        """Test pulse manager performance with many active pulses."""
        manager = PulseManager()
        
        # Simulate many active pulses (bypass cooldown for testing)
        for i in range(50):
            pos = create_vector2d(i * 100.0, i * 100.0)
            pulse = FestivalPulse(pos, Tick(1000), i)
            manager.active_pulses.append(pulse)
        
        # Time multiplier calculations
        test_positions = [create_vector2d(i * 50.0, i * 50.0) for i in range(100)]
        
        start_time = time.time()
        for pos in test_positions:
            multiplier = manager.get_festival_multiplier(pos, Tick(1000))
        end_time = time.time()
        
        elapsed = end_time - start_time
        assert elapsed < 0.1  # Should still be fast


class TestPropertyBased:
    """Property-based tests using Hypothesis."""
    
    @given(
        beacon_type=st.sampled_from(list(BeaconType)),
        x=st.floats(-1000, 1000),
        y=st.floats(-1000, 1000),
        tick=st.integers(0, 100000)
    )
    @settings(max_examples=50)
    def test_beacon_field_strength_invariants(self, beacon_type, x, y, tick):
        """Property test: beacon field strength invariants."""
        position = create_vector2d(0.0, 0.0)
        beacon = Beacon(beacon_type, position, Tick(1000), 1)
        
        test_pos = create_vector2d(x, y)
        strength = beacon.get_field_strength(test_pos, Tick(1000 + tick))
        
        # Invariant: strength always in [0, 1]
        assert 0.0 <= strength <= 1.0
        
        # Invariant: strength decreases with time
        if tick > 0:
            earlier_strength = beacon.get_field_strength(test_pos, Tick(1000))
            assert strength <= earlier_strength
    
    @given(
        budget=st.integers(1, 20),
        placements=st.lists(
            st.tuples(
                st.sampled_from(list(BeaconType)),
                st.floats(-500, 500),
                st.floats(-500, 500)
            ),
            min_size=0, max_size=10
        )
    )
    @settings(max_examples=30)
    def test_beacon_manager_budget_invariant(self, budget, placements):
        """Property test: beacon manager never exceeds budget."""
        manager = BeaconManager(budget_limit=budget)
        
        placed_beacons = []
        for beacon_type, x, y in placements:
            position = create_vector2d(x, y)
            beacon = manager.place_beacon(beacon_type, position, Tick(1000))
            if beacon is not None:
                placed_beacons.append(beacon)
        
        # Invariant: budget never exceeded
        assert manager.budget_used <= manager.budget_limit
        
        # Invariant: budget equals sum of placed beacon costs
        expected_cost = sum(BEACON_SPECS[b.beacon_type].cost for b in placed_beacons)
        assert manager.budget_used == expected_cost
    
    @given(
        pulse_type=st.sampled_from(list(PulseType)),
        x=st.floats(-1000, 1000),
        y=st.floats(-1000, 1000),
        tick_offset=st.integers(0, 50000)
    )
    @settings(max_examples=50)
    def test_pulse_effect_strength_invariants(self, pulse_type, x, y, tick_offset):
        """Property test: pulse effect strength invariants."""
        position = create_vector2d(0.0, 0.0)
        
        if pulse_type == PulseType.FESTIVAL:
            pulse = FestivalPulse(position, Tick(1000), 1)
        else:
            pulse = ScoutingPing(position, Tick(1000), 1)
        
        test_pos = create_vector2d(x, y)
        strength = pulse.get_effect_strength(test_pos, Tick(1000 + tick_offset))
        
        # Invariant: effect strength is binary (0 or 1)
        assert strength == 0.0 or strength == 1.0
        
        # Invariant: no effect after expiry
        if tick_offset > pulse.spec.duration_ticks:
            assert strength == 0.0


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_beacon_negative_time(self):
        """Test beacon handles negative time gracefully."""
        position = create_vector2d(0.0, 0.0)
        beacon = Beacon(BeaconType.LIGHT, position, Tick(1000), 1)
        
        # Should handle negative time (past) gracefully
        decay = beacon.get_temporal_decay(Tick(500))  # Before placement
        assert decay == 1.0  # Should return maximum decay as fallback
    
    def test_beacon_zero_distance(self):
        """Test beacon at exactly zero distance."""
        position = create_vector2d(0.0, 0.0)
        beacon = Beacon(BeaconType.LIGHT, position, Tick(1000), 1)
        
        decay = beacon.get_distance_decay(position)
        assert abs(decay - 1.0) < 1e-10
    
    def test_manager_zero_budget(self):
        """Test beacon manager with zero budget."""
        manager = BeaconManager(budget_limit=0)
        position = create_vector2d(0.0, 0.0)
        
        # Should not be able to place any beacons
        for beacon_type in BeaconType:
            assert not manager.can_place_beacon(beacon_type)
            beacon = manager.place_beacon(beacon_type, position, Tick(1000))
            assert beacon is None
    
    def test_pulse_at_exact_radius(self):
        """Test pulse effect at exactly the radius boundary."""
        center = create_vector2d(0.0, 0.0)
        pulse = FestivalPulse(center, Tick(1000), 1)
        
        # At exactly the radius should still have effect
        radius_pos = create_vector2d(pulse.spec.radius, 0.0)
        strength = pulse.get_effect_strength(radius_pos, Tick(1000))
        assert strength == 1.0
        
        # Just outside radius should have no effect
        outside_pos = create_vector2d(pulse.spec.radius + 0.1, 0.0)
        strength = pulse.get_effect_strength(outside_pos, Tick(1000))
        assert strength == 0.0


if __name__ == "__main__":
    pytest.main([__file__])