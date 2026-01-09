# Fix: Information Retrieval Not Working

## Problem Identified

The retriever is only returning **1 document** and it's the **wrong document**. When asking about "test tubes" or "green top tubes", it returns "28_Stoelting.md" (about drug half-lives) instead of "BloodWorkCollection.md".

## Root Causes

1. **Retriever only getting 1 result**: The backend hasn't been restarted, so the `RETRIEVER_K` setting (now default 8) isn't active
2. **Semantic search mismatch**: The embedding model isn't matching "test tubes" well with "Green Top Tubes", "Red Top Tubes", etc.
3. **Short document issue**: BloodWorkCollection.md is only 19 lines, so it might not be ranking high in similarity search

## Solutions

### Solution 1: Restart Backend (Required)

The retriever changes won't take effect until you restart:

1. **Stop the backend** (Ctrl+C)
2. **Start it again**: `./start_server.sh`
3. **Test again** - should now retrieve 8 documents instead of 1

### Solution 2: Increase Retrieval Count

The default is now 8 documents. You can increase it further by setting in `.env`:
```
RETRIEVER_K=12
```

### Solution 3: Use More Specific Queries

Try queries that match the document terminology:
- "What are green top tubes used for?" 
- "What tests go in purple top tubes?"
- "blood collection tubes" (instead of "test tubes")
- "Sodium Potassium Chloride" (specific test names from the document)

### Solution 4: Check What's Actually Retrieved

Use the debug endpoint to see what's being retrieved:
```bash
curl "http://127.0.0.1:8000/debug/retrieve?question=your%20question"
```

This shows:
- How many documents are retrieved
- Which documents are retrieved
- Preview of content

## Testing After Fix

1. Restart backend
2. Test with debug endpoint:
   ```bash
   curl "http://127.0.0.1:8000/debug/retrieve?question=green%20top%20tubes"
   ```
3. Should now show multiple documents, hopefully including BloodWorkCollection.md
4. If BloodWorkCollection.md still isn't in top results, try more specific queries

## Why This Happens

Semantic search uses embeddings to find similar content. The issue is:
- "test tubes" might not embed similarly to "Green Top Tubes"
- Short documents (19 lines) might have lower similarity scores
- The embedding model might prioritize longer, more detailed documents

Increasing `RETRIEVER_K` helps by retrieving more candidates, giving the LLM more context to work with.

