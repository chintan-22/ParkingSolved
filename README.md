# ParkingSolved - Smart Parking Availability System

A real-time parking availability overlay for Google Maps focused on pier/beach parking lots. Starting with **Manhattan Beach Pier, CA**, this system displays live parking data with color-coded availability status on an interactive map.

![Status: Active Development](https://img.shields.io/badge/status-active%20development-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

## 🎯 Features

### Core Functionality
- **Real-Time Occupancy Tracking**: Live updates via WebSocket for instant parking availability
- **Color-Coded Status**: Green (>30% free), Amber (10-30% free), Red (<10% or full)
- **Interactive Google Maps Integration**: Custom overlay layer with parking lot markers
- **Mobile-Friendly UI**: Responsive design with bottom sheet panel on mobile
- **Historical Analytics**: Track occupancy patterns by hour, day, and location

### Data Collection
- **Multiple Sensor Support**:
  - Ultrasonic sensors at entry/exit lanes
  - License Plate Recognition (LPR) cameras
  - Computer vision occupancy estimation
- **MQTT Message Broker**: Real-time event streaming
- **Event Logging**: Complete audit trail of entry/exit events

### Backend
- **FastAPI REST API**: Modern async Python framework
- **Redis Caching**: High-performance in-memory occupancy store
- **PostgreSQL Database**: Persistent storage for events and snapshots
- **WebSocket Streaming**: Real-time updates to frontend clients
- **Horizontal Scalability**: Designed for multi-location deployment

### Admin Tools
- **Occupancy Simulation**: Time-of-day realistic patterns (weekday/weekend peaks)
- **Manual Override**: Correct sensor errors via admin API
- **MQTT Ingestion Service**: Converts raw sensor data to API events

## 📋 Project Structure

```
ParkingSolved/
├── backend/                    # FastAPI application
│   ├── main.py                # Core API logic
│   ├── requirements.txt        # Python dependencies
│   └── Dockerfile             # Container image
├── frontend/                   # Google Maps web interface
│   └── index.html             # Single-page application
├── simulator/                  # Test data generator
│   ├── simulator.py           # Realistic occupancy patterns
│   ├── requirements.txt        # Simulator dependencies
│   └── Dockerfile             # Container image
├── sensor-ingestion/           # MQTT event processor
│   ├── mqtt_ingestion.py      # MQTT→API gateway
│   ├── requirements.txt        # Sensor dependencies
│   └── Dockerfile             # Container image
├── docker-compose.yml         # Multi-container orchestration
├── init-db.sql               # Database schema
├── nginx.conf                # Web server configuration
└── README.md                 # This file
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose (macOS: Install via Docker Desktop)
- Python 3.11+ (for local development)
- Google Maps API Key (from [Google Cloud Console](https://console.cloud.google.com))

### 1. Clone & Setup

```bash
cd /Users/chintanshah/Documents/ParkingSolved

# Copy environment template (optional)
cp .env.example .env
```

### 2. Configure Google Maps API Key

Edit `frontend/index.html` and replace:
```javascript
GOOGLE_MAPS_API_KEY: 'YOUR_GOOGLE_MAPS_API_KEY'
```

Get your API key from: https://console.cloud.google.com/apis/library/maps-backend.googleapis.com

### 3. Start All Services with Docker Compose

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** (port 5432)
- **Redis** (port 6379)
- **MQTT Broker** (port 1883)
- **FastAPI** (port 8000)
- **Simulator** (generating test data)
- **MQTT Ingestion** (processing sensor events)
- **Nginx Web Server** (port 3000)

### 4. Access the Application

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/health

### 5. Verify Services

```bash
# Check Docker containers
docker-compose ps

# View logs
docker-compose logs -f api simulator

# Test API
curl http://localhost:8000/lots
```

## 🏗️ Architecture

### Data Flow

```
Sensors (USB/MQTT)
      ↓
MQTT Broker (HiveMQ)
      ↓
Ingestion Service (MQTT→HTTP)
      ↓
FastAPI Backend
    ↙   ↘
Redis  PostgreSQL
    ↓
WebSocket Connection
    ↓
Google Maps Frontend
```

### System Components

#### 1. **Backend API** (`backend/main.py`)

FastAPI application with:
- **REST Endpoints**:
  - `GET /lots` - List all lots with occupancy
  - `GET /lots/{id}` - Detailed lot information
  - `POST /lots` - Create new lot
  - `POST /events` - Record entry/exit events
  - `POST /occupancy/{id}` - Set occupancy manually

- **WebSocket Endpoint**:
  - `WS /ws/lots/live` - Real-time updates stream

- **Database Models**:
  - `parking_lots` - Location, capacity, coordinates
  - `occupancy_events` - Entry/exit audit trail
  - `occupancy_snapshots` - Periodic state snapshots

#### 2. **Frontend** (`frontend/index.html`)

Vanilla JavaScript Google Maps integration:
- Custom SVG markers with color-coded status
- Info windows with occupancy bar charts
- Sidebar for lot listing (desktop)
- Bottom sheet for mobile
- Real-time WebSocket updates
- Directions integration with Google Maps

#### 3. **Simulator** (`simulator/simulator.py`)

Generates realistic occupancy patterns:
- **Weekday Pattern**: 
  - 11am-2pm: 85% peak
  - Off-peak: 10-50%
- **Weekend Pattern**:
  - 10am-4pm: 90% peak
  - Morning/evening: 40-70%
- Random event injection for natural variance

#### 4. **MQTT Ingestion** (`sensor-ingestion/mqtt_ingestion.py`)

Subscribes to sensor topics and routes events:
- `parking/lot/{lot_id}/ultrasonic` - Distance sensors
- `parking/lot/{lot_id}/lpr_entry` - License plate entry
- `parking/lot/{lot_id}/lpr_exit` - License plate exit
- `parking/lot/{lot_id}/occupancy_estimate` - Vision estimates

## 📡 API Reference

### Get All Lots

```bash
curl -X GET http://localhost:8000/lots
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Manhattan Beach Pier - Lot A",
    "address": "900 Manhattan Beach Blvd, Manhattan Beach, CA",
    "latitude": 33.8843,
    "longitude": -118.4073,
    "total_capacity": 150,
    "occupied_count": 120,
    "available_count": 30,
    "status": "amber",
    "fill_percentage": 80.0,
    "last_updated": "2024-06-02T10:30:00Z"
  }
]
```

### Record Event

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "lot_id": 1,
    "event_type": "entry"
  }'
```

