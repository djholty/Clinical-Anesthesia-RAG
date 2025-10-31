"""
Automated Citation Scoring Metrics for RAG Systems

This module provides automated metrics for evaluating citation quality in RAG systems:
- Faithfulness: Verifies if answer claims are supported by contexts
- Answer Grounding: Checks if citations match retrieved sources
- Citation Consistency: Validates citation-source alignment
- Precision@k and Recall@k: Measures retrieval quality against ground truth
"""

import re
from typing import List, Dict, Tuple, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize embedding model for semantic similarity (using same as RAG pipeline)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
try:
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
except Exception as e:
    print(f"Warning: Could not load embedding model: {e}")
    embedding_model = None


def extract_citations_from_answer(answer: str) -> List[str]:
    """
    Extract all source citations from answer text.
    
    Args:
        answer: The RAG-generated answer text
        
    Returns:
        List of extracted source filenames (e.g., ['2025_CAS_Revised_Guidelines.md'])
    """
    citations = []
    # Match pattern: [Source: filename]
    citation_pattern = r'\[Source:\s*([^\]]+)\]'
    matches = re.findall(citation_pattern, answer, re.IGNORECASE)
    
    for match in matches:
        # Clean up the citation (remove .md extension if present, normalize)
        source = match.strip()
        if source:
            citations.append(source)
    
    return citations


def calculate_answer_grounding(answer: str, contexts: List[Dict]) -> Tuple[float, List[str], List[str]]:
    """
    Calculate answer grounding score - verifies citations match retrieved sources.
    
    Args:
        answer: The RAG-generated answer
        contexts: List of context dictionaries with 'source' key
        
    Returns:
        Tuple of (grounding_score, valid_citations, invalid_citations)
        - grounding_score: 0-1, proportion of citations that match retrieved sources
        - valid_citations: List of citations that match retrieved sources
        - invalid_citations: List of citations not found in retrieved sources
    """
    if not answer or not contexts:
        return 0.0, [], []
    
    # Extract citations from answer
    answer_citations = extract_citations_from_answer(answer)
    
    if not answer_citations:
        # No citations found - if answer exists, it's not grounded
        return 0.0, [], []
    
    # Get retrieved source filenames
    retrieved_sources = []
    for ctx in contexts:
        source = ctx.get('source', '').strip()
        if source:
            retrieved_sources.append(source)
    
    # Normalize sources for comparison (remove extensions, lowercase)
    def normalize_source(source: str) -> str:
        source = source.strip().lower()
        # Remove common extensions
        for ext in ['.md', '.pdf', '.txt']:
            if source.endswith(ext):
                source = source[:-len(ext)]
        return source
    
    normalized_retrieved = {normalize_source(s): s for s in retrieved_sources}
    
    # Check each citation
    valid_citations = []
    invalid_citations = []
    
    for citation in answer_citations:
        normalized_citation = normalize_source(citation)
        # Check if citation matches any retrieved source
        if normalized_citation in normalized_retrieved:
            valid_citations.append(citation)
        else:
            # Try fuzzy matching (check if citation is substring or vice versa)
            matched = False
            for ret_source in normalized_retrieved.keys():
                if normalized_citation in ret_source or ret_source in normalized_citation:
                    valid_citations.append(citation)
                    matched = True
                    break
            if not matched:
                invalid_citations.append(citation)
    
    # Calculate grounding score
    if not answer_citations:
        grounding_score = 0.0
    else:
        grounding_score = len(valid_citations) / len(answer_citations)
    
    return grounding_score, valid_citations, invalid_citations


def check_citation_consistency(answer: str, contexts: List[Dict]) -> Tuple[float, Dict]:
    """
    Check citation consistency - verify all cited sources appear in retrieved contexts.
    
    Args:
        answer: The RAG-generated answer
        contexts: List of context dictionaries with 'source' key
        
    Returns:
        Tuple of (consistency_score, details_dict)
        - consistency_score: 0-1, proportion of consistent citations
        - details_dict: Contains lists of consistent/inconsistent citations
    """
    grounding_score, valid_citations, invalid_citations = calculate_answer_grounding(answer, contexts)
    
    # Get all citations
    all_citations = extract_citations_from_answer(answer)
    
    details = {
        'total_citations': len(all_citations),
        'consistent_citations': valid_citations,
        'inconsistent_citations': invalid_citations
    }
    
    return grounding_score, details


