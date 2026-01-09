# Rebuild Database Now

## Current Status
- ✅ Watchers are running
- ❌ Database is empty (no documents indexed)
- ✅ You have 74 markdown files ready to be indexed

## Problem
The database exists but is empty. The watchers are running but won't automatically rebuild unless files change (and then wait 5 minutes).

## Solution: Trigger Immediate Rebuild

### Option 1: Wait for Watcher (5 minutes)
I just touched a markdown file. The database watcher will:
1. Detect the change
2. Wait 5 minutes (quiet period)
3. Automatically rebuild the database

**Check backend logs** for:
```
📝 Markdown file modified: 01_Stoelting.md
⏳ Started quiet period timer (300s) for rebuild
🔄 Starting automatic database rebuild... (after 5 min)
✅ Automatic database rebuild completed successfully
```

### Option 2: Manual Rebuild (Fastest - ~2 minutes)

**Step 1:** Stop the backend
- Press `Ctrl+C` in the terminal running the backend

**Step 2:** Rebuild the database
```bash
./rebuild_db.sh
```

Or manually:
```bash
source .venv/bin/activate  # if using venv
python3 app/rebuild_database.py
```

**Step 3:** Restart the backend
```bash
./start_server.sh
```

**Step 4:** Verify
```bash
curl http://127.0.0.1:8000/list_docs
```

Should show your documents instead of empty array.

### Option 3: Rebuild on Next Startup

**Step 1:** Stop the backend

**Step 2:** Set environment variable and restart
```bash
export REBUILD_ON_STARTUP=true
./start_server.sh
```

This will rebuild when backend starts, then you can unset the variable.

## Verify Database is Populated

After rebuild, check:
```bash
curl http://127.0.0.1:8000/list_docs
```

Should return:
```json
{"documents": ["01_Stoelting.md", "02_Stoelting.md", ...]}
```

Then test a question:
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is anesthesia?"}'
```

Should return an answer with contexts instead of "insufficient information".

## Why This Happened

The database file exists (134MB) but is empty. This can happen if:
- Database was cleared but not rebuilt
- Database was corrupted
- Database was created but never populated

The watchers are now running and will automatically rebuild when files change, but for the initial population, you need to trigger a rebuild manually or wait for the watcher.

