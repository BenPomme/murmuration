"""Multi-leg migration journey system for strategic gameplay.

This module implements the A→B→C→D→Z checkpoint progression system
from Phase 2 of the roadmap.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any
from enum import Enum
import numpy as np
from pathlib import Path
import json


class MigrationStatus(Enum):
    """Status of current migration leg."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Checkpoint:
    """Individual checkpoint in migration journey."""
    id: str  # A, B, C, D, Z
    name: str
    description: str
    position: Tuple[float, float]  # x, y coordinates
    radius: float = 100.0  # Success radius
    is_rest_stop: bool = True  # Whether birds get full energy restoration
    required_survivors: int = 70  # Min birds needed to proceed


@dataclass 
class MigrationLeg:
    """Individual leg of the migration journey."""
    leg_id: str  # A-B, B-C, C-D, D-Z
    start_checkpoint: Checkpoint
    end_checkpoint: Checkpoint
    distance: float
    estimated_time: int  # seconds
    level_template: str  # Base level to use for hazards
    difficulty_multiplier: float = 1.0
    
    # Environmental challenges for this leg
    hazards: List[Dict] = None
    food_sites: List[Dict] = None
    weather_conditions: Dict = None


@dataclass
class MigrationJourney:
    """Complete multi-leg migration journey."""
    journey_id: str
    name: str
    description: str
    season: str  # Spring, Summer, Fall, Winter
    total_distance: float
    
    # Journey structure
    checkpoints: List[Checkpoint]
    legs: List[MigrationLeg]
    
    # Current progress
    current_leg: int = 0
    completed_legs: List[str] = None
    status: MigrationStatus = MigrationStatus.NOT_STARTED
    
    # Journey statistics
    starting_population: int = 100
    current_population: int = 100
    total_losses: int = 0
    journey_start_time: Optional[float] = None
    
    def __post_init__(self):
        if self.completed_legs is None:
            self.completed_legs = []


