# Deployment Guide

## Development Deployment (Local with Docker Compose)

### Requirements
- Docker Desktop (macOS, Windows) or Docker + Docker Compose (Linux)
- 4GB available RAM
- 2GB free disk space

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/chintan-22/ParkingSolved.git
   cd ParkingSolved
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your Google Maps API key
   nano .env
   ```

3. **Build and start services**
   ```bash
   docker-compose up -d
   ```

4. **Verify services**
   ```bash
   docker-compose ps
   docker-compose logs -f api
   ```

5. **Access the application**
   - Frontend: http://localhost:3000
   - API Docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

6. **Stop services**
   ```bash
   docker-compose down
   ```

---

## Production Deployment (AWS EC2)

### Architecture Diagram

```
Internet
    ↓
AWS ALB (Load Balancer)
    ↓
EC2 Instance(s)
├── Docker Container: Nginx (Reverse Proxy)
├── Docker Container: FastAPI
├── Docker Container: Simulator
├── Docker Container: MQTT Ingestion
├── Docker Container: Redis
└── RDS: PostgreSQL
```

### Prerequisites

- AWS Account with EC2 and RDS access
- Ubuntu 22.04 LTS EC2 instance (t3.medium or larger)
- Security groups configured for:
  - Port 80 (HTTP)
  - Port 443 (HTTPS)
  - Port 5432 (PostgreSQL - internal only)
  - Port 6379 (Redis - internal only)

### Step-by-Step Guide

#### 1. Prepare EC2 Instance

```bash
# SSH into instance
ssh -i your-key.pem ubuntu@your-instance-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

#### 2. Clone Repository

```bash
# Clone the repository
git clone https://github.com/chintan-22/ParkingSolved.git
cd ParkingSolved

# Create .env file for production
cat > .env << EOF
# Database (use RDS endpoint)
DATABASE_URL=postgresql://parking_user:strong_password@your-rds-endpoint:5432/parking_db
REDIS_URL=redis://redis:6379

# MQTT
MQTT_BROKER=mqtt
MQTT_PORT=1883
MQTT_USER=parking_user
MQTT_PASSWORD=strong_mqtt_password

# API
API_HOST=0.0.0.0
API_PORT=8000

# Frontend
GOOGLE_MAPS_API_KEY=your_actual_api_key
FRONTEND_URL=https://parking.example.com
API_URL=https://parking.example.com
WS_URL=wss://parking.example.com
EOF
```

#### 3. Create RDS Database (Optional but Recommended)

```bash
# Via AWS Console or AWS CLI
aws rds create-db-instance \
  --db-instance-identifier parking-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username parking_user \
  --master-user-password strong_password_here \
  --allocated-storage 20 \
  --publicly-accessible false \
  --vpc-security-group-ids sg-xxxxx
```

#### 4. Modify docker-compose.yml for Production

Remove local PostgreSQL, point to RDS instead:

```yaml
services:
  redis:
    # Keep local Redis or use ElastiCache
    ...
  
  api:
    environment:
      DATABASE_URL: postgresql://parking_user:password@your-rds-endpoint:5432/parking_db
      REDIS_URL: redis://redis:6379
    ...
    
  # Remove postgres service entirely
  # postgres:
  #   (delete entire section)
```

#### 5. Set Up HTTPS with Let's Encrypt

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get certificate
sudo certbot certonly --standalone -d parking.example.com

# Update nginx.conf to use SSL certificates
# Edit nginx.conf and set:
# ssl_certificate /etc/letsencrypt/live/parking.example.com/fullchain.pem;
# ssl_certificate_key /etc/letsencrypt/live/parking.example.com/privkey.pem;

# Mount certificates in docker-compose.yml:
# volumes:
#   - /etc/letsencrypt:/etc/letsencrypt:ro
```

#### 6. Start Services

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Verify services
docker-compose ps
docker-compose logs -f

# Run database migrations
docker-compose exec api python -c "from main import Base, engine; Base.metadata.create_all(bind=engine)"
```

#### 7. Configure Auto-Renewal for SSL Certificate

```bash
# Set up cron job for Let's Encrypt renewal
sudo crontab -e

# Add this line:
0 0 1 * * certbot renew --quiet && docker-compose restart nginx
```

#### 8. Set Up Monitoring (CloudWatch)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb

# Configure and start
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -s \
  -c file:/home/ubuntu/cloudwatch-config.json
```

---

## Production Deployment (Docker Swarm)

For multi-node deployments:

```bash
# Initialize Swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml parking

# Check services
docker service ls
docker service logs parking_api
```

---

## Production Deployment (Kubernetes)

### Prerequisites
- kubectl configured for your cluster
- Container images pushed to Docker Hub or ECR

### 1. Create Kubernetes Manifests

```yaml
# kubernetes/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: parking-system
---

