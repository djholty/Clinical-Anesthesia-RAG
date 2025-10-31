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
hf_token = os.getenv("HF_TOKEN")
if hf_token:
    os.environ["HF_TOKEN"] = hf_token

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
        try:
            # Try to remove, but handle locked files
            shutil.rmtree(db_path)
            print(f"   ✓ Removed {db_path}")
        except PermissionError as e:
            print(f"   ⚠️  Warning: Could not fully remove {db_path}")
            print(f"      Error: {str(e)}")
            print(f"      This may be because the FastAPI server is using the database.")
            print(f"      Please stop the server (Ctrl+C in its terminal) and try again.")
            raise
        except OSError as e:
            print(f"   ⚠️  Warning: Could not fully remove {db_path}")
            print(f"      Error: {str(e)}")
            print(f"      Trying to remove individual files...")
            # Try to remove individual files
            import stat
            for root, dirs, files in os.walk(db_path):
                for name in files:
                    filepath = os.path.join(root, name)
                    try:
                        os.chmod(filepath, stat.S_IWRITE | stat.S_IREAD)
                        os.remove(filepath)
                    except:
                        pass
                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except:
                        pass
            try:
                os.rmdir(db_path)
                print(f"   ✓ Removed {db_path} (after cleanup)")
            except:
                print(f"   ❌ Could not remove {db_path}. Please stop any processes using it.")
                raise
    
    # Remove optimized database
    if os.path.exists(OLD_DB_DIR):
        try:
            shutil.rmtree(OLD_DB_DIR)
            print(f"   ✓ Removed {OLD_DB_DIR}")
        except (PermissionError, OSError) as e:
            print(f"   ⚠️  Warning: Could not remove {OLD_DB_DIR}: {str(e)}")
            # Non-critical, continue anyway
    
    print("\n📂 Step 2: Loading markdown files...")
    # Load all markdown files
    # Suppress "No features in text" warnings from unstructured library
    import warnings
    import sys
    from io import StringIO
    
    # Capture stderr to filter out "No features in text" messages
    old_stderr = sys.stderr
    captured_output = StringIO()
    
    try:
        sys.stderr = captured_output
        loader = DirectoryLoader(
            md_dir,
            glob="**/*.md",
            loader_cls=UnstructuredMarkdownLoader,
            show_progress=True
        )
        documents = loader.load()
    finally:
        sys.stderr = old_stderr
        # Filter out "No features in text" from captured output
        output = captured_output.getvalue()
        if output and "No features in text" not in output:
            # Only print if there's actual error output (not just the "No features" warning)
            print(output, end="", file=sys.stderr)
    
    print(f"   ✓ Loaded {len(documents)} markdown files")
    
    print("\n✂️  Step 3: Splitting documents into chunks...")
    # Get chunk size and overlap from environment or use defaults
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "2000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "300"))
    print(f"   Using chunk_size={CHUNK_SIZE}, chunk_overlap={CHUNK_OVERLAP}")
    # Split documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    chunks = text_splitter.split_documents(documents)
    print(f"   ✓ Created {len(chunks)} chunks")
    
    print("\n🧠 Step 4: Creating embeddings and building database...")
    # Get embedding model from environment or default
    # Strip quotes in case user added them in .env file
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip().strip("'\"")
    print(f"   Using embedding model: {EMBEDDING_MODEL}")
    # HuggingFaceEmbeddings will automatically use HF_TOKEN from environment if needed
    if hf_token:
        print("   HF_TOKEN is set (will be used if model requires authentication)")
    
    try:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    except Exception as e:
        error_msg = str(e).lower()
        # Check for authentication errors
        if "401" in error_msg or "unauthorized" in error_msg or "authentication" in error_msg:
            print(f"\n❌ Error: Authentication failed for model '{EMBEDDING_MODEL}'")
            print("   This model requires a valid HF_TOKEN.")
            print("   Please set HF_TOKEN in your .env file with a valid HuggingFace token.")
            print("   Get your token at: https://huggingface.co/settings/tokens")
            raise ValueError(
                f"Authentication failed for model '{EMBEDDING_MODEL}'. "
                "This model requires a valid HF_TOKEN. "
                "Please set HF_TOKEN in your .env file."
            )
        # Re-raise other errors as-is
        raise
    
    # Ensure database directory exists and is writable
    db_path_obj = Path(db_path)
    db_path_obj.mkdir(parents=True, exist_ok=True)
    
    # Check write permissions
    try:
        test_file = db_path_obj / ".test_write"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        raise PermissionError(f"Database directory {db_path} is not writable: {e}")
    
    # Create new Chroma database
    # Use a unique temporary name first, then rename to avoid locking issues
    import tempfile
    # shutil is already imported at top of file
    
    temp_db_dir = None
    try:
        # Create database in a temp location first
        temp_db_dir = tempfile.mkdtemp(prefix="chroma_temp_")
        
        vectordb = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=temp_db_dir
        )
        
        # Force persistence
        try:
            vectordb.persist()
        except AttributeError:
            # persist() might not exist in newer Chroma versions
            pass
        
        # Close connection explicitly
        try:
            del vectordb
        except:
            pass
        
        # Small delay to ensure all files are written
        import time
        time.sleep(0.5)
        
        # Now move temp database to final location
        if os.path.exists(db_path):
            shutil.rmtree(db_path)
        shutil.move(temp_db_dir, db_path)
        
    except Exception as e:
        # Clean up temp directory on error
        if temp_db_dir and os.path.exists(temp_db_dir):
            try:
                shutil.rmtree(temp_db_dir)
            except:
                pass
        raise
    
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


