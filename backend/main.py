"""
FastAPI Backend for Smart Parking Availability System
Handles real-time occupancy data, WebSocket streaming, and parking lot management
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import redis.asyncio as redis
import logging

# ============================================================================
# CONFIGURATION & SETUP
# ============================================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://parking_user:parking_pass@localhost/parking_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis connection (will be initialized in lifespan)
redis_client: Optional[redis.Redis] = None

# ============================================================================
# DATABASE MODELS
# ============================================================================

class ParkingLot(Base):
    __tablename__ = "parking_lots"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    address = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    total_capacity = Column(Integer)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class OccupancyEvent(Base):
    __tablename__ = "occupancy_events"
    
    id = Column(Integer, primary_key=True, index=True)
    lot_id = Column(Integer, ForeignKey("parking_lots.id"))
    event_type = Column(String)  # 'entry' or 'exit'
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))


class OccupancySnapshot(Base):
    __tablename__ = "occupancy_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    lot_id = Column(Integer, ForeignKey("parking_lots.id"))
    occupied_count = Column(Integer)
    snapshot_time = Column(DateTime, default=datetime.now(timezone.utc))


# Create all tables
Base.metadata.create_all(bind=engine)

# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class ParkingLotCreate(BaseModel):
    name: str
    address: str
    latitude: float
    longitude: float
    total_capacity: int


class ParkingLotResponse(BaseModel):
    id: int
    name: str
    address: str
    latitude: float
    longitude: float
    total_capacity: int
    occupied_count: int
    available_count: int
    status: str  # 'green', 'amber', 'red'
    fill_percentage: float
    last_updated: str

    class Config:
        from_attributes = True


class OccupancyEventRequest(BaseModel):
    lot_id: int
    event_type: str  # 'entry' or 'exit'


class OccupancyUpdate(BaseModel):
    lot_id: int
    occupied_count: int
    timestamp: str


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# OCCUPANCY MANAGER (Core Logic)
# ============================================================================

class OccupancyManager:
    """Manages real-time occupancy state using Redis as cache"""
    
    def __init__(self, redis_conn: redis.Redis, db: Session):
        self.redis = redis_conn
        self.db = db
    
    async def get_lot_occupancy(self, lot_id: int) -> int:
        """Get current occupied count from Redis"""
        key = f"occupancy:lot:{lot_id}"
        occupied = await self.redis.get(key)
        return int(occupied) if occupied else 0
    
    async def set_lot_occupancy(self, lot_id: int, occupied_count: int) -> None:
        """Set occupied count in Redis and log snapshot to DB"""
        key = f"occupancy:lot:{lot_id}"
        await self.redis.set(key, occupied_count)
        
        # Store snapshot in database every update
        snapshot = OccupancySnapshot(lot_id=lot_id, occupied_count=occupied_count)
        self.db.add(snapshot)
        self.db.commit()
        logger.info(f"Lot {lot_id} occupancy updated to {occupied_count}")
    
    async def record_event(self, lot_id: int, event_type: str) -> None:
        """Record entry/exit event and update occupancy"""
        # Get current lot
        lot = self.db.query(ParkingLot).filter(ParkingLot.id == lot_id).first()
        if not lot:
            raise ValueError(f"Lot {lot_id} not found")
        
        # Record event
        event = OccupancyEvent(lot_id=lot_id, event_type=event_type)
        self.db.add(event)
        
        # Update occupancy count
        current_occupied = await self.get_lot_occupancy(lot_id)
        if event_type == "entry":
            new_occupied = min(current_occupied + 1, lot.total_capacity)
        elif event_type == "exit":
            new_occupied = max(current_occupied - 1, 0)
        else:
            raise ValueError(f"Invalid event type: {event_type}")
        
        await self.set_lot_occupancy(lot_id, new_occupied)
        self.db.commit()
    
    async def get_lot_status(self, lot: ParkingLot, occupied_count: int) -> Dict:
        """Calculate lot status based on occupancy"""
        available = lot.total_capacity - occupied_count
        fill_percentage = (occupied_count / lot.total_capacity * 100) if lot.total_capacity > 0 else 0
        
        # Color coding: Green (>30% free), Amber (10-30% free), Red (<10% or full)
        free_percentage = 100 - fill_percentage
        if free_percentage > 30:
            status = "green"
        elif free_percentage >= 10:
            status = "amber"
        else:
            status = "red"
        
        return {
            "occupied_count": occupied_count,
            "available_count": max(available, 0),
            "status": status,
            "fill_percentage": round(fill_percentage, 1),
        }


# ============================================================================
# CONNECTION MANAGER (WebSocket Broadcasting)
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections and broadcasts updates"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown"""
    global redis_client
    
    # Startup
    logger.info("Starting up...")
    redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Redis connected")
    
    # Initialize parking lots in database if empty
    db = SessionLocal()
    if db.query(ParkingLot).count() == 0:
        await initialize_sample_lots(db)
        logger.info("Sample parking lots initialized")
    db.close()
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if redis_client:
        await redis_client.close()


