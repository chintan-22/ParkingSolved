"""
Parking Availability Simulator
Generates realistic entry/exit events based on time-of-day patterns.
Sends events to the backend API and optionally via MQTT.
"""

import asyncio
import random
import logging
from datetime import datetime, timezone
from typing import Dict, List
import httpx
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = "http://localhost:8000"
SIMULATION_SPEED = 1.0  # Multiplier for time progression (e.g., 10 = 10x faster)

# Time-based occupancy patterns (percentage occupied)
OCCUPANCY_PATTERNS = {
    "weekday": {
        "0-6": 0.10,      # Night: 10% occupied
        "6-9": 0.25,      # Early morning: 25% occupied
        "9-11": 0.50,     # Morning ramp-up: 50% occupied
        "11-14": 0.85,    # Peak lunch: 85% occupied
        "14-17": 0.75,    # Afternoon: 75% occupied
        "17-19": 0.65,    # Evening: 65% occupied
        "19-23": 0.40,    # Night: 40% occupied
        "23-24": 0.15,    # Late night: 15% occupied
    },
    "weekend": {
        "0-8": 0.15,      # Night: 15% occupied
        "8-10": 0.40,     # Morning: 40% occupied
        "10-14": 0.90,    # Peak: 90% occupied
        "14-18": 0.85,    # Afternoon peak: 85% occupied
        "18-21": 0.70,    # Evening: 70% occupied
        "21-24": 0.30,    # Night: 30% occupied
    }
}

PARKING_LOTS = {
    1: {"name": "Manhattan Beach Pier - Lot A", "capacity": 150},
    2: {"name": "Manhattan Beach Pier - Lot B", "capacity": 200},
    3: {"name": "Manhattan Beach - Parking Garage", "capacity": 300},
    4: {"name": "Beach Access - Lot C", "capacity": 100},
}


class ParkingSimulator:
    """Simulates realistic parking occupancy patterns"""
    
    def __init__(self, api_base_url: str = API_BASE_URL):
        self.api_url = api_base_url
        self.lot_states: Dict[int, int] = {}  # lot_id -> current_occupied_count
        self.client = httpx.AsyncClient()
        self.running = False
    
    async def initialize(self):
        """Initialize simulator by fetching current state from API"""
        try:
            response = await self.client.get(f"{self.api_url}/lots")
            lots = response.json()
            
            for lot in lots:
                self.lot_states[lot["id"]] = lot["occupied_count"]
            
            logger.info(f"Initialized simulator with {len(self.lot_states)} lots")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize simulator: {e}")
            return False
    
    def get_target_occupancy(self, lot_id: int, current_hour: float) -> int:
        """Calculate target occupancy based on time-of-day pattern"""
        lot = PARKING_LOTS.get(lot_id)
        if not lot:
            return 0
        
        capacity = lot["capacity"]
        
        # Determine if weekday or weekend
        now = datetime.now()
        is_weekend = now.weekday() >= 5  # 5=Saturday, 6=Sunday
        pattern_key = "weekend" if is_weekend else "weekday"
        pattern = OCCUPANCY_PATTERNS[pattern_key]
        
        # Find appropriate time bucket
        hour_int = int(current_hour)
        percentage = 0.0
        
        for time_range, percent in pattern.items():
            start, end = map(int, time_range.split("-"))
            if hour_int >= start and hour_int < end:
                percentage = percent
                break
        
        target = int(capacity * percentage)
        return target
    
    async def adjust_occupancy(self, lot_id: int, target: int):
        """Adjust current occupancy towards target by simulating entry/exit events"""
        current = self.lot_states.get(lot_id, 0)
        
        if current == target:
            return
        
        # Determine direction and make small adjustments
        if current < target:
            # Simulate entries
            num_entries = random.randint(1, max(2, (target - current) // 5))
            for _ in range(num_entries):
                await self.record_event(lot_id, "entry")
        else:
            # Simulate exits
            num_exits = random.randint(1, max(2, (current - target) // 5))
            for _ in range(num_exits):
                await self.record_event(lot_id, "exit")
    
    async def record_event(self, lot_id: int, event_type: str):
        """Record an entry or exit event via API"""
        try:
            response = await self.client.post(
                f"{self.api_url}/events",
                json={"lot_id": lot_id, "event_type": event_type}
            )
            
            if response.status_code == 200:
                # Update local state
                if event_type == "entry":
                    self.lot_states[lot_id] = min(
                        self.lot_states[lot_id] + 1,
                        PARKING_LOTS[lot_id]["capacity"]
                    )
                else:
                    self.lot_states[lot_id] = max(self.lot_states[lot_id] - 1, 0)
                
                logger.debug(f"Lot {lot_id}: {event_type}, current occupancy: {self.lot_states[lot_id]}")
            else:
                logger.error(f"Failed to record event for lot {lot_id}: {response.text}")
        
        except Exception as e:
            logger.error(f"Error recording event: {e}")
    
    async def run_simulation_loop(self, update_interval: int = 30):
        """Main simulation loop - runs continuously"""
        self.running = True
        last_hour = -1
        
        while self.running:
            try:
                # Get current time with simulation speed applied
                now = datetime.now()
                current_hour = now.hour + now.minute / 60.0
                
                # Every hour (or less frequently), adjust occupancy towards target
                if int(current_hour) != last_hour:
                    last_hour = int(current_hour)
                    logger.info(f"Hour changed to {last_hour}:00, adjusting occupancy patterns")
                    
                    for lot_id in PARKING_LOTS.keys():
                        target = self.get_target_occupancy(lot_id, current_hour)
                        await self.adjust_occupancy(lot_id, target)
                
                # Add some random events throughout the period
                if random.random() < 0.3:  # 30% chance every update interval
                    random_lot = random.choice(list(PARKING_LOTS.keys()))
                    random_event = random.choice(["entry", "exit"])
                    await self.record_event(random_lot, random_event)
                
                # Log current state
                logger.info(f"Current occupancy: {json.dumps(self.lot_states, indent=2)}")
                
                await asyncio.sleep(update_interval)
            
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(update_interval)
    
    async def stop(self):
        """Stop the simulator"""
        self.running = False
        await self.client.aclose()


async def main():
    """Main entry point"""
    logger.info("Starting Parking Simulator...")
    
    simulator = ParkingSimulator(API_BASE_URL)
    
    # Initialize
    if not await simulator.initialize():
        logger.error("Failed to initialize. Retrying...")
        await asyncio.sleep(2)
        if not await simulator.initialize():
            logger.error("Giving up - could not connect to API")
            return
    
    # Run simulation loop
    try:
        await simulator.run_simulation_loop(update_interval=30)
    except KeyboardInterrupt:
        logger.info("Shutting down simulator...")
        await simulator.stop()


if __name__ == "__main__":
    asyncio.run(main())
