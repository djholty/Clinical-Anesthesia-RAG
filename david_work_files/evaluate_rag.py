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
import pandas as pd
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from tqdm import tqdm
import time

# Add parent directory to path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.rag_pipeline import query_rag

# Load environment variables
load_dotenv()

# Initialize evaluator LLM (using Groq)
evaluator_llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)

# Evaluation prompt template
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
{{"score": <0-100>, "reasoning": "<brief explanation>"}}

Where score is:
- 90-100: Fully correct and complete
- 70-89: Mostly correct with minor omissions
- 50-69: Partially correct but missing key information
- 30-49: Some correct elements but significant errors
- 0-29: Mostly or completely incorrect
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

def evaluate_answer(question, expected_answer, rag_answer):
    """Use LLM to evaluate the RAG answer against expected answer."""
    try:
        prompt_value = eval_prompt.format_messages(
            question=question,
            expected_answer=expected_answer,
            rag_answer=rag_answer
        )
        response = evaluator_llm.invoke(prompt_value)
        
        # Parse JSON response
        import json
        result = json.loads(response.content)
        return result['score'], result['reasoning']
    except Exception as e:
        print(f"  ⚠️  Evaluation error: {e}")
        return 0, f"Error: {str(e)}"

def process_single_question(idx, question, expected_answer, total):
    """Process a single question (for parallel execution)."""
    result = {
        'question': question,
        'expected_answer': expected_answer,
        'rag_answer': '',
        'score': 0,
        'reasoning': '',
        'index': idx
    }
    
    # Get RAG answer
    try:
        rag_answer = query_rag(question)
        result['rag_answer'] = rag_answer
    except Exception as e:
        result['rag_answer'] = f"Error: {str(e)}"
        result['reasoning'] = f"RAG Error: {str(e)}"
        return result
    
    # Evaluate answer
    try:
        score, reasoning = evaluate_answer(question, expected_answer, rag_answer)
        result['score'] = score
        result['reasoning'] = reasoning
    except Exception as e:
        result['score'] = 0
        result['reasoning'] = f"Eval Error: {str(e)}"
    
    return result

def run_evaluation(xlsx_path, output_csv=None):
    """Run full evaluation on all questions with progress bar."""
    print("=" * 70)
    print("   RAG MODEL EVALUATION")
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
    
    if question_col not in df.columns or answer_col not in df.columns:
        print(f"\n❌ Error: Could not find required columns.")
        print(f"   Looking for: '{question_col}' and '{answer_col}'")
        print(f"   Found: {list(df.columns)}")
        print("\n   Please update the column names in the script.")
        return
    
    print(f"\n🔄 Processing {len(df)} questions...\n")
    
    results = []
    start_time = time.time()
    
    # Process questions sequentially with progress bar
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Evaluating", unit="question"):
        question = row[question_col]
        expected_answer = row[answer_col]
        
        result = process_single_question(idx, question, expected_answer, len(df))
        results.append(result)
    
    # Calculate overall accuracy
    total_score = sum(r['score'] for r in results)
    avg_score = total_score / len(results) if len(results) > 0 else 0
    elapsed_time = time.time() - start_time
    
    print("\n" + "=" * 70)
    print(f"   EVALUATION COMPLETE")
    print("=" * 70)
    print(f"   Time taken: {elapsed_time/60:.1f} minutes")
    print(f"\n📊 Overall Results:")
    print(f"   Total Questions: {len(df)}")
    print(f"   Average Score: {avg_score:.2f}/100")
    print(f"   Accuracy: {avg_score:.1f}%")
    
    # Score distribution
    scores = [r['score'] for r in results]
    excellent = sum(1 for s in scores if s >= 90)
    good = sum(1 for s in scores if 70 <= s < 90)
    fair = sum(1 for s in scores if 50 <= s < 70)
    poor = sum(1 for s in scores if s < 50)
    
    print(f"\n   Score Distribution:")
    print(f"   Excellent (90-100): {excellent} ({excellent/len(df)*100:.1f}%)")
    print(f"   Good (70-89):       {good} ({good/len(df)*100:.1f}%)")
    print(f"   Fair (50-69):       {fair} ({fair/len(df)*100:.1f}%)")
    print(f"   Poor (0-49):        {poor} ({poor/len(df)*100:.1f}%)")
    
    # Save results to CSV
    if output_csv:
        results_df = pd.DataFrame(results)
        results_df.to_csv(output_csv, index=False)
        print(f"\n💾 Results saved to: {output_csv}")
    
    return results, avg_score

if __name__ == "__main__":
    from datetime import datetime
    
    # Path to your prompt set
    PROMPT_FILE = "./david_work_files/prompt_set.xlsx"
    
    # Create timestamped output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("./david_work_files/evaluations", exist_ok=True)
    OUTPUT_FILE = f"./david_work_files/evaluations/evaluation_{timestamp}.csv"
    
    # Also save as latest
    LATEST_FILE = "./david_work_files/evaluation_results.csv"
    
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
        shutil.copy(OUTPUT_FILE, LATEST_FILE)
        print(f"💾 Also saved as: {LATEST_FILE}")
        
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

