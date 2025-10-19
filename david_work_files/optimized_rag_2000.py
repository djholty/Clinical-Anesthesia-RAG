#!/usr/bin/env python3
"""
Optimized RAG System with 2000-character chunks for Markdown Files
Loads multiple markdown files from a directory and creates optimized chunks
Based on testing results showing optimal performance
"""

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import glob
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain

class OptimizedRAGSystem:
    def __init__(self, markdown_directory, force_rebuild=False):
        self.markdown_directory = markdown_directory
        self.force_rebuild = force_rebuild
        self.chunks = None  # Will be set if we need to process documents
        self.setup_environment()
        self.setup_embeddings()
        
        # Check if we can load existing database first
        if not force_rebuild and self._can_load_existing_database():
            print("⚡ Loading existing database without processing documents...")
            self.setup_vector_database()
        else:
            print("📄 Processing documents and creating new database...")
            self.load_and_process_documents()
            self.setup_vector_database()
        
        self.setup_llm()
        self.setup_retrieval_chain()
    
    def _can_load_existing_database(self):
        """Check if existing database can be loaded"""
        db_path = "./data/optimized_2000_markdown_chroma_db"
        return os.path.exists(db_path) and os.listdir(db_path)
    
    def setup_environment(self):
        """Load environment variables"""
        os.environ['HF_TOKEN'] = os.getenv("HF_TOKEN")
        os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
    
    def load_and_process_documents(self):
        """Load markdown files from directory and create optimized 2000-character chunks"""
        print(f"Loading markdown documents from: {self.markdown_directory}")
        
        # Check if directory exists
        if not os.path.exists(self.markdown_directory):
            raise FileNotFoundError(f"Directory not found: {self.markdown_directory}")
        
        # Find all markdown files in the directory
        markdown_files = glob.glob(os.path.join(self.markdown_directory, "*.md"))
        
        if not markdown_files:
            raise FileNotFoundError(f"No markdown files found in: {self.markdown_directory}")
        
        print(f"Found {len(markdown_files)} markdown files:")
        for md_file in markdown_files:
            print(f"  - {os.path.basename(md_file)}")
        
        # Load all markdown files using DirectoryLoader
        try:
            loader = DirectoryLoader(
                self.markdown_directory,
                glob="*.md",
                loader_cls=TextLoader,
                loader_kwargs={'encoding': 'utf-8'}
            )
            docs = loader.load()
            print(f"Successfully loaded {len(docs)} documents")
        except Exception as e:
            print(f"Error loading documents: {e}")
            raise
        
        # Optimized chunking strategy - 2000 characters with 300 overlap
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,  # Optimal size based on testing
            chunk_overlap=300,  # Generous overlap for context preservation
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]  # Smart separation
        )
        
        self.chunks = text_splitter.split_documents(docs)
        print(f"Created {len(self.chunks)} optimized chunks from markdown files")
        print(f"Average chunk length: {sum(len(chunk.page_content) for chunk in self.chunks) / len(self.chunks):.0f} characters")
        
        # Print sample chunks for verification
        print("\nSample optimized chunks:")
        for i, chunk in enumerate(self.chunks[:2]):
            print(f"Chunk {i+1} (length: {len(chunk.page_content)}):")
            print(f"Source: {chunk.metadata.get('source', 'Unknown')}")
            print(f"{chunk.page_content[:300]}...")
            print("-" * 50)
    
    def setup_embeddings(self):
        """Setup embeddings model"""
        print("Setting up embeddings...")
        self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    def setup_vector_database(self):
        """Create or load existing vector database"""
        db_path = "./data/optimized_2000_markdown_chroma_db"
        
        # Check if database already exists
        if os.path.exists(db_path) and os.listdir(db_path):
            print(f"📁 Found existing database at: {db_path}")
            print("🔄 Loading existing vector database...")
            
            try:
                # Load existing database
                self.vectordb = Chroma(
                    persist_directory=db_path,
                    embedding_function=self.embeddings
                )
                
                # Get collection info to verify it works
                collection = self.vectordb._collection
                doc_count = collection.count()
                
                print(f"✅ Successfully loaded existing database")
                print(f"📊 Database contains {doc_count} document chunks")
                print("⚡ Using cached database - much faster!")
                
                return  # Exit early - database loaded successfully
                
            except Exception as e:
                print(f"❌ Error loading existing database: {e}")
                print("🔄 Will create new database...")
        
        # Create new database if none exists or loading failed
        if self.chunks is None:
            print("📄 Need to process documents first...")
            self.load_and_process_documents()
        
        print("🔨 Creating new optimized vector database...")
        self.vectordb = Chroma.from_documents(
            documents=self.chunks,
            embedding=self.embeddings,
            persist_directory=db_path
        )
        print(f"✅ Created new vector database with {len(self.chunks)} chunks")
        print(f"💾 Saved to: {db_path}")
        print("🎯 Next time this will load instantly!")
    
    def setup_llm(self):
        """Setup LLM with optimized parameters"""
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.1,  # Low temperature for precise medical answers
            max_tokens=1200   # Increased for detailed responses
        )
    
    def setup_retrieval_chain(self):
        """Setup optimized retrieval chain"""
        
        # Enhanced clinical prompt template
        prompt = ChatPromptTemplate.from_template("""
You are a clinical anesthesia expert assistant. Answer the question based on the provided context from anesthesia documentation.

INSTRUCTIONS:
1. Use ONLY the information provided in the context below
2. Be specific and include exact details (dosages, timeframes, procedures)
3. If the context doesn't contain enough information, clearly state what's missing
4. Structure your answer with bullet points or numbered lists when appropriate
5. Cite relevant details directly from the context
6. For drug dosages and timing, be precise and include all relevant information

QUESTION: {input}

CONTEXT:
{context}

DETAILED CLINICAL ANSWER:""")
        
        # Create document chain
        self.document_chain = create_stuff_documents_chain(self.llm, prompt)
        
        # Setup optimized retriever
        self.retriever = self.vectordb.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 8  # Increased to 8 for better context with larger chunks
            }
        )
        
        # Create retrieval chain
        self.retrieval_chain = create_retrieval_chain(self.retriever, self.document_chain)
    
    def query(self, question, show_retrieved=True):
        """Query the optimized RAG system with debugging info"""
        print(f"\n{'='*70}")
        print(f"QUERY: {question}")
        print(f"{'='*70}")
        
        if show_retrieved:
            # Get retrieved documents for debugging
            retrieved_docs = self.retriever.invoke(question)
            print(f"Retrieved {len(retrieved_docs)} documents:")
            
            for i, doc in enumerate(retrieved_docs):
                print(f"\nDoc {i+1} (length: {len(doc.page_content)}):")
                print(f"{doc.page_content[:400]}...")
                print("-" * 40)
        
        print(f"\n{'='*70}")
        
        # Get response
        response = self.retrieval_chain.invoke({"input": question})
        print(f"ANSWER:\n{response['answer']}")
        print(f"\n{'='*70}")
        
        return response
    
    def test_clinical_questions(self):
        """Test the system with comprehensive clinical questions"""
        clinical_questions = [
            "How long do I need to wait for an epidural after a prophylactic dose of enoxaparin?",
            "What are the contraindications for spinal anesthesia?",
            "What are complications of arterial measurement?",
            "What is the recommended dosage for propofol induction?",
            "What are the signs and symptoms of local anesthetic systemic toxicity?",
            "What are the guidelines for neuraxial anesthesia in patients on anticoagulants?",
            "What is the management of malignant hyperthermia?",
            "What are the contraindications for succinylcholine?"
        ]
        
        print(f"\n{'='*80}")
        print("TESTING OPTIMIZED RAG SYSTEM WITH CLINICAL QUESTIONS")
        print(f"{'='*80}")
        
        for i, question in enumerate(clinical_questions, 1):
            print(f"\n[Question {i}/{len(clinical_questions)}]")
            try:
                response = self.query(question, show_retrieved=False)
            except Exception as e:
                print(f"Error with question: {e}")
            
            if i < len(clinical_questions):
                input("\nPress Enter to continue to next question...")

# Usage
if __name__ == "__main__":
    # Initialize the optimized RAG system with markdown directory
    markdown_directory = "RAG_markdown_output_files"
    
    print("🚀 Initializing Optimized RAG System with markdown files and 2000-character chunks...")
    print(f"📁 Loading from directory: {markdown_directory}")
    
    try:
        # Initialize system (will auto-load existing database if available)
        rag_system = OptimizedRAGSystem(markdown_directory)
        
        # Alternative: Force rebuild even if database exists
        # rag_system = OptimizedRAGSystem(markdown_directory, force_rebuild=True)
        
        print("\n✅ System ready! Testing with clinical questions...")
        
        # Test the system
        rag_system.test_clinical_questions()
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print(f"💡 Make sure the '{markdown_directory}' directory exists and contains .md files")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


