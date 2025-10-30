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

# Paths - can be overridden by environment variables
MARKDOWN_DIR = os.getenv("MARKDOWN_DIR", "./data/ingested_documents")
DB_DIR = os.getenv("DB_DIR", "./data/chroma_db")
OLD_DB_DIR = os.getenv("OLD_DB_DIR", "./data/optimized_2000_markdown_chroma_db")

def rebuild_database(markdown_dir: str = None, db_dir: str = None):
    """
    Rebuild the Chroma database from markdown files.
    
    Args:
        markdown_dir: Directory containing markdown files (defaults to MARKDOWN_DIR env var or ./data/ingested_documents)
        db_dir: Directory for Chroma database (defaults to DB_DIR env var or ./data/chroma_db)
    """
    # Use provided arguments or fall back to environment/global defaults
    md_dir = markdown_dir or MARKDOWN_DIR
    db_path = db_dir or DB_DIR
    
    print("🗑️  Step 1: Removing old databases...")
    # Remove old chroma_db
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
        print(f"   ✓ Removed {db_path}")
    
    # Remove optimized database
    if os.path.exists(OLD_DB_DIR):
        shutil.rmtree(OLD_DB_DIR)
        print(f"   ✓ Removed {OLD_DB_DIR}")
    
    print("\n📂 Step 2: Loading markdown files...")
    # Load all markdown files
    loader = DirectoryLoader(
        md_dir,
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
        chunk_overlap=300
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
        persist_directory=db_path
    )
    
    print(f"   ✓ Database created at {db_path}")
    print(f"\n✅ Database rebuild complete!")
    print(f"   Total documents: {len(documents)}")
    print(f"   Total chunks: {len(chunks)}")
    print(f"   Database location: {db_path}")

if __name__ == "__main__":
    print("=" * 60)
    print("   REBUILDING CHROMA DATABASE")
    print("=" * 60)
    
    # Check if markdown directory exists
    if not os.path.exists(MARKDOWN_DIR):
        print(f"❌ Error: Markdown directory not found: {MARKDOWN_DIR}")
        print("   Please make sure data/ingested_documents exists.")
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