def calculate_faithfulness_simple(answer: str, contexts: List[Dict]) -> Tuple[float, List[str]]:
    """
    Calculate simple faithfulness score using text matching.
    
    Note: This is a basic implementation. For more sophisticated checking,
    semantic similarity can be used.
    
    Args:
        answer: The RAG-generated answer
        contexts: List of context dictionaries with 'content' key
        
    Returns:
        Tuple of (faithfulness_score, unsupported_claims)
        - faithfulness_score: 0-1, estimated proportion of claims supported
        - unsupported_claims: List of claim strings that couldn't be matched
    """
    if not answer or not contexts:
        return 0.0, []
    
    # Combine all context content
    context_text = " ".join([ctx.get('content', '') for ctx in contexts]).lower()
    
    # Simple approach: Split answer into sentences and check if key phrases exist
    # Remove citations from answer for checking
    answer_clean = re.sub(r'\[Source:[^\]]+\]', '', answer)
    sentences = re.split(r'[.!?]\s+', answer_clean)
    
    supported_count = 0
    unsupported_claims = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:  # Skip very short sentences
            continue
        
        # Extract key terms (simple approach: words longer than 4 chars)
        key_terms = [word.lower() for word in sentence.split() if len(word) > 4]
        
        if not key_terms:
            continue
        
        # Check if at least some key terms appear in contexts
        matching_terms = sum(1 for term in key_terms if term in context_text)
        match_ratio = matching_terms / len(key_terms) if key_terms else 0
        
        if match_ratio >= 0.5:  # At least 50% of key terms match
            supported_count += 1
        else:
            unsupported_claims.append(sentence[:100])  # First 100 chars
    
    total_claims = len(sentences)
    if total_claims == 0:
        faithfulness_score = 0.0
    else:
        faithfulness_score = supported_count / total_claims
    
    return faithfulness_score, unsupported_claims


def calculate_faithfulness_semantic(answer: str, contexts: List[Dict], threshold: float = 0.7) -> Tuple[float, List[str]]:
    """
    Calculate faithfulness score using semantic similarity.
    
    Args:
        answer: The RAG-generated answer
        contexts: List of context dictionaries with 'content' key
        threshold: Similarity threshold for considering a claim supported (default: 0.7)
        
    Returns:
        Tuple of (faithfulness_score, unsupported_claims)
    """
    if not embedding_model:
        # Fallback to simple method
        return calculate_faithfulness_simple(answer, contexts)
    
    if not answer or not contexts:
        return 0.0, []
    
    # Remove citations from answer
    answer_clean = re.sub(r'\[Source:[^\]]+\]', '', answer)
    sentences = re.split(r'[.!?]\s+', answer_clean)
    
    # Combine all context content
    context_contents = [ctx.get('content', '') for ctx in contexts]
    
    supported_count = 0
    unsupported_claims = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue
        
        # Calculate similarity with all contexts
        try:
            sentence_embedding = embedding_model.encode(sentence)
            max_similarity = 0.0
            
            for context_content in context_contents:
                if not context_content:
                    continue
                # Take first 500 chars of context to avoid token limits
                context_snippet = context_content[:500]
                context_embedding = embedding_model.encode(context_snippet)
                
                # Cosine similarity
                similarity = np.dot(sentence_embedding, context_embedding) / (
                    np.linalg.norm(sentence_embedding) * np.linalg.norm(context_embedding)
                )
                max_similarity = max(max_similarity, similarity)
            
            if max_similarity >= threshold:
                supported_count += 1
            else:
                unsupported_claims.append(sentence[:100])
        except Exception as e:
            # If embedding fails, consider unsupported
            unsupported_claims.append(sentence[:100])
    
    total_claims = len([s for s in sentences if len(s.strip()) >= 10])
    if total_claims == 0:
        faithfulness_score = 0.0
    else:
        faithfulness_score = supported_count / total_claims
    
    return faithfulness_score, unsupported_claims


def calculate_precision_recall(retrieved_sources: List[str], ground_truth_sources: List[str]) -> Tuple[float, float]:
    """
    Calculate Precision@k and Recall@k for retrieved sources.
    
    Args:
        retrieved_sources: List of source filenames from retrieval
        ground_truth_sources: List of expected source filenames (ground truth)
        
    Returns:
        Tuple of (precision, recall)
    """
    if not ground_truth_sources:
        return 0.0, 0.0
    
    if not retrieved_sources:
        return 0.0, 0.0
    
    # Normalize sources for comparison
    def normalize_source(source: str) -> str:
        source = str(source).strip().lower()
        for ext in ['.md', '.pdf', '.txt']:
            if source.endswith(ext):
                source = source[:-len(ext)]
        return source
    
    normalized_retrieved = set(normalize_source(s) for s in retrieved_sources)
    normalized_ground_truth = set(normalize_source(s) for s in ground_truth_sources if s)
    
    # Calculate intersection
    relevant_retrieved = normalized_retrieved.intersection(normalized_ground_truth)
    
    # Precision@k: relevant retrieved / total retrieved
    precision = len(relevant_retrieved) / len(normalized_retrieved) if normalized_retrieved else 0.0
    
    # Recall@k: relevant retrieved / total ground truth
    recall = len(relevant_retrieved) / len(normalized_ground_truth) if normalized_ground_truth else 0.0
    
    return precision, recall


