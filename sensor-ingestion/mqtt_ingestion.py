"""
MQTT Sensor Ingestion Service
Subscribes to MQTT topics from parking lot sensors and forwards events to the backend API.
Supports both ultrasonic sensors and LPR (License Plate Recognition) camera feeds.
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
import httpx
from typing import Dict, Optional
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "parking_user")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "parking_pass")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# MQTT topic structure: parking/lot/{lot_id}/{sensor_type}
# sensor_type: ultrasonic, lpr_entry, lpr_exit, occupancy_estimate
MQTT_TOPICS = [
    "parking/lot/+/ultrasonic",
    "parking/lot/+/lpr_entry",
    "parking/lot/+/lpr_exit",
    "parking/lot/+/occupancy_estimate",
]

class SensorIngestionService:
    """Ingests sensor data from MQTT and forwards to backend API"""
    
    def __init__(self, broker: str, port: int, api_url: str):
        self.broker = broker
        self.port = port
        self.api_url = api_url
        if hasattr(mqtt, "CallbackAPIVersion"):
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        else:
            self.client = mqtt.Client()
        self.http_client = httpx.AsyncClient()
        
        # Set up callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
    
    def on_connect(self, client, userdata, flags, rc):
        """Called when client connects to broker"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
            # Subscribe to all sensor topics
            for topic in MQTT_TOPICS:
                client.subscribe(topic)
                logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"Failed to connect, return code {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        """Called when client disconnects from broker"""
        if rc != 0:
            logger.warning(f"Unexpected disconnection. Return code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def on_subscribe(self, client, userdata, mid, granted_qos):
        """Called when subscription is acknowledged"""
        logger.debug(f"Subscription acknowledged with QoS: {granted_qos}")
    
    def on_message(self, client, userdata, msg):
        """Called when a message is received on subscribed topic"""
        try:
            payload = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split("/")
            
            if len(topic_parts) < 4:
                logger.error(f"Invalid topic format: {msg.topic}")
                return
            
            lot_id = int(topic_parts[2])
            sensor_type = topic_parts[3]
            
            logger.info(f"Received message on {msg.topic}: {payload}")
            
            # Route to appropriate handler
            if sensor_type == "ultrasonic":
                asyncio.run(self.handle_ultrasonic(lot_id, payload))
            elif sensor_type in ["lpr_entry", "lpr_exit"]:
                asyncio.run(self.handle_lpr_event(lot_id, sensor_type, payload))
            elif sensor_type == "occupancy_estimate":
                asyncio.run(self.handle_occupancy_estimate(lot_id, payload))
        
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from topic {msg.topic}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def handle_ultrasonic(self, lot_id: int, payload: Dict):
        """
        Handle ultrasonic sensor data
        Expected payload: {"sensor_id": "s1", "distance_cm": 120, "timestamp": "2024-06-02T10:30:00Z"}
        Ultrasonic sensors can be used in pairs to detect entry/exit
        """
        try:
            sensor_id = payload.get("sensor_id")
            distance_cm = payload.get("distance_cm")
            
            logger.info(f"Ultrasonic sensor {sensor_id} (Lot {lot_id}): {distance_cm}cm")
            
            # In production, you'd implement logic to distinguish entry/exit
            # For now, this is logged for future processing
        except Exception as e:
            logger.error(f"Error handling ultrasonic data: {e}")
    
    async def handle_lpr_event(self, lot_id: int, event_type: str, payload: Dict):
        """
        Handle LPR (License Plate Recognition) camera events
        Expected payload: {"camera_id": "cam1", "license_plate": "ABC123", "timestamp": "2024-06-02T10:30:00Z"}
        """
        try:
            camera_id = payload.get("camera_id")
            license_plate = payload.get("license_plate")
            timestamp = payload.get("timestamp", datetime.now(timezone.utc).isoformat())
            
            logger.info(f"LPR event on Lot {lot_id} ({camera_id}): {event_type} - {license_plate}")
            
            # Determine entry/exit from topic
            mqtt_event_type = "entry" if event_type == "lpr_entry" else "exit"
            
            # Forward to backend API
            await self.record_event(lot_id, mqtt_event_type)
        
        except Exception as e:
            logger.error(f"Error handling LPR event: {e}")
    
    async def handle_occupancy_estimate(self, lot_id: int, payload: Dict):
        """
        Handle occupancy estimates from computer vision or other sources
        Expected payload: {"occupied_count": 45, "total_capacity": 150, "confidence": 0.95, "timestamp": "2024-06-02T10:30:00Z"}
        """
        try:
            occupied_count = payload.get("occupied_count")
            confidence = payload.get("confidence", 1.0)
            
            logger.info(f"Occupancy estimate for Lot {lot_id}: {occupied_count} (confidence: {confidence})")
            
            # If high confidence, update the backend directly
            if confidence >= 0.85:
                await self.set_occupancy(lot_id, occupied_count)
            else:
                logger.warning(f"Low confidence estimate ({confidence}) for Lot {lot_id}, ignoring")
        
        except Exception as e:
            logger.error(f"Error handling occupancy estimate: {e}")
    
    async def record_event(self, lot_id: int, event_type: str) -> bool:
        """Send event to backend API"""
        try:
            response = await self.http_client.post(
                f"{self.api_url}/events",
                json={"lot_id": lot_id, "event_type": event_type},
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"Recorded {event_type} event for Lot {lot_id}")
                return True
            else:
                logger.error(f"Backend error: {response.status_code} - {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to record event: {e}")
            return False
    
    async def set_occupancy(self, lot_id: int, occupied_count: int) -> bool:
        """Set occupancy count in backend API"""
        try:
            response = await self.http_client.post(
                f"{self.api_url}/occupancy/{lot_id}",
                params={"occupied_count": occupied_count},
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"Set occupancy for Lot {lot_id} to {occupied_count}")
                return True
            else:
                logger.error(f"Backend error: {response.status_code} - {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to set occupancy: {e}")
            return False
    
    def start(self):
        """Connect to MQTT broker and start listening"""
        logger.info("Starting MQTT ingestion service...")

        # Set username/password if provided
        if MQTT_USER and MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

        while True:
            try:
                self.client.connect(self.broker, self.port, keepalive=60)
                self.client.loop_forever()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Failed to start ingestion service: {e}")
                logger.info("Retrying MQTT connection in 5 seconds...")
                time.sleep(5)
    
    async def stop(self):
        """Stop the service"""
        logger.info("Stopping ingestion service...")
        await self.http_client.aclose()
        self.client.disconnect()


async def main():
    """Main entry point"""
    service = SensorIngestionService(MQTT_BROKER, MQTT_PORT, API_BASE_URL)
    
    try:
        service.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await service.stop()


if __name__ == "__main__":
    service = SensorIngestionService(MQTT_BROKER, MQTT_PORT, API_BASE_URL)
    service.start()
