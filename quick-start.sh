#!/bin/bash
# Quick Start Script for ParkingSolved

set -e

echo "🚗 ParkingSolved - Smart Parking System"
echo "========================================"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker Desktop."
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

echo "✓ Docker and Docker Compose found"
echo ""

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your Google Maps API key"
    echo "   Then run this script again."
    exit 0
fi

echo "✓ .env file exists"
echo ""

# Check if Google Maps API key is configured
if ! grep -q "GOOGLE_MAPS_API_KEY=YOUR_GOOGLE_MAPS_API_KEY_HERE" .env; then
    API_KEY=$(grep "GOOGLE_MAPS_API_KEY=" .env | cut -d'=' -f2)
    if [ -z "$API_KEY" ] || [ "$API_KEY" = "YOUR_GOOGLE_MAPS_API_KEY_HERE" ]; then
        echo "❌ Google Maps API key not configured in .env"
        exit 1
    fi
fi

echo "🐳 Starting Docker Compose services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start (30 seconds)..."
sleep 30

echo ""
echo "✓ Services started successfully!"
echo ""

# Check services health
echo "📊 Checking service status..."
docker-compose ps
echo ""

# Check API health
echo "🏥 Checking API health..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ API is healthy"
else
    echo "⚠️  API is starting up, please wait..."
    sleep 10
fi

echo ""
echo "🎉 ParkingSolved is ready!"
echo ""
echo "Access the application:"
echo "  - Frontend:  http://localhost:3000"
echo "  - API Docs:  http://localhost:8000/docs"
echo "  - Health:    http://localhost:8000/health"
echo ""
echo "Useful commands:"
echo "  - View logs:      docker-compose logs -f api"
echo "  - Stop services:  docker-compose down"
echo "  - Reset data:     docker-compose down -v"
echo ""
echo "Documentation:"
echo "  - API Reference:   cat API.md"
echo "  - Deployment:      cat DEPLOYMENT.md"
echo ""
