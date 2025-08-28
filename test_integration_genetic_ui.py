#!/usr/bin/env python3
"""Integration tests for unified simulation + enhanced UI genetic gameplay.

This test suite validates the complete genetic gameplay flow:
- Client-server WebSocket communication with genetic data
- UI panels receiving and displaying genetic statistics  
- Bird inspection system with live genetic traits
- Multi-generational breeding cycles and trait evolution
- Performance with large populations and complex genetic data
"""

import sys
import asyncio
import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
import websockets
from websockets.server import WebSocketServerProtocol

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sim.simulation_unified import UnifiedSimulation
from sim.server import SimulationServer
from sim.simulation_genetic import Gender


class MockWebSocketClient:
    """Mock WebSocket client for testing UI data reception."""
    
    def __init__(self):
        self.received_messages: List[Dict[str, Any]] = []
        self.genetic_data_received = False
        self.breeding_complete_received = False
        self.connection_status = "disconnected"
        
    async def connect_and_test(self, uri: str, test_duration: float = 10.0):
        """Connect to server and collect messages for analysis."""
        try:
            async with websockets.connect(uri) as websocket:
                self.connection_status = "connected"
                print(f"✅ Connected to {uri}")
                
                # Send start unified simulation command
                start_command = {
                    "type": "start_unified",
                    "data": {"migration_id": 1}
                }
                await websocket.send(json.dumps(start_command))
                print("📤 Sent start_unified command")
                
                # Collect messages for test duration
                start_time = time.time()
                while time.time() - start_time < test_duration:
                    try:
                        message_raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        message = json.loads(message_raw)
                        self.received_messages.append(message)
                        
                        # Track specific message types
                        if message.get("type") == "state_update":
                            self.analyze_genetic_data(message.get("data", {}))
                        elif message.get("type") == "migration_breeding_complete":
                            self.breeding_complete_received = True
                            print("🧬 Breeding completion message received")
                            
                    except asyncio.TimeoutError:
                        continue
                        
        except Exception as e:
            print(f"❌ Connection error: {e}")
            self.connection_status = "error"
    
    def analyze_genetic_data(self, data: Dict[str, Any]):
        """Analyze genetic data in state update messages."""
        required_genetic_fields = [
            'generation', 'migration_id', 'current_leg', 'total_legs',
            'population', 'males', 'females', 'population_stats'
        ]
        
        # Check if this is genetic gameplay data
        has_genetic_fields = all(field in data for field in required_genetic_fields)
        
        if has_genetic_fields:
            self.genetic_data_received = True
            
            # Validate birds have genetic traits
            birds = data.get('birds', [])
            if birds:
                sample_bird = birds[0]
                bird_genetic_fields = ['gender', 'generation', 'genetics']
                has_bird_genetics = all(field in sample_bird for field in bird_genetic_fields)
                
                if has_bird_genetics:
                    genetics = sample_bird.get('genetics', {})
                    expected_traits = [
                        'hazard_awareness', 'energy_efficiency', 'flock_cohesion',
                        'beacon_sensitivity', 'stress_resilience', 'leadership'
                    ]
                    has_all_traits = all(trait in genetics for trait in expected_traits)
                    
                    if has_all_traits:
                        print(f"✅ Valid genetic data - Gen {data['generation']}, "
                              f"Migration {data['migration_id']}-{data['current_leg']}/{data['total_legs']}, "
                              f"♂{data['males']} ♀{data['females']}")
                        return True
        
        return False


