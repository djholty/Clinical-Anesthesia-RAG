"""
Script to rebuild the Chroma vector database from markdown files.
"""
import os
import shutil
from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up HuggingFace token
os.environ["HF_TOKEN"] = os.getenv("HF_TOKEN")

# Paths
MARKDOWN_DIR = "./ingested_documents"
DB_DIR = "./data/chroma_db"
OLD_DB_DIR = "./data/optimized_2000_markdown_chroma_db"

def rebuild_database():
    """Rebuild the Chroma database from markdown files."""
    
    print("🗑️  Step 1: Removing old databases...")
    # Remove old chroma_db
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)
        print(f"   ✓ Removed {DB_DIR}")
    
    # Remove optimized database
    if os.path.exists(OLD_DB_DIR):
        shutil.rmtree(OLD_DB_DIR)
        print(f"   ✓ Removed {OLD_DB_DIR}")
    
    print("\n📂 Step 2: Loading markdown files...")
    # Load all markdown files
    loader = DirectoryLoader(
        MARKDOWN_DIR,
        glob="**/*.md",
        loader_cls=UnstructuredMarkdownLoader,
        show_progress=True
    )
    documents = loader.load()
    print(f"   ✓ Loaded {len(documents)} markdown files")
    
    print("\n✂️  Step 3: Splitting documents into chunks...")
    # Split documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200
    )
    chunks = text_splitter.split_documents(documents)
    print(f"   ✓ Created {len(chunks)} chunks")
    
    print("\n🧠 Step 4: Creating embeddings and building database...")
    # Create embeddings
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Create new Chroma database
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=DB_DIR
    )
    
    print(f"   ✓ Database created at {DB_DIR}")
    print(f"\n✅ Database rebuild complete!")
    print(f"   Total documents: {len(documents)}")
    print(f"   Total chunks: {len(chunks)}")
    print(f"   Database location: {DB_DIR}")

if __name__ == "__main__":
    print("=" * 60)
    print("   REBUILDING CHROMA DATABASE")
    print("=" * 60)
    
    # Check if markdown directory exists
    if not os.path.exists(MARKDOWN_DIR):
        print(f"❌ Error: Markdown directory not found: {MARKDOWN_DIR}")
        print("   Please make sure RAG_markdown_output_files exists.")
        exit(1)
    
    # Count markdown files
    md_files = list(Path(MARKDOWN_DIR).glob("**/*.md"))
    print(f"\n📊 Found {len(md_files)} markdown files to process\n")
    
    try:
        rebuild_database()
    except Exception as e:
        print(f"\n❌ Error during rebuild: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

