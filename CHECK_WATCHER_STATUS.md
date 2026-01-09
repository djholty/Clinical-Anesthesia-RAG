# Check Watcher Status

## Current Status

The watchers are **NOT running** in the background. The health endpoint shows:
```json
"watchers": {
    "pdf_watcher": {"running": false},
    "database_watcher": {"running": false}
}
```

## Why They're Not Running

The backend server was started **before** the watcher integration code was added. The watchers only start when the backend starts up (via the `@app.on_event("startup")` handler).

## Solution: Restart the Backend

**Step 1:** Stop the current backend server
- Go to the terminal where `./start_server.sh` is running
- Press `Ctrl+C`

**Step 2:** Restart the backend
```bash
./start_server.sh
```

**Step 3:** Look for these messages in the startup logs:
```
============================================================
Starting file watchers...
============================================================
✅ PDF watcher thread started
✅ Database watcher thread started
============================================================
```

**Step 4:** Verify watchers are running
```bash
curl http://127.0.0.1:8000/health | python3 -m json.tool
```

Should now show:
```json
"watchers": {
    "pdf_watcher": {"running": true},
    "database_watcher": {"running": true}
}
```

## How Watchers Work

- **PDF Watcher**: Monitors `data/pdfs/` for new PDFs, converts them to markdown after a quiet period (120 seconds default)
- **Database Watcher**: Monitors `data/ingested_documents/` for new markdown files, rebuilds the vector database after a quiet period (300 seconds default)

Both run as **daemon threads** inside the backend process, so they:
- Start automatically when backend starts
- Run in the background
- Stop when backend stops
- Don't appear as separate processes

## Check Watcher Status Anytime

```bash
curl http://127.0.0.1:8000/health | python3 -m json.tool | grep -A 5 watchers
```

## Troubleshooting

If watchers show `"running": false` after restart:

1. **Check backend logs** for errors:
   - Look for "Failed to start PDF watcher" or "Failed to start database watcher"
   - Check for import errors or missing dependencies

2. **Check environment variable**:
   ```bash
   echo $ENABLE_FILE_WATCHERS
   ```
   Should be `true` or unset (defaults to true). If set to `false`, watchers won't start.

3. **Check directories exist**:
   ```bash
   ls -la data/pdfs
   ls -la data/ingested_documents
   ```

4. **Manually test watcher imports**:
   ```bash
   python3 -c "from app.pdf_watcher import main; from app.database_watcher import main; print('Imports OK')"
   ```

