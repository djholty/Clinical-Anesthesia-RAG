# URGENT: Database is Empty - Rebuild Required

## Problem
The database is completely empty - `{"documents": []}`. This happened after restarting the backend.

## Immediate Fix

**You MUST rebuild the database now:**

1. **Stop the backend** (Ctrl+C in the terminal running it)

2. **Rebuild the database:**
   ```bash
   ./rebuild_db.sh
   ```
   
   Or manually:
   ```bash
   source .venv/bin/activate  # if using venv
   python3 app/rebuild_database.py
   ```

3. **Restart the backend:**
   ```bash
   ./start_server.sh
   ```

4. **Verify it worked:**
   ```bash
   curl http://127.0.0.1:8000/list_docs
   ```
   Should show your documents (should have ~70+ documents).

## Why This Happened

The database was likely cleared or corrupted during the restart. This can happen if:
- The database watcher tried to rebuild and failed
- The database file got locked or corrupted
- The database was cleared by accident

## Prevention

After rebuilding, the database watcher should automatically maintain it. But for now, you need to manually rebuild.

## After Rebuild

Once rebuilt, test retrieval:
```bash
curl "http://127.0.0.1:8000/debug/retrieve?question=green%20top%20tubes"
```

Should now show multiple documents being retrieved.

