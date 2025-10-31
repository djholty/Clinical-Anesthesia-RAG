"""
RAG Model Evaluation Script

This script:
1. Reads questions and expected answers from prompt_set.xlsx
2. Runs each question through the RAG model
3. Uses an LLM to compare RAG answers with expected answers
4. Calculates accuracy scores
"""
import os
import sys
import json
import re
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from tqdm import tqdm

# Add parent directory to path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.rag_pipeline import query_rag
from monitoring.citation_metrics import compute_comprehensive_citation_metrics

# Load environment variables
load_dotenv()

# Configuration: Number of parallel workers for question processing
# Reduced to 3 to avoid Groq rate limits (6000 TPM limit)
MAX_WORKERS = 3  # Adjust based on API rate limits and system resources

# Initialize evaluator LLM (using Groq)
evaluator_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)

# Evaluation prompt template for correctness
eval_prompt = ChatPromptTemplate.from_template("""
You are an expert evaluator comparing two answers to a medical question.

Question: {question}

Expected Answer: {expected_answer}

RAG Model Answer: {rag_answer}

Compare these answers and determine if the RAG model's answer is correct, partially correct, or incorrect.
Consider:
- Medical accuracy
- Completeness of information
- Relevance to the question

Respond with ONLY a JSON object in this exact format:
{{"score": <1-4>, "reasoning": "<brief explanation>"}}

Where score is:
- 4 (excellent): Fully correct and complete
- 3 (good): Mostly correct with minor omissions
- 2 (fair): Partially correct but missing key information
- 1 (poor): Mostly or completely incorrect, or has significant errors
""")

# Citation evaluation prompt template (enhanced)
citation_eval_prompt = ChatPromptTemplate.from_template("""
You are an expert evaluator assessing whether the retrieved context documents are appropriate and relevant for answering a medical question.

Question: {question}

Retrieved Context Windows:
{contexts}

{ground_truth_section}

Evaluate the citation quality across these dimensions:
1. **Relevance**: Are the retrieved contexts relevant to the question?
2. **Completeness**: Do the contexts contain sufficient information to answer the question?
3. **Missing Contexts**: Are there important relevant contexts that appear to have been missed?
4. **Irrelevant Contexts**: Are there contexts included that are clearly irrelevant?
{precision_section}

Provide a structured evaluation with sub-scores for each dimension.

Respond with ONLY a JSON object in this exact format:
{{
    "relevance_score": <1-4>,
    "completeness_score": <1-4>,
    "precision_score": <1-4>,
    "overall_score": <1-4>,
    "reasoning": "<brief explanation covering all dimensions>",
    "missing_contexts": ["<description of missing context 1>", ...],
    "irrelevant_contexts": ["<description of irrelevant context 1>", ...]
}}

Where scores are (for each dimension):
- 4 (excellent): Fully meets the criterion
- 3 (good): Mostly meets with minor issues
- 2 (fair): Partially meets but with significant gaps
- 1 (poor): Fails to meet the criterion

Overall score combines all dimensions:
- 4 (excellent): All contexts highly relevant and appropriate, no important contexts missing
- 3 (good): Most contexts relevant with minor issues
- 2 (fair): Some contexts relevant but missing important ones or including irrelevant ones
- 1 (poor): Contexts mostly irrelevant or significantly missing relevant information
""")

def load_questions(xlsx_path):
    """Load questions and expected answers from Excel file."""
    try:
        # Read with engine='openpyxl' to handle formatting better
        df = pd.read_excel(xlsx_path, engine='openpyxl')
        print(f"✓ Loaded {len(df)} questions from {xlsx_path}")
        print(f"  Columns: {list(df.columns)}")
        
        # Check for truncation
        if 'answers' in df.columns:
            avg_length = df['answers'].str.len().mean()
            print(f"  Average answer length: {avg_length:.0f} characters")
            if avg_length < 50:
                print("  ⚠️  Warning: Answers seem very short. Check Excel file.")
        
        return df
    except Exception as e:
        print(f"❌ Error loading Excel file: {e}")
        return None

