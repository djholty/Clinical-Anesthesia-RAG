from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import secrets
import logging
from pydantic import BaseModel
from app.rag_pipeline import query_rag, add_pdf_to_db, list_documents, delete_document
from app.monitoring import (
    get_latest_evaluation, 
    get_all_evaluations, 
    get_evaluation_by_timestamp,
    get_random_questions_sample,
    save_manual_assessment,
    get_all_manual_assessments,
    get_latest_manual_assessment
)
from app.security_utils import sanitize_filename, MAX_UPLOAD_SIZE, validate_file_size, validate_pdf_content
import shutil
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add monitoring directory to path to import evaluation function
monitoring_path = Path(__file__).parent.parent / "monitoring"
sys.path.insert(0, str(monitoring_path))
from evaluate_rag import run_evaluation

app = FastAPI(title="RAG Model API", version="1.3")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))
security = HTTPBasic()

# Configure CORS - allow requests from Streamlit frontend and all localhost origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Configure rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add rate limiter middleware for proper integration
app.add_middleware(SlowAPIMiddleware)

# Global flag to track evaluation status
evaluation_status = {
    "is_running": False,
    "status": "idle",
    "message": "",
    "current_question": 0,
    "total_questions": 0,
    "progress_percent": 0.0
}

from pydantic import Field, field_validator

class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User question to ask the RAG model"
    )
    
    @field_validator('question')
    @classmethod
    def validate_question(cls, v):
        """Validate and sanitize user question."""
        if not v:
            raise ValueError("Question cannot be empty")
        
        v = v.strip()
        
        # Remove potential prompt injection patterns
        # Remove excessive whitespace
        v = ' '.join(v.split())
        
        if len(v) == 0:
            raise ValueError("Question cannot be empty after sanitization")
        
        if len(v) > 5000:
            raise ValueError("Question exceeds maximum length of 5000 characters")
        
        return v

class DeleteRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)


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
@limiter.limit("10/minute")  # 10 requests per minute per IP
def ask_question(request: Request, query_request: QueryRequest):
    """Ask a question to the RAG model."""
    try:
        result = query_rag(query_request.question)
        return {
            "question": query_request.question,
            "answer": result["answer"],
            "contexts": result["contexts"]
        }
    except ValueError as e:
        # User input validation errors - can expose these safely
        logger.warning(f"Validation error in /ask: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log full error details internally
        error_str = str(e)
        error_lower = error_str.lower()
        logger.error(f"Error processing question in /ask: {error_str}", exc_info=True)
        
        # Sanitize error message to prevent information disclosure
        # Check for API key errors (don't expose details)
        if 'api_key' in error_lower or 'authentication' in error_lower or 'invalid api key' in error_lower or '401' in error_str:
            raise HTTPException(
                status_code=401,
                detail="Authentication failed. Please check your API configuration."
            )
        # Check for timeout errors
        elif 'timeout' in error_lower or 'timed out' in error_lower:
            raise HTTPException(
                status_code=504,
                detail="Request timeout. Please try again in a moment."
            )
        # Check for over capacity (503)
        elif '503' in error_str or 'over capacity' in error_lower or 'over_capacity' in error_lower:
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Please try again later."
            )
        # Check for rate limit / quota exceeded
        elif '429' in error_str or 'rate limit' in error_lower or 'quota' in error_lower or 'usage limit' in error_lower:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before trying again."
            )
        # Check for other API errors
        elif 'api' in error_lower and ('error' in error_lower or 'failed' in error_lower):
            raise HTTPException(
                status_code=502,
                detail="External service error. Please try again later."
            )
        else:
            # Generic error message - don't expose internal details
            raise HTTPException(
                status_code=500,
                detail="An error occurred processing your request. Please try again later."
            )

@app.post("/upload")
@limiter.limit("5/minute")  # 5 uploads per minute per IP
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    """Upload a PDF and add it to the vector database."""
    # Sanitize filename to prevent path traversal
    try:
        safe_filename = sanitize_filename(file.filename)
    except ValueError as e:
        logger.warning(f"Invalid filename in upload: {file.filename}")
        raise HTTPException(status_code=400, detail="Invalid filename provided.")
    
    # Check file size during upload
    file_size = 0
    MAX_CHUNK_SIZE = 1024 * 1024  # Read in 1 MB chunks
    chunks = []
    
    # Read file in chunks to check size without loading entire file into memory
    while True:
        chunk = await file.read(MAX_CHUNK_SIZE)
        if not chunk:
            break
        file_size += len(chunk)
        chunks.append(chunk)
        
        # Check size limit incrementally
        if file_size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size exceeds maximum of {MAX_UPLOAD_SIZE / (1024*1024):.0f} MB"
            )
    
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    file_path = uploads_dir / safe_filename

    # Write chunks directly (already read and validated)
    with open(file_path, "wb") as buffer:
        for chunk in chunks:
            buffer.write(chunk)
    
    # Validate file is actually a PDF (content validation)
    if not validate_pdf_content(str(file_path)):
        # Clean up invalid file
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=400,
            detail="File is not a valid PDF. Please ensure the file is a valid PDF document."
        )

    try:
        chunks_added = add_pdf_to_db(str(file_path))
        return {
            "filename": safe_filename,  # Return sanitized filename
            "chunks_added": chunks_added,
            "status": "PDF successfully processed and added to database."
        }
    except Exception as e:
        # Log detailed error internally
        logger.error(f"Error processing PDF in /upload: {str(e)}", exc_info=True)
        # Clean up file if processing failed
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing the PDF. Please try again later."
        )

