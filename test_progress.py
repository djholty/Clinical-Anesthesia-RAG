#!/usr/bin/env python3
"""
Test script to verify progress bar functionality.
"""

import sys
import os
import time

# Add the monitoring directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'monitoring'))

from evaluate_rag import run_evaluation

def test_progress_callback(current, total):
    """Test progress callback function."""
    print(f"Progress: {current}/{total} ({current/total*100:.1f}%)")
    time.sleep(0.1)  # Small delay to make progress visible

def main():
    """Test the evaluation with progress callback."""
    print("Testing progress bar functionality...")
    
    # Path to the prompt file
    prompt_file = "monitoring/prompt_set.xlsx"
    
    if not os.path.exists(prompt_file):
        print(f"Error: {prompt_file} not found")
        return
    
    print(f"Running evaluation on {prompt_file}")
    print("You should see progress updates below:")
    print("-" * 50)
    
    # Run evaluation with progress callback
    results, avg_score = run_evaluation(
        prompt_file, 
        progress_callback=test_progress_callback
    )
    
    if results:
        print("-" * 50)
        print(f"Evaluation completed! Average score: {avg_score:.2f}/4")
        print(f"Processed {len(results)} questions")
    else:
        print("Evaluation failed!")

if __name__ == "__main__":
    main()
