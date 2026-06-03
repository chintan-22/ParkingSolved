# Sensor Integration Guide

## Overview

This guide covers how to integrate various parking lot sensors with the ParkingSolved system. The system supports:

1. **Ultrasonic/Infrared Distance Sensors** - For space occupancy detection
2. **License Plate Recognition (LPR) Cameras** - For entry/exit counting
3. **Computer Vision Occupancy Estimation** - From existing CCTV feeds
4. **Manual Sensor Simulation** - For testing without hardware

---

## 1. Ultrasonic Distance Sensors

### Hardware Requirements

- **Sensor**: HC-SR04 Ultrasonic Sensor or similar
- **Microcontroller**: Arduino, Raspberry Pi, or ESP32
- **Connection**: USB serial or GPIO
- **Cost**: $5-15 per sensor

### Wiring Diagram (Raspberry Pi)

```
HC-SR04 Sensor
├── VCC → Pin 2 (5V)
├── GND → Pin 6 (Ground)
├── TRIG → GPIO 17 (Pin 11)
└── ECHO → GPIO 27 (Pin 13)
```

### Python Integration Script

```python
# sensor_integration/ultrasonic_sensor.py

import RPi.GPIO as GPIO
import time
import json
import paho.mqtt.client as mqtt
from datetime import datetime

# GPIO Setup
GPIO.setmode(GPIO.BCM)
TRIG_PIN = 17
ECHO_PIN = 27
GPIO.setup(TRIG_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)

# MQTT Setup
mqtt_client = mqtt.Client()
mqtt_client.connect("mqtt_broker_ip", 1883)
mqtt_client.loop_start()

LOT_ID = 1
SENSOR_ID = "sensor_entry_1"

def measure_distance():
    """Measure distance using ultrasonic sensor"""
    
    # Send pulse
    GPIO.output(TRIG_PIN, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, GPIO.LOW)
    
    # Measure echo time
    start_time = time.time()
    while GPIO.input(ECHO_PIN) == 0:
        start_time = time.time()
    
    while GPIO.input(ECHO_PIN) == 1:
        end_time = time.time()
    
    # Calculate distance
    pulse_duration = end_time - start_time
    distance_cm = pulse_duration * 17150  # Speed of sound
    
    return distance_cm

def detect_vehicle(distance_cm, threshold_cm=100):
    """
    Detect vehicle based on distance
    Returns True if vehicle detected (distance < threshold)
    """
    return distance_cm < threshold_cm

def main():
    """Main sensor reading loop"""
    
    previous_state = False
    debounce_count = 0
    DEBOUNCE_THRESHOLD = 5  # Readings to confirm state change
    
    try:
        while True:
            distance = measure_distance()
            current_state = detect_vehicle(distance)
            
            # Debounce readings
            if current_state != previous_state:
                debounce_count += 1
                if debounce_count > DEBOUNCE_THRESHOLD:
                    # State confirmed - publish event
                    event_type = "entry" if current_state else "exit"
                    
                    payload = {
                        "sensor_id": SENSOR_ID,
                        "distance_cm": round(distance, 1),
                        "event_type": event_type,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    topic = f"parking/lot/{LOT_ID}/ultrasonic"
                    mqtt_client.publish(topic, json.dumps(payload))
                    
                    print(f"[{datetime.now()}] {event_type.upper()} detected at {distance:.1f}cm")
                    
                    previous_state = current_state
                    debounce_count = 0
            else:
                debounce_count = 0
            
            time.sleep(0.5)  # 500ms reading interval
    
    except KeyboardInterrupt:
        print("Shutting down...")
        GPIO.cleanup()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()
```

### Installation Steps (Raspberry Pi)

```bash
# Install required libraries
sudo apt install python3-pip python3-rpi.gpio
pip3 install paho-mqtt

# Copy sensor script
cp sensor_integration/ultrasonic_sensor.py /home/pi/

# Create systemd service
sudo nano /etc/systemd/system/parking-sensor.service

# Add content:
[Unit]
Description=Parking Lot Ultrasonic Sensor
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/ultrasonic_sensor.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target

# Enable and start service
sudo systemctl enable parking-sensor
sudo systemctl start parking-sensor

# View logs
sudo journalctl -f -u parking-sensor
```

---

## 2. License Plate Recognition (LPR)

### Hardware Requirements

- **Camera**: IP Camera with RTSP stream (Hikvision, Dahua, etc.)
- **Compute**: GPU-enabled device (NVIDIA Jetson, RTX GPU, etc.)
- **Cost**: $200-1000+ for camera and processing

### Prerequisites

