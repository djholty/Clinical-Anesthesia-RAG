"""
View evaluation results in a nice formatted way
"""
import pandas as pd
import sys

def view_results(csv_path):
    """Display evaluation results in a readable format."""
    
    # Load results
    df = pd.read_csv(csv_path)
    
    # Calculate statistics
    total = len(df)
    avg_score = df['score'].mean()
    
    excellent = len(df[df['score'] >= 90])
    good = len(df[(df['score'] >= 70) & (df['score'] < 90)])
    fair = len(df[(df['score'] >= 50) & (df['score'] < 70)])
    poor = len(df[df['score'] < 50])
    
    # Print summary
    print("=" * 80)
    print("   EVALUATION RESULTS SUMMARY")
    print("=" * 80)
    print(f"\n📊 Overall Statistics:")
    print(f"   Total Questions: {total}")
    print(f"   Average Score: {avg_score:.2f}/100")
    print(f"   Accuracy: {avg_score:.1f}%")
    
    print(f"\n📈 Score Distribution:")
    print(f"   Excellent (90-100): {excellent:3d} ({excellent/total*100:5.1f}%)")
    print(f"   Good (70-89):       {good:3d} ({good/total*100:5.1f}%)")
    print(f"   Fair (50-69):       {fair:3d} ({fair/total*100:5.1f}%)")
    print(f"   Poor (0-49):        {poor:3d} ({poor/total*100:5.1f}%)")
    
    # Show detailed results
    print("\n" + "=" * 80)
    print("   DETAILED RESULTS")
    print("=" * 80)
    
    for idx, row in df.iterrows():
        score_emoji = "✅" if row['score'] >= 90 else "✓" if row['score'] >= 70 else "⚠️" if row['score'] >= 50 else "❌"
        
        print(f"\n{score_emoji} Question {idx + 1}/{total} - Score: {row['score']}/100")
        print("-" * 80)
        print(f"Q: {row['question']}")
        print(f"\nExpected: {row['expected_answer'][:200]}...")
        print(f"\nRAG Answer: {row['rag_answer'][:200]}...")
        print(f"\nEvaluation: {row['reasoning']}")
        
        if idx < total - 1:
            input("\nPress Enter for next question (or Ctrl+C to exit)...")
    
    print("\n" + "=" * 80)
    print("   END OF RESULTS")
    print("=" * 80)

if __name__ == "__main__":
    csv_file = "./david_work_files/evaluation_results.csv"
    
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    
    try:
        view_results(csv_file)
    except FileNotFoundError:
        print(f"❌ Error: Could not find {csv_file}")
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...")