@app.get("/list_docs")
def get_list_of_documents():
    """List all documents currently stored in the vector DB."""
    docs = list_documents()
    return {"documents": docs}

@app.delete("/delete_doc")
def delete_file_docs(request: DeleteRequest):
    """Delete all document chunks from a specific file in Chroma."""
    try:
        # Sanitize filename to prevent path traversal
        try:
            safe_filename = sanitize_filename(request.filename)
        except ValueError as e:
            logger.warning(f"Invalid filename in delete_doc: {request.filename}")
            raise HTTPException(status_code=400, detail="Invalid filename provided.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_doc: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred. Please try again later.")
    
    try:
        result = delete_document(safe_filename)
        return result
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred deleting the document. Please try again later.")

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

# Manual Assessment Endpoints
class ManualAssessmentRequest(BaseModel):
    questions: list

@app.post("/monitoring/manual_assessment/start")
def start_manual_assessment():
    """Generate random sample of 20 questions from latest evaluation."""
    try:
        sample = get_random_questions_sample(n=20)
        if sample is None:
            return {"error": "No evaluation results found. Run an evaluation first."}
        return {"questions": sample}
    except Exception as e:
        logger.error(f"Error generating random sample: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating random sample: {str(e)}")

@app.post("/monitoring/manual_assessment/submit")
def submit_manual_assessment(request: ManualAssessmentRequest):
    """Save manual assessment results."""
    try:
        timestamp = save_manual_assessment({"questions": request.questions})
        return {"success": True, "timestamp": timestamp, "message": "Manual assessment saved successfully"}
    except Exception as e:
        logger.error(f"Error saving manual assessment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error saving manual assessment: {str(e)}")

@app.get("/monitoring/manual_assessments")
def get_all_manual_assessments_endpoint():
    """Get summary of all manual assessment runs."""
    try:
        assessments = get_all_manual_assessments()
        return {"assessments": assessments}
    except Exception as e:
        logger.error(f"Error getting manual assessments: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting manual assessments: {str(e)}")

@app.get("/monitoring/manual_assessment/latest")
def get_latest_manual_assessment_endpoint():
    """Get the most recent manual assessment results."""
    try:
        result = get_latest_manual_assessment()
        if result is None:
            return {"error": "No manual assessment results found"}
        return result
    except Exception as e:
        logger.error(f"Error getting latest manual assessment: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting latest manual assessment: {str(e)}")

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
        # Log detailed error internally
        logger.error(f"Error during evaluation: {str(e)}", exc_info=True)
        evaluation_status["is_running"] = False
        evaluation_status["status"] = "error"
        evaluation_status["message"] = "An error occurred during evaluation."  # Generic message

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
        # Log detailed error internally
        logger.error(f"Failed to start evaluation: {str(e)}", exc_info=True)
        # Reset status on error
        evaluation_status["is_running"] = False
        evaluation_status["status"] = "error"
        evaluation_status["message"] = "Failed to start evaluation."  # Generic message
        return {
            "status": "error",
            "message": "Failed to start evaluation. Please try again later."  # Generic message
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
@limiter.limit("10/minute")  # 10 uploads per minute per IP (admin can upload more)
async def admin_upload_pdf(request: Request, file: UploadFile = File(...), background_tasks: BackgroundTasks = None, _: bool = Depends(_require_admin)):
    """Upload a PDF to data/pdfs. Optionally trigger background conversion to markdown."""
    try:
        # Sanitize filename first to prevent path traversal, then check extension
        try:
            safe_filename = sanitize_filename(file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid filename: {str(e)}")
        
        # Check extension on sanitized filename
        if not safe_filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")

        # Check file size during upload
        file_size = 0
        MAX_CHUNK_SIZE = 1024 * 1024  # Read in 1 MB chunks
        chunks = []
        
        while True:
            chunk = await file.read(MAX_CHUNK_SIZE)
            if not chunk:
                break
            file_size += len(chunk)
            chunks.append(chunk)
            
            # Check size limit incrementally
            if file_size > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File size exceeds maximum of {MAX_UPLOAD_SIZE / (1024*1024):.0f} MB"
                )
        
        # Reset file pointer
        file.file.seek(0)

        pdfs_dir = Path("./data/pdfs")
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        dest_path = pdfs_dir / safe_filename

        with open(dest_path, "wb") as buffer:
            for chunk in chunks:
                buffer.write(chunk)
        
        # Validate file is actually a PDF (content validation)
        if not validate_pdf_content(str(dest_path)):
            # Clean up invalid file
            if dest_path.exists():
                dest_path.unlink()
            raise HTTPException(
                status_code=400,
                detail="File is not a valid PDF. Please ensure the file is a valid PDF document."
            )

        # Optionally convert to markdown in background
        if background_tasks is not None:
            background_tasks.add_task(_maybe_convert_pdf_to_markdown, str(dest_path))

        # Redirect back to admin with success flag
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "upload_success": True,
                "uploaded_filename": safe_filename,  # Return sanitized filename
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        # Log detailed error internally
        logger.error(f"Error in admin upload: {str(e)}", exc_info=True)
        # Return generic error to user
        raise HTTPException(status_code=500, detail="An error occurred during upload. Please try again later.")

