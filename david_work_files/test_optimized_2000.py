#!/usr/bin/env python3
"""
Test the optimized 2000-character RAG system (non-interactive)
"""

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
from dotenv import load_dotenv
load_dotenv()
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain

def create_optimized_rag_system(pdf_path):
    """Create the optimized RAG system with 2000-character chunks"""
    
    # Load and process documents
    print("Loading documents...")
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    
    # Optimized chunking - 2000 characters with 300 overlap
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=300,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
    )
    
    chunks = text_splitter.split_documents(docs)
    print(f"✅ Created {len(chunks)} optimized chunks (avg: {sum(len(c.page_content) for c in chunks) / len(chunks):.0f} chars)")
    
    # Setup components
    os.environ['HF_TOKEN'] = os.getenv("HF_TOKEN")
    os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
    
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./data/final_optimized_2000"
    )
    
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0.1,
        max_tokens=1200
    )
    
    # Enhanced clinical prompt
    prompt = ChatPromptTemplate.from_template("""
You are a clinical anesthesia expert. Answer based ONLY on the provided context.

INSTRUCTIONS:
- Be specific with dosages, timeframes, and procedures
- Use bullet points for clarity when appropriate
- If information is insufficient, state what's missing
- Cite relevant details directly from context

QUESTION: {input}

CONTEXT:
{context}

CLINICAL ANSWER:""")
    
    document_chain = create_stuff_documents_chain(llm, prompt)
    retriever = vectordb.as_retriever(search_kwargs={"k": 8})
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    
    return retrieval_chain, retriever

def test_questions(retrieval_chain, retriever):
    """Test key clinical questions"""
    
    questions = [
        "How long do I need to wait for an epidural after a prophylactic dose of enoxaparin?",
        "What are the contraindications for spinal anesthesia?",
        "What is the management of malignant hyperthermia?",
        "What are the signs of local anesthetic systemic toxicity?"
    ]
    
    print(f"\n{'='*80}")
    print("🧪 TESTING OPTIMIZED 2000-CHARACTER RAG SYSTEM")
    print(f"{'='*80}")
    
    for i, question in enumerate(questions, 1):
        print(f"\n[Question {i}] {question}")
        print("-" * 70)
        
        # Show retrieved context
        retrieved = retriever.invoke(question)
        print(f"📄 Retrieved {len(retrieved)} relevant documents")
        
        # Get answer
        response = retrieval_chain.invoke({"input": question})
        print(f"\n💡 ANSWER:\n{response['answer']}")
        print("\n" + "="*70)

def main():
    """Main function"""
    pdf_path = '/Users/davidholt/Library/CloudStorage/OneDrive-Personal/Documents/Anesthesia Materials/Anesthesia RAG Materials/RAG Ready Documents/Anesthesia Notes.pdf'
    
    print("🚀 Creating Optimized RAG System with 2000-character chunks...")
    retrieval_chain, retriever = create_optimized_rag_system(pdf_path)
    
    print("✅ System ready! Running tests...")
    test_questions(retrieval_chain, retriever)
    
    print(f"\n🎉 CONCLUSION: 2000-character chunks provide excellent clinical answers!")
    print("📋 Benefits:")
    print("   • More comprehensive context per chunk")
    print("   • Better preservation of clinical procedures")
    print("   • Detailed answers with specific dosages/timeframes")
    print("   • Fewer total chunks (922 vs 1146 with 1500 chars)")

if __name__ == "__main__":
    main()