def calculate_context_relevance_semantic(question: str, contexts: List[Dict]) -> Tuple[float, List[float]]:
    """
    Calculate semantic relevance of contexts to question.
    
    Args:
        question: The user question
        contexts: List of context dictionaries with 'content' key
        
    Returns:
        Tuple of (average_relevance, per_context_relevance_scores)
    """
    if not embedding_model:
        # Fallback: return neutral scores
        return 0.5, [0.5] * len(contexts)
    
    if not question or not contexts:
        return 0.0, []
    
    try:
        question_embedding = embedding_model.encode(question)
        relevance_scores = []
        
        for ctx in contexts:
            content = ctx.get('content', '')
            if not content:
                relevance_scores.append(0.0)
                continue
            
            # Use first 500 chars to avoid token limits
            content_snippet = content[:500]
            content_embedding = embedding_model.encode(content_snippet)
            
            # Cosine similarity
            similarity = np.dot(question_embedding, content_embedding) / (
                np.linalg.norm(question_embedding) * np.linalg.norm(content_embedding)
            )
            relevance_scores.append(float(similarity))
        
        avg_relevance = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0
        
        return avg_relevance, relevance_scores
    except Exception as e:
        # Fallback: return neutral scores
        return 0.5, [0.5] * len(contexts)


def compute_comprehensive_citation_metrics(
    question: str,
    answer: str,
    contexts: List[Dict],
    ground_truth_sources: Optional[List[str]] = None
) -> Dict:
    """
    Compute all citation metrics comprehensively.
    
    Args:
        question: The user question
        answer: The RAG-generated answer
        contexts: List of context dictionaries
        ground_truth_sources: Optional list of expected source filenames
        
    Returns:
        Dictionary with all citation metrics
    """
    metrics = {}
    
    # 1. Answer Grounding
    grounding_score, valid_citations, invalid_citations = calculate_answer_grounding(answer, contexts)
    metrics['grounding'] = grounding_score
    metrics['grounding_details'] = {
        'valid_citations': valid_citations,
        'invalid_citations': invalid_citations
    }
    
    # 2. Citation Consistency
    consistency_score, consistency_details = check_citation_consistency(answer, contexts)
    metrics['consistency'] = consistency_score
    
    # 3. Faithfulness (use semantic if available, else simple)
    if embedding_model:
        faithfulness_score, unsupported_claims = calculate_faithfulness_semantic(answer, contexts)
    else:
        faithfulness_score, unsupported_claims = calculate_faithfulness_simple(answer, contexts)
    metrics['faithfulness'] = faithfulness_score
    metrics['unsupported_claims'] = unsupported_claims
    
    # 4. Precision and Recall (if ground truth available)
    if ground_truth_sources:
        retrieved_sources = [ctx.get('source', '') for ctx in contexts if ctx.get('source')]
        precision, recall = calculate_precision_recall(retrieved_sources, ground_truth_sources)
        metrics['precision'] = precision
        metrics['recall'] = recall
        metrics['precision_recall_details'] = {
            'retrieved_sources': retrieved_sources,
            'ground_truth_sources': ground_truth_sources,
            'matched_sources': list(set(retrieved_sources) & set(ground_truth_sources)) if ground_truth_sources else []
        }
    else:
        metrics['precision'] = None
        metrics['recall'] = None
    
    # 5. Context Relevance
    avg_relevance, per_context_relevance = calculate_context_relevance_semantic(question, contexts)
    metrics['relevance'] = avg_relevance
    metrics['per_context_relevance'] = per_context_relevance
    
    # Identify irrelevant contexts (relevance < 0.5)
    irrelevant_contexts = []
    for i, (ctx, rel_score) in enumerate(zip(contexts, per_context_relevance)):
        if rel_score < 0.5:
            irrelevant_contexts.append({
                'index': i,
                'source': ctx.get('source', 'Unknown'),
                'relevance_score': rel_score
            })
    metrics['irrelevant_contexts'] = irrelevant_contexts
    
    return metrics

