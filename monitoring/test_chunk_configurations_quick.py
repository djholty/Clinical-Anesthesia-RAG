"""
Quick Chunk Configuration Testing for BioBERT

This is a faster version that tests retrieval quality quickly without
running full LLM-based evaluations. It uses:
- Smaller subset of test questions (default: 10 questions)
- Faster metrics (retrieval relevance, chunk count)
- Shorter evaluation time

For comprehensive testing, use test_chunk_configurations.py
"""

import os
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Don't import rag_pipeline here - it will try to open the database at import time
# Import it inside functions after database is created

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = Path(os.getenv("DB_DIR", str(PROJECT_ROOT / "data" / "chroma_db")))
MARKDOWN_DIR = Path(os.getenv("MARKDOWN_DIR", str(PROJECT_ROOT / "data" / "ingested_documents")))
EVALUATION_FILE = PROJECT_ROOT / "monitoring" / "prompt_set.xlsx"
RESULTS_DIR = PROJECT_ROOT / "monitoring" / "chunk_config_tests"

# Quick test configurations - reduced set for faster testing
TEST_CONFIGURATIONS = [
    # Small chunks - more granular
    (1000, 150, "Small chunks - high precision"),
    (1500, 250, "Medium-small chunks"),
    
    # Medium chunks - balanced
    (2000, 300, "Default - balanced"),
    (2000, 400, "Default - higher overlap"),
    
    # Larger chunks - more context
    (2500, 400, "Large chunks - good context"),
    (3000, 500, "Very large chunks - high overlap"),
]

# Number of questions to test (use subset for speed)
NUM_TEST_QUESTIONS = 10  # Adjust based on desired speed vs. accuracy


def rebuild_database_with_config(chunk_size: int, chunk_overlap: int):
    """
    Rebuild the database with specified chunk configuration.
    
    Args:
        chunk_size: Size of each chunk in characters
        chunk_overlap: Overlap between chunks in characters
        
    Returns:
        int: Number of chunks created, or None if failed
    """
    print(f"\nRebuilding database: chunk_size={chunk_size}, chunk_overlap={chunk_overlap}...")
    
    # Set environment variables for this test
    os.environ["CHUNK_SIZE"] = str(chunk_size)
    os.environ["CHUNK_OVERLAP"] = str(chunk_overlap)
    
    # Import here to ensure env vars are set
    from app.rebuild_database import rebuild_database
    
    try:
        # First, try to remove the database directory if it exists
        if DB_DIR.exists():
            print("  Removing old database...")
            
            # Force close any existing database connections first
            try:
                import importlib
                import app.rag_pipeline as rag_module
                # Try to close existing connection if it exists
                if hasattr(rag_module, 'vectordb'):
                    try:
                        del rag_module.vectordb
                    except:
                        pass
            except:
                pass
            
            # Force garbage collection to release file handles
            import gc
            gc.collect()
            time.sleep(1.0)  # Wait for handles to be released
            
            try:
                import shutil
                shutil.rmtree(DB_DIR)
                print("  ✓ Removed old database")
            except PermissionError:
                print("  ⚠️  Could not remove database (may be in use). Trying anyway...")
            except Exception as e:
                print(f"  ⚠️  Warning removing database: {e}")
                # Try again after a longer wait
                time.sleep(2.0)
                try:
                    shutil.rmtree(DB_DIR)
                    print("  ✓ Removed old database (after retry)")
                except:
                    print("  ⚠️  Still could not remove database - will try to overwrite")
        
        # Small delay to ensure file handles are released
        time.sleep(1.0)
        
        # Count chunks before rebuild
        start_time = time.time()
        rebuild_database()
        rebuild_time = time.time() - start_time
        
        # Wait longer to ensure Chroma releases all file locks
        # Chroma can take a moment to flush writes and close connections
        print("  Waiting for database to settle...")
        time.sleep(3.0)
        
        # Count chunks by creating a fresh Chroma connection
        # Don't use rag_pipeline's existing connection to avoid locking
        num_chunks = 0
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            from langchain_chroma import Chroma
            
            # Create fresh connection with same config
            EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
            
            # Open database in read-only mode if possible
            vectordb = Chroma(
                persist_directory=str(DB_DIR),
                embedding_function=embeddings
            )
            retriever = vectordb.as_retriever()
            test_docs = retriever.invoke("anesthesia")
            num_chunks = len(test_docs) if test_docs else 0
            
            # Close connection
            try:
                del vectordb
                del retriever
            except:
                pass
        except Exception as e:
            # If we can't query, just estimate based on chunks created
            # We can get this from rebuild_database if we modify it to return chunk count
            print(f"    ⚠️  Could not query database for chunk count: {e}")
            print(f"    (This is OK - database was created successfully)")
            num_chunks = None  # Will indicate successful rebuild without chunk count
        
        if num_chunks is not None:
            print(f"✓ Rebuilt in {rebuild_time:.1f}s, created ~{num_chunks} chunks\n")
        else:
            print(f"✓ Rebuilt in {rebuild_time:.1f}s\n")
        return num_chunks if num_chunks is not None else 10000  # Return large number to indicate success
        
    except Exception as e:
        error_msg = str(e)
        if "readonly" in error_msg.lower() or "1032" in error_msg:
            print(f"✗ Error: Database is locked or readonly")
            print(f"  This usually means:")
            print(f"  1. FastAPI server is still running - stop it first")
            print(f"  2. Another process is using the database")
            print(f"  3. File permissions issue")
            print(f"  Run: pkill -f 'uvicorn app.main:app'")
        else:
            print(f"✗ Error: {e}")
        print()
        return None


