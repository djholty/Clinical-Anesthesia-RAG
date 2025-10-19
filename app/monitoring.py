"""
Monitoring endpoints for RAG model evaluation
"""
import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# Directory for storing evaluation results
EVAL_DIR = "./monitoring/evaluations"
os.makedirs(EVAL_DIR, exist_ok=True)

def get_latest_evaluation():
    """Get the most recent evaluation results."""
    eval_files = list(Path(EVAL_DIR).glob("evaluation_*.csv"))
    
    if not eval_files:
        # Check for default file
        default_file = "./monitoring/evaluation_results.csv"
        if os.path.exists(default_file):
            df = pd.read_csv(default_file)
            return {
                "timestamp": "Unknown",
                "total_questions": len(df),
                "average_score": float(df['score'].mean()),
                "score_distribution": {
                    "excellent": int(len(df[df['score'] >= 90])),
                    "good": int(len(df[(df['score'] >= 70) & (df['score'] < 90)])),
                    "fair": int(len(df[(df['score'] >= 50) & (df['score'] < 70)])),
                    "poor": int(len(df[df['score'] < 50]))
                },
                "results": df.to_dict('records')
            }
        return None
    
    # Get most recent file
    latest_file = max(eval_files, key=lambda p: p.stat().st_mtime)
    df = pd.read_csv(latest_file)
    
    # Extract timestamp from filename
    timestamp = latest_file.stem.replace("evaluation_", "")
    
    return {
        "timestamp": timestamp,
        "total_questions": len(df),
        "average_score": float(df['score'].mean()),
        "score_distribution": {
            "excellent": int(len(df[df['score'] >= 90])),
            "good": int(len(df[(df['score'] >= 70) & (df['score'] < 90)])),
            "fair": int(len(df[(df['score'] >= 50) & (df['score'] < 70)])),
            "poor": int(len(df[df['score'] < 50]))
        },
        "results": df.to_dict('records')
    }

def get_all_evaluations():
    """Get summary of all evaluation runs."""
    eval_files = list(Path(EVAL_DIR).glob("evaluation_*.csv"))
    
    evaluations = []
    for file in sorted(eval_files, key=lambda p: p.stat().st_mtime, reverse=True):
        df = pd.read_csv(file)
        timestamp = file.stem.replace("evaluation_", "")
        
        evaluations.append({
            "timestamp": timestamp,
            "total_questions": len(df),
            "average_score": float(df['score'].mean()),
            "filename": file.name
        })
    
    return evaluations

def get_evaluation_by_timestamp(timestamp):
    """Get specific evaluation by timestamp."""
    file_path = Path(EVAL_DIR) / f"evaluation_{timestamp}.csv"
    
    if not file_path.exists():
        return None
    
    df = pd.read_csv(file_path)
    
    return {
        "timestamp": timestamp,
        "total_questions": len(df),
        "average_score": float(df['score'].mean()),
        "score_distribution": {
            "excellent": int(len(df[df['score'] >= 90])),
            "good": int(len(df[(df['score'] >= 70) & (df['score'] < 90)])),
            "fair": int(len(df[(df['score'] >= 50) & (df['score'] < 70)])),
            "poor": int(len(df[df['score'] < 50]))
        },
        "results": df.to_dict('records')
    }