```bash
# Install YOLO and OpenCV
pip install opencv-python ultralytics torch torchvision

# Download YOLOv8 models
from ultralytics import YOLO
model = YOLO('yolov8m.pt')  # Auto-downloads on first use
```

### LPR Integration Script

```python
# sensor_integration/lpr_camera.py

import cv2
import json
import paho.mqtt.client as mqtt
from datetime import datetime
from ultralytics import YOLO
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CAMERA_RTSP = "rtsp://admin:password@192.168.1.100:554/stream"
MQTT_BROKER = "mqtt_broker_ip"
LOT_ID = 1
CAMERA_LOCATION = "entry"  # 'entry' or 'exit'

# Initialize YOLO
model = YOLO('yolov8m.pt')

# MQTT Setup
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, 1883)
mqtt_client.loop_start()

# Tracking
tracked_plates = {}  # plate -> timestamp

def extract_license_plate(image):
    """
    Extract license plate from image using YOLO
    Returns license plate text or None
    """
    try:
        # Run YOLO detection
        results = model(image)
        
        # Extract detections with high confidence
        for result in results:
            for box in result.boxes:
                confidence = box.conf[0].item()
                
                if confidence > 0.7 and "plate" in result.names[int(box.cls)]:
                    # Crop plate region
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    plate_region = image[y1:y2, x1:x2]
                    
                    # Use OCR (could use EasyOCR or Tesseract)
                    # For this example, we'll use a placeholder
                    plate_text = ocr_plate(plate_region)
                    
                    return plate_text
    except Exception as e:
        logger.error(f"Error extracting plate: {e}")
    
    return None

def ocr_plate(image):
    """
    Extract text from license plate image
    Using EasyOCR for production
    """
    try:
        import easyocr
        reader = easyocr.Reader(['en'])
        results = reader.readtext(image)
        text = ''.join([result[1] for result in results])
        return text.upper()
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return None

def main():
    """Main camera processing loop"""
    
    cap = cv2.VideoCapture(CAMERA_RTSP)
    
    if not cap.isOpened():
        logger.error(f"Failed to open camera: {CAMERA_RTSP}")
        return
    
    logger.info(f"Connected to camera: {CAMERA_RTSP}")
    
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                logger.error("Failed to read frame")
                break
            
            frame_count += 1
            
            # Process every 5th frame for performance
            if frame_count % 5 == 0:
                # Resize for faster processing
                resized = cv2.resize(frame, (640, 480))
                
                # Detect vehicles
                results = model(resized, conf=0.5)
                
                # Check for license plates
                for result in results:
                    for box in result.boxes:
                        class_id = int(box.cls)
                        
                        # Check if detected object is a car
                        if model.names[class_id].lower() == 'car':
                            confidence = box.conf[0].item()
                            
                            if confidence > 0.7:
                                # Extract plate from detected vehicle
                                x1, y1, x2, y2 = map(int, box.xyxy[0])
                                vehicle_region = resized[y1:y2, x1:x2]
                                
                                plate_text = extract_license_plate(vehicle_region)
                                
                                if plate_text and len(plate_text) >= 3:
                                    # Check if plate is new or stale
                                    current_time = datetime.now()
                                    
                                    if plate_text not in tracked_plates:
                                        # New plate detected
                                        tracked_plates[plate_text] = current_time
                                        
                                        # Publish event
                                        topic_suffix = "lpr_entry" if CAMERA_LOCATION == "entry" else "lpr_exit"
                                        payload = {
                                            "camera_id": f"cam_{CAMERA_LOCATION}_1",
                                            "license_plate": plate_text,
                                            "confidence": round(float(confidence), 2),
                                            "timestamp": current_time.isoformat()
                                        }
                                        
                                        topic = f"parking/lot/{LOT_ID}/{topic_suffix}"
                                        mqtt_client.publish(topic, json.dumps(payload))
                                        
                                        logger.info(f"[{current_time}] {CAMERA_LOCATION.upper()}: {plate_text}")
                                    else:
                                        # Update timestamp if still visible
                                        tracked_plates[plate_text] = current_time
            
            # Clean up old tracked plates (older than 30 seconds)
            current_time = datetime.now()
            stale_plates = [plate for plate, ts in tracked_plates.items() 
                           if (current_time - ts).seconds > 30]
            for plate in stale_plates:
                del tracked_plates[plate]
            
            # Display frame (optional, for debugging)
            # cv2.imshow("LPR Camera", frame)
            # if cv2.waitKey(1) & 0xFF == ord('q'):
            #     break
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()
```

### Installation (NVIDIA Jetson)

