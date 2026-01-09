# Fix: Retriever Only Returning 1 Document

## Problem
- Database is populated (76 documents, 9402 chunks) ✅
- Retriever is configured for `k=8` ✅  
- But only returning **1 document** ❌
- Always the same wrong document (28_Stoelting.md) ❌

## Root Cause
The retriever might have a default score threshold or Chroma is filtering results. The configuration needs to explicitly disable score filtering.

## Fix Applied
Updated retriever configuration to:
```python
retriever = vectordb.as_retriever(
    search_kwargs={
        "k": RETRIEVER_K,
        "score_threshold": None  # Don't filter by score threshold
    }
)
```

## Action Required

**Restart the backend** to apply the fix:

1. Stop backend (Ctrl+C)
2. Start again: `./start_server.sh`
3. Test retrieval:
   ```bash
   curl "http://127.0.0.1:8000/debug/retrieve?question=green%20top%20tubes"
   ```

Should now return 8 documents instead of 1.

## About the Double Rebuild

The database watcher rebuilt the database on startup because `REBUILD_ON_STARTUP` was set to `true` (or defaulted to true). This is actually fine - it ensures the database is always up to date. But if you want to disable it:

Set in `.env`:
```
REBUILD_ON_STARTUP=false
```

Or in docker-compose.yml it defaults to `false`, so the double rebuild won't happen in Docker.

## Expected Behavior After Fix

After restart, queries should:
- Return 8 documents (configurable via RETRIEVER_K)
- Include relevant documents like BloodWorkCollection.md when appropriate
- Show better semantic matching