### Set Occupancy

```bash
curl -X POST http://localhost:8000/occupancy/1?occupied_count=45
```

### WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/lots/live');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'initial_state') {
    console.log('Initial lots state:', data.lots);
  } else if (data.type === 'occupancy_update') {
    console.log(`Lot ${data.lot_id}: ${data.available_count} spots available`);
  }
};
```

## 🔧 Development

### Local Setup (without Docker)

```bash
# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt
pip install -r simulator/requirements.txt
pip install -r sensor-ingestion/requirements.txt

# Start services locally
postgres # Start PostgreSQL service
redis-server # Start Redis
# Then run each service in separate terminals

# Terminal 1: Backend API
cd backend && python -m uvicorn main:app --reload

# Terminal 2: Simulator
cd simulator && python simulator.py

# Terminal 3: MQTT Ingestion
cd sensor-ingestion && python mqtt_ingestion.py

# Terminal 4: Frontend (simple HTTP server)
cd frontend && python -m http.server 3000
```

### Running Tests

```bash
# API health check
curl http://localhost:8000/health

# Fetch lots
curl http://localhost:8000/lots

# Simulate an entry event
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"lot_id": 1, "event_type": "entry"}'

# WebSocket test (using websocat)
websocat ws://localhost:8000/ws/lots/live
```

## 📊 Database Schema

### parking_lots
```sql
CREATE TABLE parking_lots (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  address VARCHAR(500) NOT NULL,
  latitude DECIMAL(10, 8) NOT NULL,
  longitude DECIMAL(11, 8) NOT NULL,
  total_capacity INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### occupancy_events
```sql
CREATE TABLE occupancy_events (
  id SERIAL PRIMARY KEY,
  lot_id INTEGER NOT NULL REFERENCES parking_lots(id),
  event_type VARCHAR(20) CHECK (event_type IN ('entry', 'exit')),
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### occupancy_snapshots
```sql
CREATE TABLE occupancy_snapshots (
  id SERIAL PRIMARY KEY,
  lot_id INTEGER NOT NULL REFERENCES parking_lots(id),
  occupied_count INTEGER NOT NULL,
  snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🌐 Deploying to Production

### 1. Environment Configuration

Create `.env` file:
```env
# Database
DATABASE_URL=postgresql://user:password@db.example.com:5432/parking
REDIS_URL=redis://redis.example.com:6379

# MQTT
MQTT_BROKER=mqtt.example.com
MQTT_PORT=8883
MQTT_USER=your_mqtt_user
MQTT_PASSWORD=your_mqtt_password

# API
API_HOST=0.0.0.0
API_PORT=8000

# Google Maps
GOOGLE_MAPS_API_KEY=your_api_key_here

# Google Places API (optional, for native integration)
GOOGLE_PLACES_API_KEY=your_places_api_key
```

### 2. Deploy with Docker Compose

On your production server:

```bash
# Copy files to server
scp -r ParkingSolved/ user@server:/home/parking/

# SSH into server
ssh user@server

# Navigate to project
cd /home/parking/ParkingSolved

# Start services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f
```

### 3. Set Up Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name parking.example.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name parking.example.com;
    
    ssl_certificate /etc/letsencrypt/live/parking.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/parking.example.com/privkey.pem;
    
    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
    }
    
    # API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_set_header Host $host;
    }
    
    # WebSocket
    location /ws/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 4. Enable HTTPS with Let's Encrypt

