# Clinical-Anesthesia-QA-System-using-RAG-and-LLMs
An AI assistant for anesthesia knoweldge using retrieval-augmented generation and LLMs to answer clinical questions
## Admin Page

- Start API: 
  - **Recommended:** `./start_server.sh` (excludes .venv and other non-source files from watching)
  - **Or manually:** `uvicorn app.main:app --reload --reload-exclude '.venv/*' --reload-exclude '__pycache__/*'`
- Open admin: `http://127.0.0.1:8000/admin`
  - Monitor evaluation status (auto-refreshes every 2s)
  - Trigger evaluations
  - Upload PDFs to `data/pdfs`

Optional automatic PDF→Markdown conversion:

```
export ENABLE_PDF_CONVERSION=true
export OPENAI_API_KEY=your_key
```

If not enabled, run your own PDF watcher or converter (e.g., `watchmedo` with `app/extract_pdf_to_markdown.py`) so that saved PDFs are converted into Markdown in `data/ingested_documents`, which then triggers the DB rebuild via the existing watcher.

## Watchers (Quiet Period Flow)

To achieve: Upload PDF → (quiet A) → Convert to .md → (quiet B) → Rebuild DB

1) PDF Watcher (waits, then converts):
```
export PDF_WATCH_DIRECTORY=./data/pdfs
export MD_OUTPUT_DIR=./data/ingested_documents
export PDF_QUIET_PERIOD_SECONDS=120
python3 app/pdf_watcher.py
```

2) Database Watcher (waits, then rebuilds DB):
```
export WATCH_DIRECTORY=./data/ingested_documents
export MARKDOWN_DIR=./data/ingested_documents
export DB_DIR=./data/chroma_db
export QUIET_PERIOD_SECONDS=300
python3 app/database_watcher.py
```

Notes:
- Run both watchers to chain conversion then rebuild.
- In Docker, mount `/app/data` for persistence.
The goal is to make an intelligent system that could help an anesthesiologist ask clinical questions and retrieve accurate and context aware answers.
---

## Project Overview
-Collect anesthesia-related documents as knoweldge base.  
-Use a **retriever** to fetch relevant document chunks.

---

## Tech Stack
-**Python**  
-**LangChain / LlamaIndex** (for RAG pipeline)

--
