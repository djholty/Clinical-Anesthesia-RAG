import os
import time
import re
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import re as _re
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv

# === Load Environment Variables ===
load_dotenv()

# === Initialize components ===
hf_token = os.getenv("HF_TOKEN")
groq_api_key = os.getenv("GROQ_API_KEY")

# Set environment variables for libraries that need them
if hf_token:
    os.environ["HF_TOKEN"] = hf_token
if groq_api_key:
    os.environ["GROQ_API_KEY"] = groq_api_key

# Get embedding model from environment or default to current model
# Strip quotes in case user added them in .env file
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip().strip("'\"")
# Initialize embeddings
# HuggingFaceEmbeddings will automatically use HF_TOKEN from environment if needed
# Public models like all-MiniLM-L6-v2 don't require a token
# Gated models (e.g., NeuML/pubmedbert-base-embeddings) require HF_TOKEN to be set
try:
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
except Exception as e:
    error_msg = str(e).lower()
    # Check for authentication errors
    if "401" in error_msg or "unauthorized" in error_msg or "authentication" in error_msg:
        raise ValueError(
            f"Authentication failed for model '{EMBEDDING_MODEL}'. "
            "This model requires a valid HF_TOKEN. "
            "Please set HF_TOKEN in your .env file with a valid HuggingFace token. "
            "Get your token at: https://huggingface.co/settings/tokens\n"
            f"Original error: {str(e)}"
        )
    # Re-raise other errors as-is
    raise

# Persistent DB directory (can be overridden via env DB_DIR)
DB_DIR = os.getenv("DB_DIR", "./data/chroma_db")
vectordb = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)

# Configure retriever with search parameters
# Retrieve more documents to improve recall, especially for short documents
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "5"))  # Number of documents to retrieve (default: 5)
retriever = vectordb.as_retriever(
    search_kwargs={"k": RETRIEVER_K}
)

# LLM (Groq) - Configure with timeout
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    timeout=25.0,  # 25 second timeout to prevent hanging
    max_retries=2  # Limit retries to prevent long waits
)

# Prompt Template
prompt = ChatPromptTemplate.from_template("""
You are a clinical anesthesia assistant designed to help anesthesiologists with evidence-based clinical decision support. Your role is to provide accurate, well-cited information based on the clinical guidelines and medical literature in your knowledge base.

## Instructions:
1. **Evidence-Based Responses**: Base your answer STRICTLY on the provided context. Do not use any external knowledge or make assumptions beyond what is explicitly stated in the context.

2. **Source Citations**: 
   - ALWAYS cite your sources using the format: [Source: filename]
   - Include citations for each piece of information you reference
   - If information comes from multiple sources, cite each one

3. **Clinical Accuracy**:
   - Use appropriate medical terminology
   - Be precise and specific with clinical information
   - If the context provides specific dosages, protocols, or guidelines, cite them accurately

4. **Uncertainty Handling**:
   - If the provided context does not contain sufficient information to answer the question, clearly state: "The available context does not provide sufficient information to answer this question."
   - Do not speculate or make up information

5. **Patient Safety**:
   - Emphasize patient safety considerations when relevant
   - Note any important warnings or contraindications mentioned in the context
   - Highlight critical clinical recommendations

6. **Response Structure**:
   - Provide clear, well-organized answers
   - Use bullet points or numbered lists for complex information
   - Structure responses for clinical clarity

7. **Allowed Sources (Strict)**:
   - Only cite from the following allowed source filenames: {allowed_sources}
   - Do not invent or guess citations. If none of the allowed sources apply, state that the context is insufficient.

## Important Disclaimer:
This is a decision support tool and does not replace clinical judgment. All information should be verified against current clinical guidelines and protocols. In emergency situations or when in doubt, consult with senior colleagues or relevant specialists.

---

Question: {input}

Context from clinical guidelines and medical literature:
{context}

Please provide a comprehensive, evidence-based answer with proper source citations:
""")

