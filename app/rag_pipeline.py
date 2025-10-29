import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv

# === Load Environment Variables ===
load_dotenv()

# === Initialize components ===
os.environ["HF_TOKEN"] = os.getenv("HF_TOKEN")
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Persistent DB directory
DB_DIR = "./data/chroma_db"
vectordb = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
retriever = vectordb.as_retriever()

# LLM (Groq)
llm = ChatGroq(model="llama-3.1-8b-instant")

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
def query_rag(question: str):
    """Query the RAG pipeline with a user question."""
    response = retrieval_chain.invoke({"input": question})
    return response.content


# === FUNCTION 2: Add PDF to DB ===
def add_pdf_to_db(pdf_path: str):
    """Load, split, and embed a PDF into the vector database."""
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=300)
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
