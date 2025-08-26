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
    from websockets.server import WebSocketServerProtocol
except ImportError:
    print("Please install websockets: pip install websockets")
    exit(1)

import numpy as np
from dataclasses import asdict

from .simulation_evolved import EvolvedSimulation, GameConfig, Breed
from .simulation_genetic import GeneticSimulation
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
        self.clients: List[WebSocketServerProtocol] = []
        self.running = False
        self.speed = 1.0
        self.paused = False
        self.current_breed = Breed(name="Player's Flock")
        
    async def register(self, websocket: WebSocketServerProtocol) -> None:
        """Register a new client."""
        self.clients.append(websocket)
        logger.info("Client connected", clients=len(self.clients))
        
        # Send initial state
        if self.simulation:
            await self.send_state(websocket)
            
    async def unregister(self, websocket: WebSocketServerProtocol) -> None:
        """Unregister a client."""
        if websocket in self.clients:
            self.clients.remove(websocket)
        logger.info("Client disconnected", clients=len(self.clients))
        
    async def send_state(self, websocket: WebSocketServerProtocol) -> None:
        """Send current simulation state to client."""
        # Use genetic sim if active, otherwise regular sim
        if self.genetic_sim:
            await self.send_genetic_state(websocket)
            return
            
        if not self.simulation:
            return
            
        # Get current game state
        state = self.simulation.step()
        
        # Convert agents to serializable format
        agents_data = []
        for agent in state['agents'][:300]:  # Limit to 300 for performance
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
                "panic_events": state.get('panic_events', 0)
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
        
    async def handle_message(self, websocket: WebSocketServerProtocol, message: str) -> None:
        """Handle incoming message from client.
        
        Args:
            websocket: Client connection
            message: JSON message string
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
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
                
            elif msg_type == "breed":
                await self.breed_population()
                
            elif msg_type == "get_family_tree":
                await self.send_family_tree(data.get("bird_id"))
                
            elif msg_type == "reset_to_gen_zero":
                await self.reset_to_generation_zero()
                
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
        
        # Create evolved simulation with current breed
        import random
        seed = random.randint(1, 100000)  # Different seed each play for variety
        config = GameConfig.from_level(level_id, seed=seed, breed=self.current_breed)
        
        self.simulation = EvolvedSimulation(config)
        self.running = True
        
        # Send initial state immediately
        await self.broadcast_state()
        logger.info("Level loaded with evolved breed", level=level_id, seed=seed, generation=self.current_breed.generation)
        
    async def place_beacon(self, beacon_data: Dict[str, Any]) -> None:
        """Place a beacon in the simulation."""
        if not beacon_data:
            return
        
        x = beacon_data.get('x', 0)
        y = beacon_data.get('y', 0)
        beacon_type = beacon_data.get('type', 'food')
        
        # Place beacon in whichever simulation is active
        if self.genetic_sim:
            self.genetic_sim.place_beacon(beacon_type, x, y)
            logger.info("Beacon placed in genetic sim", type=beacon_type, x=x, y=y)
        elif self.simulation:
            self.simulation.place_beacon(beacon_type, x, y)
            logger.info("Beacon placed in regular sim", type=beacon_type, x=x, y=y)
        
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
        
    async def send_genetic_state(self, websocket: WebSocketServerProtocol) -> None:
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
    
    async def simulation_loop(self) -> None:
        """Main simulation loop."""
        last_update = time.time()
        target_fps = 30  # Target 30 FPS for network updates
        frame_time = 1.0 / target_fps
        
        while True:  # Run forever
            # Handle genetic simulation
            if self.genetic_sim and not self.paused and self.running:
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
                if self.simulation or self.genetic_sim:  # Broadcast if any sim exists
                    await self.broadcast_state()
                last_update = current_time
                
            # Small sleep to prevent CPU spinning
            await asyncio.sleep(0.001)
            
    async def handle_client(self, websocket: WebSocketServerProtocol) -> None:
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