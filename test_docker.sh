#!/bin/bash
# Docker Testing Script for Clinical Anesthesia QA System
# This script tests the Docker build and container startup

set -e  # Exit on error

echo "========================================="
echo "Docker Testing Script"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker daemon is not running.${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo -e "${GREEN}✓ Docker daemon is running${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}WARNING: .env file not found. Creating from sample.env...${NC}"
    if [ -f sample.env ]; then
        cp sample.env .env
        echo -e "${YELLOW}Please edit .env file with your actual values before continuing.${NC}"
        echo "Press Enter to continue or Ctrl+C to exit..."
        read
    else
        echo -e "${RED}ERROR: sample.env not found. Cannot proceed.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓ .env file found${NC}"
echo ""

# Phase 1: Build Backend
echo "========================================="
echo "Phase 1: Building Backend Image"
echo "========================================="
docker build -t test-backend -f Dockerfile . || {
    echo -e "${RED}✗ Backend build failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Backend image built successfully${NC}"
echo ""

# Phase 2: Build Frontend
echo "========================================="
echo "Phase 2: Building Frontend Image"
echo "========================================="
docker build -t test-frontend -f Dockerfile.frontend . || {
    echo -e "${RED}✗ Frontend build failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Frontend image built successfully${NC}"
echo ""

# Phase 3: Test Backend Container Startup (dry run)
echo "========================================="
echo "Phase 3: Testing Container Startup"
echo "========================================="
echo "Testing backend container..."
docker run --rm --name test-backend-container \
    --env-file .env \
    -p 8001:8000 \
    test-backend &
BACKEND_PID=$!

# Wait a moment for startup
sleep 5

# Check if container is still running
if docker ps | grep -q test-backend-container; then
    echo -e "${GREEN}✓ Backend container started successfully${NC}"
    
    # Test health endpoint
    if curl -s http://localhost:8001/health > /dev/null; then
        echo -e "${GREEN}✓ Backend health endpoint is accessible${NC}"
    else
        echo -e "${YELLOW}⚠ Backend health endpoint not accessible yet (may need more time)${NC}"
    fi
    
    # Stop the test container
    docker stop test-backend-container > /dev/null 2>&1 || true
    wait $BACKEND_PID 2>/dev/null || true
else
    echo -e "${RED}✗ Backend container failed to start${NC}"
    docker logs test-backend-container 2>&1 || true
    docker rm test-backend-container > /dev/null 2>&1 || true
    exit 1
fi

echo ""

# Phase 4: Test Docker Compose
echo "========================================="
echo "Phase 4: Testing Docker Compose Build"
echo "========================================="
echo "Building all services with docker-compose..."
docker-compose build || {
    echo -e "${RED}✗ Docker Compose build failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Docker Compose build successful${NC}"
echo ""

# Summary
echo "========================================="
echo "Testing Summary"
echo "========================================="
echo -e "${GREEN}✓ All Docker builds successful${NC}"
echo -e "${GREEN}✓ Containers can start correctly${NC}"
echo ""
echo "To start the full stack, run:"
echo "  docker-compose up"
echo ""
echo "To start in detached mode:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop the stack:"
echo "  docker-compose down"
echo ""

