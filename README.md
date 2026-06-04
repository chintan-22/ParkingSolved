# ParkingSolved

ParkingSolved is a smart parking availability prototype. It combines a map-based user interface, destination search, nearby parking discovery, estimated parking availability, and a sensor-ready backend for live occupancy updates.

The current frontend uses **MapLibre GL JS** with **OpenFreeMap** tiles, so it does not require a Google Maps API key. Destination search uses OpenStreetMap/Nominatim, and nearby parking discovery uses OpenStreetMap/Overpass.

## Current Status

This project is a working local demo and sensor-ingestion prototype.

- The map and destination search are dynamic.
- Nearby parking lots are fetched from OpenStreetMap around the searched destination.
- Parking capacities and availability are estimated unless OpenStreetMap provides capacity data or your own backend/sensors provide live data.
- The backend still includes sample lots and live occupancy APIs for sensor/simulator workflows.

## Features

- Destination search with a persistent map search bar.
- Current-location support through browser geolocation.
- Interactive MapLibre map with OpenFreeMap vector tiles.
- Dynamic nearby parking discovery from OpenStreetMap.
- Parking markers color-coded by availability:
  - Green: more than 30% free
  - Amber: 10-30% free
  - Red: less than 10% free
- Parking cards sorted by distance from the destination.
- Correct full percentage display based on `occupied_count / total_capacity`.
- Directions button that opens Google Maps directions to the selected parking lot.
- FastAPI backend with REST and WebSocket endpoints.
- Redis-backed occupancy state.
- PostgreSQL event/snapshot persistence.
- MQTT ingestion service for future sensors.
- Simulator service for demo occupancy events.

## Important Limitations

OpenStreetMap can provide mapped parking locations, but it does not provide live parking availability for most lots.

For OpenStreetMap-sourced lots, this app estimates:

- total capacity, when no `capacity` tag exists
- occupied spaces
- available spaces
- percentage full

For real live availability, you need one of these:

- your own sensors connected through MQTT
- a city/garage parking API
- a commercial parking provider
- manual updates through the backend API

## Project Structure

```text
ParkingSolved/
├── backend/
│   ├── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── index.html
├── sensor-ingestion/
│   ├── mqtt_ingestion.py
│   ├── Dockerfile
│   └── requirements.txt
├── simulator/
│   ├── simulator.py
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── init-db.sql
├── mqtt-config.xml
├── nginx.conf
├── quick-start.sh
├── API.md
├── ARCHITECTURE.md
├── DEPLOYMENT.md
├── GETTING_STARTED.md
├── INDEX.md
├── LEAFLET_MIGRATION.md
├── MIGRATION_COMPLETE.md
└── README.md
```

## Quick Start

### Prerequisites

- Docker
- Docker Compose
- A browser with internet access

No Google Maps API key is required.

The browser must be able to load:

- MapLibre GL JS from `unpkg.com`
- OpenFreeMap tiles from `tiles.openfreemap.org`
- Nominatim search from `nominatim.openstreetmap.org`
- Overpass parking data from `overpass-api.de`

### Start the App

```bash
docker-compose up -d
```

This starts:

- PostgreSQL on port `5432`
- Redis on port `6379`
- HiveMQ MQTT broker on port `1883`
- FastAPI backend on port `8000`
- simulator service
- MQTT ingestion service
- nginx frontend on port `3000`

### Open the App

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/health

### Verify Services

```bash
docker-compose ps
curl http://localhost:8000/health
curl http://localhost:8000/lots
```

## Deploying the Frontend to Vercel

The repository root does not contain `index.html`; the frontend lives at:

```text
frontend/index.html
```

Vercel will return a 404 if it deploys the repository root without being told where the static app is. This repo includes:

```text
vercel.json
```

with a rewrite that serves `frontend/index.html` for incoming routes.

```json
{
  "rewrites": [
    {
      "source": "/(.*)",
      "destination": "/frontend/index.html"
    }
  ]
}
```

After adding or updating `vercel.json`, redeploy the Vercel project.

On Vercel, the frontend runs in static mode:

