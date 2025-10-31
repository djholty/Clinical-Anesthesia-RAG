from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from pydantic import BaseModel
from app.rag_pipeline import query_rag, add_pdf_to_db, list_documents, delete_document
from app.monitoring import get_latest_evaluation, get_all_evaluations, get_evaluation_by_timestamp
import shutil
import os
import sys
from pathlib import Path

# Add monitoring directory to path to import evaluation function
monitoring_path = Path(__file__).parent.parent / "monitoring"
sys.path.insert(0, str(monitoring_path))
from evaluate_rag import run_evaluation

app = FastAPI(title="RAG Model API", version="1.3")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
security = HTTPBasic()

# Global flag to track evaluation status
evaluation_status = {
    "is_running": False,
    "status": "idle",
    "message": "",
    "current_question": 0,
    "total_questions": 0,
    "progress_percent": 0.0
}

class QueryRequest(BaseModel):
    question: str

class DeleteRequest(BaseModel):
    filename: str


@app.get("/")
def home():
    return {"message": "Clinical Anesthesia QA System API is running 🚀"}

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "server": "running",
        "evaluation_status": evaluation_status
    }

@app.post("/ask")
def ask_question(request: QueryRequest):
    """Ask a question to the RAG model."""
    try:
        result = query_rag(request.question)
        return {
            "question": request.question,
            "answer": result["answer"],
            "contexts": result["contexts"]
        }
    except Exception as e:
        error_str = str(e)
        error_lower = error_str.lower()
        
        # Check for API key errors
        if 'api_key' in error_lower or 'authentication' in error_lower or 'invalid api key' in error_lower or '401' in error_str:
            raise HTTPException(
                status_code=401,
                detail="API key error: Your Groq API key may be invalid, expired, or missing. Please check your GROQ_API_KEY environment variable."
            )
        # Check for timeout errors
        elif 'timeout' in error_lower or 'timed out' in error_lower:
            raise HTTPException(
                status_code=504,
                detail="Request timeout: The Groq API took too long to respond. This might indicate the API is slow or unresponsive. Please try again in a moment."
            )
        # Check for over capacity (503)
        elif '503' in error_str or 'over capacity' in error_lower or 'over_capacity' in error_lower:
            raise HTTPException(
                status_code=503,
                detail="API over capacity: The Groq API is currently overloaded. Please try again later with exponential backoff. Check https://groqstatus.com for service status."
            )
        # Check for rate limit / quota exceeded
        elif '429' in error_str or 'rate limit' in error_lower or 'quota' in error_lower or 'usage limit' in error_lower:
            raise HTTPException(
                status_code=429,
                detail="Rate limit or quota exceeded: You may have reached your API usage limit. Please check your Groq account or wait before trying again."
            )
        # Check for other API errors
        elif 'api' in error_lower and ('error' in error_lower or 'failed' in error_lower):
            raise HTTPException(
                status_code=502,
                detail=f"API error: {error_str}. This might be a temporary issue with the Groq API service."
            )
        else:
            # Re-raise as 500 with error message
            raise HTTPException(
                status_code=500,
                detail=f"Error processing question: {error_str}"
            )

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF and add it to the vector database."""
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    chunks_added = add_pdf_to_db(file_path)
    return {
        "filename": file.filename,
        "chunks_added": chunks_added,
        "status": "PDF successfully processed and added to database."
    }

@app.get("/list_docs")
def get_list_of_documents():
    """List all documents currently stored in the vector DB."""
    docs = list_documents()
    return {"documents": docs}

@app.delete("/delete_doc")
def delete_file_docs(request: DeleteRequest):
    """Delete all document chunks from a specific file in Chroma."""
    result = delete_document(request.filename)
    return result

@app.get("/monitoring/latest")
def get_latest_eval():
    """Get the most recent evaluation results."""
    result = get_latest_evaluation()
    if result is None:
        return {"error": "No evaluation results found"}
    return result

@app.get("/monitoring/all")
def get_all_evals():
    """Get summary of all evaluation runs."""
    return {"evaluations": get_all_evaluations()}

@app.get("/monitoring/evaluation_status")
def get_evaluation_status():
    """Get current evaluation status."""
    # Debug: log what we're returning
    print(f"DEBUG: get_evaluation_status called. is_running={evaluation_status.get('is_running')}, status={evaluation_status.get('status')}")
    # Ensure all required keys exist (defensive programming)
    result = {
        "is_running": evaluation_status.get("is_running", False),
        "status": evaluation_status.get("status", "idle"),
        "message": evaluation_status.get("message", ""),
        "current_question": evaluation_status.get("current_question", 0),
        "total_questions": evaluation_status.get("total_questions", 0),
        "progress_percent": evaluation_status.get("progress_percent", 0.0)
    }
    print(f"DEBUG: Returning status: {result}")
    return result

@app.get("/monitoring/{timestamp}")
def get_eval_by_timestamp(timestamp: str):
    """Get specific evaluation by timestamp."""
    result = get_evaluation_by_timestamp(timestamp)
    if result is None:
        return {"error": f"Evaluation not found for timestamp: {timestamp}"}
    return result

def run_evaluation_task():
    """Background task to run evaluation."""
    global evaluation_status
    
    # Ensure status is set at the very start (redundant but safe)
    print(f"DEBUG: run_evaluation_task starting. Current status: is_running={evaluation_status.get('is_running')}")
    evaluation_status["is_running"] = True
    evaluation_status["status"] = "running"
    evaluation_status["current_question"] = 0
    evaluation_status["total_questions"] = 0
    evaluation_status["progress_percent"] = 0.0
    evaluation_status["message"] = "Loading questions and initializing..."
    print(f"DEBUG: Status set to running. is_running={evaluation_status.get('is_running')}")
    
    def progress_callback(current, total):
        """Callback to update progress status."""
        global evaluation_status
        evaluation_status["current_question"] = current
        evaluation_status["total_questions"] = total
        if total > 0:
            evaluation_status["progress_percent"] = (current / total) * 100
            evaluation_status["message"] = f"Processing question {current} of {total} ({evaluation_status['progress_percent']:.1f}%)"
        
        # Debug: print progress to console
        print(f"API Progress Callback: {current}/{total} ({evaluation_status['progress_percent']:.1f}%) - is_running={evaluation_status.get('is_running')}")
    
    try:
        
        # Get paths relative to the monitoring directory
        script_dir = monitoring_path
        prompt_file = script_dir / "prompt_set.xlsx"
        
        if not prompt_file.exists():
            evaluation_status["is_running"] = False
            evaluation_status["status"] = "error"
            evaluation_status["message"] = f"Error: Could not find {prompt_file}"
            return
        
        # Create timestamped output file
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        eval_dir = script_dir / "evaluations"
        eval_dir.mkdir(exist_ok=True)
        output_file = eval_dir / f"evaluation_{timestamp}.csv"
        
        # Also save as latest
        latest_file = script_dir / "evaluation_results.csv"
        
        # Run evaluation with progress callback (returns tuple: (results, avg_score))
        results, avg_score = run_evaluation(str(prompt_file), str(output_file), progress_callback=progress_callback)
        
        if results is None:
            evaluation_status["is_running"] = False
            evaluation_status["status"] = "error"
            evaluation_status["message"] = "Evaluation failed: Could not load questions or process evaluation"
            return
        
        # Copy to latest file
        shutil.copy(str(output_file), str(latest_file))
        
        evaluation_status["is_running"] = False
        evaluation_status["status"] = "completed"
        evaluation_status["progress_percent"] = 100.0
        evaluation_status["message"] = f"Evaluation completed successfully! Average score: {avg_score:.2f}/4. Saved to {output_file.name}"
        
    except Exception as e:
        evaluation_status["is_running"] = False
        evaluation_status["status"] = "error"
        evaluation_status["message"] = f"Error during evaluation: {str(e)}"

@app.post("/monitoring/trigger_evaluation")
def trigger_evaluation(background_tasks: BackgroundTasks):
    """Trigger a new evaluation run."""
    global evaluation_status
    
    try:
        print(f"DEBUG: trigger_evaluation called. Current is_running={evaluation_status.get('is_running')}")
        if evaluation_status.get("is_running", False):
            return {
                "status": "error",
                "message": "Evaluation is already running. Please wait for it to complete."
            }
        
        # Set initial status BEFORE starting background task to avoid race condition
        evaluation_status["is_running"] = True
        evaluation_status["status"] = "running"
        evaluation_status["current_question"] = 0
        evaluation_status["total_questions"] = 0
        evaluation_status["progress_percent"] = 0.0
        evaluation_status["message"] = "Starting evaluation..."
        print(f"DEBUG: Status set in trigger_evaluation. is_running={evaluation_status.get('is_running')}")
        
        # Start evaluation in background
        background_tasks.add_task(run_evaluation_task)
        print(f"DEBUG: Background task added. Status should be: is_running={evaluation_status.get('is_running')}")
        
        return {
            "status": "started",
            "message": "Evaluation started in background. Check status endpoint for updates."
        }
    except Exception as e:
        # Reset status on error
        evaluation_status["is_running"] = False
        evaluation_status["status"] = "error"
        evaluation_status["message"] = f"Failed to start evaluation: {str(e)}"
        return {
            "status": "error",
            "message": f"Failed to start evaluation: {str(e)}"
        }


# ==========================
# Admin Page and Uploads
# ==========================

def _require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """HTTP Basic auth for admin endpoints.
    Uses ADMIN_USERNAME (default: 'admin') and ADMIN_PASSWORD env vars.
    """
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "")
    # If no password configured, allow open access
    if not admin_pass:
        return True
    user_ok = secrets.compare_digest(credentials.username, admin_user)
    pass_ok = secrets.compare_digest(credentials.password, admin_pass)
    if not (user_ok and pass_ok):
        # Trigger browser basic auth prompt
        raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Basic"})
    return True


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, _: bool = Depends(_require_admin)):
    """Render the administrative dashboard with monitoring and upload."""
    return templates.TemplateResponse("admin.html", {"request": request})


def _maybe_convert_pdf_to_markdown(pdf_path: str):
    """Optionally convert a saved PDF to markdown if enabled.

    Controlled by env var ENABLE_PDF_CONVERSION ("true"/"false").
    Requires OPENAI_API_KEY and docling/openai packages to be available.
    """
    enable = os.getenv("ENABLE_PDF_CONVERSION", "false").lower() == "true"
    if not enable:
        return
    try:
        # Import lazily to avoid hard dependency if user doesn't enable it
        from app.extract_pdf_to_markdown import convert_pdf_to_markdown
        success, _msg = convert_pdf_to_markdown(pdf_path)
        # No raise on failure; conversion errors should not break upload
        _ = success
    except Exception:
        # Silent fail – admin page will still report successful upload
        pass


@app.post("/admin/upload", response_class=HTMLResponse)
async def admin_upload_pdf(request: Request, file: UploadFile = File(...), background_tasks: BackgroundTasks = None, _: bool = Depends(_require_admin)):
    """Upload a PDF to data/pdfs. Optionally trigger background conversion to markdown."""
    try:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")

        pdfs_dir = Path("./data/pdfs")
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        dest_path = pdfs_dir / file.filename

        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Optionally convert to markdown in background
        if background_tasks is not None:
            background_tasks.add_task(_maybe_convert_pdf_to_markdown, str(dest_path))

        # Redirect back to admin with success flag
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "upload_success": True,
                "uploaded_filename": file.filename,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

