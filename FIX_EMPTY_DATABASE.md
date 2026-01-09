# Fix: No Answers from Ask Question Section

## Problem
The database is empty even though you have markdown files. The API returns:
```json
{"answer": "The available context does not provide sufficient information to answer this question.", "contexts": []}
```

## Solution: Rebuild the Database

You have markdown files in `data/ingested_documents/` but they haven't been indexed into the vector database yet.

### Option 1: Use the Rebuild Script (Recommended)

**Step 1:** Stop the FastAPI backend server
- Go to the terminal where the backend is running
- Press `Ctrl+C` to stop it

**Step 2:** Run the rebuild script
```bash
./rebuild_db.sh
```

Or manually:
```bash
# Activate virtual environment if using one
source .venv/bin/activate

# Run rebuild
python3 app/rebuild_database.py
```

**Step 3:** Restart the backend
```bash
./start_server.sh
```

**Step 4:** Test again
- Try asking a question in the frontend
- Or test with: `curl -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d '{"question": "What is anesthesia?"}'`

### Option 2: Trigger Database Watcher (Automatic)

If the database watcher is running (integrated in backend), you can trigger it by:

**Step 1:** Touch a markdown file to trigger the watcher
```bash
touch data/ingested_documents/01_Stoelting.md
```

**Step 2:** Wait 5 minutes (QUIET_PERIOD_SECONDS=300)
- The watcher will detect the change
- After the quiet period, it will automatically rebuild the database

**Step 3:** Check backend logs for:
```
🔄 Starting automatic database rebuild...
✅ Automatic database rebuild completed successfully
```

### Option 3: Set REBUILD_ON_STARTUP (One-time)

**Step 1:** Stop the backend server

**Step 2:** Set environment variable and restart
```bash
export REBUILD_ON_STARTUP=true
./start_server.sh
```

This will rebuild the database when the backend starts.

**Step 3:** After first startup, unset the variable
```bash
unset REBUILD_ON_STARTUP
```

## Verify Database is Populated

After rebuilding, check:
```bash
curl http://127.0.0.1:8000/list_docs
```

Should return something like:
```json
{"documents": ["01_Stoelting.md", "02_Stoelting.md", ...]}
```

## Why This Happened

The database exists (`chroma.sqlite3`) but is empty. This can happen if:
- Database was cleared but not rebuilt
- Markdown files were added but database wasn't rebuilt
- Database watcher hasn't run yet (waiting for quiet period)

## Prevention

The integrated database watcher should automatically rebuild when:
- New markdown files are added to `data/ingested_documents/`
- Existing markdown files are modified
- After a 5-minute quiet period (no changes)

You can also manually trigger it by touching a file or using the rebuild script.

