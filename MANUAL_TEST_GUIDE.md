# Manual Testing Guide

This guide helps you test the backend and frontend servers manually before dockerizing.

## Prerequisites

1. Virtual environment activated (if using one)
2. `.env` file configured with your API keys
3. Required directories exist: `data/pdfs`, `data/ingested_documents`, `data/chroma_db`

## Quick Test (Automated)

Run the automated test script:

```bash
./test_servers_manual.sh
```

This will:
- Start the backend server
- Test the health endpoint
- Verify watchers are starting
- Show you how to start the frontend

## Manual Testing (Step by Step)

### Step 1: Start Backend Server

**Terminal 1:**

```bash
# Activate virtual environment (if using one)
source .venv/bin/activate

# Start backend (watchers are integrated)
./start_server.sh

# Or manually:
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
============================================================
Starting file watchers...
============================================================
✅ PDF watcher thread started
✅ Database watcher thread started
============================================================
```

**Verify backend is running:**
```bash
# In another terminal, test health endpoint
curl http://127.0.0.1:8000/health
```

Should return:
```json
{
  "status": "healthy",
  "server": "running",
  "evaluation_status": {...}
}
```

**Check watchers are running:**
- Look for "Starting file watchers..." in the backend logs
- Look for "PDF watcher thread started" and "Database watcher thread started"

### Step 2: Start Frontend Server

**Terminal 2:**

```bash
# Activate virtual environment (if using one)
source .venv/bin/activate

# Start Streamlit frontend
streamlit run app_main.py --server.port=8501 --server.address=127.0.0.1
```

**Expected output:**
```
You can now view your Streamlit app in your browser.

Local URL: http://localhost:8501
Network URL: http://0.0.0.0:8501
```

### Step 3: Verify Everything Works

1. **Backend API:**
   - Open: http://127.0.0.1:8000/docs
   - Should see FastAPI interactive documentation

2. **Backend Admin:**
   - Open: http://127.0.0.1:8000/admin
   - Should see admin dashboard

3. **Frontend:**
   - Open: http://127.0.0.1:8501
   - Should see "Clinical Anesthesia QA System"
   - Try asking a question in the "💬 Ask Questions" tab

4. **Test Watchers:**
   - Place a PDF file in `data/pdfs/`
   - Watch backend logs - you should see PDF watcher detecting the file
   - After quiet period, PDF should be converted to markdown in `data/ingested_documents/`
   - Database watcher should detect the new markdown and rebuild the database

## Troubleshooting

### Backend Won't Start

1. **Check port 8000 is available:**
   ```bash
   lsof -i :8000
   ```

2. **Check for import errors:**
   ```bash
   python -c "from app.main import app"
   ```

3. **Check watchers can be imported:**
   ```bash
   python -c "from app.pdf_watcher import main; from app.database_watcher import main"
   ```

### Watchers Not Starting

1. **Check environment variable:**
   ```bash
   echo $ENABLE_FILE_WATCHERS
   ```
   Should be `true` or unset (defaults to true)

2. **Check directories exist:**
   ```bash
   ls -la data/pdfs
   ls -la data/ingested_documents
   ```

3. **Check backend logs for errors:**
   - Look for "Failed to start PDF watcher" or "Failed to start database watcher"
   - Check for import errors or missing dependencies

### Frontend Won't Connect to Backend

1. **Verify backend is running:**
   ```bash
   curl http://127.0.0.1:8000/health
   ```

2. **Check API_URL in frontend:**
   - Frontend uses `API_URL` environment variable
   - Default: `http://127.0.0.1:8000`
   - Can be set in `.env` or environment

3. **Check CORS settings:**
   - Backend should allow all origins in development (already configured)

## What to Look For

### Successful Backend Startup:
- ✅ "Uvicorn running on http://127.0.0.1:8000"
- ✅ "Application startup complete"
- ✅ "Starting file watchers..."
- ✅ "PDF watcher thread started"
- ✅ "Database watcher thread started"

### Successful Frontend Startup:
- ✅ "You can now view your Streamlit app"
- ✅ Can access http://127.0.0.1:8501
- ✅ Can see the QA interface
- ✅ Can ask questions and get answers

### Successful Watcher Integration:
- ✅ Watchers start automatically with backend
- ✅ No separate processes needed
- ✅ Watchers run as background threads
- ✅ Logs show watcher activity

## Next Steps

Once manual testing is successful:

1. **Stop both servers** (Ctrl+C in each terminal)
2. **Build Docker containers:**
   ```bash
   docker-compose build
   ```
3. **Start with Docker:**
   ```bash
   docker-compose up
   ```

The Docker setup will use the same integrated watcher approach, so if manual testing works, Docker should work too!

