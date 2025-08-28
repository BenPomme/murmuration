"""WebSocket server for Murmuration simulation.

This module provides a WebSocket interface for the React client to
communicate with the Python simulation following CLAUDE.md standards.
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    import websockets
    from websockets.asyncio.server import ServerConnection
    # Use newer websockets API without deprecated classes
except ImportError:
    print("Please install websockets: pip install websockets")
    exit(1)

import numpy as np
from dataclasses import asdict

from .simulation_evolved import EvolvedSimulation, GameConfig, Breed
from .simulation_genetic import GeneticSimulation
from .simulation_unified import UnifiedSimulation  # NEW: Unified simulation
from .migration_system import MigrationManager, MigrationStatus
from .scoring import SimulationResult
from .core.agent import Agent
from .utils.logging import get_logger

logger = get_logger("websocket_server")


class SimulationServer:
    """WebSocket server for Murmuration simulation."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """Initialize server.
        
        Args:
            host: Host address
            port: Port number
        """
        self.host = host
        self.port = port
        self.simulation: Optional[EvolvedSimulation] = None
        self.genetic_sim: Optional[GeneticSimulation] = None  # For genetic mode
        self.unified_sim: Optional[UnifiedSimulation] = None  # NEW: For unified mode
        self.clients: List[ServerConnection] = []
        self.running = False
        self.speed = 1.0
        self.paused = False
        self.current_breed = Breed(name="Player's Flock")
        self.migration_manager = MigrationManager()  # NEW: Multi-leg journey system
        self.victory_processed = False  # Track if current victory has been processed
        self.current_leg = 1  # Track current migration leg (1 = A->B, 2 = B->C, etc.)
        self.max_legs = 4  # Total legs in migration (A->B->C->D->Z)
        
    async def register(self, websocket: ServerConnection) -> None:
        """Register a new client."""
        self.clients.append(websocket)
        logger.info("Client connected", clients=len(self.clients))
        
        # Send initial state
        if self.simulation:
            await self.send_state(websocket)
            
    async def unregister(self, websocket: ServerConnection) -> None:
        """Unregister a client."""
        if websocket in self.clients:
            self.clients.remove(websocket)
        logger.info("Client disconnected", clients=len(self.clients))
        
    async def send_state(self, websocket: ServerConnection) -> None:
        """Send current simulation state to client."""
        # PHASE 2: Prioritize our enhanced simulation, then genetic, then unified as fallback
        if self.simulation:
            await self.send_evolved_state(websocket)
            return
        elif self.genetic_sim:
            await self.send_genetic_state(websocket)
            return
        elif self.unified_sim:
            await self.send_unified_state(websocket)
            return
            
        # No simulation running - auto-start Phase 2 simulation
        await self.load_level("W1-1")
        return
    
    async def send_evolved_state(self, websocket: ServerConnection) -> None:
        """Send Phase 2 evolved simulation state to client."""
        if not self.simulation:
            return
            
        # Get current game state
        state = self.simulation.step()
        
        # Convert agents to serializable format
        agents_data = []
        for agent in state['agents'][:300]:  # Limit to 300 for performance
            # Handle both dict and object agents
            if hasattr(agent, 'id'):
                # Agent object
                agents_data.append({
                    "id": int(agent.id),
                    "x": float(agent.position[0]),
                    "y": float(agent.position[1]),
                    "vx": float(agent.velocity[0]),
                    "vy": float(agent.velocity[1]),
                    "energy": float(agent.energy),
                    "stress": float(agent.stress),
                    "alive": agent.alive
                })
            else:
                # Agent dict (already serialized)
                agents_data.append(agent)
        
        message = {
            "type": "state_update",
            "data": {
                "tick": state['tick'],
                "level": self.simulation.config.level,
                "agents": agents_data,
                "population": state['population'],
                "arrivals": state['arrivals'],
                "losses": state['losses'],
                "cohesion": float(state['cohesion']),
                "beacons": state['beacons'],
                "hazards": [
                    {k: float(v) if isinstance(v, (int, float, np.number)) else 
                     v.tolist() if isinstance(v, np.ndarray) else v 
                     for k, v in h.items()} 
                    for h in state['hazards']
                ],
                "destination": list(state['destination']) if state['destination'] else None,
                "game_over": state['game_over'],
                "victory": state['victory'],
                "time_remaining": state['time_remaining'],
                "season": {
                    "day": state['tick'] // 1800,
                    "hour": (state['tick'] % 1800) // 75
                },
                "beacon_budget": self.simulation.config.beacon_budget - len(state['beacons']),
                "breed": state.get('breed', {}),
                "survival_rate": state.get('survival_rate', 0),
                "close_calls": state.get('close_calls', 0),
                "panic_events": state.get('panic_events', 0),
                # Add migration progression info for genetics panel
                "migration_id": 1,  # For now, always migration 1
                "current_leg": self.current_leg,
                "total_legs": self.max_legs,
                # Add food sites for environmental food system
                "food_sites": state.get('food_havens', [])
            }
        }
        
        await websocket.send(json.dumps(message))
        
    async def broadcast_state(self) -> None:
        """Broadcast state to all connected clients."""
        if not self.clients:
            return
            
        # Send to all clients concurrently
        tasks = [self.send_state(client) for client in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """Broadcast any message to all connected clients."""
        if not self.clients:
            return
        
        msg_str = json.dumps(message)
        tasks = [client.send(msg_str) for client in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def handle_message(self, websocket: ServerConnection, message: str) -> None:
        """Handle incoming message from client.
        
        Args:
            websocket: Client connection
            message: JSON message string
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            # Debug all incoming messages
            logger.info(f"📨 Received message: {msg_type}", data=data)
            
            if msg_type == "load_level":
                await self.load_level(data.get("level", "W1-1"))
                
            elif msg_type == "place_beacon":
                await self.place_beacon(data.get("beacon"))
                
            elif msg_type == "remove_beacon":
                await self.remove_beacon(data.get("id"))
                
            elif msg_type == "activate_pulse":
                await self.activate_pulse(data.get("pulse"))
                
            elif msg_type == "set_speed":
                self.speed = data.get("speed", 1.0)
                self.paused = (self.speed == 0)
                
            elif msg_type == "toggle_overlay":
                # Handle overlay toggle
                pass
                
            elif msg_type == "save_breed":
                await self.save_breed()
                
            elif msg_type == "load_breed":
                await self.load_breed(data.get("breed_data"))
                
            elif msg_type == "start_genetic":
                await self.start_genetic_simulation(data.get("level", "W1-1"))
                
            elif msg_type == "start_unified":
                # PHASE 2: Redirect to our evolved migration system
                migration_id = data.get("migration_id", "spring_coastal") 
                if isinstance(migration_id, int):
                    # Convert legacy numeric ID to journey string
                    journey_map = {1: "spring_coastal", 2: "fall_mountain", 3: "summer_desert", 4: "winter_arctic"}
                    migration_id = journey_map.get(migration_id, "spring_coastal")
                
                # Start migration journey with Phase 2 system
                success = self.migration_manager.start_journey(migration_id, population=100)
                if success:
                    current_leg = self.migration_manager.get_current_leg()
                    if current_leg:
                        # Load the first leg as a level
                        await self.load_level(current_leg.level_template)
                    logger.info("Phase 2 migration journey started", journey_id=migration_id)
                else:
                    logger.error("Failed to start migration journey", journey_id=migration_id)
                
            elif msg_type == "breed":
                await self.breed_population()
                
            elif msg_type == "get_family_tree":
                await self.send_family_tree(data.get("bird_id"))
                
            elif msg_type == "reset_to_gen_zero":
                await self.reset_to_generation_zero()
                
            elif msg_type == "continue_migration":
                logger.info("🔄 Continue migration message received")
                await self.continue_migration()
                
            elif msg_type == "start_journey":
                await self.start_journey(data.get("journey_id", "spring_coastal"))
                
            elif msg_type == "complete_leg":
                await self.complete_current_leg(data.get("survivors", 0))
                
            elif msg_type == "get_journey_progress":
                await self.send_journey_progress(websocket)
                
            elif msg_type == "get_available_journeys":
                await self.send_available_journeys(websocket)
                
            elif msg_type == "inspect_bird":
                await self.send_bird_inspection(websocket, data.get("bird_id"))
                
            elif msg_type == "get_flock_statistics":
                await self.send_flock_statistics(websocket)
                
            elif msg_type == "get_migration_results":
                await self.send_migration_results(websocket)
                
            else:
                logger.warning("Unknown message type", type=msg_type)
                
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON", error=str(e))
        except Exception as e:
            logger.error("Message handling error", error=str(e))
            
    async def load_level(self, level_id: str) -> None:
        """Load a level and start simulation.
        
        Args:
            level_id: Level identifier (e.g., "W1-1")
        """
        logger.info("Loading level", level=level_id)
        
        # Complete cleanup of existing simulation
        if self.simulation:
            self.running = False
            # Evolve breed if level was completed
            if self.simulation.game_over:
                self.simulation.evolve_breed()
                self.current_breed = self.simulation.breed
            self.simulation = None
            await asyncio.sleep(0.1)  # Brief pause to ensure cleanup
        
        # Reset game state completely
        self.paused = False
        self.speed = 1.0
        self.victory_processed = False  # Reset victory flag for new level
        
        # Reset migration leg counter for new levels starting with W1-1
        if level_id == "W1-1":
            self.current_leg = 1
        
        # Create evolved simulation with current breed and migration scaling
        import random
        seed = random.randint(1, 100000)  # Different seed each play for variety
        
        # Get migration number for scaling difficulty
        migration_number = 1
        if self.migration_manager.current_journey:
            migration_number = self.migration_manager.current_journey.current_leg + 1
        
        config = GameConfig.from_level(level_id, seed=seed, breed=self.current_breed, migration_number=migration_number)
        
        self.simulation = EvolvedSimulation(config)
        self.running = True
        
        # Send initial state immediately
        await self.broadcast_state()
        
        # Send level_loaded message to trigger Level Panel
        total_birds = sum(1 for agent in self.simulation.agents if agent.alive)
        # For now, split 50/50 since we don't have gender tracking yet
        males = total_birds // 2
        females = total_birds - males
        
        # Generate leg name based on current progression
        leg_names = ["Breeding Grounds to Coastal Wetlands", "Coastal Wetlands to Mountain Pass", "Mountain Pass to Desert Oasis", "Desert Oasis to Final Destination"]
        leg_name = leg_names[min(self.current_leg-1, len(leg_names)-1)]
        
        level_loaded_msg = {
            "type": "level_loaded", 
            "level": level_id,
            "leg_name": leg_name,
            "current_leg": self.current_leg,
            "total_legs": self.max_legs,
            "males": males,
            "females": females
        }
        logger.info("Sending level_loaded message", msg=level_loaded_msg)
        await self.broadcast_message(level_loaded_msg)
        
        logger.info("Level loaded with evolved breed", level=level_id, seed=seed, generation=self.current_breed.generation)
        
    async def place_beacon(self, beacon_data: Dict[str, Any]) -> None:
        """Place a beacon in the simulation."""
        if not beacon_data:
            return
        
        x = beacon_data.get('x', 0)
        y = beacon_data.get('y', 0)
        beacon_type = beacon_data.get('type', 'food')
        
        # Wind beacons are now the primary beacon types
        # No mapping needed - wind_up and wind_down are the actual types
        
        # Place beacon in whichever simulation is active
        logger.info("🌟 place_beacon called", beacon_data=beacon_data, 
                   unified_sim=bool(self.unified_sim), genetic_sim=bool(self.genetic_sim), regular_sim=bool(self.simulation))
        if self.unified_sim:
            result = self.unified_sim.place_beacon(beacon_type, x, y)
            logger.info("🌟 Beacon placed in unified sim", type=beacon_type, x=x, y=y, result=result)
        elif self.genetic_sim:
            result = self.genetic_sim.place_beacon(beacon_type, x, y)
            logger.info("🌟 Beacon placed in genetic sim", type=beacon_type, x=x, y=y, result=result)
        elif self.simulation:
            result = self.simulation.place_beacon(beacon_type, x, y)
            logger.info("🌟 Beacon placed in regular sim", type=beacon_type, x=x, y=y, result=result)
        
    async def remove_beacon(self, beacon_id: int) -> None:
        """Remove a beacon from the simulation."""
        if not self.simulation:
            return
            
        self.simulation.remove_beacon(beacon_id)
        logger.info("Beacon removed", id=beacon_id)
        
    async def activate_pulse(self, pulse_type: str) -> None:
        """Activate a pulse effect."""
        if not self.simulation or not pulse_type:
            return
            
        self.simulation.activate_pulse(pulse_type)
        logger.info("Pulse activated", type=pulse_type)
        
    async def save_breed(self) -> None:
        """Save current breed data."""
        if not self.simulation:
            return
        
        breed_data = self.simulation.breed.to_dict()
        # Send breed data back to client for download
        message = {
            "type": "breed_data",
            "data": breed_data
        }
        await self.broadcast_message(message)
        logger.info("Breed data sent to client", generation=self.current_breed.generation)
    
    async def load_breed(self, breed_data: Dict[str, Any]) -> None:
        """Load breed from data."""
        if not breed_data:
            return
        
        from .simulation_evolved import Breed
        self.current_breed = Breed.from_dict(breed_data)
        logger.info("Breed loaded", name=self.current_breed.name, generation=self.current_breed.generation)
        
        # Send confirmation
        message = {
            "type": "breed_loaded",
            "data": {"success": True, "breed": self.current_breed.to_dict()}
        }
        await self.broadcast_message(message)
    
    async def start_genetic_simulation(self, level: str) -> None:
        """Start a genetic simulation."""
        logger.info("Starting genetic simulation", level=level)
        
        # Stop regular simulation
        if self.simulation:
            self.simulation = None
            self.running = False
        
        # If we have an existing genetic simulation with bred population, 
        # preserve the birds and just reset the level
        if self.genetic_sim and hasattr(self.genetic_sim, 'birds') and self.genetic_sim.birds:
            # Use the reset_level method to properly reset everything
            self.genetic_sim.reset_level(level)
            logger.info(f"Continuing with existing population of {len(self.genetic_sim.birds)} birds")
        else:
            # Create new genetic simulation for first level
            import random
            config = {
                'level': level,
                'seed': random.randint(1, 100000),
                'n_agents': 100
            }
            
            self.genetic_sim = GeneticSimulation(config)
        
        self.running = True
        self.paused = False  # Make sure simulation isn't paused
        self._breeding_triggered = False  # Reset breeding trigger
        
        await self.broadcast_state()
        logger.info("Genetic simulation started")
    
    async def start_unified_simulation(self, migration_id: int = 1) -> None:
        """Start a unified multi-generational simulation."""
        logger.info("Starting unified simulation", migration_id=migration_id)
        
        # Stop any existing simulations
        if self.simulation:
            self.simulation = None
        if self.genetic_sim:
            self.genetic_sim = None
        self.running = False
        
        # Create new unified simulation
        import random
        config = {
            'migration_id': migration_id,
            'seed': random.randint(1, 100000),
            'n_agents': 100
        }
        
        self.unified_sim = UnifiedSimulation(config)
        self.running = True
        self.paused = False
        self._breeding_triggered = False  # Reset breeding trigger
        
        await self.broadcast_state()
        logger.info(f"Unified simulation started: Migration {migration_id}")
    
    async def reset_to_generation_zero(self) -> None:
        """Reset the game to generation 0 with fresh birds."""
        try:
            logger.info("Resetting to Generation 0")
            
            # Stop the current simulation
            self.running = False
            self.paused = False
            
            # Clear the genetic simulation completely
            self.genetic_sim = None
            self._breeding_triggered = False
            
            # Reset generation counter if it exists
            if hasattr(self, 'generation_count'):
                self.generation_count = 0
            
            # Send confirmation to client
            await self.broadcast_message({
                "type": "reset_complete",
                "generation": 0,
                "message": "Reset to Generation 0 successful"
            })
            
            logger.info("Reset to Generation 0 complete")
        except Exception as e:
            logger.error(f"Error during reset: {e}")
            await self.broadcast_message({
                "type": "error",
                "message": f"Reset failed: {str(e)}"
            })
    
    async def continue_migration(self) -> None:
        """Continue to next leg of migration (for manual progression)."""
        if self.unified_sim:
            success = self.unified_sim.continue_to_next_leg()
            if success:
                logger.info("Manually advanced to next migration leg")
                await self.broadcast_message({
                    "type": "migration_continued",
                    "data": {
                        "current_leg": self.unified_sim.migration_config.current_leg,
                        "total_legs": self.unified_sim.migration_config.total_legs,
                        "level_name": self.unified_sim.migration_config.level_name
                    }
                })
            else:
                logger.warning("Failed to continue migration - not waiting for continue")
        elif self.simulation:
            # Handle manual progression for evolved simulation
            logger.info(f"🔄 Current leg: {self.current_leg}, Max legs: {self.max_legs}")
            
            if self.current_leg < self.max_legs:
                self.current_leg += 1
                
                # Preserve survivors for next leg
                survivors = [agent for agent in self.simulation.agents if agent.alive]
                logger.info(f"🔄 Continuing to leg {self.current_leg} with {len(survivors)} survivors")
                
                # Generate next level name
                leg_names = ["A→B", "B→C", "C→D", "D→Z"]
                next_level = f"W1-{self.current_leg}"
                leg_name = leg_names[min(self.current_leg-1, len(leg_names)-1)]
                
                logger.info(f"🔄 Loading next level: {next_level} ({leg_name})")
                
                # Load next leg and restart simulation
                await self.load_level(next_level)
                self.running = True  # Restart simulation for next leg
                
                # Send continuation message
                await self.broadcast_message({
                    "type": "migration_continued", 
                    "data": {
                        "current_leg": self.current_leg,
                        "total_legs": self.max_legs,
                        "level_name": leg_name,
                        "survivors": len(survivors)
                    }
                })
                logger.info(f"🔄 Migration continued to leg {self.current_leg}")
            else:
                # Migration complete!
                logger.info("🏁 Migration complete! All legs finished.")
                await self.broadcast_message({
                    "type": "migration_complete",
                    "data": {
                        "message": "Migration complete! Your flock has reached the final destination.",
                        "final_survivors": len([a for a in self.simulation.agents if a.alive])
                    }
                })
        else:
            logger.warning("No simulation running - cannot continue migration")
    
    async def breed_population(self) -> None:
        """Perform breeding in genetic simulation."""
        if not self.genetic_sim:
            return
        
        result = self.genetic_sim.breed_population()
        
        # Send breeding results
        message = {
            "type": "breeding_complete",
            "data": result
        }
        await self.broadcast_message(message)
        logger.info("Breeding complete", **result)
    
    async def send_family_tree(self, bird_id: int) -> None:
        """Send family tree for a bird."""
        if not self.genetic_sim:
            return
        
        from .core.types import AgentID
        tree = self.genetic_sim.get_family_tree(AgentID(bird_id), depth=3)
        
        message = {
            "type": "family_tree",
            "data": tree
        }
        await self.broadcast_message(message)
        
    async def send_genetic_state(self, websocket: ServerConnection) -> None:
        """Send genetic simulation state."""
        if not self.genetic_sim:
            return
        
        try:
            # Don't step here - the simulation loop already steps
            # Just get the current state
            
            # Convert hazards to JSON-serializable format
            hazards_data = []
            for hazard in self.genetic_sim.hazards:
                h = hazard.copy()
                # Convert numpy arrays to lists
                if 'direction' in h and hasattr(h['direction'], 'tolist'):
                    h['direction'] = h['direction'].tolist()
                hazards_data.append(h)
            
            state = {
                'tick': self.genetic_sim.tick,
                'generation': self.genetic_sim.generation,
                'birds': [self.genetic_sim.bird_to_dict(b) for b in self.genetic_sim.birds.values() if b.agent.alive],
                'population': len([b for b in self.genetic_sim.birds.values() if b.agent.alive]),
                'males': sum(1 for b in self.genetic_sim.birds.values() if b.agent.alive and b.gender.value == 'male'),
                'females': sum(1 for b in self.genetic_sim.birds.values() if b.agent.alive and b.gender.value == 'female'),
                'arrivals': self.genetic_sim.arrivals,
                'losses': self.genetic_sim.losses,
                'destination': self.genetic_sim.destination_zone,
                'hazards': hazards_data,
                'beacons': self.genetic_sim.beacons,
                'game_over': self.genetic_sim.game_over,
                'victory': self.genetic_sim.victory,
                'time_remaining': max(0, self.genetic_sim.time_limit - (time.time() - self.genetic_sim.start_time)),
                'population_stats': self.genetic_sim.population_stats.__dict__,
                'breeding_pairs': len(self.genetic_sim.breeding_pairs)
            }
            
            message = {
                "type": "state_update",
                "data": state
            }
            
            await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending genetic state: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def send_unified_state(self, websocket: ServerConnection) -> None:
        """Send unified simulation state."""
        if not self.unified_sim:
            return
        
        try:
            # Get state from unified simulation
            state = self.unified_sim.step()
            
            # Convert for JSON serialization
            hazards_data = []
            for hazard in state['hazards']:
                h = hazard.copy()
                if 'direction' in h and hasattr(h['direction'], 'tolist'):
                    h['direction'] = h['direction'].tolist()
                hazards_data.append(h)
            
            message = {
                "type": "state_update", 
                "data": {
                    "tick": state['tick'],
                    "generation": state['generation'],
                    "migration_id": state['migration_id'],
                    "current_leg": state['current_leg'],
                    "total_legs": state['total_legs'],
                    "level_name": state['level_name'],
                    "agents": state['birds'][:300],  # Limit for performance - client expects 'agents'
                    "population": state['population'],
                    "males": state['males'],
                    "females": state['females'],
                    "arrivals": state['arrivals'],
                    "losses": state['losses'],
                    "destination": list(state['destination']),
                    "hazards": hazards_data,
                    "beacons": state['beacons'],
                    "food_sites": state['food_sites'],
                    "game_over": state['game_over'],
                    "victory": state['victory'],
                    "migration_complete": state['migration_complete'],
                    "population_stats": state['population_stats'],
                    "leadership_leaders": state['leadership_leaders'],
                    "close_calls": state['close_calls'],
                    "panic_events": state['panic_events'],
                    # Additional UI data
                    "season": {
                        "day": state['tick'] // 1800,
                        "hour": (state['tick'] % 1800) // 75
                    },
                    "beacon_budget": 3 - len([b for b in state['beacons'] if not b.get('environmental', False)])
                }
            }
            
            await websocket.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending unified state: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def simulation_loop(self) -> None:
        """Main simulation loop."""
        last_update = time.time()
        target_fps = 30  # Target 30 FPS for network updates
        frame_time = 1.0 / target_fps
        
        while True:  # Run forever
            # PHASE 2: Handle Phase 2 evolved simulation first (priority)
            if self.simulation and not self.paused and self.running:
                # CRITICAL FIX: Actually run the simulation step
                self.simulation.step()
                
                # Check for level completion and migration progression
                if self.simulation.game_over and self.simulation.victory and not self.victory_processed:
                    try:
                        self.victory_processed = True  # Mark victory as processed
                        
                        # CRITICAL: Stop simulation to prevent further updates
                        self.running = False
                        
                        # Level complete! Pause and send completion message
                        survivors = self.simulation.arrivals
                        logger.info(f"Migration leg complete! {survivors} birds survived")
                        
                        # Pause the game and wait for user input
                        self.paused = True
                        
                        # Send level completion message to client
                        await self.broadcast_message({
                            "type": "level_completed",
                            "data": {
                                "survivors": survivors,
                                "total_started": self.simulation.config.n_agents,
                                "survival_rate": survivors / self.simulation.config.n_agents if self.simulation.config.n_agents > 0 else 0,
                                "losses": self.simulation.losses,
                                "level": self.simulation.config.level,
                                "current_leg": self.current_leg,
                                "total_legs": self.max_legs,
                                "migration_leg_complete": True
                            }
                        })
                        
                        logger.info(f"Level completed - paused for user input. {survivors} survivors ready for next leg.")
                    except Exception as e:
                        logger.error(f"Error during victory processing: {e}")
                        self.paused = True  # Ensure game pauses even if error occurs
                        
                elif self.simulation.game_over and not self.simulation.victory:
                    # Level failed
                    logger.info("Level failed - pausing")
                    self.paused = True
                
                # Small yield for other tasks
                await asyncio.sleep(0.001)
                
            # Handle unified simulation (fallback)
            elif self.unified_sim and not self.paused and self.running:
                state = self.unified_sim.step()
                
                # Check for migration completion (trigger breeding)
                if state['migration_complete'] and not getattr(self, '_breeding_triggered', False):
                    logger.info("Migration complete! Triggering breeding phase...")
                    self._breeding_triggered = True
                    
                    await asyncio.sleep(1.0)  # Brief pause to show completion
                    
                    # Perform breeding between migrations
                    breeding_result = self.unified_sim.breed_population()
                    logger.info(f"Breeding complete: {breeding_result}")
                    
                    # Send breeding results to client
                    message = {
                        "type": "migration_breeding_complete",
                        "data": breeding_result
                    }
                    await self.broadcast_message(message)
                    
                    # Reset for next migration
                    self.unified_sim.migration_config = self.unified_sim.migration_config.__class__.generate_migration(
                        migration_id=self.unified_sim.migration_config.migration_id + 1,
                        rng=self.unified_sim.rng
                    )
                    
                    # Continue with new migration
                    self._breeding_triggered = False
                    logger.info(f"Starting Migration {self.unified_sim.migration_config.migration_id}")
                
                elif state['game_over'] and not state['victory'] and not self.paused:
                    logger.info("Migration failed! Population extinct")
                    self.paused = True
                    
            # Handle genetic simulation
            elif self.genetic_sim and not self.paused and self.running:
                state = self.genetic_sim.step()
                # Check if we've just achieved victory (not already breeding)
                if state['game_over'] and state['victory'] and not getattr(self, '_breeding_triggered', False):
                    logger.info("Victory achieved! Triggering automatic breeding...")
                    self._breeding_triggered = True
                    
                    # Trigger breeding after a short delay
                    await asyncio.sleep(1.0)  # Give players a moment to see victory
                    
                    # Perform breeding
                    breeding_result = self.genetic_sim.breed_population()
                    logger.info(f"Breeding complete: {breeding_result}")
                    
                    # Send breeding results to client
                    message = {
                        "type": "breeding_complete",
                        "data": breeding_result
                    }
                    await self.broadcast_message(message)
                    
                    # Pause the game until user clicks continue
                    self.paused = True
                    logger.info(f"Game paused after breeding. Generation {breeding_result['new_generation']}, {breeding_result['population_size']} birds ready for next level")
                    
                elif state['game_over'] and not state['victory'] and not self.paused:
                    logger.info("Defeat! Population struggled")
                    self.paused = True
            # Handle regular simulation
            elif self.simulation and not self.paused and self.running:
                # Step simulation
                state = self.simulation.step()
                
                # Check if game over
                if state['game_over']:
                    if state['victory']:
                        logger.info("Victory! Level complete")
                    else:
                        logger.info("Defeat! Try again")
                    # Stop updating but keep simulation for state display
                    self.paused = True
                    
            # Broadcast state at target FPS
            current_time = time.time()
            if current_time - last_update >= frame_time:
                if self.simulation or self.genetic_sim or self.unified_sim:  # Broadcast if any sim exists
                    await self.broadcast_state()
                last_update = current_time
                
            # Small sleep to prevent CPU spinning
            await asyncio.sleep(0.001)
            
    async def start_journey(self, journey_id: str) -> None:
        """Start a new multi-leg migration journey."""
        success = self.migration_manager.start_journey(journey_id, population=100)
        if success:
            logger.info("Started journey", journey_id=journey_id)
            await self.broadcast_message({
                "type": "journey_started",
                "data": self.migration_manager.get_journey_progress()
            })
        else:
            logger.warning("Failed to start journey", journey_id=journey_id)
    
    async def complete_current_leg(self, survivors: int) -> None:
        """Complete the current migration leg and advance."""
        success = self.migration_manager.complete_leg(survivors)
        if success:
            progress = self.migration_manager.get_journey_progress()
            logger.info("Completed migration leg", 
                       leg=progress.get("current_leg", 0),
                       survivors=survivors)
            
            await self.broadcast_message({
                "type": "leg_completed", 
                "data": progress
            })
            
            # If journey is complete, trigger breeding/evolution
            if progress.get("status") == "completed":
                await self.complete_journey()
        else:
            logger.warning("Failed to complete leg - insufficient survivors", survivors=survivors)
            await self.broadcast_message({
                "type": "journey_failed",
                "data": {"survivors": survivors, "reason": "insufficient_survivors"}
            })
    
    async def complete_journey(self) -> None:
        """Handle completion of entire migration journey."""
        if self.simulation and self.migration_manager.current_journey:
            # Evolve breed based on journey performance
            survival_rate = (self.migration_manager.current_journey.current_population / 
                           self.migration_manager.current_journey.starting_population)
            
            self.simulation.evolve_breed()
            self.current_breed = self.simulation.breed
            
            logger.info("Journey completed - breed evolved", 
                       generation=self.current_breed.generation,
                       survival_rate=survival_rate)
            
            await self.broadcast_message({
                "type": "journey_completed",
                "data": {
                    "breed": self.current_breed.to_dict(),
                    "survival_rate": survival_rate,
                    "journey": self.migration_manager.get_journey_progress()
                }
            })
    
    async def send_journey_progress(self, websocket) -> None:
        """Send current journey progress to client."""
        progress = self.migration_manager.get_journey_progress()
        await websocket.send(json.dumps({
            "type": "journey_progress",
            "data": progress
        }))
    
    async def send_available_journeys(self, websocket) -> None:
        """Send list of available journeys to client."""
        journeys = self.migration_manager.get_available_journeys()
        await websocket.send(json.dumps({
            "type": "available_journeys",
            "data": journeys
        }))
    
    async def send_bird_inspection(self, websocket, bird_id: Optional[int]) -> None:
        """Send detailed information about a specific bird."""
        if not bird_id or not self.simulation:
            await websocket.send(json.dumps({
                "type": "bird_inspection",
                "error": "Invalid bird ID or no simulation running"
            }))
            return
            
        # Find the bird
        target_bird = None
        for agent in self.simulation.agents:
            if int(agent.id) == int(bird_id) and agent.alive:
                target_bird = agent
                break
        
        if not target_bird:
            await websocket.send(json.dumps({
                "type": "bird_inspection", 
                "error": f"Bird {bird_id} not found or not alive"
            }))
            return
        
        # Calculate additional statistics
        neighbors = self.simulation.get_neighbors(target_bird, radius=150)
        flock_center = np.mean([a.position for a in self.simulation.agents if a.alive], axis=0) if any(a.alive for a in self.simulation.agents) else target_bird.position
        distance_to_flock_center = np.linalg.norm(target_bird.position - flock_center)
        
        # Calculate distance to destination
        dest_x, dest_y, dest_r = self.simulation.config.destination_zone
        distance_to_destination = np.linalg.norm(target_bird.position - np.array([dest_x, dest_y]))
        
        # Calculate nearest hazard distance
        nearest_hazard_distance = float('inf')
        nearest_hazard_type = "None"
        for hazard in self.simulation.hazards:
            hazard_pos = np.array([hazard.get('x', 0), hazard.get('y', 0)])
            dist = np.linalg.norm(target_bird.position - hazard_pos)
            if dist < nearest_hazard_distance:
                nearest_hazard_distance = dist
                nearest_hazard_type = hazard.get('type', 'Unknown')
        
        bird_data = {
            "id": int(target_bird.id),
            "position": {
                "x": float(target_bird.position[0]),
                "y": float(target_bird.position[1])
            },
            "velocity": {
                "x": float(target_bird.velocity[0]),
                "y": float(target_bird.velocity[1]),
                "speed": float(np.linalg.norm(target_bird.velocity))
            },
            "vital_stats": {
                "energy": float(target_bird.energy),
                "stress": float(target_bird.stress),
                "alive": target_bird.alive,
                "age_ticks": self.simulation.tick - getattr(target_bird, 'birth_tick', 0)
            },
            "genetic_traits": {
                "hazard_detection": float(target_bird.hazard_detection),
                "beacon_response": float(target_bird.beacon_response),
                "generation": getattr(target_bird, 'generation', self.simulation.breed.generation),
                "gender": getattr(target_bird, 'gender', 'unknown'),
                "parent_male_id": getattr(target_bird, 'parent_male_id', -1),
                "parent_female_id": getattr(target_bird, 'parent_female_id', -1)
            },
            "breed_traits": self.simulation.breed.to_dict(),
            "flock_dynamics": {
                "neighbors_count": len(neighbors),
                "distance_to_flock_center": float(distance_to_flock_center),
                "flock_position": "Center" if distance_to_flock_center < 50 else "Edge" if distance_to_flock_center < 150 else "Straggler"
            },
            "navigation": {
                "distance_to_destination": float(distance_to_destination),
                "progress_percentage": max(0, 100 * (1 - distance_to_destination / 2000)),  # Rough estimate
                "nearest_hazard_distance": float(nearest_hazard_distance if nearest_hazard_distance != float('inf') else 0),
                "nearest_hazard_type": nearest_hazard_type
            },
            "survival_history": {
                "close_calls": getattr(target_bird, 'close_calls', 0),
                "hazards_survived": getattr(target_bird, 'hazards_survived', 0),
                "energy_recoveries": getattr(target_bird, 'energy_recoveries', 0)
            }
        }
        
        await websocket.send(json.dumps({
            "type": "bird_inspection",
            "data": bird_data
        }))
    
    async def send_flock_statistics(self, websocket) -> None:
        """Send comprehensive flock statistics."""
        if not self.simulation:
            await websocket.send(json.dumps({
                "type": "flock_statistics",
                "error": "No simulation running"
            }))
            return
            
        alive_agents = [a for a in self.simulation.agents if a.alive]
        if not alive_agents:
            await websocket.send(json.dumps({
                "type": "flock_statistics",
                "data": {"population": 0, "message": "No surviving birds"}
            }))
            return
        
        # Calculate energy statistics
        energies = [a.energy for a in alive_agents]
        stress_levels = [a.stress for a in alive_agents]
        speeds = [np.linalg.norm(a.velocity) for a in alive_agents]
        
        # Calculate spatial distribution
        positions = np.array([a.position for a in alive_agents])
        flock_center = np.mean(positions, axis=0)
        distances_to_center = [np.linalg.norm(pos - flock_center) for pos in positions]
        
        # Calculate progress to destination
        dest_x, dest_y, dest_r = self.simulation.config.destination_zone
        distances_to_dest = [np.linalg.norm(a.position - np.array([dest_x, dest_y])) for a in alive_agents]
        
        # Gender distribution (if available)
        gender_counts = {"male": 0, "female": 0, "unknown": 0}
        for agent in alive_agents:
            gender = getattr(agent, 'gender', 'unknown')
            gender_counts[gender] += 1
        
        # Trait distribution
        hazard_detections = [a.hazard_detection for a in alive_agents]
        beacon_responses = [a.beacon_response for a in alive_agents]
        
        flock_stats = {
            "population": {
                "alive": len(alive_agents),
                "total_started": self.simulation.config.n_agents,
                "survival_rate": len(alive_agents) / self.simulation.config.n_agents,
                "losses": self.simulation.losses,
                "arrivals": self.simulation.arrivals
            },
            "energy_stats": {
                "average": float(np.mean(energies)),
                "min": float(np.min(energies)),
                "max": float(np.max(energies)),
                "std": float(np.std(energies)),
                "low_energy_count": sum(1 for e in energies if e < 50)
            },
            "stress_stats": {
                "average": float(np.mean(stress_levels)),
                "min": float(np.min(stress_levels)),
                "max": float(np.max(stress_levels)),
                "high_stress_count": sum(1 for s in stress_levels if s > 0.7)
            },
            "movement_stats": {
                "average_speed": float(np.mean(speeds)),
                "max_speed": float(np.max(speeds)),
                "min_speed": float(np.min(speeds))
            },
            "spatial_distribution": {
                "flock_center": {
                    "x": float(flock_center[0]),
                    "y": float(flock_center[1])
                },
                "average_distance_to_center": float(np.mean(distances_to_center)),
                "max_distance_to_center": float(np.max(distances_to_center)),
                "cohesion_score": self.simulation.calculate_cohesion(alive_agents)
            },
            "progress": {
                "average_distance_to_destination": float(np.mean(distances_to_dest)),
                "closest_to_destination": float(np.min(distances_to_dest)),
                "progress_percentage": max(0, 100 * (1 - np.mean(distances_to_dest) / 2000))
            },
            "demographics": {
                "gender_distribution": gender_counts,
                "generation": self.simulation.breed.generation,
                "breed_name": self.simulation.breed.name
            },
            "trait_distribution": {
                "hazard_detection": {
                    "average": float(np.mean(hazard_detections)),
                    "min": float(np.min(hazard_detections)),
                    "max": float(np.max(hazard_detections))
                },
                "beacon_response": {
                    "average": float(np.mean(beacon_responses)),
                    "min": float(np.min(beacon_responses)), 
                    "max": float(np.max(beacon_responses))
                }
            },
            "breed_evolution": self.simulation.breed.to_dict(),
            "hazard_encounters": self.simulation.hazards_encountered.copy(),
            "game_events": {
                "close_calls": self.simulation.close_calls,
                "panic_events": self.simulation.panic_events,
                "ticks_survived": self.simulation.tick
            }
        }
        
        await websocket.send(json.dumps({
            "type": "flock_statistics",
            "data": flock_stats
        }))
    
    async def send_migration_results(self, websocket) -> None:
        """Send end-of-migration breeding summary and results."""
        if not self.simulation:
            await websocket.send(json.dumps({
                "type": "migration_results",
                "error": "No simulation running"
            }))
            return
        
        # Calculate final migration statistics
        alive_agents = [a for a in self.simulation.agents if a.alive]
        arrived_agents = self.simulation.arrivals
        
        # Calculate trait evolution potential
        survivors = alive_agents + [a for a in self.simulation.agents if not a.alive and hasattr(a, 'reached_destination')]
        
        # Pre-migration breed state for comparison
        original_breed = self.simulation.breed.to_dict()
        
        # Simulate what breeding would produce
        if len(alive_agents) >= 2:
            breeding_preview = self.simulation.breed_survivors(alive_agents, target_population=100)
        else:
            breeding_preview = []
        
        # Calculate performance metrics
        survival_rate = len(alive_agents) / self.simulation.config.n_agents if self.simulation.config.n_agents > 0 else 0
        arrival_rate = arrived_agents / self.simulation.config.n_agents if self.simulation.config.n_agents > 0 else 0
        
        # Migration challenges encountered
        challenges_faced = {
            "total_hazards": len(self.simulation.hazards),
            "hazard_encounters": self.simulation.hazards_encountered.copy(),
            "close_calls": self.simulation.close_calls,
            "panic_events": self.simulation.panic_events,
            "time_elapsed": self.simulation.tick / 60  # Convert to minutes at 60 FPS
        }
        
        # Calculate trait distribution changes
        if alive_agents:
            current_hazard_detection = np.mean([a.hazard_detection for a in alive_agents])
            current_beacon_response = np.mean([a.beacon_response for a in alive_agents])
        else:
            current_hazard_detection = self.simulation.breed.hazard_awareness
            current_beacon_response = self.simulation.breed.beacon_sensitivity
        
        # Performance evaluation
        if arrival_rate >= 0.8:
            performance_grade = "Exceptional"
            performance_description = "Outstanding migration with minimal losses"
        elif arrival_rate >= 0.6:
            performance_grade = "Good"
            performance_description = "Successful migration with acceptable losses"
        elif arrival_rate >= 0.4:
            performance_grade = "Fair"
            performance_description = "Challenging migration with significant losses"
        elif survival_rate >= 0.2:
            performance_grade = "Poor"
            performance_description = "Difficult migration with heavy casualties"
        else:
            performance_grade = "Catastrophic"
            performance_description = "Migration failed with devastating losses"
        
        # Breeding recommendations
        breeding_recommendations = []
        if survival_rate < 0.3:
            breeding_recommendations.append("Focus on hazard awareness - too many birds were lost to dangers")
        if self.simulation.panic_events > 5:
            breeding_recommendations.append("Improve stress resilience - flock panicked frequently")
        if challenges_faced.get('hazard_encounters', {}).get('tornado', 0) > 0.5:
            breeding_recommendations.append("Storm survival traits needed - many birds struggled in bad weather")
        if len(breeding_recommendations) == 0:
            breeding_recommendations.append("Well-adapted flock - minor improvements to all traits")
        
        migration_results = {
            "migration_summary": {
                "level": self.simulation.config.level,
                "migration_number": getattr(self.simulation.config, 'migration_number', 1),
                "duration_minutes": challenges_faced["time_elapsed"],
                "performance_grade": performance_grade,
                "performance_description": performance_description
            },
            "population_results": {
                "started_with": self.simulation.config.n_agents,
                "survivors": len(alive_agents),
                "arrived_safely": arrived_agents,
                "losses": self.simulation.losses,
                "survival_rate": survival_rate,
                "arrival_rate": arrival_rate,
                "success": arrival_rate >= 0.6  # 60% arrival rate for success
            },
            "breed_evolution": {
                "before": original_breed,
                "generation_number": self.simulation.breed.generation,
                "evolved_traits": {
                    "hazard_awareness": self.simulation.breed.hazard_awareness,
                    "energy_efficiency": self.simulation.breed.energy_efficiency,
                    "flock_cohesion": self.simulation.breed.flock_cohesion,
                    "beacon_sensitivity": self.simulation.breed.beacon_sensitivity,
                    "stress_resilience": self.simulation.breed.stress_resilience
                },
                "trait_improvements": {
                    "hazard_detection_avg": current_hazard_detection,
                    "beacon_response_avg": current_beacon_response
                }
            },
            "challenges_overcome": challenges_faced,
            "next_generation": {
                "projected_population": len(breeding_preview),
                "breeding_pairs": len(breeding_preview) // 2 if breeding_preview else 0,
                "genetic_diversity": len(set(f"{bp.get('parent_male_id', -1)}-{bp.get('parent_female_id', -1)}" for bp in breeding_preview)) if breeding_preview else 0
            },
            "recommendations": {
                "breeding_advice": breeding_recommendations,
                "strategic_tips": [
                    "Use shelter beacons near storms to reduce stress",
                    "Place thermal beacons to boost flock speed in safe areas", 
                    "Watch for moving hazards and plan beacon placement accordingly",
                    "High-stress birds need more recovery time between challenges"
                ]
            },
            "achievements": self._calculate_achievements(survival_rate, arrival_rate, challenges_faced),
            "ready_for_next_migration": len(alive_agents) >= 50  # Minimum viable population
        }
        
        await websocket.send(json.dumps({
            "type": "migration_results",
            "data": migration_results
        }))
    
    def _calculate_achievements(self, survival_rate: float, arrival_rate: float, challenges: dict) -> list:
        """Calculate achievements earned during migration."""
        achievements = []
        
        if arrival_rate >= 0.9:
            achievements.append({"name": "Flock Master", "description": "90%+ arrival rate", "icon": "🏆"})
        elif arrival_rate >= 0.8:
            achievements.append({"name": "Expert Guide", "description": "80%+ arrival rate", "icon": "🥇"})
        elif arrival_rate >= 0.6:
            achievements.append({"name": "Successful Migration", "description": "60%+ arrival rate", "icon": "🥈"})
            
        if survival_rate >= 0.95:
            achievements.append({"name": "Zero Losses", "description": "Almost no birds lost", "icon": "💎"})
            
        if challenges.get("close_calls", 0) >= 10:
            achievements.append({"name": "Close Call Survivor", "description": "Survived many dangerous encounters", "icon": "⚡"})
            
        if challenges.get("panic_events", 0) == 0:
            achievements.append({"name": "Calm Under Pressure", "description": "No panic events during migration", "icon": "🧘"})
            
        if challenges.get("time_elapsed", float('inf')) <= 2.0:  # Under 2 minutes
            achievements.append({"name": "Speed Run", "description": "Completed migration quickly", "icon": "💨"})
        
        return achievements

    async def handle_client(self, websocket: ServerConnection) -> None:
        """Handle a client connection.
        
        Args:
            websocket: Client WebSocket connection
        """
        await self.register(websocket)
        
        try:
            async for message in websocket:
                try:
                    await self.handle_message(websocket, message)
                except Exception as e:
                    logger.error("Error handling message", error=str(e), client=websocket.remote_address)
        except websockets.exceptions.ConnectionClosed as e:
            logger.info("Client connection closed normally", reason=e.reason, code=e.code)
        except Exception as e:
            logger.error("Unexpected client error", error=str(e), client=websocket.remote_address)
        finally:
            await self.unregister(websocket)
            
    async def start(self) -> None:
        """Start the WebSocket server."""
        logger.info("Starting server", host=self.host, port=self.port)
        
        # Start simulation loop
        asyncio.create_task(self.simulation_loop())
        
        # Start WebSocket server with extended timeouts and ping settings
        async with websockets.serve(
            self.handle_client, 
            self.host, 
            self.port,
            ping_interval=20,  # Send ping every 20 seconds
            ping_timeout=10,   # Wait 10 seconds for pong
            close_timeout=10   # Wait 10 seconds to close
        ):
            logger.info("Server running", url=f"ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever


def main():
    """Main entry point."""
    server = SimulationServer()
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()