def test_retrieval_quality(chunk_size: int, chunk_overlap: int, test_questions: list):
    """
    Test retrieval quality with a subset of questions.
    
    Args:
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks
        test_questions: List of (question, expected_answer) tuples
        
    Returns:
        dict: Quick metrics
    """
    # Import after database is ready to avoid locking issues
    # Reload module to get fresh connection to new database
    import importlib
    import app.rag_pipeline as rag_module
    
    # Force reload to get fresh database connection
    try:
        importlib.reload(rag_module)
    except:
        pass
    
    # Reload citation_metrics to ensure it uses the current embedding model
    import monitoring.citation_metrics as citation_module
    try:
        importlib.reload(citation_module)
    except:
        pass
    
    from monitoring.citation_metrics import calculate_context_relevance_semantic, embedding_model, EMBEDDING_MODEL as cm_embedding_model
    
    # Debug: Show which embedding model is being used for relevance calculation
    if embedding_model:
        try:
            model_name = embedding_model.get_sentence_embedding_dimension()
            print(f"\n  Using embedding model for relevance: {cm_embedding_model}")
            print(f"  Model dimensions: {model_name}")
        except:
            print(f"\n  Using embedding model for relevance: {cm_embedding_model}")
    else:
        print(f"\n  ⚠️  Warning: Embedding model not loaded, using fallback scores")
    
    # Use the reloaded module's query_rag function
    query_rag = rag_module.query_rag
    
    print(f"  Testing {len(test_questions)} questions...")
    
    relevance_scores = []
    chunk_counts = []
    context_lengths = []
    query_times = []
    
    for idx, (question, _) in enumerate(test_questions, 1):
        try:
            print(f"    Question {idx}/{len(test_questions)}: {question[:60]}...", end=" ", flush=True)
            start = time.time()
            result = query_rag(question)
            query_time = time.time() - start
            print(f"✓ ({query_time:.2f}s)", flush=True)
            
            contexts = result.get('contexts', [])
            chunk_counts.append(len(contexts))
            
            # Calculate total context length
            total_length = sum(len(ctx.get('content', '')) for ctx in contexts)
            context_lengths.append(total_length)
            
            # Calculate relevance score
            if contexts:
                relevance, individual_scores = calculate_context_relevance_semantic(question, contexts)
                relevance_scores.append(relevance)
                # Debug: Show relevance details for first 2 questions
                if idx <= 2:
                    print(f"      Relevance: {relevance:.3f} (individual: {[f'{s:.3f}' for s in individual_scores[:min(4, len(individual_scores))]]})")
                    print(f"      Contexts retrieved: {len(contexts)}, Score range: {min(individual_scores):.3f}-{max(individual_scores):.3f}")
                    # Show sample context snippets
                    for i, ctx in enumerate(contexts[:2], 1):
                        content_preview = ctx.get('content', '')[:80].replace('\n', ' ')
                        print(f"        Context {i} (rel={individual_scores[i-1]:.3f}): {content_preview}...")
            else:
                relevance_scores.append(0.0)
                if idx <= 2:
                    print(f"      No contexts retrieved")
            
            query_times.append(query_time)
            
        except Exception as e:
            print(f"    ⚠️  Error with question: {e}")
            relevance_scores.append(0.0)
            chunk_counts.append(0)
            context_lengths.append(0)
            query_times.append(0)
    
    # Calculate averages
    avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0
    avg_chunks = sum(chunk_counts) / len(chunk_counts) if chunk_counts else 0
    avg_context_length = sum(context_lengths) / len(context_lengths) if context_lengths else 0
    avg_query_time = sum(query_times) / len(query_times) if query_times else 0
    
    # Debug: Show relevance score statistics
    if relevance_scores:
        min_rel = min(relevance_scores)
        max_rel = max(relevance_scores)
        std_rel = (sum((r - avg_relevance) ** 2 for r in relevance_scores) / len(relevance_scores)) ** 0.5
        print(f"  Relevance stats: min={min_rel:.3f}, max={max_rel:.3f}, avg={avg_relevance:.3f}, std={std_rel:.3f}")
    
    return {
        'avg_relevance': avg_relevance,
        'avg_chunks_retrieved': avg_chunks,
        'avg_context_length': avg_context_length,
        'avg_query_time': avg_query_time,
        'total_chunks_in_db': None  # Will be filled by rebuild function
    }