```bash
# Install CUDA-enabled libraries
sudo apt update
sudo apt install python3-pip cuda-toolkit-11-4

# Install YOLOv8 with GPU support
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip3 install ultralytics opencv-python easyocr

# Test GPU
python3 -c "import torch; print(torch.cuda.is_available())"
```

---

## 3. Computer Vision from Existing CCTV

### Occupancy Estimation Script

```python
# sensor_integration/occupancy_estimator.py

import cv2
import numpy as np
from ultralytics import YOLO
import json
import paho.mqtt.client as mqtt
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CAMERA_RTSP = "rtsp://admin:password@camera_ip:554/stream"
MQTT_BROKER = "mqtt_broker_ip"
LOT_ID = 1

# Initialize YOLO for vehicle detection
model = YOLO('yolov8m.pt')

# MQTT Setup
mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, 1883)
mqtt_client.loop_start()

def estimate_occupancy(frame):
    """
    Estimate parking occupancy from camera frame
    Returns: occupied_count, total_capacity, confidence
    """
    try:
        # Detect vehicles in frame
        results = model(frame, conf=0.5)
        
        vehicle_count = 0
        total_detections = 0
        
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls)
                class_name = model.names[class_id].lower()
                
                # Count vehicles (cars, trucks, etc.)
                if class_name in ['car', 'truck', 'bus']:
                    confidence = box.conf[0].item()
                    if confidence > 0.6:
                        vehicle_count += 1
                
                total_detections += 1
        
        # Calculate confidence based on detection clarity
        # (Higher when there are clear detections)
        confidence = min(0.5 + (vehicle_count / 100), 0.95)
        
        return vehicle_count, 150, confidence  # Assuming 150 total spaces
    
    except Exception as e:
        logger.error(f"Occupancy estimation error: {e}")
        return None, None, 0

def main():
    """Main occupancy monitoring loop"""
    
    cap = cv2.VideoCapture(CAMERA_RTSP)
    
    if not cap.isOpened():
        logger.error(f"Failed to connect to camera: {CAMERA_RTSP}")
        return
    
    logger.info(f"Connected to camera: {CAMERA_RTSP}")
    
    frame_count = 0
    last_update_time = datetime.now()
    UPDATE_INTERVAL_SECONDS = 60  # Update every 60 seconds
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                logger.error("Failed to read frame from camera")
                break
            
            frame_count += 1
            current_time = datetime.now()
            
            # Process every 30 frames for performance
            if frame_count % 30 == 0:
                # Resize for faster processing
                small_frame = cv2.resize(frame, (416, 416))
                
                # Estimate occupancy
                occupied, total, confidence = estimate_occupancy(small_frame)
                
                # Publish update every UPDATE_INTERVAL_SECONDS
                if (current_time - last_update_time).seconds >= UPDATE_INTERVAL_SECONDS:
                    if occupied is not None:
                        payload = {
                            "occupied_count": occupied,
                            "total_capacity": total,
                            "confidence": round(float(confidence), 2),
                            "timestamp": current_time.isoformat()
                        }
                        
                        topic = f"parking/lot/{LOT_ID}/occupancy_estimate"
                        mqtt_client.publish(topic, json.dumps(payload))
                        
                        logger.info(f"[{current_time}] Occupancy: {occupied}/{total} "
                                  f"({confidence*100:.0f}% confidence)")
                        
                        last_update_time = current_time
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        cap.release()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()
```

---

## 4. Testing Sensor Integration

### MQTT Test Publisher

```bash
# Publish test ultrasonic reading
mosquitto_pub -h localhost -t "parking/lot/1/ultrasonic" \
  -m '{
    "sensor_id": "test_sensor",
    "distance_cm": 80,
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }'

# Publish test LPR entry
mosquitto_pub -h localhost -t "parking/lot/1/lpr_entry" \
  -m '{
    "camera_id": "test_cam",
    "license_plate": "ABC123",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }'

# Publish occupancy estimate
mosquitto_pub -h localhost -t "parking/lot/1/occupancy_estimate" \
  -m '{
    "occupied_count": 45,
    "total_capacity": 150,
    "confidence": 0.92,
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }'
```

### Monitor MQTT Topics

```bash
# Subscribe to all parking messages
mosquitto_sub -h localhost -t "parking/#" -v

# Subscribe to specific lot
mosquitto_sub -h localhost -t "parking/lot/1/#" -v
```

---

## 5. Sensor Calibration

### Distance Threshold Calibration (Ultrasonic)

