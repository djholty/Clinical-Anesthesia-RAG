# Quick Start Guide

This guide will help you get the Clinical Anesthesia QA System up and running quickly, both locally and with Docker.

## Prerequisites

- Python 3.9+ installed
- Docker and Docker Compose (for Docker setup)
- API keys:
  - `GROQ_API_KEY` (for LLM)
  - `OPENAI_API_KEY` (optional, for PDF conversion)
  - `HF_TOKEN` (optional, for authenticated HuggingFace models)

## Local Setup

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy sample environment file
cp sample.env .env

# Edit .env with your API keys
# Required: GROQ_API_KEY
# Optional: OPENAI_API_KEY, HF_TOKEN
```

### 3. Start Services

You'll need **4 terminal windows** to run all services locally:

#### Terminal 1: FastAPI Backend
```bash
# Activate virtual environment if not already active
source .venv/bin/activate

# Start FastAPI server
./start_server.sh

# Or manually:
uvicorn app.main:app --reload --reload-exclude '.venv/*' --reload-exclude '__pycache__/*' --host 127.0.0.1 --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

**Access:**
- API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs
- Admin Page: http://127.0.0.1:8000/admin

#### Terminal 2: Streamlit Frontend
```bash
# Activate virtual environment if not already active
source .venv/bin/activate

# Start Streamlit
streamlit run app_main.py --server.port=8501 --server.address=127.0.0.1
```

**Expected output:**
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
Network URL: http://0.0.0.0:8501
```

**Note:** Even though Streamlit may display `http://0.0.0.0:8501`, use **`http://127.0.0.1:8501`** or **`http://localhost:8501`** to access the app. The `0.0.0.0` address is just Streamlit's internal binding display.

**Access:** http://127.0.0.1:8501 (or http://localhost:8501)

#### Terminal 3: PDF Watcher (Monitors PDFs)
```bash
# Activate virtual environment if not already active
source .venv/bin/activate

# Optional: Set environment variables (or use defaults)
export PDF_WATCH_DIRECTORY=./data/pdfs
export MD_OUTPUT_DIR=./data/ingested_documents
export PDF_QUIET_PERIOD_SECONDS=120

# Start PDF watcher
python3 app/pdf_watcher.py
```

**What it does:**
- Watches `./data/pdfs` for new/updated PDF files
- After 120 seconds of no changes (quiet period), converts PDFs to Markdown
- Saves converted Markdown files to `./data/ingested_documents`

**Expected output:**
```
============================================================
   PDF WATCHER SERVICE
============================================================
   Watch Directory: ./data/pdfs
   Markdown Output: ./data/ingested_documents
   Quiet Period: 120 seconds
============================================================
👀 Watching directory: ./data/pdfs
   Waiting for PDF changes...
   Press Ctrl+C to stop
```

#### Terminal 4: Database Watcher (Monitors Markdown Files)
```bash
# Activate virtual environment if not already active
source .venv/bin/activate

# Optional: Set environment variables (or use defaults)
export WATCH_DIRECTORY=./data/ingested_documents
export MARKDOWN_DIR=./data/ingested_documents
export DB_DIR=./data/chroma_db
export QUIET_PERIOD_SECONDS=300

# Start database watcher
python3 app/database_watcher.py
```

**What it does:**
- Watches `./data/ingested_documents` for new/updated Markdown files
- After 300 seconds (5 minutes) of no changes (quiet period), rebuilds the ChromaDB vector database
- This ensures the RAG system has the latest documents indexed

**Expected output:**
```
============================================================
   DATABASE WATCHER SERVICE
============================================================
Configuration:
   Watch Directory: ./data/ingested_documents
   Markdown Directory: ./data/ingested_documents
   Database Directory: ./data/chroma_db
   Quiet Period: 300 seconds (5.0 minutes)
   Rebuild on Startup: false
============================================================
👀 Watching directory: ./data/ingested_documents
   Waiting for markdown file changes...
   Press Ctrl+C to stop
```

### 4. Workflow

The watchers create an automated pipeline:

1. **Upload PDF** → Place PDF in `./data/pdfs/`
2. **PDF Watcher** → Detects PDF, waits 120 seconds (quiet period), converts to Markdown
3. **Markdown saved** → File appears in `./data/ingested_documents/`
4. **Database Watcher** → Detects new Markdown, waits 300 seconds (quiet period), rebuilds ChromaDB
5. **RAG ready** → New documents are now searchable in the QA system

### 5. Verify Everything is Working

1. **Check FastAPI health:**
   ```bash
   curl http://127.0.0.1:8000/health
   ```
   Should return: `{"status":"healthy","server":"running",...}`

2. **Check Streamlit:**
   - Open http://127.0.0.1:8501 in your browser
   - You should see the "Clinical Anesthesia QA System" interface