- MapLibre/OpenFreeMap works.
- Destination search works.
- OpenStreetMap parking discovery works.
- The local Docker backend at `localhost:8000` is disabled because hosted users cannot access your machine's localhost.

To enable live backend/WebSocket data in production, deploy the FastAPI backend separately and update the frontend config to point to that hosted API.

## User Guide

### 1. Open the Map

Go to:

```text
http://localhost:3000
```

The app will ask for location permission. If you allow it, the map starts near your current location. If you deny it, the app falls back to the default Manhattan Beach coordinates.

### 2. Enter a Destination

Use the search bar at the top-left of the map.

Example searches:

```text
Santa Monica Pier
Phoenix Convention Center
Times Square
900 Manhattan Beach Blvd
```

Click `Find Parking`.

The app will:

- geocode the destination
- move the map to the destination
- place a red destination marker
- fetch nearby parking lots from OpenStreetMap
- show parking markers around that destination
- open the parking list panel

### 3. Read Parking Availability

Each parking card shows:

- distance from the destination
- percent full
- filled spaces as `occupied / total`
- available spaces
- whether the slots are estimated or based on mapped capacity
- source

Example:

```text
12% full
12/100
88 available
Estimated slots
OpenStreetMap
```

### 4. Get Directions

Click `Get Directions` on a parking card or popup.

The app opens Google Maps directions from your current location to that parking lot. This does not require a Google Maps API key because it uses a normal Google Maps URL.

### 5. Return to Your Location

Click `Use My Location`.

The app will:

- clear the destination marker
- center the map on your location
- search nearby mapped parking lots around you

### 6. Toggle Parking Markers

Click `Hide Parking` or `Show Parking` to toggle the parking markers.

## How the Frontend Works

The frontend is a single file:

```text
frontend/index.html
```

It uses:

- MapLibre GL JS for the map
- OpenFreeMap for vector tiles
- Nominatim for destination geocoding
- Overpass API for parking-lot discovery
- browser geolocation for current location
- WebSocket connection to the backend for live updates

Important frontend config:

```javascript
const CONFIG = {
  API_BASE_URL: 'http://localhost:8000',
  WS_URL: 'ws://localhost:8000/ws/lots/live',
  MAP_STYLE_URL: 'https://tiles.openfreemap.org/styles/liberty',
  OVERPASS_URLS: [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter'
  ],
  DEFAULT_CENTER: { lat: 33.8843, lng: -118.4073 },
  DEFAULT_ZOOM: 15,
  DESTINATION_ZOOM: 14,
  NEARBY_RADIUS_MILES: 5,
  NEARBY_RADIUS_METERS: 8047,
  PARKING_SEARCH_RADII_METERS: [2500, 5000, 8047]
};
```

## Backend API

The backend is a FastAPI app:

```text
backend/main.py
```

It manages known parking lots, occupancy events, manual occupancy updates, and WebSocket broadcasts.

### Main Endpoints

```text
GET  /health
GET  /lots
GET  /lots/{lot_id}
POST /lots
POST /events
POST /occupancy/{lot_id}
WS   /ws/lots/live
```

### Health Check

```bash
curl http://localhost:8000/health
```

### Get Backend Lots

```bash
curl http://localhost:8000/lots
```

The backend contains demo/sample lots used for simulator and sensor workflows. The frontend destination search now uses OpenStreetMap dynamically instead of relying only on these demo lots.

### Record Entry/Exit Event

```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"lot_id": 1, "event_type": "entry"}'
```

### Manually Set Occupancy

```bash
curl -X POST "http://localhost:8000/occupancy/1?occupied_count=45"
```

## Live Updates

The backend broadcasts updates over:

```text
ws://localhost:8000/ws/lots/live
```

Frontend code listens for:

- `initial_state`
- `occupancy_update`

The current live WebSocket flow works best for backend-managed lots. OpenStreetMap-discovered lots are external map data and do not have real backend IDs unless you import them into the backend.

## MQTT Sensor Ingestion

The MQTT ingestion service is in:

```text
sensor-ingestion/mqtt_ingestion.py
```

It subscribes to:

```text
parking/lot/+/ultrasonic
parking/lot/+/lpr_entry
parking/lot/+/lpr_exit
parking/lot/+/occupancy_estimate
```