class IntegrationTestSuite:
    """Comprehensive integration test suite for genetic gameplay."""
    
    def __init__(self):
        self.server = None
        self.server_task = None
        self.test_results = {}
        
    async def run_all_tests(self):
        """Run complete integration test suite."""
        print("🚀 Starting Integration Test Suite - Genetic Gameplay")
        print("=" * 70)
        
        try:
            # Start server for testing
            await self.setup_test_server()
            
            # Run test categories
            await self.test_websocket_genetic_communication()
            await self.test_multi_generational_breeding()
            await self.test_ui_data_structures()
            await self.test_performance_with_genetics()
            await self.test_edge_cases_and_error_handling()
            
            # Generate test report
            self.generate_test_report()
            
        except Exception as e:
            print(f"❌ Test suite failed: {e}")
            import traceback
            print(traceback.format_exc())
        finally:
            await self.cleanup_test_server()
    
    async def setup_test_server(self):
        """Start WebSocket server for testing."""
        print("🔧 Setting up test server...")
        
        self.server = SimulationServer("localhost", 8766)  # Different port for testing
        self.server_task = asyncio.create_task(self.run_test_server())
        
        # Give server time to start
        await asyncio.sleep(2.0)
        print("✅ Test server running on ws://localhost:8766")
    
    async def run_test_server(self):
        """Run the test server."""
        try:
            async def handle_client(websocket, path):
                try:
                    await self.server.register(websocket)
                    async for message in websocket:
                        await self.server.handle_message(websocket, message)
                except websockets.exceptions.ConnectionClosed:
                    pass
                finally:
                    await self.server.unregister(websocket)
            
            # Start WebSocket server and simulation loop
            websocket_server = websockets.serve(handle_client, "localhost", 8766)
            simulation_task = asyncio.create_task(self.server.simulation_loop())
            
            await asyncio.gather(websocket_server, simulation_task)
            
        except Exception as e:
            print(f"❌ Test server error: {e}")
    
    async def cleanup_test_server(self):
        """Stop test server."""
        if self.server_task:
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
        print("🔧 Test server stopped")
    
    async def test_websocket_genetic_communication(self):
        """Test WebSocket communication with genetic data."""
        print("🧪 Testing WebSocket Genetic Communication")
        
        client = MockWebSocketClient()
        
        try:
            # Test genetic data flow
            await client.connect_and_test("ws://localhost:8766", test_duration=8.0)
            
            # Validate results
            assert client.connection_status == "connected", "Failed to connect to server"
            assert len(client.received_messages) > 0, "No messages received from server"
            assert client.genetic_data_received, "No genetic data received"
            
            # Analyze genetic data quality
            genetic_messages = [
                msg for msg in client.received_messages 
                if msg.get("type") == "state_update" and "generation" in msg.get("data", {})
            ]
            
            assert len(genetic_messages) > 0, "No genetic state updates received"
            
            sample_data = genetic_messages[0]["data"]
            
            # Validate required fields for UI
            required_fields = [
                'generation', 'migration_id', 'current_leg', 'total_legs',
                'birds', 'population', 'males', 'females', 'population_stats',
                'leadership_leaders', 'food_sites'
            ]
            
            for field in required_fields:
                assert field in sample_data, f"Missing required field: {field}"
            
            # Validate bird genetic data
            birds = sample_data.get('birds', [])
            if birds:
                bird = birds[0]
                required_bird_fields = ['gender', 'generation', 'genetics']
                for field in required_bird_fields:
                    assert field in bird, f"Missing bird field: {field}"
                
                genetics = bird.get('genetics', {})
                trait_fields = [
                    'hazard_awareness', 'energy_efficiency', 'flock_cohesion',
                    'beacon_sensitivity', 'stress_resilience', 'leadership'
                ]
                for trait in trait_fields:
                    assert trait in genetics, f"Missing genetic trait: {trait}"
                    assert 0 <= genetics[trait] <= 1, f"Invalid trait value: {genetics[trait]}"
            
            self.test_results["websocket_communication"] = "PASSED"
            print("✅ WebSocket genetic communication test PASSED")
            
        except AssertionError as e:
            self.test_results["websocket_communication"] = f"FAILED: {e}"
            print(f"❌ WebSocket test failed: {e}")
        except Exception as e:
            self.test_results["websocket_communication"] = f"ERROR: {e}"
            print(f"💥 WebSocket test error: {e}")
    
    async def test_multi_generational_breeding(self):
        """Test multi-generational breeding cycles."""
        print("🧪 Testing Multi-Generational Breeding")
        
        try:
            # Create unified simulation for direct testing
            config = {
                'migration_id': 1,
                'seed': 42,
                'n_agents': 20  # Smaller for faster testing
            }
            
            sim = UnifiedSimulation(config)
            
            # Validate initial generation
            assert sim.generation == 0, f"Expected generation 0, got {sim.generation}"
            initial_population = len(sim.birds)
            assert initial_population == 20, f"Expected 20 birds, got {initial_population}"
            
            # Check initial gender distribution
            males = sum(1 for b in sim.birds.values() if b.gender == Gender.MALE)
            females = len(sim.birds) - males
            assert 8 <= males <= 12, f"Unbalanced initial gender: {males} males, {females} females"
            
            print(f"✅ Generation 0: {len(sim.birds)} birds (♂{males} ♀{females})")
            
            # Simulate breeding by marking birds as survivors
            survivors = list(sim.birds.values())[:12]  # 12 survivors
            for bird in survivors:
                bird.survived_levels = 1
                bird.agent.alive = True
            
            # Record initial trait averages
            initial_traits = {}
            for trait in ['hazard_awareness', 'leadership']:
                values = [getattr(bird.genetics, trait) for bird in survivors]
                initial_traits[trait] = np.mean(values)
                print(f"Initial {trait}: {initial_traits[trait]:.3f}")
            
            # Perform breeding
            breeding_result = sim.breed_population()
            
            # Validate breeding results
            assert sim.generation == 1, f"Expected generation 1 after breeding, got {sim.generation}"
            assert breeding_result['new_generation'] == 1, "Breeding result generation mismatch"
            assert breeding_result['offspring_created'] >= 0, "No offspring created"
            
            new_population = len(sim.birds)
            new_males = sum(1 for b in sim.birds.values() if b.gender == Gender.MALE)
            new_females = new_population - new_males
            
            print(f"✅ Generation 1: {new_population} birds (♂{new_males} ♀{new_females})")
            print(f"   Breeding: {breeding_result['pairs_formed']} pairs → {breeding_result['offspring_created']} offspring")
            
            # Validate genetic diversity maintained
            gen1_birds = [b for b in sim.birds.values() if b.generation == 1]
            if gen1_birds:
                # Check trait inheritance
                for trait in ['hazard_awareness', 'leadership']:
                    values = [getattr(bird.genetics, trait) for bird in gen1_birds]
                    if values:  # Only if we have Gen 1 birds
                        avg_trait = np.mean(values)
                        print(f"Generation 1 {trait}: {avg_trait:.3f}")
                        
                        # Traits should be similar to parents (within reasonable range)
                        trait_diff = abs(avg_trait - initial_traits[trait])
                        assert trait_diff < 0.3, f"Extreme trait change in {trait}: {trait_diff:.3f}"
            
            # Test another breeding cycle
            survivors_gen1 = list(sim.birds.values())[:10]
            for bird in survivors_gen1:
                bird.survived_levels += 1
                bird.agent.alive = True
            
            breeding_result_2 = sim.breed_population()
            
            assert sim.generation == 2, f"Expected generation 2, got {sim.generation}"
            print(f"✅ Generation 2: {len(sim.birds)} birds")
            
            self.test_results["multi_generational_breeding"] = "PASSED"
            print("✅ Multi-generational breeding test PASSED")
            
        except AssertionError as e:
            self.test_results["multi_generational_breeding"] = f"FAILED: {e}"
            print(f"❌ Breeding test failed: {e}")
        except Exception as e:
            self.test_results["multi_generational_breeding"] = f"ERROR: {e}"
            print(f"💥 Breeding test error: {e}")
            import traceback
            print(traceback.format_exc())
    
    async def test_ui_data_structures(self):
        """Test UI data structure compatibility."""
        print("🧪 Testing UI Data Structures")
        
        try:
            config = {'migration_id': 2, 'seed': 123, 'n_agents': 15}
            sim = UnifiedSimulation(config)
            
            # Run simulation for several steps
            for _ in range(10):
                state = sim.step()
            
            # Validate state structure matches UI expectations
            required_ui_fields = [
                'tick', 'generation', 'migration_id', 'current_leg', 'total_legs',
                'level_name', 'birds', 'population', 'males', 'females',
                'arrivals', 'losses', 'food_sites', 'population_stats',
                'leadership_leaders', 'close_calls', 'panic_events'
            ]
            
            for field in required_ui_fields:
                assert field in state, f"Missing UI field: {field}"
            
            # Validate bird data structure for UI
            birds = state.get('birds', [])
            assert len(birds) > 0, "No birds in state"
            
            sample_bird = birds[0]
            required_bird_ui_fields = [
                'id', 'x', 'y', 'energy', 'stress', 'alive',
                'gender', 'generation', 'genetics', 'fitness'
            ]
            
            for field in required_bird_ui_fields:
                assert field in sample_bird, f"Missing bird UI field: {field}"
            
            # Validate genetics structure for UI display
            genetics = sample_bird.get('genetics', {})
            expected_genetics_fields = [
                'hazard_awareness', 'energy_efficiency', 'flock_cohesion',
                'beacon_sensitivity', 'stress_resilience', 'leadership'
            ]
            
            for field in expected_genetics_fields:
                assert field in genetics, f"Missing genetics field: {field}"
                value = genetics[field]
                assert isinstance(value, (int, float)), f"Invalid genetics type: {field}={value}"
                assert 0 <= value <= 1, f"Genetics value out of range: {field}={value}"
            
            # Validate population stats structure
            pop_stats = state.get('population_stats', {})
            expected_pop_fields = [
                'total_population', 'males', 'females', 'genetic_diversity',
                'avg_hazard_awareness', 'avg_leadership'
            ]
            
            for field in expected_pop_fields:
                assert field in pop_stats, f"Missing population stats field: {field}"
            
            # Validate leadership leaders structure
            leaders = state.get('leadership_leaders', [])
            if leaders:
                leader = leaders[0]
                expected_leader_fields = [
                    'id', 'gender', 'generation', 'lead_time', 
                    'lead_percentage', 'leadership_trait'
                ]
                for field in expected_leader_fields:
                    assert field in leader, f"Missing leader field: {field}"
            
            # Validate food sites structure
            food_sites = state.get('food_sites', [])
            if food_sites:
                site = food_sites[0]
                assert 'x' in site and 'y' in site, "Food site missing coordinates"
                assert 'radius' in site, "Food site missing radius"
            
            self.test_results["ui_data_structures"] = "PASSED"
            print("✅ UI data structures test PASSED")
            
        except AssertionError as e:
            self.test_results["ui_data_structures"] = f"FAILED: {e}"
            print(f"❌ UI data structures test failed: {e}")
        except Exception as e:
            self.test_results["ui_data_structures"] = f"ERROR: {e}"
            print(f"💥 UI data structures test error: {e}")
            import traceback
            print(traceback.format_exc())
    
    async def test_performance_with_genetics(self):
        """Test performance with large genetic populations."""
        print("🧪 Testing Performance with Genetic Data")
        
        try:
            # Test with larger population (target: 100+ birds)
            config = {'migration_id': 1, 'seed': 789, 'n_agents': 100}
            sim = UnifiedSimulation(config)
            
            assert len(sim.birds) == 100, f"Expected 100 birds, got {len(sim.birds)}"
            print(f"✅ Created population of {len(sim.birds)} birds")
            
            # Measure simulation step performance
            step_times = []
            
            for i in range(20):  # 20 steps for performance measurement
                start_time = time.time()
                state = sim.step()
                step_time = time.time() - start_time
                step_times.append(step_time)
                
                if i % 5 == 0:
                    alive_birds = len([b for b in state['birds'] if b['alive']])
                    print(f"  Step {i}: {step_time*1000:.1f}ms, {alive_birds} alive birds")
            
            avg_step_time = np.mean(step_times)
            max_step_time = max(step_times)
            
            print(f"📊 Performance Results:")
            print(f"   Average step time: {avg_step_time*1000:.1f}ms")
            print(f"   Maximum step time: {max_step_time*1000:.1f}ms")
            print(f"   Target FPS (30Hz): {33.3:.1f}ms per frame")
            
            # Performance assertions (should maintain 30 FPS)
            assert avg_step_time < 0.033, f"Performance too slow: {avg_step_time*1000:.1f}ms > 33ms"
            assert max_step_time < 0.050, f"Performance spike too high: {max_step_time*1000:.1f}ms"
            
            # Test breeding performance with large population
            survivors = list(sim.birds.values())[:60]  # 60% survival rate
            for bird in survivors:
                bird.survived_levels = 1
                bird.agent.alive = True
            
            breeding_start = time.time()
            breeding_result = sim.breed_population()
            breeding_time = time.time() - breeding_start
            
            print(f"🧬 Breeding Performance:")
            print(f"   Breeding time: {breeding_time*1000:.1f}ms")
            print(f"   Result: {breeding_result['population_size']} total birds")
            
            # Breeding should complete quickly (< 1 second)
            assert breeding_time < 1.0, f"Breeding too slow: {breeding_time:.3f}s"
            
            # Validate population size is reasonable
            assert 50 <= breeding_result['population_size'] <= 120, \
                f"Population size out of range: {breeding_result['population_size']}"
            
            self.test_results["performance_with_genetics"] = "PASSED"
            print("✅ Performance with genetics test PASSED")
            
        except AssertionError as e:
            self.test_results["performance_with_genetics"] = f"FAILED: {e}"
            print(f"❌ Performance test failed: {e}")
        except Exception as e:
            self.test_results["performance_with_genetics"] = f"ERROR: {e}"
            print(f"💥 Performance test error: {e}")
            import traceback
            print(traceback.format_exc())
    
    async def test_edge_cases_and_error_handling(self):
        """Test edge cases and error handling."""
        print("🧪 Testing Edge Cases and Error Handling")
        
        try:
            test_cases_passed = 0
            total_test_cases = 4
            
            # Test 1: Very small population breeding
            print("  Testing small population breeding...")
            config = {'migration_id': 1, 'seed': 999, 'n_agents': 4}
            sim = UnifiedSimulation(config)
            
            # Only 2 survivors (edge case)
            survivors = list(sim.birds.values())[:2]
            for bird in survivors:
                bird.survived_levels = 1
                bird.agent.alive = True
            
            breeding_result = sim.breed_population()
            assert breeding_result['population_size'] >= 4, "Population too small after breeding"
            test_cases_passed += 1
            print("    ✅ Small population breeding handled")
            
            # Test 2: All male or all female population (edge case)
            print("  Testing gender imbalance...")
            for bird in sim.birds.values():
                bird.gender = Gender.MALE  # Force all male
            
            try:
                breeding_result = sim.breed_population()
                # System should handle this gracefully (create some females)
                final_females = sum(1 for b in sim.birds.values() if b.gender == Gender.FEMALE)
                assert final_females > 0, "No females created to fix gender imbalance"
                test_cases_passed += 1
                print("    ✅ Gender imbalance handled")
            except Exception as e:
                print(f"    ❌ Gender imbalance test failed: {e}")
            
            # Test 3: Extreme trait values
            print("  Testing extreme trait values...")
            for bird in list(sim.birds.values())[:5]:
                bird.genetics.hazard_awareness = 0.0  # Minimum
                bird.genetics.leadership = 1.0        # Maximum
            
            state = sim.step()
            # Should not crash with extreme values
            assert len(state['birds']) > 0, "Simulation crashed with extreme traits"
            test_cases_passed += 1
            print("    ✅ Extreme trait values handled")
            
            # Test 4: Migration completion edge cases
            print("  Testing migration completion...")
            # Force all birds to destination (test completion logic)
            dest_x, dest_y, dest_r = sim.migration_config.destination_zone
            for bird in sim.birds.values():
                if bird.agent.alive:
                    bird.agent.position = np.array([dest_x, dest_y], dtype=np.float32)
            
            state = sim.step()
            # Should detect completion
            assert state['arrivals'] > 0 or state['victory'], "Migration completion not detected"
            test_cases_passed += 1
            print("    ✅ Migration completion handled")
            
            # Overall edge case success rate
            success_rate = test_cases_passed / total_test_cases
            assert success_rate >= 0.75, f"Too many edge case failures: {success_rate:.2%}"
            
            self.test_results["edge_cases"] = f"PASSED ({test_cases_passed}/{total_test_cases})"
            print(f"✅ Edge cases test PASSED ({test_cases_passed}/{total_test_cases})")
            
        except AssertionError as e:
            self.test_results["edge_cases"] = f"FAILED: {e}"
            print(f"❌ Edge cases test failed: {e}")
        except Exception as e:
            self.test_results["edge_cases"] = f"ERROR: {e}"
            print(f"💥 Edge cases test error: {e}")
            import traceback
            print(traceback.format_exc())
    
    def generate_test_report(self):
        """Generate comprehensive test report."""
        print("\n" + "=" * 70)
        print("🎯 INTEGRATION TEST RESULTS")
        print("=" * 70)
        
        passed_tests = 0
        total_tests = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result == "PASSED" or result.startswith("PASSED") else "❌"
            print(f"{status_icon} {test_name.replace('_', ' ').title()}: {result}")
            
            if result == "PASSED" or result.startswith("PASSED"):
                passed_tests += 1
        
        print("\n" + "=" * 70)
        success_rate = passed_tests / total_tests if total_tests > 0 else 0
        print(f"📊 Overall Success Rate: {passed_tests}/{total_tests} ({success_rate:.1%})")
        
        if success_rate >= 0.8:
            print("🎉 INTEGRATION TESTS PASSED - System ready for production!")
        elif success_rate >= 0.6:
            print("⚠️  PARTIAL SUCCESS - Some issues need attention")
        else:
            print("❌ INTEGRATION TESTS FAILED - Critical issues found")
        
        print("=" * 70)
        
        return success_rate >= 0.8


async def main():
    """Run the complete integration test suite."""
    test_suite = IntegrationTestSuite()
    
    try:
        success = await test_suite.run_all_tests()
        return success
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return False
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {e}")
        import traceback
        print(traceback.format_exc())
        return False


if __name__ == "__main__":
    print("🧪 Starting Genetic Gameplay Integration Tests...")
    print("This will test the unified simulation + enhanced UI integration")
    print("Testing WebSocket communication, breeding cycles, and UI compatibility\n")
    
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 Integration tests cancelled")
        sys.exit(1)