async def initialize_sample_lots(db: Session):
    """Initialize sample parking lots for Manhattan Beach Pier area"""
    lots = [
        ParkingLot(
            name="Manhattan Beach Pier - Lot A",
            address="900 Manhattan Beach Blvd, Manhattan Beach, CA",
            latitude=33.8843,
            longitude=-118.4073,
            total_capacity=150
        ),
        ParkingLot(
            name="Manhattan Beach Pier - Lot B",
            address="1000 Manhattan Beach Blvd, Manhattan Beach, CA",
            latitude=33.8845,
            longitude=-118.4080,
            total_capacity=200
        ),
        ParkingLot(
            name="Manhattan Beach - Parking Garage",
            address="1100 Manhattan Beach Blvd, Manhattan Beach, CA",
            latitude=33.8850,
            longitude=-118.4090,
            total_capacity=300
        ),
        ParkingLot(
            name="Beach Access - Lot C",
            address="500 Manhattan Beach Blvd, Manhattan Beach, CA",
            latitude=33.8835,
            longitude=-118.4060,
            total_capacity=100
        ),
    ]
    for lot in lots:
        db.add(lot)
    db.commit()
    
    # Initialize Redis occupancy for each lot with 0 vehicles
    redis_conn = await redis.from_url(REDIS_URL, decode_responses=True)
    for lot in lots:
        await redis_conn.set(f"occupancy:lot:{lot.id}", 0)
    await redis_conn.close()


# ============================================================================
# API ENDPOINTS
# ============================================================================