# Document + Retrieval Chain using LCEL (LangChain Expression Language)
def format_docs(docs):
    """Format documents with source citations."""
    formatted = []
    for doc in docs:
        # Skip documents with None or empty page_content
        if not doc.page_content or not doc.page_content.strip():
            continue
        
        source = "Unknown source"
        if doc.metadata and "source" in doc.metadata:
            # Extract filename from full path
            source_path = doc.metadata["source"]
            source = source_path.split("/")[-1] if "/" in source_path else source_path
        formatted.append(f"[Source: {source}]\n{doc.page_content}")
    return "\n\n".join(formatted)

retrieval_chain = (
    RunnablePassthrough.assign(context=lambda x: format_docs(retriever.invoke(x["input"])))
    | prompt
    | llm
)


# === FUNCTION 1: Ask question ===
# Maximum question length constant
MAX_QUESTION_LENGTH = 5000

def query_rag(question: str):
    """
    Query the RAG pipeline with a user question.
    
    Args:
        question (str): The user's question. Must be between 1 and 5000 characters.
        
    Returns:
        dict: Dictionary with 'answer' (str) and 'contexts' (List[dict]).
              Each context dict contains:
              - source (str): Filename of the source document
              - page (int): Page number if available, else None
              - content (str): The chunk content
              - chunk_id (str): Optional chunk identifier if available
    
    Raises:
        ValueError: If question is empty, too long, or invalid.
    """
    # Validate input
    if not question or not question.strip():
        raise ValueError("Question cannot be empty")
    
    question = question.strip()
    
    if len(question) > MAX_QUESTION_LENGTH:
        raise ValueError(f"Question exceeds maximum length of {MAX_QUESTION_LENGTH} characters")
    
    # Retrieve documents first
    retrieved_docs = retriever.invoke(question)
    
    # Filter out documents with None or empty page_content
    valid_docs = [doc for doc in retrieved_docs if doc.page_content and doc.page_content.strip()]
    
    if not valid_docs:
        return {
            "answer": "The available context does not provide sufficient information to answer this question.",
            "contexts": []
        }
    
    # Format documents for the prompt
    formatted_context = format_docs(valid_docs)

    # Build allowed sources set from valid documents (dynamic per request)
    allowed_sources_set = set()
    for doc in valid_docs:
        if doc.metadata and "source" in doc.metadata:
            source_path = doc.metadata["source"]
            filename = source_path.split("/")[-1] if "/" in source_path else source_path
            if filename:
                allowed_sources_set.add(filename)
    # If nothing retrieved, fail safely
    if not allowed_sources_set:
        return {
            "answer": "The available context does not provide sufficient information to answer this question.",
            "contexts": []
        }
    
    # Get LLM response using prompt template with retry logic for rate limits
    allowed_sources_str = ", ".join(sorted(allowed_sources_set)) if allowed_sources_set else "(none)"
    messages = prompt.format_messages(input=question, context=formatted_context, allowed_sources=allowed_sources_str)
    
    # Retry logic for rate limit errors and timeouts
    max_retries = 3  # Reduced from 5 to avoid long waits
    last_exception = None
    for attempt in range(max_retries):
        try:
            response = llm.invoke(messages)
            break  # Success, exit retry loop
        except Exception as e:
            last_exception = e
            error_str = str(e).lower()
            
            # Check for timeout errors
            if 'timeout' in error_str or 'timed out' in error_str or 'read timeout' in error_str:
                if attempt < max_retries - 1:
                    # Wait a bit before retry, but shorter for timeouts
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                    time.sleep(wait_time)
                    continue
                else:
                    raise TimeoutError(
                        f"Groq API request timed out after {max_retries} attempts. "
                        "The API may be slow or unresponsive. Please try again later."
                    )
            
            # Check if it's a rate limit or capacity error (503)
            elif '429' in str(e) or '503' in str(e) or 'rate_limit' in error_str or 'rate limit' in error_str or 'over capacity' in error_str or 'over_capacity' in error_str:
                # Check if error mentions exponential backoff
                if 'back off exponentially' in error_str:
                    # Use exponential backoff as suggested by API
                    wait_time = min(2 ** attempt, 60)  # Cap at 60 seconds for capacity issues
                    time.sleep(wait_time)
                else:
                    # Parse wait time from error message if available
                    wait_time_match = re.search(r'please try again in ([\d.]+)s', error_str)
                    if wait_time_match:
                        wait_time = float(wait_time_match.group(1)) + 0.5  # Add 0.5s buffer
                        time.sleep(wait_time)
                    else:
                        # Exponential backoff if no wait time specified
                        wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                        time.sleep(wait_time)
                continue  # Retry
            else:
                # Not a retryable error, re-raise immediately
                raise
    
    # If we've exhausted retries, raise the last exception
    if 'response' not in locals():
        raise last_exception if last_exception else Exception("Failed to get LLM response")
    
    # Extract contexts with metadata (only from valid documents)
    contexts = []
    for doc in valid_docs:
        # Skip documents with None or empty page_content
        if not doc.page_content or not doc.page_content.strip():
            continue
        
        context_dict = {
            "content": doc.page_content
        }
        
        # Extract source filename
        if doc.metadata and "source" in doc.metadata:
            source_path = doc.metadata["source"]
            context_dict["source"] = source_path.split("/")[-1] if "/" in source_path else source_path
        else:
            context_dict["source"] = "Unknown source"
        
        # Extract page number if available
        if doc.metadata and "page" in doc.metadata:
            context_dict["page"] = doc.metadata["page"]
        else:
            context_dict["page"] = None
        
        # Extract chunk_id if available
        if doc.metadata and "id" in doc.metadata:
            context_dict["chunk_id"] = doc.metadata["id"]
        elif hasattr(doc, "id"):
            context_dict["chunk_id"] = doc.id
        else:
            context_dict["chunk_id"] = None
        
        contexts.append(context_dict)
    
    # Sanitize citations: keep only [Source: filename] where filename in allowed set
    answer_text = response.content
    try:
        pattern = _re.compile(r"\[Source:\s*([^\]]+)\]")
        def _keep_allowed(match):
            fname = match.group(1).strip()
            return match.group(0) if fname in allowed_sources_set else ""
        answer_text = pattern.sub(_keep_allowed, answer_text)
        # Collapse double spaces from removed tags
        answer_text = _re.sub(r"\s{2,}", " ", answer_text).strip()
    except Exception:
        # If post-processing fails, return original content
        answer_text = response.content

    return {
        "answer": answer_text,
        "contexts": contexts
    }


