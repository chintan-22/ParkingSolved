# API Documentation

## Smart Parking Availability API

### Base URL
```
http://localhost:8000
```

### Health Check

**GET** `/health`

Check if API is running.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2024-06-02T10:30:00Z"
}
```

---

## Parking Lots Endpoints

### Get All Lots

**GET** `/lots`

Returns all parking lots with current occupancy information.

**Query Parameters:**
- `limit` (optional): Maximum number of lots to return (default: 1000)
- `offset` (optional): Number of lots to skip (default: 0)

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
  },
  {
    "id": 2,
    "name": "Manhattan Beach Pier - Lot B",
    "address": "1000 Manhattan Beach Blvd, Manhattan Beach, CA",
    "latitude": 33.8845,
    "longitude": -118.4080,
    "total_capacity": 200,
    "occupied_count": 45,
    "available_count": 155,
    "status": "green",
    "fill_percentage": 22.5,
    "last_updated": "2024-06-02T10:30:00Z"
  }
]
```

---

### Get Single Lot

**GET** `/lots/{lot_id}`

Returns detailed information for a specific parking lot.

**Path Parameters:**
- `lot_id` (required): Numeric ID of the parking lot

**Response:**
```json
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
```

**Error Response:**
```json
{
  "detail": "Lot not found"
}
```

---

### Create Lot

**POST** `/lots`

Create a new parking lot.

**Request Body:**
```json
{
  "name": "Redondo Beach Pier - Lot A",
  "address": "1800 Harbor Drive, Redondo Beach, CA",
  "latitude": 33.8353,
  "longitude": -118.3938,
  "total_capacity": 250
}
```

**Response:** (201 Created)
```json
{
  "id": 5,
  "name": "Redondo Beach Pier - Lot A",
  "address": "1800 Harbor Drive, Redondo Beach, CA",
  "latitude": 33.8353,
  "longitude": -118.3938,
  "total_capacity": 250,
  "occupied_count": 0,
  "available_count": 250,
  "status": "green",
  "fill_percentage": 0.0,
  "last_updated": "2024-06-02T10:30:00Z"
}
```

---

## Occupancy Events

### Record Event

**POST** `/events`

Record an entry or exit event from a sensor.

**Request Body:**
```json
{
  "lot_id": 1,
  "event_type": "entry"
}
```

**Parameters:**
- `lot_id`: ID of the parking lot
- `event_type`: Either "entry" or "exit"

**Response:** (200 OK)
```json
{
  "status": "success",
  "lot_id": 1,
  "event_type": "entry"
}
```

**Error Response:**
```json
{
  "detail": "Invalid event type: invalid_type"
}
```

---

### Set Occupancy

**POST** `/occupancy/{lot_id}`

Manually set the occupancy count for a lot. Useful for corrections and initial setup.

**Path Parameters:**
- `lot_id` (required): ID of the parking lot

**Query Parameters:**
- `occupied_count` (required): Number of occupied spots (0 to total_capacity)

**Example:**
```
POST /occupancy/1?occupied_count=45
```

**Response:** (200 OK)
```json
{
  "status": "success",
  "lot_id": 1,
  "occupied_count": 45
}
```

**Error Response:**
```json
{
  "detail": "Invalid occupancy count"
}
```

---

## Real-Time Updates (WebSocket)

### Subscribe to Live Updates

**WebSocket** `ws://localhost:8000/ws/lots/live`

Establishes a persistent WebSocket connection for real-time occupancy updates.

#### Connection Example (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/lots/live');