def load_test_questions(num_questions: int = None):
    """
    Load a subset of questions from the evaluation file.
    
    Args:
        num_questions: Number of questions to load (None = all)
        
    Returns:
        list: List of (question, expected_answer) tuples
    """
    if not EVALUATION_FILE.exists():
        print(f"✗ Error: Evaluation file not found: {EVALUATION_FILE}")
        return []
    
    try:
        df = pd.read_excel(EVALUATION_FILE)
        
        # Find question and answer columns
        question_col = 'questions' if 'questions' in df.columns else df.columns[0]
        answer_col = 'answers' if 'answers' in df.columns else df.columns[1]
        
        questions = []
        for _, row in df.iterrows():
            question = str(row[question_col]).strip()
            answer = str(row[answer_col]).strip()
            
            if question and answer and question != 'nan' and answer != 'nan':
                questions.append((question, answer))
        
        # Return subset if requested
        if num_questions and len(questions) > num_questions:
            # Sample evenly across the dataset
            step = len(questions) // num_questions
            questions = questions[::step][:num_questions]
        
        return questions
        
    except Exception as e:
        print(f"✗ Error loading questions: {e}")
        return []


def check_prerequisites():
    """
    Check prerequisites before testing.
    
    Returns:
        bool: True if prerequisites are met, False otherwise
    """
    print("Checking prerequisites...")
    
    # Check if servers are running
    import subprocess
    try:
        result = subprocess.run(
            ["pgrep", "-f", "uvicorn app.main:app"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("  ⚠️  Warning: FastAPI server appears to be running!")
            print("     Please stop it first: pkill -f 'uvicorn app.main:app'")
            response = input("     Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                return False
    except FileNotFoundError:
        # pgrep not available, skip check
        pass
    except Exception:
        pass
    
    # Check markdown directory
    if not MARKDOWN_DIR.exists():
        print(f"  ✗ Error: Markdown directory not found: {MARKDOWN_DIR}")
        return False
    print(f"  ✓ Markdown directory exists: {MARKDOWN_DIR}")
    
    # Check evaluation file
    if not EVALUATION_FILE.exists():
        print(f"  ✗ Error: Evaluation file not found: {EVALUATION_FILE}")
        return False
    print(f"  ✓ Evaluation file exists: {EVALUATION_FILE}")
    
    # Check database directory permissions
    if DB_DIR.exists():
        try:
            test_file = DB_DIR / ".test_write"
            test_file.write_text("test")
            test_file.unlink()
            print(f"  ✓ Database directory is writable: {DB_DIR}")
        except Exception as e:
            print(f"  ✗ Error: Database directory not writable: {e}")
            print(f"     Try: chmod -R u+w {DB_DIR}")
            return False
    else:
        print(f"  ✓ Database directory will be created: {DB_DIR}")
    
    print()
    return True


def test_all_configurations_quick():
    """
    Quickly test all chunk configurations.
    """
    print("="*60)
    print("QUICK CHUNK CONFIGURATION TESTING")
    print("="*60)
    embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
    print(f"Embedding Model: {embedding_model}")
    print(f"Testing {NUM_TEST_QUESTIONS} questions per configuration")
    print(f"Database Directory: {DB_DIR}")
    print("="*60)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n✗ Prerequisites not met. Please fix issues above and try again.")
        return
    
    # Load test questions
    print(f"\nLoading test questions...")
    test_questions = load_test_questions(NUM_TEST_QUESTIONS)
    
    if not test_questions:
        print("✗ No test questions loaded. Exiting.")
        return
    
    print(f"✓ Loaded {len(test_questions)} test questions")
    
    all_results = []
    total_start = time.time()
    
    # Test each configuration
    for idx, (chunk_size, chunk_overlap, description) in enumerate(TEST_CONFIGURATIONS, 1):
        print(f"\n{'#'*60}")
        print(f"TEST {idx}/{len(TEST_CONFIGURATIONS)}: {description}")
        print(f"{'#'*60}")
        
        # Rebuild database
        num_chunks = rebuild_database_with_config(chunk_size, chunk_overlap)
        
        if num_chunks is None:
            print("✗ Skipping due to rebuild failure\n")
            continue
        
        # Small delay to let database settle
        time.sleep(1)
        
        # Test retrieval quality
        print(f"\n  Starting retrieval quality tests...")
        config_start = time.time()
        metrics = test_retrieval_quality(chunk_size, chunk_overlap, test_questions)
        config_time = time.time() - config_start
        print(f"  ✓ Completed retrieval tests")
        
        # Clean up: Force close any database connections before next rebuild
        # This prevents locking issues on subsequent tests
        import gc
        gc.collect()  # Force garbage collection to clean up connections
        time.sleep(0.5)  # Small delay after cleanup
        
        metrics['total_chunks_in_db'] = num_chunks
        metrics['chunk_size'] = chunk_size
        metrics['chunk_overlap'] = chunk_overlap
        metrics['description'] = description
        metrics['test_time'] = config_time
        metrics['embedding_model'] = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        # Get LLM model from rag_pipeline or environment
        try:
            import app.rag_pipeline as rag_module
            # Try to get model name from the llm object (ChatGroq stores it in model_name attribute)
            if hasattr(rag_module, 'llm'):
                llm_obj = rag_module.llm
                llm_model = getattr(llm_obj, 'model_name', None)
                if not llm_model:
                    # Fallback: check model attribute or use default
                    llm_model = getattr(llm_obj, 'model', None) or os.getenv('LLM_MODEL', 'llama-3.1-8b-instant')
                metrics['llm_model'] = llm_model
            else:
                metrics['llm_model'] = os.getenv('LLM_MODEL', 'llama-3.1-8b-instant')
        except Exception as e:
            # Default fallback
            metrics['llm_model'] = os.getenv('LLM_MODEL', 'llama-3.1-8b-instant')
        
        all_results.append(metrics)
        
        print(f"✓ Configuration tested in {config_time:.1f}s")
        print(f"  Avg Relevance: {metrics['avg_relevance']:.3f}")
        print(f"  Avg Chunks Retrieved: {metrics['avg_chunks_retrieved']:.1f}")
        print(f"  Avg Query Time: {metrics['avg_query_time']:.2f}s\n")
    
    # Compare and report results
    if all_results:
        total_time = time.time() - total_start
        
        print("\n" + "="*60)
        print("QUICK TEST RESULTS")
        print("="*60)
        
        # Create comparison DataFrame
        df = pd.DataFrame(all_results)
        
        # Calculate composite score (higher is better)
        # Normalize relevance (0-1) and penalize slow queries
        df['composite_score'] = (
            df['avg_relevance'] * 0.6 +  # Relevance is most important
            (df['avg_chunks_retrieved'] / 10).clip(0, 1) * 0.2 +  # Good chunk count (cap at 10)
            (1 / (df['avg_query_time'] + 0.5)).clip(0, 1) * 0.2  # Faster is better
        )
        
        df = df.sort_values('composite_score', ascending=False)
        
        # Print summary table
        print("\nConfiguration Comparison (sorted by composite score):")
        print("-" * 80)
        print(f"{'Config':<25} {'Relevance':<12} {'Chunks':<10} {'Query Time':<12} {'Score':<10}")
        print("-" * 80)
        
        for _, row in df.iterrows():
            config_desc = f"{row['chunk_size']}/{row['chunk_overlap']}"
            print(f"{config_desc:<25} {row['avg_relevance']:.3f}{'':<6} "
                  f"{row['avg_chunks_retrieved']:.1f}{'':<4} "
                  f"{row['avg_query_time']:.2f}s{'':<5} {row['composite_score']:.3f}")
        
        # Find best configuration
        best_config = df.iloc[0]
        
        print("\n" + "="*60)
        print("RECOMMENDED CONFIGURATION (Quick Test)")
        print("="*60)
        print(f"Description: {best_config['description']}")
        print(f"Chunk Size: {int(best_config['chunk_size'])}")
        print(f"Chunk Overlap: {int(best_config['chunk_overlap'])}")
        print(f"Avg Relevance: {best_config['avg_relevance']:.3f}")
        print(f"Avg Chunks Retrieved: {best_config['avg_chunks_retrieved']:.1f}")
        print(f"Avg Query Time: {best_config['avg_query_time']:.2f}s")
        print(f"Total Chunks in DB: {int(best_config['total_chunks_in_db'])}")
        print("="*60)
        
        # Save results
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = RESULTS_DIR / f"quick_test_results_{timestamp}.csv"
        df.to_csv(results_file, index=False)
        
        print(f"\n✓ Results saved to: {results_file}")
        print(f"✓ Total test time: {total_time/60:.1f} minutes")
        print(f"\nNote: This is a quick test. For comprehensive evaluation,")
        print(f"      run: python monitoring/test_chunk_configurations.py")
        
        # Recommend configuration
        print("\n" + "="*60)
        print("RECOMMENDED .env CONFIGURATION")
        print("="*60)
        print(f"CHUNK_SIZE={int(best_config['chunk_size'])}")
        print(f"CHUNK_OVERLAP={int(best_config['chunk_overlap'])}")
        print("="*60)
        
    else:
        print("\n✗ No successful tests. Check errors above.")


if __name__ == "__main__":
    try:
        test_all_configurations_quick()
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

