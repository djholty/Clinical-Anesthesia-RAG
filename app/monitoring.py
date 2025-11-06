"""
Monitoring endpoints for RAG model evaluation
"""
import os
import pandas as pd
import json
import math
import random
from datetime import datetime
from pathlib import Path

# Directory for storing evaluation results
EVAL_DIR = "./monitoring/evaluations"
os.makedirs(EVAL_DIR, exist_ok=True)

# Directory for storing manual assessment results
MANUAL_ASSESSMENT_DIR = "./monitoring/manual_assessments"
os.makedirs(MANUAL_ASSESSMENT_DIR, exist_ok=True)

def clean_nan_values(obj):
    """
    Recursively replace NaN, Inf, and -Inf values with None in dictionaries and lists.
    This prevents JSON serialization errors.
    """
    if isinstance(obj, dict):
        return {k: clean_nan_values(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nan_values(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif pd.isna(obj):
        return None
    else:
        return obj

def get_latest_evaluation():
    """Get the most recent evaluation results."""
    eval_files = list(Path(EVAL_DIR).glob("evaluation_*.csv"))
    
    if not eval_files:
        # Check for default file
        default_file = "./monitoring/evaluation_results.csv"
        if os.path.exists(default_file):
            df = pd.read_csv(default_file)
            
            # Calculate citation score stats if column exists
            citation_stats = {}
            if 'citation_score' in df.columns:
                avg_cit_score = df['citation_score'].mean()
                citation_stats = {
                    "average_citation_score": float(avg_cit_score) if not pd.isna(avg_cit_score) else 0.0,
                    "citation_score_distribution": {
                        "excellent": int(len(df[df['citation_score'] == 4])),
                        "good": int(len(df[df['citation_score'] == 3])),
                        "fair": int(len(df[df['citation_score'] == 2])),
                        "poor": int(len(df[df['citation_score'] == 1]))
                    }
                }
            
            # Parse JSON strings back to dicts for citation_metrics and citation_details
            results = []
            for _, row in df.iterrows():
                result_dict = row.to_dict()
                # Clean NaN values immediately after conversion
                result_dict = clean_nan_values(result_dict)
                
                # Parse citation_metrics if it's a JSON string
                if 'citation_metrics' in result_dict and isinstance(result_dict['citation_metrics'], str):
                    try:
                        result_dict['citation_metrics'] = json.loads(result_dict['citation_metrics'])
                    except:
                        result_dict['citation_metrics'] = {}
                
                # Reconstruct citation_metrics from separate columns if JSON parsing failed
                if not isinstance(result_dict.get('citation_metrics'), dict) or not result_dict.get('citation_metrics'):
                    metrics = {}
                    if 'citation_faithfulness' in result_dict and pd.notna(result_dict['citation_faithfulness']):
                        metrics['faithfulness'] = result_dict['citation_faithfulness']
                    if 'citation_grounding' in result_dict and pd.notna(result_dict['citation_grounding']):
                        metrics['grounding'] = result_dict['citation_grounding']
                    if 'citation_precision' in result_dict and pd.notna(result_dict['citation_precision']):
                        metrics['precision'] = result_dict['citation_precision']
                    if 'citation_recall' in result_dict and pd.notna(result_dict['citation_recall']):
                        metrics['recall'] = result_dict['citation_recall']
                    if 'citation_relevance' in result_dict and pd.notna(result_dict['citation_relevance']):
                        metrics['relevance'] = result_dict['citation_relevance']
                    if 'citation_consistency' in result_dict and pd.notna(result_dict['citation_consistency']):
                        metrics['consistency'] = result_dict['citation_consistency']
                    if metrics:
                        result_dict['citation_metrics'] = metrics
                
                # Parse citation_details if it's a JSON string
                if 'citation_details' in result_dict and isinstance(result_dict['citation_details'], str):
                    try:
                        result_dict['citation_details'] = json.loads(result_dict['citation_details'])
                    except:
                        result_dict['citation_details'] = {}
                
                # Parse contexts if it's a JSON string
                if 'contexts' in result_dict and isinstance(result_dict['contexts'], str):
                    try:
                        result_dict['contexts'] = json.loads(result_dict['contexts'])
                    except:
                        result_dict['contexts'] = []
                
                results.append(clean_nan_values(result_dict))
            
            avg_score = df['score'].mean()
            result = {
                "timestamp": "Unknown",
                "total_questions": len(df),
                "average_score": float(avg_score) if not pd.isna(avg_score) else 0.0,
                "score_distribution": {
                    "excellent": int(len(df[df['score'] == 4])),
                    "good": int(len(df[df['score'] == 3])),
                    "fair": int(len(df[df['score'] == 2])),
                    "poor": int(len(df[df['score'] == 1]))
                },
                **citation_stats,  # Add citation stats if available
                "results": results
            }
            return clean_nan_values(result)
        return None
    
    # Get most recent file
    latest_file = max(eval_files, key=lambda p: p.stat().st_mtime)
    df = pd.read_csv(latest_file)
    
    # Extract timestamp from filename
    timestamp = latest_file.stem.replace("evaluation_", "")
    
    # Calculate citation score stats if column exists
    citation_stats = {}
    if 'citation_score' in df.columns:
        avg_cit_score = df['citation_score'].mean()
        citation_stats = {
            "average_citation_score": float(avg_cit_score) if not pd.isna(avg_cit_score) else 0.0,
            "citation_score_distribution": {
                "excellent": int(len(df[df['citation_score'] == 4])),
                "good": int(len(df[df['citation_score'] == 3])),
                "fair": int(len(df[df['citation_score'] == 2])),
                "poor": int(len(df[df['citation_score'] == 1]))
            }
        }
    
    # Parse JSON strings back to dicts for citation_metrics and citation_details
    results = []
    for _, row in df.iterrows():
        result_dict = row.to_dict()
        # Clean NaN values immediately after conversion
        result_dict = clean_nan_values(result_dict)
        
        # Parse citation_metrics if it's a JSON string
        if 'citation_metrics' in result_dict and isinstance(result_dict['citation_metrics'], str):
            try:
                result_dict['citation_metrics'] = json.loads(result_dict['citation_metrics'])
            except:
                result_dict['citation_metrics'] = {}
        
        # Reconstruct citation_metrics from separate columns if JSON parsing failed
        if not isinstance(result_dict.get('citation_metrics'), dict) or not result_dict.get('citation_metrics'):
            metrics = {}
            if 'citation_faithfulness' in result_dict and pd.notna(result_dict['citation_faithfulness']):
                metrics['faithfulness'] = result_dict['citation_faithfulness']
            if 'citation_grounding' in result_dict and pd.notna(result_dict['citation_grounding']):
                metrics['grounding'] = result_dict['citation_grounding']
            if 'citation_precision' in result_dict and pd.notna(result_dict['citation_precision']):
                metrics['precision'] = result_dict['citation_precision']
            if 'citation_recall' in result_dict and pd.notna(result_dict['citation_recall']):
                metrics['recall'] = result_dict['citation_recall']
            if 'citation_relevance' in result_dict and pd.notna(result_dict['citation_relevance']):
                metrics['relevance'] = result_dict['citation_relevance']
            if 'citation_consistency' in result_dict and pd.notna(result_dict['citation_consistency']):
                metrics['consistency'] = result_dict['citation_consistency']
            if metrics:
                result_dict['citation_metrics'] = metrics
        
        # Parse citation_details if it's a JSON string
        if 'citation_details' in result_dict and isinstance(result_dict['citation_details'], str):
            try:
                result_dict['citation_details'] = json.loads(result_dict['citation_details'])
            except:
                result_dict['citation_details'] = {}
        
        # Parse contexts if it's a JSON string
        if 'contexts' in result_dict and isinstance(result_dict['contexts'], str):
            try:
                result_dict['contexts'] = json.loads(result_dict['contexts'])
            except:
                result_dict['contexts'] = []
        
        results.append(clean_nan_values(result_dict))
    
    avg_score = df['score'].mean()
    result = {
        "timestamp": timestamp,
        "total_questions": len(df),
        "average_score": float(avg_score) if not pd.isna(avg_score) else 0.0,
        "score_distribution": {
            "excellent": int(len(df[df['score'] == 4])),
            "good": int(len(df[df['score'] == 3])),
            "fair": int(len(df[df['score'] == 2])),
            "poor": int(len(df[df['score'] == 1]))
        },
        **citation_stats,  # Add citation stats if available
        "results": results
    }
    return clean_nan_values(result)

def get_all_evaluations():
    """Get summary of all evaluation runs."""
    eval_files = list(Path(EVAL_DIR).glob("evaluation_*.csv"))
    
    evaluations = []
    for file in sorted(eval_files, key=lambda p: p.stat().st_mtime, reverse=True):
        df = pd.read_csv(file)
        timestamp = file.stem.replace("evaluation_", "")
        
        avg_score = df['score'].mean()
        evaluations.append({
            "timestamp": timestamp,
            "total_questions": len(df),
            "average_score": float(avg_score) if not pd.isna(avg_score) else 0.0,
            "filename": file.name
        })
    
    return evaluations

def get_evaluation_by_timestamp(timestamp):
    """Get specific evaluation by timestamp."""
    file_path = Path(EVAL_DIR) / f"evaluation_{timestamp}.csv"
    
    if not file_path.exists():
        return None
    
    df = pd.read_csv(file_path)
    
    # Calculate citation score stats if column exists
    citation_stats = {}
    if 'citation_score' in df.columns:
        avg_cit_score = df['citation_score'].mean()
        citation_stats = {
            "average_citation_score": float(avg_cit_score) if not pd.isna(avg_cit_score) else 0.0,
            "citation_score_distribution": {
                "excellent": int(len(df[df['citation_score'] == 4])),
                "good": int(len(df[df['citation_score'] == 3])),
                "fair": int(len(df[df['citation_score'] == 2])),
                "poor": int(len(df[df['citation_score'] == 1]))
            }
        }
    
    # Parse JSON strings back to dicts for citation_metrics and citation_details
    results = []
    for _, row in df.iterrows():
        result_dict = row.to_dict()
        # Clean NaN values immediately after conversion
        result_dict = clean_nan_values(result_dict)
        
        # Parse citation_metrics if it's a JSON string
        if 'citation_metrics' in result_dict and isinstance(result_dict['citation_metrics'], str):
            try:
                result_dict['citation_metrics'] = json.loads(result_dict['citation_metrics'])
            except:
                result_dict['citation_metrics'] = {}
        
        # Reconstruct citation_metrics from separate columns if JSON parsing failed
        if not isinstance(result_dict.get('citation_metrics'), dict) or not result_dict.get('citation_metrics'):
            metrics = {}
            if 'citation_faithfulness' in result_dict and pd.notna(result_dict['citation_faithfulness']):
                metrics['faithfulness'] = result_dict['citation_faithfulness']
            if 'citation_grounding' in result_dict and pd.notna(result_dict['citation_grounding']):
                metrics['grounding'] = result_dict['citation_grounding']
            if 'citation_precision' in result_dict and pd.notna(result_dict['citation_precision']):
                metrics['precision'] = result_dict['citation_precision']
            if 'citation_recall' in result_dict and pd.notna(result_dict['citation_recall']):
                metrics['recall'] = result_dict['citation_recall']
            if 'citation_relevance' in result_dict and pd.notna(result_dict['citation_relevance']):
                metrics['relevance'] = result_dict['citation_relevance']
            if 'citation_consistency' in result_dict and pd.notna(result_dict['citation_consistency']):
                metrics['consistency'] = result_dict['citation_consistency']
            if metrics:
                result_dict['citation_metrics'] = metrics
        
        # Parse citation_details if it's a JSON string
        if 'citation_details' in result_dict and isinstance(result_dict['citation_details'], str):
            try:
                result_dict['citation_details'] = json.loads(result_dict['citation_details'])
            except:
                result_dict['citation_details'] = {}
        
        # Parse contexts if it's a JSON string
        if 'contexts' in result_dict and isinstance(result_dict['contexts'], str):
            try:
                result_dict['contexts'] = json.loads(result_dict['contexts'])
            except:
                result_dict['contexts'] = []
        
        results.append(result_dict)
    
    avg_score = df['score'].mean()
    result = {
        "timestamp": timestamp,
        "total_questions": len(df),
        "average_score": float(avg_score) if not pd.isna(avg_score) else 0.0,
        "score_distribution": {
            "excellent": int(len(df[df['score'] == 4])),
            "good": int(len(df[df['score'] == 3])),
            "fair": int(len(df[df['score'] == 2])),
            "poor": int(len(df[df['score'] == 1]))
        },
        **citation_stats,  # Add citation stats if available
        "results": results
    }
    return clean_nan_values(result)

def get_random_questions_sample(n=20):
    """
    Get a random sample of n questions from the latest evaluation.
    
    Args:
        n (int): Number of questions to sample (default: 20)
        
    Returns:
        list: List of question dictionaries with question, rag_answer, expected_answer, etc.
    """
    latest_eval = get_latest_evaluation()
    if not latest_eval or 'results' not in latest_eval:
        return None
    
    results = latest_eval['results']
    if len(results) < n:
        # If we have fewer questions than requested, return all
        return results
    
    # Randomly sample n questions
    return random.sample(results, n)

def save_manual_assessment(assessment_data):
    """
    Save manual assessment results to CSV file.
    
    Args:
        assessment_data (dict): Dictionary containing:
            - questions: List of question dictionaries with manual scores
            - Each question dict should have: question, rag_answer, expected_answer (optional),
              manual_accuracy_score, manual_citation_score
    
    Returns:
        str: Timestamp of the saved assessment
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"manual_assessment_{timestamp}.csv"
    filepath = Path(MANUAL_ASSESSMENT_DIR) / filename
    
    # Prepare data for CSV
    rows = []
    for q in assessment_data.get('questions', []):
        row = {
            'question': q.get('question', ''),
            'rag_answer': q.get('rag_answer', ''),
            'expected_answer': q.get('expected_answer', ''),
            'manual_accuracy_score': q.get('manual_accuracy_score', None),
            'manual_citation_score': q.get('manual_citation_score', None),
            'timestamp': timestamp,
            'assessment_type': 'manual'
        }
        rows.append(row)
    
    # Create DataFrame and save
    df = pd.DataFrame(rows)
    df.to_csv(filepath, index=False)
    
    return timestamp

def get_all_manual_assessments():
    """
    Get summary of all manual assessment runs.
    
    Returns:
        list: List of assessment summaries with timestamp, total_questions, average_score, etc.
    """
    assessment_files = list(Path(MANUAL_ASSESSMENT_DIR).glob("manual_assessment_*.csv"))
    
    assessments = []
    for file in sorted(assessment_files, key=lambda p: p.stat().st_mtime, reverse=True):
        df = pd.read_csv(file)
        timestamp = file.stem.replace("manual_assessment_", "")
        
        # Calculate averages
        avg_accuracy = df['manual_accuracy_score'].mean() if 'manual_accuracy_score' in df.columns else 0.0
        avg_citation = df['manual_citation_score'].mean() if 'manual_citation_score' in df.columns else 0.0
        
        # Calculate distributions
        accuracy_dist = {
            "excellent": int(len(df[df['manual_accuracy_score'] == 4])),
            "good": int(len(df[df['manual_accuracy_score'] == 3])),
            "fair": int(len(df[df['manual_accuracy_score'] == 2])),
            "poor": int(len(df[df['manual_accuracy_score'] == 1]))
        }
        
        citation_dist = {}
        if 'manual_citation_score' in df.columns:
            citation_dist = {
                "excellent": int(len(df[df['manual_citation_score'] == 4])),
                "good": int(len(df[df['manual_citation_score'] == 3])),
                "fair": int(len(df[df['manual_citation_score'] == 2])),
                "poor": int(len(df[df['manual_citation_score'] == 1]))
            }
        
        assessments.append({
            "timestamp": timestamp,
            "total_questions": len(df),
            "average_score": float(avg_accuracy) if not pd.isna(avg_accuracy) else 0.0,
            "average_citation_score": float(avg_citation) if not pd.isna(avg_citation) else 0.0,
            "score_distribution": accuracy_dist,
            "citation_score_distribution": citation_dist,
            "assessment_type": "manual",
            "filename": file.name
        })
    
    return assessments

def get_latest_manual_assessment():
    """
    Get the most recent manual assessment results.
    
    Returns:
        dict: Assessment results in same format as get_latest_evaluation(), or None if no assessments exist
    """
    assessment_files = list(Path(MANUAL_ASSESSMENT_DIR).glob("manual_assessment_*.csv"))
    
    if not assessment_files:
        return None
    
    # Get most recent file
    latest_file = max(assessment_files, key=lambda p: p.stat().st_mtime)
    df = pd.read_csv(latest_file)
    
    # Extract timestamp from filename
    timestamp = latest_file.stem.replace("manual_assessment_", "")
    
    # Calculate averages
    avg_accuracy = df['manual_accuracy_score'].mean() if 'manual_accuracy_score' in df.columns else 0.0
    avg_citation = df['manual_citation_score'].mean() if 'manual_citation_score' in df.columns else 0.0
    
    # Calculate distributions
    accuracy_dist = {
        "excellent": int(len(df[df['manual_accuracy_score'] == 4])),
        "good": int(len(df[df['manual_accuracy_score'] == 3])),
        "fair": int(len(df[df['manual_accuracy_score'] == 2])),
        "poor": int(len(df[df['manual_accuracy_score'] == 1]))
    }
    
    citation_dist = {}
    citation_stats = {}
    if 'manual_citation_score' in df.columns:
        citation_dist = {
            "excellent": int(len(df[df['manual_citation_score'] == 4])),
            "good": int(len(df[df['manual_citation_score'] == 3])),
            "fair": int(len(df[df['manual_citation_score'] == 2])),
            "poor": int(len(df[df['manual_citation_score'] == 1]))
        }
        citation_stats = {
            "average_citation_score": float(avg_citation) if not pd.isna(avg_citation) else 0.0,
            "citation_score_distribution": citation_dist
        }
    
    # Prepare results in same format as evaluation
    results = []
    for _, row in df.iterrows():
        result_dict = {
            'question': row.get('question', ''),
            'rag_answer': row.get('rag_answer', ''),
            'expected_answer': row.get('expected_answer', ''),
            'score': int(row['manual_accuracy_score']) if pd.notna(row.get('manual_accuracy_score')) else None,
            'citation_score': int(row['manual_citation_score']) if pd.notna(row.get('manual_citation_score')) else None
        }
        results.append(clean_nan_values(result_dict))
    
    result = {
        "timestamp": timestamp,
        "total_questions": len(df),
        "average_score": float(avg_accuracy) if not pd.isna(avg_accuracy) else 0.0,
        "score_distribution": accuracy_dist,
        "assessment_type": "manual",
        "results": results,
        **citation_stats  # Add citation stats if available
    }
    
    return clean_nan_values(result)