ws.onopen = () => {
  console.log('Connected to live updates');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update received:', data);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from live updates');
};
```

#### Message Types

##### Initial State

Sent immediately upon connection, contains the current state of all lots.

```json
{
  "type": "initial_state",
  "lots": [
    {
      "id": 1,
      "name": "Manhattan Beach Pier - Lot A",
      "latitude": 33.8843,
      "longitude": -118.4073,
      "total_capacity": 150,
      "occupied_count": 120,
      "available_count": 30,
      "status": "amber",
      "fill_percentage": 80.0
    }
  ],
  "timestamp": "2024-06-02T10:30:00Z"
}
```

##### Occupancy Update

Sent whenever occupancy changes for any lot.

```json
{
  "type": "occupancy_update",
  "lot_id": 1,
  "occupied_count": 121,
  "available_count": 29,
  "status": "amber",
  "fill_percentage": 80.67,
  "timestamp": "2024-06-02T10:30:05Z"
}
```

---

## MQTT Integration

### Sensor Topics

The MQTT ingestion service subscribes to the following topics:

#### Ultrasonic Sensors
```
parking/lot/{lot_id}/ultrasonic
```

**Payload:**
```json
{
  "sensor_id": "s1",
  "distance_cm": 120.5,
  "timestamp": "2024-06-02T10:30:00Z"
}
```

#### License Plate Recognition - Entry
```
parking/lot/{lot_id}/lpr_entry
```

**Payload:**
```json
{
  "camera_id": "cam_entry_1",
  "license_plate": "ABC123",
  "timestamp": "2024-06-02T10:30:00Z"
}
```

#### License Plate Recognition - Exit
```
parking/lot/{lot_id}/lpr_exit
```

**Payload:**
```json
{
  "camera_id": "cam_exit_1",
  "license_plate": "ABC123",
  "timestamp": "2024-06-02T10:30:00Z"
}
```

#### Occupancy Estimate (from Computer Vision)
```
parking/lot/{lot_id}/occupancy_estimate
```

**Payload:**
```json
{
  "occupied_count": 45,
  "total_capacity": 150,
  "confidence": 0.95,
  "timestamp": "2024-06-02T10:30:00Z"
}
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200  | OK - Request succeeded |
| 201  | Created - Resource created successfully |
| 400  | Bad Request - Invalid input |
| 404  | Not Found - Resource not found |
| 500  | Internal Server Error |

---

## Rate Limiting

Currently, the API does not have rate limiting enabled. In production, consider implementing:
- API key-based rate limiting
- Per-IP rate limiting
- Per-lot rate limiting for sensor events

---

## Authentication (Future)

The current implementation does not include authentication. For production deployment, consider:
- API Key authentication for sensor integrations
- OAuth 2.0 for admin dashboard
- JWT tokens for frontend authentication

---

## Example Usage

### Using curl

#### Get all lots
```bash
curl -X GET http://localhost:8000/lots
```

#### Record an entry event
```bash
curl -X POST http://localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"lot_id": 1, "event_type": "entry"}'
```

#### Set occupancy
```bash
curl -X POST "http://localhost:8000/occupancy/1?occupied_count=75"
```

### Using Python

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# Get all lots
response = requests.get(f"{BASE_URL}/lots")
lots = response.json()
print(f"Found {len(lots)} parking lots")

# Record an event
event_data = {
    "lot_id": 1,
    "event_type": "entry"
}
response = requests.post(f"{BASE_URL}/events", json=event_data)
print(response.json())

# Set occupancy
response = requests.post(
    f"{BASE_URL}/occupancy/1",
    params={"occupied_count": 75}
)
print(response.json())
```

### Using JavaScript

```javascript
const BASE_URL = 'http://localhost:8000';

// Get all lots
fetch(`${BASE_URL}/lots`)
  .then(response => response.json())
  .then(lots => console.log(`Found ${lots.length} parking lots`));

// Record an event
fetch(`${BASE_URL}/events`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    lot_id: 1,
    event_type: 'entry'
  })
})
  .then(response => response.json())
  .then(data => console.log(data));

// WebSocket for real-time updates
const ws = new WebSocket('ws://localhost:8000/ws/lots/live');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

---

## Swagger UI

Interactive API documentation is available at:
```
http://localhost:8000/docs
```

Alternative ReDoc documentation:
```
http://localhost:8000/redoc
```

---

## Support

For API issues or questions, refer to the main README.md or contact support@parkingsolved.io
