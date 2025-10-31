"""
Test Different Chunk Configurations for BioBERT Embedding Model

This script tests various chunk size and overlap combinations to find
the optimal configuration for medical/clinical text retrieval.

Process:
1. Defines test configurations (chunk_size, chunk_overlap pairs)
2. For each configuration:
   - Sets environment variables
   - Rebuilds database
   - Runs evaluation on test questions
   - Collects performance metrics
3. Compares all results and reports the best configuration
"""

import os
import sys
import subprocess
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import shutil

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from monitoring.evaluate_rag import run_evaluation

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
DB_DIR = Path(os.getenv("DB_DIR", str(PROJECT_ROOT / "data" / "chroma_db")))
MARKDOWN_DIR = Path(os.getenv("MARKDOWN_DIR", str(PROJECT_ROOT / "data" / "ingested_documents")))
EVALUATION_FILE = PROJECT_ROOT / "monitoring" / "prompt_set.xlsx"
RESULTS_DIR = PROJECT_ROOT / "monitoring" / "chunk_config_tests"

# Test configurations to evaluate
# Format: (chunk_size, chunk_overlap, description)
TEST_CONFIGURATIONS = [
    # Small chunks - more granular
    (1000, 150, "Small chunks - high precision"),
    (1000, 200, "Small chunks - medium overlap"),
    
    # Medium chunks - balanced
    (1500, 200, "Medium-small chunks"),
    (1500, 300, "Medium-small chunks - good overlap"),
    (2000, 300, "Default - balanced"),
    (2000, 400, "Default - higher overlap"),
    
    # Larger chunks - more context
    (2500, 400, "Large chunks - good context"),
    (3000, 400, "Very large chunks"),
    (3000, 500, "Very large chunks - high overlap"),
]