Example LPR entry payload:

```json
{
  "camera_id": "cam_entry_1",
  "license_plate": "ABC123",
  "timestamp": "2026-06-04T12:00:00Z"
}
```

Example occupancy estimate payload:

```json
{
  "occupied_count": 45,
  "total_capacity": 150,
  "confidence": 0.95,
  "timestamp": "2026-06-04T12:00:00Z"
}
```

## Simulator

The simulator is in:

```text
simulator/simulator.py
```

It generates realistic entry/exit events against the backend API using time-of-day patterns.

It reads the API URL from:

```text
API_BASE_URL
```

In Docker Compose, this is:

```text
http://api:8000
```

## Data Flow

### Dynamic Destination Search Flow

```text
User enters destination
      ↓
Nominatim geocodes destination
      ↓
MapLibre centers map
      ↓
Overpass finds mapped parking lots nearby
      ↓
Frontend estimates availability when live data is unavailable
      ↓
User chooses a lot and opens directions
```

### Sensor/Backend Live Flow

```text
Sensor or simulator
      ↓
MQTT broker or backend API
      ↓
FastAPI backend
      ↓
Redis occupancy state
      ↓
PostgreSQL event/snapshot history
      ↓
WebSocket broadcast
      ↓
Frontend live update
```

## Database Tables

### `parking_lots`

Stores backend-managed lots.

### `occupancy_events`

Stores entry/exit events.

### `occupancy_snapshots`

Stores point-in-time occupancy snapshots.

The schema is initialized from:

```text
init-db.sql
```

## Development Notes

### Restart Services

```bash
docker-compose restart
```

### Rebuild Services

```bash
docker-compose up -d --build
```

### View Logs

```bash
docker-compose logs -f
docker-compose logs -f api
docker-compose logs -f simulator
docker-compose logs -f ingestion
docker-compose logs -f mqtt
```

### Stop Services

```bash
docker-compose down
```

### Reset Data

```bash
docker-compose down -v
docker-compose up -d --build
```

## Troubleshooting

### The Map Does Not Load

Check that your browser can access:

```text
https://unpkg.com
https://tiles.openfreemap.org
```

Also open browser DevTools and check the Console/Network tabs.

### Destination Search Does Not Work

The browser must be able to call:

```text
https://nominatim.openstreetmap.org
```

Try a more specific destination, such as a full address or well-known place name.

### No Parking Lots Appear Near a Destination

The app searches OpenStreetMap parking data within 5 miles of the destination.

If no parking appears, it may mean:

- OpenStreetMap has no mapped parking lots nearby
- Overpass is temporarily slow or unavailable
- the destination is too vague
- the search radius is too small

You can adjust:

```javascript
NEARBY_RADIUS_MILES
NEARBY_RADIUS_METERS
```

in `frontend/index.html`.

### Percent Full Looks Wrong

The UI displays:

```text
occupied_count / total_capacity
```

and calculates:

```text
percent_full = occupied_count / total_capacity * 100
```

Available spaces are shown separately.

### API Is Not Responding

```bash
docker-compose ps
docker-compose logs api --tail=100
curl http://localhost:8000/health
```

### MQTT Is Not Healthy

```bash
docker-compose ps mqtt
docker-compose logs mqtt --tail=100
```

The current HiveMQ config is:

```text
mqtt-config.xml
```

## Production Considerations

Before using this as a production app:

- replace estimated availability with real parking data
- import OpenStreetMap lots into your own backend if you need stable IDs
- cache Nominatim/Overpass results or run your own services
- follow Nominatim and Overpass usage policies
- add backend authentication for admin/manual updates
- add rate limiting
- add monitoring and logs
- use HTTPS
- use production-grade database credentials

## Roadmap

- Import OpenStreetMap lots into PostgreSQL.
- Connect dynamic OSM lots to backend occupancy state.
- Add a production geocoding provider or self-hosted Nominatim.
- Add a production Overpass alternative or cached parking dataset.
- Add real sensor integrations.
- Add admin dashboard for managing lots and overrides.
- Add historical analytics.
- Add route-aware parking recommendations.
- Add accessibility improvements.

## License

MIT License.