app = FastAPI(title="Smart Parking API", version="1.0.0", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/lots", response_model=List[ParkingLotResponse])
async def get_all_lots(db: Session = Depends(get_db)):
    """Get all parking lots with current occupancy"""
    lots = db.query(ParkingLot).all()
    
    result = []
    for lot in lots:
        occupied = await OccupancyManager(redis_client, db).get_lot_occupancy(lot.id)
        status_info = await OccupancyManager(redis_client, db).get_lot_status(lot, occupied)
        
        result.append(ParkingLotResponse(
            id=lot.id,
            name=lot.name,
            address=lot.address,
            latitude=lot.latitude,
            longitude=lot.longitude,
            total_capacity=lot.total_capacity,
            occupied_count=status_info["occupied_count"],
            available_count=status_info["available_count"],
            status=status_info["status"],
            fill_percentage=status_info["fill_percentage"],
            last_updated=datetime.now(timezone.utc).isoformat()
        ))
    
    return result


@app.get("/lots/{lot_id}", response_model=ParkingLotResponse)
async def get_lot_detail(lot_id: int, db: Session = Depends(get_db)):
    """Get single parking lot with detailed info"""
    lot = db.query(ParkingLot).filter(ParkingLot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    manager = OccupancyManager(redis_client, db)
    occupied = await manager.get_lot_occupancy(lot_id)
    status_info = await manager.get_lot_status(lot, occupied)
    
    return ParkingLotResponse(
        id=lot.id,
        name=lot.name,
        address=lot.address,
        latitude=lot.latitude,
        longitude=lot.longitude,
        total_capacity=lot.total_capacity,
        occupied_count=status_info["occupied_count"],
        available_count=status_info["available_count"],
        status=status_info["status"],
        fill_percentage=status_info["fill_percentage"],
        last_updated=datetime.now(timezone.utc).isoformat()
    )


@app.post("/lots", response_model=ParkingLotResponse)
async def create_lot(lot: ParkingLotCreate, db: Session = Depends(get_db)):
    """Create a new parking lot"""
    db_lot = ParkingLot(**lot.dict())
    db.add(db_lot)
    db.commit()
    db.refresh(db_lot)
    
    # Initialize occupancy
    await redis_client.set(f"occupancy:lot:{db_lot.id}", 0)
    
    return ParkingLotResponse(
        id=db_lot.id,
        name=db_lot.name,
        address=db_lot.address,
        latitude=db_lot.latitude,
        longitude=db_lot.longitude,
        total_capacity=db_lot.total_capacity,
        occupied_count=0,
        available_count=db_lot.total_capacity,
        status="green",
        fill_percentage=0.0,
        last_updated=datetime.now(timezone.utc).isoformat()
    )


@app.post("/events")
async def record_occupancy_event(event: OccupancyEventRequest, db: Session = Depends(get_db)):
    """Record entry/exit event from sensors"""
    manager = OccupancyManager(redis_client, db)
    
    try:
        await manager.record_event(event.lot_id, event.event_type)
        
        # Get updated lot info and broadcast
        lot = db.query(ParkingLot).filter(ParkingLot.id == event.lot_id).first()
        occupied = await manager.get_lot_occupancy(event.lot_id)
        status_info = await manager.get_lot_status(lot, occupied)
        
        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "occupancy_update",
            "lot_id": event.lot_id,
            "occupied_count": status_info["occupied_count"],
            "available_count": status_info["available_count"],
            "status": status_info["status"],
            "fill_percentage": status_info["fill_percentage"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {"status": "success", "lot_id": event.lot_id, "event_type": event.event_type}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/occupancy/{lot_id}")
async def set_occupancy(lot_id: int, occupied_count: int = Query(...), db: Session = Depends(get_db)):
    """Manually set occupancy for a lot (useful for sync/corrections)"""
    lot = db.query(ParkingLot).filter(ParkingLot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    
    if occupied_count < 0 or occupied_count > lot.total_capacity:
        raise HTTPException(status_code=400, detail="Invalid occupancy count")
    
    manager = OccupancyManager(redis_client, db)
    await manager.set_lot_occupancy(lot_id, occupied_count)
    status_info = await manager.get_lot_status(lot, occupied_count)
    
    # Broadcast update
    await manager.broadcast({
        "type": "occupancy_update",
        "lot_id": lot_id,
        "occupied_count": status_info["occupied_count"],
        "available_count": status_info["available_count"],
        "status": status_info["status"],
        "fill_percentage": status_info["fill_percentage"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "success", "lot_id": lot_id, "occupied_count": occupied_count}


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@app.websocket("/ws/lots/live")
async def websocket_lot_updates(websocket: WebSocket):
    """WebSocket endpoint for real-time occupancy updates"""
    await manager.connect(websocket)
    logger.info("Client connected to WebSocket")
    
    try:
        # Send initial state
        db = SessionLocal()
        lots = db.query(ParkingLot).all()
        manager_inst = OccupancyManager(redis_client, db)
        
        initial_state = []
        for lot in lots:
            occupied = await manager_inst.get_lot_occupancy(lot.id)
            status_info = await manager_inst.get_lot_status(lot, occupied)
            initial_state.append({
                "id": lot.id,
                "name": lot.name,
                "latitude": lot.latitude,
                "longitude": lot.longitude,
                "total_capacity": lot.total_capacity,
                "occupied_count": status_info["occupied_count"],
                "available_count": status_info["available_count"],
                "status": status_info["status"],
                "fill_percentage": status_info["fill_percentage"],
            })
        db.close()
        
        await websocket.send_json({
            "type": "initial_state",
            "lots": initial_state,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received: {data}")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