3. **Test a question:**
   - In Streamlit, go to "💬 Ask Questions" tab
   - Enter a question like "What is anesthesia?"
   - You should get an answer with citations

## Docker Setup

### 1. Configure Environment

```bash
# Copy sample environment file
cp sample.env .env

# Edit .env with your API keys
# Required: GROQ_API_KEY
# Optional: OPENAI_API_KEY, HF_TOKEN
```

### 2. Start All Services with Docker Compose

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode (background)
docker-compose up -d --build
```

This starts **4 services automatically:**
- **backend**: FastAPI server (port 8000)
- **frontend**: Streamlit app (port 8501)
- **watcher**: Database watcher (monitors markdown files)
- **pdf_watcher**: PDF watcher (monitors PDF files)

### 3. Access Services

- **Streamlit Frontend**: http://localhost:8501
- **FastAPI Backend**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Admin Page**: http://localhost:8000/admin

### 4. View Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f watcher
docker-compose logs -f pdf_watcher
```

### 5. Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

## Quick Reference

### Local Commands

| Service | Command | Port | Access URL |
|---------|---------|------|------------|
| FastAPI Backend | `./start_server.sh` | 8000 | http://127.0.0.1:8000 |
| Streamlit Frontend | `streamlit run app_main.py --server.port=8501 --server.address=127.0.0.1` | 8501 | http://127.0.0.1:8501 |
| PDF Watcher | `python3 app/pdf_watcher.py` | N/A | N/A |
| Database Watcher | `python3 app/database_watcher.py` | N/A | N/A |

### Docker Commands

| Action | Command |
|--------|---------|
| Start all services | `docker-compose up --build` |
| Start in background | `docker-compose up -d --build` |
| Stop services | `docker-compose down` |
| View logs | `docker-compose logs -f` |
| Restart service | `docker-compose restart <service-name>` |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | Required | API key for Groq LLM |
| `OPENAI_API_KEY` | Optional | For PDF conversion |
| `HF_TOKEN` | Optional | For authenticated HuggingFace models |
| `PDF_WATCH_DIRECTORY` | `./data/pdfs` | Directory to watch for PDFs |
| `MD_OUTPUT_DIR` | `./data/ingested_documents` | Output directory for Markdown |
| `PDF_QUIET_PERIOD_SECONDS` | `120` | Seconds to wait before converting PDF |
| `WATCH_DIRECTORY` | `./data/ingested_documents` | Directory to watch for Markdown |
| `DB_DIR` | `./data/chroma_db` | ChromaDB directory |
| `QUIET_PERIOD_SECONDS` | `300` | Seconds to wait before rebuilding DB |

## Troubleshooting

### FastAPI Server Won't Start

- **Check if port 8000 is in use:**
  ```bash
  lsof -i :8000
  ```
- **Check virtual environment is activated:**
  ```bash
  which python  # Should show .venv path
  ```

### Streamlit Won't Start

- **Check if port 8501 is in use:**
  ```bash
  lsof -i :8501
  ```
- **Check API connection:**
  - Ensure FastAPI server is running
  - Check `API_URL` in Streamlit matches FastAPI URL

### Watchers Not Working

- **Check directories exist:**
  ```bash
  ls -la data/pdfs
  ls -la data/ingested_documents
  ```
- **Check environment variables:**
  ```bash
  echo $PDF_WATCH_DIRECTORY
  echo $WATCH_DIRECTORY
  ```
- **Check logs for errors:**
  - PDF watcher logs will show conversion errors
  - Database watcher logs will show rebuild errors

### Docker Issues

- **Build fails:**
  - Check `.env` file exists and has required values
  - Check Docker is running: `docker ps`

- **Container exits immediately:**
  ```bash
  docker-compose logs <service-name>
  ```

- **Port conflicts:**
  - Modify port mappings in `docker-compose.yml` if ports are in use

- **Permission errors:**
  - Ensure Docker has access to mounted directories
  - On Linux/Mac, may need to adjust directory permissions

## Next Steps

1. **Upload PDFs:**
   - Place PDF files in `./data/pdfs/` (local) or upload via Admin page
   - Wait for automatic conversion and indexing

2. **Ask Questions:**
   - Use the Streamlit interface to ask clinical questions
   - View answers with citations and source chunks

3. **Monitor Performance:**
   - Access Admin page in Streamlit
   - View evaluation metrics and historical trends
   - Run manual assessments

4. **Customize:**
   - Adjust quiet periods in environment variables
   - Modify chunk sizes in `app/rag_pipeline.py`
   - Update prompts in the RAG pipeline

## Support

For more detailed information, see:
- `README.md` - Full project documentation
- `app/main.py` - FastAPI endpoints
- `app_main.py` - Streamlit application
- `app/rag_pipeline.py` - RAG pipeline implementation