def is_rate_limit_error(exception):
    """Check if the exception is a rate limit or capacity error (retryable)."""
    error_str = str(exception)
    error_lower = error_str.lower()
    # Check for rate limit (429), over capacity (503), or capacity messages
    return (
        '429' in error_str or 
        '503' in error_str or
        'rate_limit' in error_lower or 
        'Rate limit' in error_str or
        'over capacity' in error_lower or
        'over_capacity' in error_lower or
        'capacity' in error_lower and ('exceeded' in error_lower or 'over' in error_lower)
    )

def invoke_llm_with_retry(llm, messages, max_retries=5):
    """Invoke LLM with retry logic for rate limit errors."""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return llm.invoke(messages)
        except Exception as e:
            last_exception = e
            if is_rate_limit_error(e):
                # Parse wait time from error message if available
                error_str = str(e)
                # Check if error message mentions exponential backoff
                if 'back off exponentially' in error_str.lower():
                    # Use exponential backoff as suggested
                    wait_time = min(2 ** attempt, 60)  # Cap at 60 seconds for capacity issues
                    print(f"  ⏳ API over capacity (attempt {attempt + 1}/{max_retries}). Backing off exponentially: waiting {wait_time:.1f}s...")
                else:
                    wait_time_match = re.search(r'Please try again in ([\d.]+)s', error_str, re.IGNORECASE)
                    if wait_time_match:
                        wait_time = float(wait_time_match.group(1)) + 1  # Add 1s buffer
                        print(f"  ⏳ Rate limit hit (attempt {attempt + 1}/{max_retries}). Waiting {wait_time:.1f}s before retry...")
                    else:
                        # Exponential backoff if no wait time specified
                        wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                        print(f"  ⏳ Rate limit/capacity issue (attempt {attempt + 1}/{max_retries}). Waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
                continue  # Retry
            else:
                # Not a rate limit error, re-raise immediately
                raise
    
    # If we've exhausted retries, raise the last exception with helpful message
    error_msg = str(last_exception)
    if 'over capacity' in error_msg.lower():
        raise Exception(
            f"API over capacity after {max_retries} attempts. "
            f"Please try again later. Original error: {error_msg}. "
            f"Check https://groqstatus.com for service status."
        )
    raise last_exception

def evaluate_answer(question, expected_answer, rag_answer):
    """Use LLM to evaluate the RAG answer against expected answer."""
    try:
        prompt_value = eval_prompt.format_messages(
            question=question,
            expected_answer=expected_answer,
            rag_answer=rag_answer
        )
        response = invoke_llm_with_retry(evaluator_llm, prompt_value)
        
        # Parse JSON response
        content = response.content
        
        # Look for JSON object in the response
        json_match = re.search(r'\{[^}]*"score"[^}]*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            return result['score'], result.get('reasoning', 'No reasoning provided')
        else:
            # If no JSON found, try parsing the whole content
            result = json.loads(content)
            return result['score'], result.get('reasoning', 'No reasoning provided')
            
    except json.JSONDecodeError as e:
        # If JSON parsing fails, assign a default score and use the raw response
        print(f"  ⚠️  JSON parsing error: {e}")
        return 2, f"Could not parse evaluation. Raw response: {response.content[:200] if 'response' in locals() else 'No response'}"
    except Exception as e:
        if is_rate_limit_error(e):
            print(f"  ⚠️  Rate limit error after retries: {e}")
            return 1, f"Rate limit error: Could not evaluate due to API rate limits"
        print(f"  ⚠️  Evaluation error: {e}")
        return 1, f"Error: {str(e)}"

def evaluate_citation_score(question, contexts, ground_truth_sources=None, answer=None):
    """
    Evaluate citation quality using hybrid approach: automated metrics + LLM evaluation.
    
    Args:
        question (str): The question being asked.
        contexts (List[dict]): List of context dictionaries with 'source', 'content', etc.
        ground_truth_sources (List[str], optional): Expected source documents from ground truth
        
    Returns:
        dict: Comprehensive citation evaluation with scores and metrics
    """
    # Step 1: Compute automated metrics
    # Use provided answer if available, otherwise empty string (faithfulness won't be computed)
    answer_text = answer if answer else ""
    auto_metrics = compute_comprehensive_citation_metrics(
        question=question,
        answer=answer_text,
        contexts=contexts,
        ground_truth_sources=ground_truth_sources
    )
    
    # Step 2: LLM-based qualitative evaluation
    llm_score = None
    llm_reasoning = ""
    
    try:
        # Format contexts for the prompt
        contexts_text = []
        for i, ctx in enumerate(contexts, 1):
            source = ctx.get('source', 'Unknown source')
            page = ctx.get('page', 'N/A')
            content = ctx.get('content', '')[:500]  # Limit content length to avoid token limits
            contexts_text.append(f"Context {i} [Source: {source}, Page: {page}]:\n{content}")
        
        contexts_formatted = "\n\n".join(contexts_text)
        
        # Build ground truth section if available
        ground_truth_section = ""
        precision_section = ""
        if ground_truth_sources:
            gt_text = "\n".join([f"- {src}" for src in ground_truth_sources if src])
            ground_truth_section = f"\nExpected Sources (Ground Truth):\n{gt_text}\n"
            precision_section = "\n5. **Precision**: How many of the retrieved contexts match the expected sources?"
        
        # Format prompt - handle empty ground_truth_section and precision_section
        if not ground_truth_section:
            ground_truth_section = ""
        if not precision_section:
            precision_section = ""
        
        # Format the prompt template
        prompt_value = citation_eval_prompt.format_messages(
            question=question,
            contexts=contexts_formatted,
            ground_truth_section=ground_truth_section,
            precision_section=precision_section
        )
        
        response = invoke_llm_with_retry(evaluator_llm, prompt_value)
        
        # Parse JSON response
        content = response.content
        
        # Look for JSON object in the response (multi-line)
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            llm_score = result.get('overall_score') or result.get('score')
            llm_reasoning = result.get('reasoning', 'No reasoning provided')
        else:
            # Fallback: try parsing whole content
            result = json.loads(content)
            llm_score = result.get('overall_score') or result.get('score', 2)
            llm_reasoning = result.get('reasoning', 'No reasoning provided')
            
    except json.JSONDecodeError as e:
        print(f"  ⚠️  Citation JSON parsing error: {e}")
        llm_score = 2
        llm_reasoning = f"Could not parse LLM evaluation. Raw: {response.content[:200] if 'response' in locals() else 'No response'}"
    except Exception as e:
        if is_rate_limit_error(e):
            print(f"  ⚠️  Rate limit error in citation evaluation: {e}")
            llm_score = 1
            llm_reasoning = "Rate limit error: Could not complete LLM evaluation"
        else:
            print(f"  ⚠️  Citation LLM evaluation error: {e}")
            llm_score = 1
            llm_reasoning = f"LLM Evaluation Error: {str(e)}"
    
    # Step 3: Combine automated metrics with LLM evaluation
    # Weight: 60% automated metrics, 40% LLM evaluation
    
    # Convert automated metrics to 1-4 scale
    auto_scores = []
    if auto_metrics.get('precision') is not None:
        precision = auto_metrics['precision']
        auto_scores.append(1 + (precision * 3))  # Scale 0-1 to 1-4
    
    if auto_metrics.get('recall') is not None:
        recall = auto_metrics['recall']
        auto_scores.append(1 + (recall * 3))  # Scale 0-1 to 1-4
    
    if auto_metrics.get('relevance') is not None:
        relevance = auto_metrics['relevance']
        auto_scores.append(1 + (relevance * 3))  # Scale 0-1 to 1-4
    
    # Calculate average automated score
    if auto_scores:
        avg_auto_score = sum(auto_scores) / len(auto_scores)
    else:
        avg_auto_score = 2.0  # Default neutral
    
    # Combine with LLM score
    if llm_score:
        final_score = (0.6 * avg_auto_score) + (0.4 * llm_score)
        final_score = max(1, min(4, round(final_score)))  # Clamp to 1-4 and round
    else:
        final_score = max(1, min(4, round(avg_auto_score)))
    
    # Return only citation_score and citation_reasoning
    return {
        'citation_score': int(final_score),
        'citation_reasoning': llm_reasoning
    }

def process_single_question(idx, question, expected_answer, ground_truth_sources, total):
    """
    Process a single question with parallelized evaluations.
    
    After RAG answer is generated, correctness and citation evaluations run in parallel.
    
    Args:
        idx: Question index
        question: The question text
        expected_answer: Expected answer text
        ground_truth_sources: List of expected source documents (can be None)
        total: Total number of questions
    """
    result = {
        'question': question,
        'expected_answer': expected_answer,
        'ground_truth_sources': ', '.join(ground_truth_sources) if ground_truth_sources else '',
        'rag_answer': '',
        'score': 1,
        'reasoning': '',
        'citation_score': 1,
        'citation_reasoning': '',
        'contexts': [],
        'index': idx
    }
    
    # Get RAG result (now returns dict with 'answer' and 'contexts')
    # Add small delay to avoid rate limits
    time.sleep(0.1)  # Small delay between RAG calls
    try:
        rag_result = query_rag(question)
        result['rag_answer'] = rag_result['answer']
        result['contexts'] = rag_result['contexts']
    except Exception as e:
        result['rag_answer'] = f"Error: {str(e)}"
        result['reasoning'] = f"RAG Error: {str(e)}"
        result['citation_reasoning'] = f"RAG Error: {str(e)}"
        return result
    
    # Run both evaluations in parallel for speedup
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both evaluation tasks
        correctness_future = executor.submit(
            evaluate_answer, question, expected_answer, result['rag_answer']
        )
        citation_future = executor.submit(
            evaluate_citation_score, question, result['contexts'], ground_truth_sources, result['rag_answer']
        )
        
        # Wait for correctness evaluation
        try:
            score, reasoning = correctness_future.result()
            result['score'] = score
            result['reasoning'] = reasoning
        except Exception as e:
            result['score'] = 1
            result['reasoning'] = f"Eval Error: {str(e)}"
        
        # Wait for citation evaluation (now returns dict)
        try:
            citation_result = citation_future.result()
            # Handle both old format (tuple) and new format (dict)
            if isinstance(citation_result, dict):
                result['citation_score'] = citation_result.get('citation_score', 1)
                result['citation_reasoning'] = citation_result.get('citation_reasoning', '')
            else:
                # Fallback for old format
                citation_score, citation_reasoning = citation_result
                result['citation_score'] = citation_score
                result['citation_reasoning'] = citation_reasoning
        except Exception as e:
            result['citation_score'] = 1
            result['citation_reasoning'] = f"Citation Eval Error: {str(e)}"
    
    return result

def run_evaluation(xlsx_path, output_csv=None, max_workers=None, progress_callback=None):
    """
    Run full evaluation on all questions with parallel processing.
    
    Args:
        xlsx_path (str): Path to Excel file with questions and answers.
        output_csv (str, optional): Path to output CSV file.
        max_workers (int, optional): Number of parallel workers. Defaults to MAX_WORKERS.
        progress_callback (callable, optional): Callback function(current, total) called on each question completion.
    
    Returns:
        tuple: (results list, average score)
    """
    if max_workers is None:
        max_workers = MAX_WORKERS
    
    print("=" * 70)
    print("   RAG MODEL EVALUATION")
    print("=" * 70)
    print(f"   Using {max_workers} parallel workers for question processing")
    print("=" * 70)
    
    # Load questions
    df = load_questions(xlsx_path)
    if df is None:
        return
    
    # Check for required columns
    print(f"\n📋 Available columns: {list(df.columns)}")
    
    # Column names from the Excel file
    question_col = 'questions'
    answer_col = 'answers'
    source_col = None  # Column 3 - ground truth sources
    table_col = None   # Column 4 - table numbers (optional)
    
    # Try to find source column (could be named differently)
    potential_source_cols = ['source', 'sources', 'ground_truth', 'ground_truth_sources', 'expected_sources']
    for col in df.columns:
        if col.lower() in potential_source_cols or 'source' in col.lower():
            source_col = col
            break
    
    # If not found, assume it's the 3rd column (index 2)
    if source_col is None and len(df.columns) >= 3:
        source_col = df.columns[2]  # Third column (0-indexed)
        print(f"   Using '{source_col}' as ground truth sources column")
    
    # Try to find table column (4th column)
    if len(df.columns) >= 4:
        table_col = df.columns[3]  # Fourth column (0-indexed)
        print(f"   Using '{table_col}' as table numbers column (if available)")
    
    if question_col not in df.columns or answer_col not in df.columns:
        print(f"\n❌ Error: Could not find required columns.")
        print(f"   Looking for: '{question_col}' and '{answer_col}'")
        print(f"   Found: {list(df.columns)}")
        print("\n   Please update the column names in the script.")
        return
    
    print(f"\n🔄 Processing {len(df)} questions in parallel...\n")
    if source_col:
        print(f"   Ground truth sources column: '{source_col}'")
    else:
        print(f"   ⚠️  Warning: No ground truth sources column found. Citation metrics will not use Precision/Recall.")
    
    # Prepare question list and lookup dictionary
    questions_list = []
    question_lookup = {}  # Map idx to (question, expected_answer, ground_truth_sources) for error handling
    
    for idx, row in df.iterrows():
        question = row[question_col]
        expected_answer = row[answer_col]
        
        # Extract ground truth sources
        ground_truth_sources = []
        if source_col and source_col in row:
            sources_str = str(row[source_col]) if pd.notna(row[source_col]) else ""
            if sources_str and sources_str.strip() and sources_str.lower() != 'nan':
                # Split by comma, semicolon, or newline
                sources = re.split(r'[,;\n]', sources_str)
                ground_truth_sources = [s.strip() for s in sources if s.strip()]
        
        questions_list.append((idx, question, expected_answer, ground_truth_sources))
        question_lookup[idx] = (question, expected_answer, ground_truth_sources)
    
    total_questions = len(questions_list)
    results = []
    start_time = time.time()
    completed_count = 0
    
    # Process questions in parallel with progress bar
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all questions
        future_to_question = {
            executor.submit(
                process_single_question, idx, question, expected_answer, ground_truth_sources, len(df)
            ): idx
            for idx, question, expected_answer, ground_truth_sources in questions_list
        }
        
        # Use tqdm to show progress as tasks complete
        with tqdm(total=total_questions, desc="Evaluating", unit="question") as pbar:
            # Dictionary to store results by index to maintain order
            results_dict = {}
            
            # Process completed tasks as they finish
            for future in as_completed(future_to_question):
                idx = future_to_question[future]
                try:
                    result = future.result()
                    results_dict[idx] = result
                except Exception as e:
                    # Handle errors gracefully
                    print(f"\n⚠️  Error processing question {idx}: {e}")
                    question, expected_answer, ground_truth_sources = question_lookup[idx]
                    results_dict[idx] = {
                        'question': question,
                        'expected_answer': expected_answer,
                        'ground_truth_sources': ', '.join(ground_truth_sources) if ground_truth_sources else '',
                        'rag_answer': f"Error: {str(e)}",
                        'score': 1,
                        'reasoning': f"Processing Error: {str(e)}",
                        'citation_score': 1, 
                        'citation_reasoning': f"Processing Error: {str(e)}",
                        'contexts': [],
                        'index': idx
                    }
                finally:
                    completed_count += 1
                    pbar.update(1)
                    # Call progress callback if provided
                    if progress_callback:
                        try:
                            progress_callback(completed_count, total_questions)
                            # Debug: print progress to console
                            print(f"Progress: {completed_count}/{total_questions} ({completed_count/total_questions*100:.1f}%)")
                        except Exception as e:
                            # Don't fail evaluation if callback errors
                            print(f"Progress callback error: {e}")
                            pass
        
        # Sort results by index to maintain original order
        results = [results_dict[idx] for idx in sorted(results_dict.keys())]
    
    # Calculate overall accuracy
    total_score = sum(r['score'] for r in results)
    avg_score = total_score / len(results) if len(results) > 0 else 0
    avg_citation_score = sum(r.get('citation_score', 1) for r in results) / len(results) if len(results) > 0 else 0
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 70)
    print(f"   EVALUATION COMPLETE")
    print("=" * 70)
    print(f"   Time taken: {elapsed_time/60:.1f} minutes")
    print(f"\n📊 Overall Results:")
    print(f"   Total Questions: {len(df)}")
    print(f"   Average Correctness Score: {avg_score:.2f}/4")
    print(f"   Average Citation Score: {avg_citation_score:.2f}/4")
    
    # Correctness score distribution
    scores = [r['score'] for r in results]
    excellent = sum(1 for s in scores if s == 4)
    good = sum(1 for s in scores if s == 3)
    fair = sum(1 for s in scores if s == 2)
    poor = sum(1 for s in scores if s == 1)
    
    print(f"\n   Correctness Score Distribution:")
    print(f"   Excellent (4): {excellent} ({excellent/len(df)*100:.1f}%)")
    print(f"   Good (3):      {good} ({good/len(df)*100:.1f}%)")
    print(f"   Fair (2):      {fair} ({fair/len(df)*100:.1f}%)")
    print(f"   Poor (1):      {poor} ({poor/len(df)*100:.1f}%)")
    
    # Citation score distribution
    citation_scores = [r.get('citation_score', 1) for r in results]
    cit_excellent = sum(1 for s in citation_scores if s == 4)
    cit_good = sum(1 for s in citation_scores if s == 3)
    cit_fair = sum(1 for s in citation_scores if s == 2)
    cit_poor = sum(1 for s in citation_scores if s == 1)
    
    print(f"\n   Citation Score Distribution:")
    print(f"   Excellent (4): {cit_excellent} ({cit_excellent/len(df)*100:.1f}%)")
    print(f"   Good (3):      {cit_good} ({cit_good/len(df)*100:.1f}%)")
    print(f"   Fair (2):      {cit_fair} ({cit_fair/len(df)*100:.1f}%)")
    print(f"   Poor (1):      {cit_poor} ({cit_poor/len(df)*100:.1f}%)")
    
    # Save results to CSV
    if output_csv:
        # Convert nested structures to strings for CSV compatibility
        results_for_csv = []
        for r in results:
            r_copy = r.copy()
            
            # Convert contexts list to JSON string for CSV storage
            if 'contexts' in r_copy:
                r_copy['contexts'] = json.dumps(r_copy['contexts'])
            
            # Remove citation_metrics and citation_details if they exist (for backward compatibility)
            r_copy.pop('citation_metrics', None)
            r_copy.pop('citation_details', None)
            
            results_for_csv.append(r_copy)
        
        results_df = pd.DataFrame(results_for_csv)
        results_df.to_csv(output_csv, index=False)
        print(f"\n💾 Results saved to: {output_csv}")
    
    return results, avg_score

if __name__ == "__main__":
    from datetime import datetime
    
    # Path to your prompt set (relative to monitoring/ directory)
    PROMPT_FILE = "./prompt_set.xlsx"
    
    # Create timestamped output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("./evaluations", exist_ok=True)
    OUTPUT_FILE = f"./evaluations/evaluation_{timestamp}.csv"
    
    # Also save as latest (in monitoring directory)
    LATEST_FILE = "./evaluation_results.csv"
    
    # Check if file exists
    if not os.path.exists(PROMPT_FILE):
        print(f"❌ Error: Could not find {PROMPT_FILE}")
        print("   Please make sure the file exists.")
        exit(1)
    
    # Run evaluation
    try:
        results, avg_score = run_evaluation(PROMPT_FILE, OUTPUT_FILE)
        
        # Also save as latest for easy access
        import shutil
        os.makedirs(os.path.dirname(LATEST_FILE), exist_ok=True)
        shutil.copy(OUTPUT_FILE, LATEST_FILE)
        print(f"💾 Also saved as: {LATEST_FILE}")
        
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