# === FUNCTION 2: Add PDF to DB ===
def add_pdf_to_db(pdf_path: str):
    """Load, split, and embed a PDF into the vector database."""
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    # Get chunk size and overlap from environment or use defaults
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "2000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "300"))
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = text_splitter.split_documents(docs)

    vectordb.add_documents(chunks)
    #vectordb.persist()

    return len(chunks)


# === FUNCTION 3: List documents in DB ===
def list_documents():
    """List all unique sources (PDFs) currently in the DB."""
    collection = vectordb._collection
    items = collection.get(include=["metadatas"])
    sources = set()

    for meta in items["metadatas"]:
        if meta and "source" in meta:
            sources.add(meta["source"].split("/")[-1])

    return list(sources)


# === FUNCTION 4: Delete specific document ===
def delete_document(file_name: str):
    """Delete all chunks from a specific file."""
    collection = vectordb._collection
    items = collection.get(include=["metadatas", "ids"])

    ids_to_delete = [
        item_id
        for item_id, meta in zip(items["ids"], items["metadatas"])
        if meta and meta.get("source", "").endswith(file_name)
    ]

    if not ids_to_delete:
        return {"deleted": 0, "message": f"No documents found for '{file_name}'."}

    collection.delete(ids=ids_to_delete)
    return {"deleted": len(ids_to_delete), "message": f"Deleted {len(ids_to_delete)} chunks from '{file_name}'."}