# kubernetes/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: parking-secrets
  namespace: parking-system
type: Opaque
stringData:
  DATABASE_URL: postgresql://user:password@postgres:5432/parking_db
  REDIS_URL: redis://redis:6379
  GOOGLE_MAPS_API_KEY: your_key_here

---

# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: parking-api
  namespace: parking-system
spec:
  replicas: 3
  selector:
    matchLabels:
      app: parking-api
  template:
    metadata:
      labels:
        app: parking-api
    spec:
      containers:
      - name: api
        image: parking-api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - secretRef:
            name: parking-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
---

# kubernetes/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: parking-api-service
  namespace: parking-system
spec:
  selector:
    app: parking-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### 2. Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f kubernetes/namespace.yaml

# Create secrets
kubectl apply -f kubernetes/secrets.yaml

# Deploy application
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml

# Check status
kubectl get all -n parking-system
kubectl logs -f deployment/parking-api -n parking-system
```

---

## Scaling Considerations

### Horizontal Scaling
- FastAPI is stateless and can be load balanced
- Redis connection pooling for concurrent requests
- PostgreSQL replicas for read scaling

### Vertical Scaling
- Increase instance type for compute
- Adjust Docker resource limits
- Database optimization and indexing

### Load Testing

```bash
# Using Apache Bench
ab -n 10000 -c 100 http://localhost:8000/lots

# Using wrk
wrk -t12 -c400 -d30s http://localhost:8000/lots
```

---

## Monitoring & Logging

### Application Logs

```bash
# View logs
docker-compose logs -f api

# Export logs
docker-compose logs api > api.log
```

### Database Monitoring

```sql
-- Check active connections
SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan FROM pg_stat_user_indexes;

-- Check slow queries
SELECT query, calls, mean_time FROM pg_stat_statements ORDER BY mean_time DESC;
```

### Redis Monitoring

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# Check memory usage
INFO memory

# Monitor commands
MONITOR

# Check keyspace
INFO keyspace
```

---

## Backup & Disaster Recovery

### Database Backup

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U parking_user parking_db > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U parking_user parking_db < backup.sql
```

### Redis Persistence

Redis snapshots are automatically created. For better durability:

```bash
# Enable AOF (Append-Only File) in Redis config
appendonly yes
appendfsync everysec
```

---

## Troubleshooting Production Issues

### API Container Crashes

```bash
# Check logs
docker-compose logs api

# Check resource limits
docker stats parking_api

# Increase memory limit in docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 1G
```

### Database Connection Pool Exhaustion

```bash
# Check pool status
docker-compose exec redis redis-cli
KEYS "occupancy:*" | wc -l

# Increase pool size in backend/main.py
pool_size = 20
max_overflow = 10
```

### WebSocket Disconnections

```bash
# Check nginx WebSocket configuration
# Ensure proxy_read_timeout is sufficiently high
proxy_read_timeout 300s;
```

---

## Performance Tuning

### PostgreSQL Optimization

```sql
-- Create indexes on frequently queried columns
CREATE INDEX idx_events_lot_timestamp ON occupancy_events(lot_id, timestamp);
CREATE INDEX idx_snapshots_lot_time ON occupancy_snapshots(lot_id, snapshot_time);

-- Analyze query plans
EXPLAIN ANALYZE SELECT * FROM occupancy_events WHERE lot_id = 1;
```

### Redis Optimization

```bash
# Adjust maxmemory policy
CONFIG SET maxmemory-policy allkeys-lru

# Enable compression
CONFIG SET client-output-buffer-limit "normal 0 0 0"
```

### Nginx Optimization

```nginx
# Increase worker processes
worker_processes auto;

# Optimize buffering
client_body_buffer_size 128k;
client_max_body_size 10m;

# Enable caching
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=parking_cache:10m;
```

---

## Security Hardening

### API Security

```python
# Add rate limiting
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.get("/lots")
@limiter.limit("100/minute")
async def get_all_lots():
    ...
```

### Database Security

```sql
-- Create restricted user for API
CREATE USER api_user WITH PASSWORD 'secure_password';
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO api_user;
```

### Network Security

```bash
# Configure firewall rules
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

---

## Costs Estimation (AWS)

| Service | Monthly Cost |
|---------|-------------|
| EC2 (t3.medium) | $30 |
| RDS PostgreSQL (db.t3.micro) | $15 |
| ElastiCache Redis | $15 |
| Data Transfer | $5-50 |
| **Total** | **$65-110/month** |

---

For additional help, see README.md or contact support@parkingsolved.io
