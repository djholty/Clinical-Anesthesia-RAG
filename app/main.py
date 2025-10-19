from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from app.rag_pipeline import query_rag, add_pdf_to_db, list_documents, delete_document
import shutil
import os

app = FastAPI(title="RAG Model API", version="1.3")

class QueryRequest(BaseModel):
    question: str

class DeleteRequest(BaseModel):
    filename: str


@app.get("/")
def home():
    return {"message": "Clinical Anesthesia QA System API is running 🚀"}

@app.post("/ask")
def ask_question(request: QueryRequest):
    """Ask a question to the RAG model."""
    answer = query_rag(request.question)
    return {"question": request.question, "answer": answer}

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