# Create results directory
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def rebuild_database_with_config(chunk_size: int, chunk_overlap: int):
    """
    Rebuild the database with specified chunk configuration.
    
    Args:
        chunk_size: Size of each chunk in characters
        chunk_overlap: Overlap between chunks in characters
    """
    print(f"\n{'='*60}")
    print(f"Rebuilding database with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    print(f"{'='*60}")
    
    # Set environment variables for this test
    os.environ["CHUNK_SIZE"] = str(chunk_size)
    os.environ["CHUNK_OVERLAP"] = str(chunk_overlap)
    
    # Import here to ensure env vars are set
    from app.rebuild_database import rebuild_database
    
    try:
        rebuild_database()
        print(f"✓ Database rebuilt successfully\n")
        return True
    except Exception as e:
        print(f"✗ Error rebuilding database: {e}\n")
        return False


def run_evaluation_for_config(chunk_size: int, chunk_overlap: int, description: str):
    """
    Run evaluation for a specific chunk configuration.
    
    Args:
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks
        description: Description of this configuration
        
    Returns:
        dict: Evaluation results with metrics
    """
    print(f"\n{'='*60}")
    print(f"Evaluating configuration: {description}")
    print(f"  chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
    print(f"{'='*60}\n")
    
    if not EVALUATION_FILE.exists():
        print(f"✗ Error: Evaluation file not found: {EVALUATION_FILE}")
        return None
    
    # Run evaluation
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    config_name = f"chunk{chunk_size}_overlap{chunk_overlap}"
    output_file = RESULTS_DIR / f"eval_{config_name}_{timestamp}.csv"
    
    try:
        # Run evaluation with progress callback
        def progress_callback(current, total):
            if current % 5 == 0 or current == total:
                print(f"  Progress: {current}/{total} questions ({current/total*100:.1f}%)")
        
        eval_result = run_evaluation(
            str(EVALUATION_FILE),
            output_csv=str(output_file),
            max_workers=3,
            progress_callback=progress_callback
        )
        
        # Handle tuple return (results, avg_score) or just results
        if isinstance(eval_result, tuple):
            results, avg_score_from_eval = eval_result
        else:
            results = eval_result
        
        if results:
            # Calculate metrics
            scores = [r['score'] for r in results if isinstance(r.get('score'), (int, float))]
            citation_scores = [r.get('citation_score', 0) for r in results if isinstance(r.get('citation_score'), (int, float))]
            
            avg_score = sum(scores) / len(scores) if scores else 0
            avg_citation = sum(citation_scores) / len(citation_scores) if citation_scores else 0
            
            # Count score distribution
            score_dist = {
                4: sum(1 for s in scores if s == 4),
                3: sum(1 for s in scores if s == 3),
                2: sum(1 for s in scores if s == 2),
                1: sum(1 for s in scores if s == 1),
            }
            
            # Get model names
            embedding_model = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
            # Get LLM model from rag_pipeline or environment
            try:
                import app.rag_pipeline as rag_module
                if hasattr(rag_module, 'llm'):
                    llm_obj = rag_module.llm
                    llm_model = getattr(llm_obj, 'model_name', None)
                    if not llm_model:
                        llm_model = getattr(llm_obj, 'model', None) or os.getenv('LLM_MODEL', 'llama-3.1-8b-instant')
                else:
                    llm_model = os.getenv('LLM_MODEL', 'llama-3.1-8b-instant')
            except Exception:
                llm_model = os.getenv('LLM_MODEL', 'llama-3.1-8b-instant')
            
            result_summary = {
                'chunk_size': chunk_size,
                'chunk_overlap': chunk_overlap,
                'description': description,
                'avg_score': avg_score,
                'avg_citation_score': avg_citation,
                'total_questions': len(results),
                'excellent_count': score_dist[4],
                'good_count': score_dist[3],
                'fair_count': score_dist[2],
                'poor_count': score_dist[1],
                'excellent_pct': (score_dist[4] / len(scores) * 100) if scores else 0,
                'output_file': str(output_file),
                'embedding_model': embedding_model,
                'llm_model': llm_model
            }
            
            print(f"\n✓ Evaluation complete")
            print(f"  Average Score: {avg_score:.2f}/4")
            print(f"  Average Citation Score: {avg_citation:.2f}/4")
            print(f"  Excellent Answers: {score_dist[4]} ({score_dist[4]/len(scores)*100:.1f}%)")
            print(f"  Results saved to: {output_file}\n")
            
            return result_summary
        else:
            print(f"✗ Evaluation returned no results\n")
            return None
            
    except Exception as e:
        print(f"✗ Error during evaluation: {e}\n")
        import traceback
        traceback.print_exc()
        return None


def test_all_configurations():
    """
    Test all chunk configurations and compare results.
    """
    print("="*60)
    print("CHUNK CONFIGURATION TESTING FOR BIOBERT")
    print("="*60)
    print(f"Embedding Model: {os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')}")
    print(f"Database Directory: {DB_DIR}")
    print(f"Markdown Directory: {MARKDOWN_DIR}")
    print(f"Evaluation File: {EVALUATION_FILE}")
    print(f"Results Directory: {RESULTS_DIR}")
    print("="*60)
    
    # Verify prerequisites
    if not MARKDOWN_DIR.exists():
        print(f"✗ Error: Markdown directory not found: {MARKDOWN_DIR}")
        return
    
    if not EVALUATION_FILE.exists():
        print(f"✗ Error: Evaluation file not found: {EVALUATION_FILE}")
        return
    
    all_results = []
    
    # Test each configuration
    for idx, (chunk_size, chunk_overlap, description) in enumerate(TEST_CONFIGURATIONS, 1):
        print(f"\n{'#'*60}")
        print(f"TEST {idx}/{len(TEST_CONFIGURATIONS)}")
        print(f"{'#'*60}")
        
        # Rebuild database with this configuration
        if not rebuild_database_with_config(chunk_size, chunk_overlap):
            print(f"✗ Skipping evaluation due to rebuild failure\n")
            continue
        
        # Run evaluation
        result = run_evaluation_for_config(chunk_size, chunk_overlap, description)
        
        if result:
            all_results.append(result)
        else:
            print(f"✗ Skipping due to evaluation failure\n")
    
    # Compare and report results
    if all_results:
        print("\n" + "="*60)
        print("COMPARISON RESULTS")
        print("="*60)
        
        # Create comparison DataFrame
        df = pd.DataFrame(all_results)
        df = df.sort_values('avg_score', ascending=False)
        
        # Print summary table
        print("\nConfiguration Comparison (sorted by average score):")
        print("-" * 60)
        print(f"{'Config':<30} {'Avg Score':<12} {'Excellent %':<12} {'Citation':<10}")
        print("-" * 60)
        
        for _, row in df.iterrows():
            config_desc = f"{row['chunk_size']}/{row['chunk_overlap']}"
            print(f"{config_desc:<30} {row['avg_score']:.2f}/4{'':<6} {row['excellent_pct']:.1f}%{'':<6} {row['avg_citation_score']:.2f}/4")
        
        # Find best configuration
        best_config = df.iloc[0]
        
        print("\n" + "="*60)
        print("BEST CONFIGURATION")
        print("="*60)
        print(f"Description: {best_config['description']}")
        print(f"Chunk Size: {best_config['chunk_size']}")
        print(f"Chunk Overlap: {best_config['chunk_overlap']}")
        print(f"Average Score: {best_config['avg_score']:.2f}/4")
        print(f"Average Citation Score: {best_config['avg_citation_score']:.2f}/4")
        print(f"Excellent Answers: {best_config['excellent_count']} ({best_config['excellent_pct']:.1f}%)")
        print(f"Total Questions: {best_config['total_questions']}")
        print("="*60)
        
        # Save comparison results
        comparison_file = RESULTS_DIR / f"chunk_config_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(comparison_file, index=False)
        print(f"\n✓ Comparison results saved to: {comparison_file}")
        
        # Save summary JSON
        summary_file = RESULTS_DIR / f"chunk_config_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary = {
            'best_config': {
                'chunk_size': int(best_config['chunk_size']),
                'chunk_overlap': int(best_config['chunk_overlap']),
                'description': best_config['description'],
                'avg_score': float(best_config['avg_score']),
                'avg_citation_score': float(best_config['avg_citation_score']),
                'excellent_pct': float(best_config['excellent_pct'])
            },
            'all_configs': df.to_dict('records'),
            'test_date': datetime.now().isoformat(),
            'embedding_model': os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"✓ Summary saved to: {summary_file}")
        
        # Recommend configuration for .env file
        print("\n" + "="*60)
        print("RECOMMENDED .env CONFIGURATION")
        print("="*60)
        print(f"CHUNK_SIZE={int(best_config['chunk_size'])}")
        print(f"CHUNK_OVERLAP={int(best_config['chunk_overlap'])}")
        print("="*60)
        
    else:
        print("\n✗ No successful evaluations. Check errors above.")


if __name__ == "__main__":
    try:
        test_all_configurations()
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