```python
# sensor_integration/calibrate_distance.py

import RPi.GPIO as GPIO
import time
import statistics

TRIG_PIN = 17
ECHO_PIN = 27

GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG_PIN, GPIO.OUT)
GPIO.setup(ECHO_PIN, GPIO.IN)

def measure_distance():
    GPIO.output(TRIG_PIN, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIG_PIN, GPIO.LOW)
    
    start_time = time.time()
    while GPIO.input(ECHO_PIN) == 0:
        start_time = time.time()
    
    while GPIO.input(ECHO_PIN) == 1:
        end_time = time.time()
    
    return (end_time - start_time) * 17150

try:
    print("Calibration: Empty space")
    print("Keep space clear for 10 seconds...")
    time.sleep(3)
    
    empty_readings = [measure_distance() for _ in range(20)]
    empty_avg = statistics.mean(empty_readings)
    empty_std = statistics.stdev(empty_readings)
    
    print(f"Empty: {empty_avg:.1f}cm (±{empty_std:.1f}cm)")
    
    print("\nCalibration: Vehicle present")
    print("Place vehicle and press Enter...")
    input()
    
    occupied_readings = [measure_distance() for _ in range(20)]
    occupied_avg = statistics.mean(occupied_readings)
    occupied_std = statistics.stdev(occupied_readings)
    
    print(f"Occupied: {occupied_avg:.1f}cm (±{occupied_std:.1f}cm)")
    
    # Recommend threshold
    threshold = (empty_avg + occupied_avg) / 2
    print(f"\nRecommended threshold: {threshold:.0f}cm")
    
finally:
    GPIO.cleanup()
```

---

## 6. Data Validation & Error Handling

### Sensor Data Validation

```python
# sensor_integration/data_validator.py

from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SensorDataValidator:
    """Validates sensor data before sending to API"""
    
    def __init__(self, lot_capacity):
        self.lot_capacity = lot_capacity
        self.last_event_time = None
        self.last_occupancy = 0
    
    def validate_occupancy_event(self, event_type, timestamp=None):
        """
        Validate entry/exit event
        Returns: (is_valid, reason)
        """
        if event_type not in ['entry', 'exit']:
            return False, f"Invalid event type: {event_type}"
        
        # Check timestamp is recent
        if timestamp:
            age = (datetime.now() - datetime.fromisoformat(timestamp)).seconds
            if age > 300:  # Older than 5 minutes
                return False, "Event timestamp too old"
        
        # Check minimum time between events (debouncing)
        if self.last_event_time:
            time_since_last = (datetime.now() - self.last_event_time).seconds
            if time_since_last < 2:  # Less than 2 seconds
                return False, "Events too frequent (debounce)"
        
        self.last_event_time = datetime.now()
        return True, "OK"
    
    def validate_occupancy_count(self, count, total=None):
        """
        Validate occupancy count
        Returns: (is_valid, reason, corrected_count)
        """
        total = total or self.lot_capacity
        
        if count < 0:
            return False, "Negative occupancy", 0
        
        if count > total:
            return False, "Occupancy exceeds capacity", total
        
        return True, "OK", count
    
    def validate_occupancy_estimate(self, count, total, confidence):
        """
        Validate occupancy estimate from computer vision
        Returns: (is_valid, reason)
        """
        if confidence < 0.6:
            return False, f"Low confidence: {confidence}"
        
        if count < 0 or count > total:
            return False, "Invalid count range"
        
        return True, "OK"

# Usage
validator = SensorDataValidator(lot_capacity=150)

# Validate event
is_valid, reason = validator.validate_occupancy_event("entry")
if not is_valid:
    logger.warning(f"Event validation failed: {reason}")

# Validate count
is_valid, reason, corrected = validator.validate_occupancy_count(160, 150)
if not is_valid:
    logger.error(f"Occupancy invalid: {reason}, using {corrected}")
```

---

## Troubleshooting

### Ultrasonic Sensor Issues

```bash
# Test GPIO pins
gpio readall

# Test with simple Python script
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.HIGH)
print('GPIO 17 is HIGH')
GPIO.cleanup()
"
```

### LPR Camera Connection Issues

```bash
# Test RTSP stream
ffplay rtsp://admin:password@192.168.1.100:554/stream

# Check network connectivity
ping 192.168.1.100
nmap -p 554 192.168.1.100
```

### MQTT Connectivity

```bash
# Test MQTT connection
mosquitto_sub -h mqtt_broker_ip -t "test" -u parking_user -P parking_pass

# Check mosquitto broker logs
docker logs parking_mqtt
```

---

For more help, refer to the main README.md or contact support@parkingsolved.io
