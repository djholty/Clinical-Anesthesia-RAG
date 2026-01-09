#!/bin/bash
# Test script to verify backend and frontend servers manually before dockerizing

echo "=========================================="
echo "Manual Server Test Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ -d ".venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment found"
    source .venv/bin/activate
else
    echo -e "${YELLOW}⚠${NC}  No virtual environment found. Using system Python."
fi

# Check if .env file exists
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env file found"
else
    echo -e "${RED}✗${NC} .env file not found. Please create it from sample.env"
    exit 1
fi

# Check if required directories exist
echo ""
echo "Checking required directories..."
mkdir -p data/pdfs data/ingested_documents data/chroma_db uploads
echo -e "${GREEN}✓${NC} Required directories exist"

echo ""
echo "=========================================="
echo "Testing Backend Server"
echo "=========================================="
echo ""
echo "Starting backend server in the background..."
echo "This will start:"
echo "  - FastAPI server on http://127.0.0.1:8000"
echo "  - PDF watcher (integrated)"
echo "  - Database watcher (integrated)"
echo ""

# Start backend in background
uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    > backend_test.log 2>&1 &
BACKEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Logs are being written to: backend_test.log"
echo ""

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Test health endpoint
echo "Testing /health endpoint..."
HEALTH_RESPONSE=$(curl -s http://127.0.0.1:8000/health || echo "FAILED")

if [[ "$HEALTH_RESPONSE" == *"healthy"* ]] || [[ "$HEALTH_RESPONSE" == *"status"* ]]; then
    echo -e "${GREEN}✓${NC} Backend health check passed"
    echo "Response: $HEALTH_RESPONSE"
else
    echo -e "${RED}✗${NC} Backend health check failed"
    echo "Response: $HEALTH_RESPONSE"
    echo "Check backend_test.log for errors"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "Checking if watchers started..."
# Check logs for watcher startup messages
if grep -q "Starting file watchers" backend_test.log 2>/dev/null; then
    echo -e "${GREEN}✓${NC} File watchers initialization detected"
else
    echo -e "${YELLOW}⚠${NC}  Watcher startup messages not found in logs (may still be starting)"
fi

if grep -q "PDF watcher thread started" backend_test.log 2>/dev/null; then
    echo -e "${GREEN}✓${NC} PDF watcher thread started"
else
    echo -e "${YELLOW}⚠${NC}  PDF watcher thread not confirmed (check logs)"
fi

if grep -q "Database watcher thread started" backend_test.log 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Database watcher thread started"
else
    echo -e "${YELLOW}⚠${NC}  Database watcher thread not confirmed (check logs)"
fi

echo ""
echo "=========================================="
echo "Backend Test Summary"
echo "=========================================="
echo -e "${GREEN}✓${NC} Backend server is running on http://127.0.0.1:8000"
echo -e "${GREEN}✓${NC} Health endpoint is responding"
echo ""
echo "You can now:"
echo "  - View API docs: http://127.0.0.1:8000/docs"
echo "  - Access admin page: http://127.0.0.1:8000/admin"
echo "  - Check logs: tail -f backend_test.log"
echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "In a NEW terminal, start the frontend:"
echo ""
echo "  cd $(pwd)"
echo "  source .venv/bin/activate  # if using venv"
echo "  streamlit run app_main.py --server.port=8501 --server.address=127.0.0.1"
echo ""
echo "Then access:"
echo "  - Frontend: http://127.0.0.1:8501"
echo "  - Backend API: http://127.0.0.1:8000"
echo ""
echo "=========================================="
echo "To stop the backend server:"
echo "  kill $BACKEND_PID"
echo "  or: pkill -f 'uvicorn app.main:app'"
echo "=========================================="
echo ""
echo "Backend is running. Press Ctrl+C to stop this script (backend will keep running)"
echo "Or leave this running and open a new terminal for the frontend."

# Keep script running so user can see logs
tail -f backend_test.log

