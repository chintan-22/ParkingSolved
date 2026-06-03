# Getting Started Guide

## 🎯 5-Minute Quick Start

### Step 1: Prerequisites Check

```bash
# Check Docker is installed
docker --version
# Should output: Docker version 20.10+

# Check Docker Compose
docker-compose --version
# Should output: Docker Compose version 2.0+
```

If not installed, [install Docker Desktop](https://www.docker.com/products/docker-desktop).

### Step 2: Get Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project: "ParkingSolved"
3. Enable Maps API:
   - Search for "Maps JavaScript API"
   - Click "Enable"
   - Also enable "Places API"
4. Go to Credentials → Create API Key
5. Copy the API key

### Step 3: Clone & Configure

```bash
cd /Users/chintanshah/Documents/ParkingSolved

# Create environment file
cp .env.example .env

# Edit .env and replace YOUR_GOOGLE_MAPS_API_KEY_HERE
nano .env
# Or use your preferred editor
```

### Step 4: Start Services

```bash
# Make quick-start script executable
chmod +x quick-start.sh

# Run the startup script
./quick-start.sh

# Or manually:
docker-compose up -d
```

### Step 5: Verify It Works

```bash
# Check all services are running
docker-compose ps

# Test API
curl http://localhost:8000/health

# Test frontend loads
open http://localhost:3000
# Or: curl -s http://localhost:3000 | head -20
```

### Step 6: See Live Data

Open browser to: **http://localhost:3000**

You should see:
- Google Map centered on Manhattan Beach Pier
- 4 colored parking lot markers
- Sidebar with live parking availability
- Real-time updates from simulator

---

## 🔧 Development Workflow

### Understanding the System

```
User opens http://localhost:3000
           ↓
Nginx serves index.html
           ↓
JavaScript initializes Google Maps
           ↓
Connects to http://localhost:8000/lots API
           ↓
Gets current occupancy from backend
           ↓
Displays markers with color-coded status
           ↓
Connects to WebSocket: ws://localhost:8000/ws/lots/live
           ↓
Simulator generates events every 30 seconds
           ↓
Backend broadcasts to all WebSocket clients
           ↓
Markers and sidebar update in real-time
```

### Modifying the Frontend

**Edit**: `frontend/index.html`

```javascript
// Change default location
const CONFIG = {
    DEFAULT_CENTER: { lat: 33.8843, lng: -118.4073 }, // Change these
    DEFAULT_ZOOM: 14,
};

// Change API URL
API_BASE_URL: 'http://localhost:8000',
WS_URL: 'ws://localhost:8000/ws/lots/live',
```

Changes reload automatically in browser.

### Modifying the Backend

**Edit**: `backend/main.py`

```bash
# Backend runs with auto-reload
docker-compose logs -f api

# To rebuild after changes:
docker-compose up -d --build api
```

### Adding a New Parking Lot

**Option 1: Via API**
```bash
curl -X POST http://localhost:8000/lots \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Beach Lot",
    "address": "123 Main St, Beach City, CA",
    "latitude": 33.8800,
    "longitude": -118.4000,
    "total_capacity": 200
  }'
```

**Option 2: Edit backend code**

Edit `backend/main.py`, function `initialize_sample_lots()`:

```python
ParkingLot(
    name="New Beach Lot",
    address="123 Main St, Beach City, CA",
    latitude=33.8800,
    longitude=-118.4000,
    total_capacity=200
),
```

Then restart: `docker-compose restart api`

### Simulating Parking Events

The simulator automatically generates realistic events. To manually trigger:

```bash
# Record an entry event
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"lot_id": 1, "event_type": "entry"}'

# Record an exit event
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"lot_id": 1, "event_type": "exit"}'

# Set occupancy directly
curl -X POST http://localhost:8000/occupancy/1?occupied_count=75
```

Watch the map update in real-time!

---

## 🔍 Debugging

### View All Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f simulator
docker-compose logs -f mqtt
docker-compose logs -f postgres
docker-compose logs -f redis

# Last 100 lines
docker-compose logs api --tail=100

# Follow and filter
docker-compose logs -f api | grep "occupancy"
```

### Check Database

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U parking_user -d parking_db

# See all parking lots
SELECT * FROM parking_lots;

# See recent events
SELECT * FROM occupancy_events ORDER BY timestamp DESC LIMIT 20;

# Count total events
SELECT COUNT(*) FROM occupancy_events;

# Exit psql
\q
```

### Check Redis

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# See all keys
KEYS *

# Get occupancy for lot 1
GET occupancy:lot:1

# See all data
KEYS "occupancy:*"
MGET occupancy:lot:1 occupancy:lot:2 occupancy:lot:3 occupancy:lot:4

# Exit redis-cli
EXIT
```

### Test WebSocket

```bash
# Install websocat if needed
brew install websocat

# Connect to WebSocket
websocat ws://localhost:8000/ws/lots/live

# You'll see JSON messages flowing in real-time
# Press Ctrl+C to disconnect
```

### Check MQTT

```bash
# Subscribe to all parking events
docker-compose exec mqtt mosquitto_sub -h localhost -t "parking/#" -v

# In another terminal, publish test message
docker-compose exec mqtt mosquitto_pub -h localhost \
  -t "parking/lot/1/ultrasonic" \
  -m '{"sensor_id":"test","distance_cm":90}'
```

### View API Documentation

Visit: **http://localhost:8000/docs**

This is automatically generated from the FastAPI code and shows:
- All endpoints
- Request/response schemas
- Ability to test endpoints directly
- Authentication info

---

## 📊 Monitoring

### Service Health

```bash
# Check all containers are healthy
docker-compose ps

# Should show all with status "Up"
# Status column shows running time
```

### Performance Stats

```bash
# Real-time resource usage
docker stats

# Press Ctrl+C to exit
```

### Event Rate

```bash
# Count events per lot (database)
docker-compose exec postgres psql -U parking_user -d parking_db \
  -c "SELECT lot_id, COUNT(*) FROM occupancy_events GROUP BY lot_id;"

# Count recent events (last minute)
docker-compose exec postgres psql -U parking_user -d parking_db \
  -c "SELECT COUNT(*) FROM occupancy_events WHERE timestamp > NOW() - INTERVAL '1 minute';"
```

---

## 🚨 Common Issues & Solutions

### "Cannot connect to Docker daemon"

```bash
# Start Docker
open -a Docker

# Or restart Docker service
sudo systemctl restart docker  # Linux
```

### "Port 3000 already in use"

```bash
# Find process using port
lsof -i :3000

# Kill it
kill -9 <PID>

# Or change port in docker-compose.yml
# Change "3000:80" to "3001:80"
```

### "Port 8000 already in use"

```bash
lsof -i :8000
kill -9 <PID>

# Or change in docker-compose.yml
# Change "8000:8000" to "8001:8000"
```

### "API returns 502 Bad Gateway"

```bash
# Check API logs
docker-compose logs api

# Check if API is running
docker-compose ps api

# Restart API
docker-compose restart api

# Wait 10 seconds for startup
sleep 10

# Try again
curl http://localhost:8000/health
```

### "WebSocket connection failed"

```bash
# Check WebSocket logs
docker-compose logs api | grep -i websocket

# Verify frontend is connecting to correct URL
# Check browser console: F12 → Console tab
# Should see: "WebSocket connected"

# If not, edit frontend/index.html and verify:
WS_URL: 'ws://localhost:8000/ws/lots/live'
```

### "Database migrations fail"

```bash
# Reset database
docker-compose down -v

# This removes all data - start fresh
docker-compose up -d
```

### "Simulator not generating events"

```bash
# Check simulator logs
docker-compose logs simulator

# Check if it can reach API
docker-compose exec simulator curl http://api:8000/health

# Check lots exist
curl http://localhost:8000/lots
```

---

## 📚 Learning Path

### Beginner (Day 1)
1. ✅ Get everything running locally
2. ✅ View map in browser
3. ✅ Watch real-time updates
4. ✅ Add a new parking lot
5. ✅ Trigger manual events

### Intermediate (Day 2-3)
1. ✅ Read API documentation at `/docs`
2. ✅ Understand database schema
3. ✅ Modify frontend styling
4. ✅ Add custom lot locations
5. ✅ Set up your own environment file

### Advanced (Week 1+)
1. ✅ Deploy to Docker Swarm
2. ✅ Set up production `.env`
3. ✅ Integrate real sensors
4. ✅ Build admin dashboard
5. ✅ Customize for your city

---

## 🎓 Key Concepts

### Real-Time Updates
- **Method 1**: REST polling (slow)
- **Method 2**: Server-Sent Events (better)
- **Method 3**: WebSocket (best for 2-way) ✓ Used here

### Color Coding
```
Green  (#4CAF50) → >30% spots available
Amber  (#FFC107) → 10-30% spots available  
Red    (#F44336) → <10% or full
```

### Event Flow
1. Sensor detects vehicle
2. Sends MQTT message
3. Ingestion service receives
4. Calls API `/events` endpoint
5. Backend updates Redis cache
6. Broadcasts via WebSocket
7. Frontend updates map

### Occupancy Calculation
```
Available = Total Capacity - Occupied Count
Fill % = (Occupied Count / Total Capacity) * 100
Status = Determine based on % available
```

---

## 🔐 Security Notes

### For Development
- No authentication needed
- All defaults are acceptable
- Localhost only

### For Production
- Change all default passwords
- Set Google Maps API key restrictions
- Enable HTTPS/SSL
- Use private database
- Enable API rate limiting
- See `DEPLOYMENT.md` for details

---

## 💡 Pro Tips

### Make Changes Stick
```bash
# After editing files, restart relevant service
docker-compose restart api        # After backend changes
docker-compose restart simulator  # After simulator changes

# For full rebuild:
docker-compose down
docker-compose up -d --build
```

### Save Money on Google Maps API
```javascript
// Enable at only the map scale you need
googlemap.setZoom(14);  // Close zoom saves API calls

// Use static maps where possible
// Limit info windows to one at a time
```

### Monitor Costs
```bash
# Check ingestion rate (should be <100 events/minute when idle)
docker-compose logs simulator | grep "occupancy" | wc -l

# This tells you how many log lines (≈ events) in simulator output
```

### Profile Performance
```bash
# Measure API response time
time curl http://localhost:8000/lots

# Should be <100ms with Redis

# Monitor memory usage
docker stats parking_api --no-stream

# Check database indexes
docker-compose exec postgres psql -U parking_user -d parking_db \
  -c "\d+ occupancy_events"
```

---

## 🎉 You're Ready!

You now have:
- ✅ Real-time parking system
- ✅ Google Maps integration
- ✅ Live data streaming
- ✅ Scalable architecture
- ✅ Production-ready code

**Next**: Read `DEPLOYMENT.md` to take it to production!

---

For detailed help on specific topics:
- **API Usage**: See `API.md`
- **Sensor Integration**: See `SENSORS.md`
- **Architecture**: See `ARCHITECTURE.md`
- **Production**: See `DEPLOYMENT.md`

**Questions?** Open an issue on GitHub or email support@parkingsolved.io
