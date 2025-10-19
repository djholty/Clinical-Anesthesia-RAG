import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
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
Answer the following question based only on the provided context:
question: {input}
<context>
{context}
</context>
""")

# Document + Retrieval Chains
document_chain = create_stuff_documents_chain(llm, prompt)
retrieval_chain = create_retrieval_chain(retriever, document_chain)


# === FUNCTION 1: Ask question ===
def query_rag(question: str):
    """Query the RAG pipeline with a user question."""
    response = retrieval_chain.invoke({"input": question})
    return response["answer"]


# === FUNCTION 2: Add PDF to DB ===
def add_pdf_to_db(pdf_path: str):
    """Load, split, and embed a PDF into the vector database."""
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=50)
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