class MigrationManager:
    """Manages multi-leg migration journeys and progression."""
    
    def __init__(self):
        self.current_journey: Optional[MigrationJourney] = None
        self.available_journeys: Dict[str, MigrationJourney] = {}
        self._load_journey_templates()
    
    def _load_journey_templates(self):
        """Load predefined journey templates from JSON."""
        # Define standard migration routes
        self.available_journeys = {
            "spring_coastal": self._create_spring_coastal_journey(),
            "fall_mountain": self._create_fall_mountain_journey(),  
            "summer_desert": self._create_summer_desert_journey(),
            "winter_arctic": self._create_winter_arctic_journey()
        }
    
    def _create_spring_coastal_journey(self) -> MigrationJourney:
        """Create spring coastal migration template."""
        checkpoints = [
            Checkpoint("A", "Breeding Grounds", "Safe starting area", (200, 600), 120, True, 95),
            Checkpoint("B", "Coastal Wetlands", "Rich feeding area", (600, 400), 100, True, 80),
            Checkpoint("C", "Island Stopover", "Mid-ocean rest point", (1100, 300), 80, True, 70),
            Checkpoint("D", "Mainland Shore", "Continental approach", (1500, 500), 100, True, 65),
            Checkpoint("Z", "Summer Territory", "Final destination", (1850, 600), 150, True, 60)
        ]
        
        legs = [
            MigrationLeg("A-B", checkpoints[0], checkpoints[1], 450, 90, "W1-1", 1.0),
            MigrationLeg("B-C", checkpoints[1], checkpoints[2], 520, 100, "W1-2", 1.2),
            MigrationLeg("C-D", checkpoints[2], checkpoints[3], 460, 95, "W2-1", 1.4),
            MigrationLeg("D-Z", checkpoints[3], checkpoints[4], 420, 85, "W2-2", 1.6)
        ]
        
        return MigrationJourney(
            journey_id="spring_coastal",
            name="Spring Coastal Migration", 
            description="Follow the ancient coastal route to summer breeding grounds",
            season="Spring",
            total_distance=1850.0,
            checkpoints=checkpoints,
            legs=legs
        )
    
    def _create_fall_mountain_journey(self) -> MigrationJourney:
        """Create challenging fall mountain migration."""
        checkpoints = [
            Checkpoint("A", "Highland Meadows", "Mountain starting point", (150, 800), 100, True, 95),
            Checkpoint("B", "Valley Pass", "Narrow mountain pass", (500, 600), 80, True, 85),
            Checkpoint("C", "Ridge Rest", "High altitude stopover", (900, 400), 70, True, 75),
            Checkpoint("D", "Foothill Lakes", "Descent to lowlands", (1300, 700), 90, True, 70),
            Checkpoint("Z", "Winter Refuge", "Protected wintering area", (1800, 900), 120, True, 65)
        ]
        
        legs = [
            MigrationLeg("A-B", checkpoints[0], checkpoints[1], 480, 120, "W2-1", 1.3),
            MigrationLeg("B-C", checkpoints[1], checkpoints[2], 510, 130, "W3-1", 1.5),  
            MigrationLeg("C-D", checkpoints[2], checkpoints[3], 520, 140, "W3-2", 1.7),
            MigrationLeg("D-Z", checkpoints[3], checkpoints[4], 550, 150, "W4-1", 1.9)
        ]
        
        return MigrationJourney(
            journey_id="fall_mountain",
            name="Fall Mountain Migration",
            description="Navigate treacherous mountain passes before winter",
            season="Fall", 
            total_distance=2060.0,
            checkpoints=checkpoints,
            legs=legs
        )
    
    def _create_summer_desert_journey(self) -> MigrationJourney:
        """Create hot summer desert crossing."""
        checkpoints = [
            Checkpoint("A", "Oasis Start", "Last water before desert", (100, 500), 110, True, 95),
            Checkpoint("B", "Midday Rest", "Shade shelter point", (450, 650), 60, True, 80),
            Checkpoint("C", "Canyon Springs", "Hidden water source", (850, 400), 70, True, 75), 
            Checkpoint("D", "Mesa View", "High ground waypoint", (1250, 550), 80, True, 70),
            Checkpoint("Z", "Cool Highlands", "Escape the heat", (1750, 300), 130, True, 65)
        ]
        
        legs = [
            MigrationLeg("A-B", checkpoints[0], checkpoints[1], 420, 80, "W1-2", 1.1),
            MigrationLeg("B-C", checkpoints[1], checkpoints[2], 480, 90, "W2-2", 1.3),
            MigrationLeg("C-D", checkpoints[2], checkpoints[3], 450, 85, "W3-1", 1.5),
            MigrationLeg("D-Z", checkpoints[3], checkpoints[4], 520, 100, "W4-2", 1.7)
        ]
        
        return MigrationJourney(
            journey_id="summer_desert",
            name="Summer Desert Crossing",
            description="Cross the scorching desert before the heat peaks",
            season="Summer",
            total_distance=1870.0,
            checkpoints=checkpoints,
            legs=legs
        )
    
    def _create_winter_arctic_journey(self) -> MigrationJourney:
        """Create brutal winter arctic migration."""
        checkpoints = [
            Checkpoint("A", "Storm Shelter", "Protected starting cove", (250, 700), 90, True, 90),
            Checkpoint("B", "Ice Bridge", "Treacherous crossing point", (600, 500), 50, True, 75),
            Checkpoint("C", "Frozen Lake", "Ice-locked rest area", (1000, 300), 60, True, 65),
            Checkpoint("D", "Blizzard Pass", "Final challenge point", (1400, 650), 70, True, 55),
            Checkpoint("Z", "Safe Harbor", "Storm-protected destination", (1850, 400), 140, True, 50)
        ]
        
        legs = [
            MigrationLeg("A-B", checkpoints[0], checkpoints[1], 460, 110, "W2-2", 1.4),
            MigrationLeg("B-C", checkpoints[1], checkpoints[2], 500, 120, "W3-2", 1.6),
            MigrationLeg("C-D", checkpoints[2], checkpoints[3], 480, 115, "W4-1", 1.8),
            MigrationLeg("D-Z", checkpoints[3], checkpoints[4], 520, 125, "W4-2", 2.0)
        ]
        
        return MigrationJourney(
            journey_id="winter_arctic",
            name="Winter Arctic Migration",
            description="Survive the harshest conditions nature can offer",
            season="Winter",
            total_distance=1960.0,
            checkpoints=checkpoints,
            legs=legs
        )
    
    def start_journey(self, journey_id: str, population: int = 100) -> bool:
        """Start a new migration journey."""
        if journey_id not in self.available_journeys:
            return False
            
        self.current_journey = self.available_journeys[journey_id]
        self.current_journey.starting_population = population
        self.current_journey.current_population = population
        self.current_journey.current_leg = 0
        self.current_journey.completed_legs = []
        self.current_journey.status = MigrationStatus.IN_PROGRESS
        self.current_journey.journey_start_time = None  # Set when simulation starts
        
        return True
    
    def complete_leg(self, survivors: int) -> bool:
        """Complete current leg and advance to next."""
        if not self.current_journey or self.current_journey.status != MigrationStatus.IN_PROGRESS:
            return False
            
        current_leg = self.current_journey.legs[self.current_journey.current_leg]
        
        # Check if enough birds survived
        if survivors < current_leg.end_checkpoint.required_survivors:
            self.current_journey.status = MigrationStatus.FAILED
            return False
            
        # Mark leg as completed
        leg_id = current_leg.leg_id
        self.current_journey.completed_legs.append(leg_id)
        self.current_journey.current_population = survivors
        
        # Check if journey is complete
        if self.current_journey.current_leg >= len(self.current_journey.legs) - 1:
            self.current_journey.status = MigrationStatus.COMPLETED
            return True
            
        # Advance to next leg
        self.current_journey.current_leg += 1
        return True
    
    def get_current_leg(self) -> Optional[MigrationLeg]:
        """Get the currently active migration leg."""
        if not self.current_journey:
            return None
            
        if self.current_journey.current_leg >= len(self.current_journey.legs):
            return None
            
        return self.current_journey.legs[self.current_journey.current_leg]
    
    def get_journey_progress(self) -> Dict[str, Any]:
        """Get current journey progress information."""
        if not self.current_journey:
            return {"status": "no_journey"}
            
        current_leg = self.get_current_leg()
        
        return {
            "journey_id": self.current_journey.journey_id,
            "journey_name": self.current_journey.name,
            "status": self.current_journey.status.value,
            "current_leg": self.current_journey.current_leg + 1,
            "total_legs": len(self.current_journey.legs),
            "completed_legs": len(self.current_journey.completed_legs),
            "current_leg_name": current_leg.leg_id if current_leg else "Complete",
            "population": self.current_journey.current_population,
            "starting_population": self.current_journey.starting_population,
            "survival_rate": self.current_journey.current_population / self.current_journey.starting_population,
            "checkpoints": [
                {
                    "id": cp.id,
                    "name": cp.name,
                    "description": cp.description,
                    "position": cp.position,
                    "completed": i < len(self.current_journey.completed_legs)
                }
                for i, cp in enumerate(self.current_journey.checkpoints)
            ]
        }
    
    def get_available_journeys(self) -> List[Dict[str, Any]]:
        """Get list of available journey options."""
        return [
            {
                "id": journey.journey_id,
                "name": journey.name,
                "description": journey.description,
                "season": journey.season,
                "total_distance": journey.total_distance,
                "difficulty": len(journey.legs)  # Simple difficulty rating
            }
            for journey in self.available_journeys.values()
        ]