```bash
sudo certbot certonly --standalone -d parking.example.com
```

## 🔌 Integrating Real Sensors

### USB Ultrasonic Sensors

```python
import serial
import json
import paho.mqtt.client as mqtt

# Connect to sensor
sensor = serial.Serial('/dev/ttyUSB0', 9600)

# Create MQTT client
client = mqtt.Client()
client.connect('mqtt_broker', 1883)

while True:
    distance = sensor.readline().decode().strip()
    
    # Send to MQTT broker
    payload = {
        'sensor_id': 'sensor_1',
        'distance_cm': float(distance),
        'timestamp': datetime.now().isoformat()
    }
    client.publish('parking/lot/1/ultrasonic', json.dumps(payload))
```

### LPR Camera Integration (YOLO + OpenCV)

```python
import cv2
import torch
from ultralytics import YOLO
import paho.mqtt.client as mqtt
import json

# Load YOLO model for license plate detection
model = YOLO('yolov8m.pt')
plate_detector = torch.hub.load('ultralytics/yolov8', 'custom', 'license_plate.pt')

# MQTT client
client = mqtt.Client()
client.connect('mqtt_broker', 1883)

# Connect to camera
cap = cv2.VideoCapture('rtsp://camera_ip:554/stream')

while True:
    ret, frame = cap.read()
    
    # Detect vehicles
    results = model(frame)
    
    # Extract license plates
    for detection in results[0].boxes:
        crop = frame[int(detection.xyxy[0][1]):int(detection.xyxy[0][3]),
                     int(detection.xyxy[0][0]):int(detection.xyxy[0][2])]
        
        plate_results = plate_detector(crop)
        plate_text = extract_plate_text(plate_results)
        
        # Send to MQTT
        payload = {
            'camera_id': 'cam_entry_1',
            'license_plate': plate_text,
            'timestamp': datetime.now().isoformat()
        }
        client.publish('parking/lot/1/lpr_entry', json.dumps(payload))
```

## 📈 Scaling for Multiple Locations

### 1. Add New Parking Lot

```bash
curl -X POST http://localhost:8000/lots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Redondo Beach Pier - Lot A",
    "address": "1800 Harbor Drive, Redondo Beach, CA",
    "latitude": 33.8353,
    "longitude": -118.3938,
    "total_capacity": 250
  }'
```

### 2. Update Frontend Map Center

Edit `frontend/index.html`:
```javascript
const CONFIG = {
  DEFAULT_CENTER: { lat: 33.8353, lng: -118.3938 }, // Redondo Beach
  DEFAULT_ZOOM: 14,
};
```

### 3. Onboard Sensors for New Location

Configure new MQTT topics:
```
parking/lot/{new_lot_id}/ultrasonic
parking/lot/{new_lot_id}/lpr_entry
parking/lot/{new_lot_id}/lpr_exit
```

## 🆘 Troubleshooting

### Services Won't Start

```bash
# Check Docker daemon
docker ps

# View logs
docker-compose logs

# Restart all services
docker-compose restart

# Full cleanup and rebuild
docker-compose down -v
docker-compose up -d --build
```

### Database Connection Issues

```bash
# Check PostgreSQL
psql -h localhost -U parking_user -d parking_db

# Verify connection string
echo "postgresql://parking_user:parking_pass@localhost/parking_db"

# Check if port 5432 is listening
netstat -an | grep 5432
```

### WebSocket Connection Failures

```javascript
// Check browser console for errors
// Verify WebSocket URL matches your server
console.log(new WebSocket('ws://localhost:8000/ws/lots/live'));

// Test with curl
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  http://localhost:8000/ws/lots/live
```

### MQTT Connection Issues

```bash
# Test MQTT broker
docker-compose exec mqtt mqtt_sub -h localhost -t "parking/#"

# Publish test message
docker-compose exec mqtt mqtt_pub -h localhost \
  -t "parking/lot/1/ultrasonic" \
  -m '{"sensor_id":"s1","distance_cm":120}'
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📝 License

MIT License - see LICENSE file for details

## 🗺️ Roadmap

- [ ] Admin dashboard with historical analytics
- [ ] SMS alerts (Twilio integration) for full lots
- [ ] Machine learning for occupancy prediction
- [ ] Rate limiting and OAuth2 authentication
- [ ] Mobile app (React Native)
- [ ] Google Places API native integration
- [ ] Support for EV charging station availability
- [ ] Integration with smart city platforms (CKAN)
- [ ] Multi-language support
- [ ] Accessibility (WCAG 2.1 AA)

## 📞 Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/chintan-22/ParkingSolved/issues)
- Email: support@parkingsolved.io
- Documentation: https://parkingsolved.io/docs

---

**Built with ❤️ for smarter parking in coastal cities.**
