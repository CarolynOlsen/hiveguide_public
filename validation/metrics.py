import json
import logging
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from scipy import stats
from tqdm import tqdm

from validation.services.db import SessionLocal
from validation.services.models import DocumentChunk
from validation.services.config import OPENROUTER_API_KEY

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"

# Suppress verbose logging from HTTP clients and RAGAS telemetry
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("requests.packages.urllib3").setLevel(logging.WARNING)
# Suppress RAGAS telemetry/analytics debug logs
logging.getLogger("ragas").setLevel(logging.WARNING)

# Import PDF_SOURCES mapping to match filenames to document titles
try:
    from validation.prepare_sources import PDF_SOURCES
except ImportError:
    PDF_SOURCES = {}


def _safe_import_sklearn():
    try:
        from sklearn.metrics import (
            classification_report,
            confusion_matrix,
            roc_auc_score,
        )

        return classification_report, confusion_matrix, roc_auc_score
    except Exception as e:
        logging.warning(f"Failed to import sklearn: {e}")
        return None, None, None


def compute_intent_metrics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute intent classification metrics.
    Expected fields per result:
    - ground_truth_intent_mapped (or ground_truth_intent as fallback)
    - predicted_intent
    - class_probabilities (optional dict with 3 classes)
    """
    classification_report, confusion_matrix, roc_auc_score = _safe_import_sklearn()
    if not classification_report:
        return {"classification_report": {}, "roc_auc": None}

    # Extract ground truth and predictions
    y_true = []
    y_pred = []
    y_proba = []  # For ROC-AUC

    for result in results:
        # Get ground truth (prefer mapped version)
        gt = result.get("ground_truth_intent_mapped") or result.get("ground_truth_intent")
        if not gt:
            continue

        # Get prediction
        pred = result.get("predicted_intent")
        if not pred:
            continue

        y_true.append(gt)
        y_pred.append(pred)

        # Get probabilities for ROC-AUC
        proba = result.get("class_probabilities")
        if proba and isinstance(proba, dict):
            # Order: personal_only, documents_only, both_combined
            y_proba.append([
                proba.get("personal_only", 0.0),
                proba.get("documents_only", 0.0),
                proba.get("both_combined", 0.0),
            ])
        else:
            y_proba.append(None)

    if not y_true:
        return {"classification_report": {}, "roc_auc": None}

    # Compute classification report
    labels = ["personal_only", "documents_only", "both_combined"]
    report = classification_report(
        y_true, y_pred, labels=labels, output_dict=True, zero_division=0
    )

    # Compute ROC-AUC (multi-class, one-vs-rest)
    roc_auc = {}
    if y_proba and all(p is not None for p in y_proba):
        try:
            # Convert labels to indices
            label_to_idx = {label: i for i, label in enumerate(labels)}
            y_true_indices = [label_to_idx[label] for label in y_true]

            # Compute ROC-AUC for each class (one-vs-rest)
            for i, label in enumerate(labels):
                try:
                    y_true_binary = [1 if idx == i else 0 for idx in y_true_indices]
                    y_proba_class = [p[i] for p in y_proba]
                    auc = roc_auc_score(y_true_binary, y_proba_class)
                    roc_auc[label] = float(auc)
                except Exception as e:
                    logging.warning(f"Failed to compute ROC-AUC for {label}: {e}")
                    roc_auc[label] = None
        except Exception as e:
            logging.warning(f"Failed to compute ROC-AUC: {e}")
            roc_auc = None
    else:
        roc_auc = None

    return {
        "classification_report": report,
        "roc_auc": roc_auc,
    }


def _map_ground_truth_chunk_to_id(gt_chunk: str) -> Optional[int]:
    """
    Map a ground truth chunk string to a DocumentChunk ID.
    
    Ground truth chunks can be in various formats:
    - "ENTO-333.pdf#chunk_0" -> lookup by document_title="ENTO-333.pdf" and chunk_position=0
    - "chunk_123" -> try as chunk_id=123 (legacy format)
    - "123" -> try as chunk_id=123
    - Full chunk text -> try to find matching chunk ID
    """
    if not gt_chunk:
        return None
    
    # Handle format like "ENTO-333.pdf#chunk_0" - this means document filename and chunk_position
    if "#chunk_" in gt_chunk:
        try:
            # Split into document and chunk_position
            parts = gt_chunk.split("#chunk_")
            if len(parts) == 2:
                document_filename = parts[0]  # e.g., "ENTO-333.pdf"
                chunk_position_str = parts[1]  # e.g., "0"
                chunk_position = int(chunk_position_str)
                
                # Look up chunk by source_url (contains filename) and chunk_position
                # The source_url contains the ENTO-XXX.pdf pattern
                db = SessionLocal()
                try:
                    # First try matching by source_url containing the filename
                    chunk = db.query(DocumentChunk).filter(
                        DocumentChunk.source_url.like(f'%{document_filename}%'),
                        DocumentChunk.chunk_position == chunk_position
                    ).first()
                    if chunk:
                        return chunk.id
                    
                    # Fallback: try matching by document_title (in case filename matches title)
                    chunk = db.query(DocumentChunk).filter(
                        DocumentChunk.document_title == document_filename,
                        DocumentChunk.chunk_position == chunk_position
                    ).first()
                    if chunk:
                        return chunk.id
                finally:
                    db.close()
        except (ValueError, IndexError) as e:
            logging.debug(f"Failed to parse ground truth chunk format '{gt_chunk}': {e}")
    
    # Try direct ID extraction (legacy formats)
    if gt_chunk.startswith("chunk_"):
        try:
            return int(gt_chunk.replace("chunk_", ""))
        except ValueError:
            pass
    
    # Try parsing as integer (legacy format - direct chunk_id)
    try:
        return int(gt_chunk)
    except ValueError:
        pass
    
    # Try to find by chunk text (expensive, but sometimes necessary)
    try:
        db = SessionLocal()
        try:
            chunk = db.query(DocumentChunk).filter(
                DocumentChunk.chunk_text == gt_chunk
            ).first()
            if chunk:
                return chunk.id
        finally:
            db.close()
    except Exception as e:
        logging.warning(f"Failed to lookup chunk by text: {e}")
    
    return None


def compute_retrieval_hit_rate_at_k(
    results: List[Dict[str, Any]], k_values: List[int] = [3, 5, 10]
) -> Dict[str, float]:
    """
    Compute retrieval hit rate at k (recall@k).
    
    For each query:
    - Ground truth chunks: from ground_truth_chunks field
    - Retrieved chunks: from sources field (chunk IDs)
    
    Hit rate@k = (number of queries where at least one ground truth chunk is in top k) / (total queries)
    """
    hit_rates = {}
    
    for k in k_values:
        hits = 0
        total = 0
        
        for result in results:
            gt_chunks = result.get("ground_truth_chunks", [])
            if not gt_chunks:
                continue  # Skip queries without ground truth
            
            sources = result.get("sources", [])
            if not sources:
                total += 1
                continue  # No retrieval, can't be a hit
            
            # Get top k chunk IDs
            top_k_chunk_ids = []
            for source in sources[:k]:
                chunk_id = source.get("chunk_id")
                if chunk_id:
                    top_k_chunk_ids.append(chunk_id)
            
            # Map ground truth chunks to IDs
            gt_chunk_ids = set()
            for gt_chunk in gt_chunks:
                chunk_id = _map_ground_truth_chunk_to_id(gt_chunk)
                if chunk_id:
                    gt_chunk_ids.add(chunk_id)
            
            # Check if any ground truth chunk is in top k
            if gt_chunk_ids and any(gt_id in top_k_chunk_ids for gt_id in gt_chunk_ids):
                hits += 1
            
            total += 1
        
        hit_rate = hits / total if total > 0 else 0.0
        hit_rates[f"retrieval_hit_rate@{k}"] = hit_rate
    
    return hit_rates


def compute_recall_at_k(
    results: List[Dict[str, Any]], k_values: List[int] = [3, 5, 10]
) -> Dict[str, float]:
    """
    Compute recall@k for retrieval.
    
    Recall@k = (number of relevant items retrieved in top k) / (total number of relevant items)
    
    Averaged across all queries.
    """
    recalls = {}
    
    for k in k_values:
        total_recall = 0.0
        total_queries = 0
        
        for result in results:
            gt_chunks = result.get("ground_truth_chunks", [])
            if not gt_chunks:
                continue  # Skip queries without ground truth
            
            sources = result.get("sources", [])
            if not sources:
                total_queries += 1
                continue  # No retrieval, recall is 0
            
            # Get top k chunk IDs
            top_k_chunk_ids = []
            for source in sources[:k]:
                chunk_id = source.get("chunk_id")
                if chunk_id:
                    top_k_chunk_ids.append(chunk_id)
            
            # Map ground truth chunks to IDs
            gt_chunk_ids = set()
            for gt_chunk in gt_chunks:
                chunk_id = _map_ground_truth_chunk_to_id(gt_chunk)
                if chunk_id:
                    gt_chunk_ids.add(chunk_id)
            
            if not gt_chunk_ids:
                continue
            
            # Compute recall for this query
            relevant_retrieved = sum(1 for gt_id in gt_chunk_ids if gt_id in top_k_chunk_ids)
            recall = relevant_retrieved / len(gt_chunk_ids) if gt_chunk_ids else 0.0
            total_recall += recall
            total_queries += 1
        
        avg_recall = total_recall / total_queries if total_queries > 0 else 0.0
        recalls[f"recall@{k}"] = avg_recall
    
    return recalls


def compute_latency_metrics(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute latency statistics (p50, p90, p95, p99, mean) in milliseconds."""
    latencies = [r.get("latency_ms") for r in results if r.get("latency_ms") is not None]
    
    if not latencies:
        return {}
    
    latencies.sort()
    n = len(latencies)
    
    def percentile(p: float) -> float:
        idx = int(p * n)
        if idx >= n:
            idx = n - 1
        return latencies[idx]
    
    return {
        "p50_ms": percentile(0.50),
        "p90_ms": percentile(0.90),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "mean_ms": sum(latencies) / n,
        "min_ms": min(latencies),
        "max_ms": max(latencies),
    }


# Global token tracker for RAGAS evaluation
_ragas_token_usage = {"input": 0, "output": 0}

def _get_ragas_llm():
    """Get RAGAS LLM instance (Nvidia metrics)."""
    global _ragas_token_usage
    try:
        from ragas.llms import LangchainLLMWrapper
        from langchain_openai import ChatOpenAI
        from langchain_core.callbacks import BaseCallbackHandler
        
        # Create token callback for RAGAS
        class RAGASTokenCallback(BaseCallbackHandler):
            def on_llm_end(self, response, **kwargs):
                """Capture token usage from RAGAS LLM calls."""
                token_usage = {}
                
                # Try usage_metadata first
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    usage = response.usage_metadata
                    if hasattr(usage, 'input_tokens') or hasattr(usage, 'prompt_tokens'):
                        token_usage = {
                            'prompt_tokens': getattr(usage, 'input_tokens', 0) or getattr(usage, 'prompt_tokens', 0),
                            'completion_tokens': getattr(usage, 'output_tokens', 0) or getattr(usage, 'completion_tokens', 0),
                        }
                
                # Try response_metadata
                if not token_usage and hasattr(response, 'response_metadata') and response.response_metadata:
                    usage = response.response_metadata.get('usage', {})
                    if usage and isinstance(usage, dict):
                        token_usage = {
                            'prompt_tokens': usage.get('prompt_tokens', usage.get('input_tokens', 0)),
                            'completion_tokens': usage.get('completion_tokens', usage.get('output_tokens', 0)),
                        }
                    if not token_usage:
                        token_usage = response.response_metadata.get('token_usage', {})
                
                # Try llm_output
                if not token_usage and hasattr(response, 'llm_output') and response.llm_output:
                    if isinstance(response.llm_output, dict):
                        token_usage = response.llm_output.get('token_usage', {})
                
                if token_usage:
                    _ragas_token_usage["input"] += token_usage.get('prompt_tokens', 0) or token_usage.get('input_tokens', 0)
                    _ragas_token_usage["output"] += token_usage.get('completion_tokens', 0) or token_usage.get('output_tokens', 0)
        
        ragas_callback = RAGASTokenCallback()
        
        # Use OpenRouter for RAGAS evaluation
        llm = ChatOpenAI(
            model="anthropic/claude-haiku-4.5",
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
            callbacks=[ragas_callback],
        )
        return LangchainLLMWrapper(llm)
    except Exception as e:
        logging.warning(f"Failed to create RAGAS LLM: {e}")
        return None

def get_ragas_token_usage():
    """Get accumulated RAGAS token usage and reset."""
    global _ragas_token_usage
    usage = _ragas_token_usage.copy()
    _ragas_token_usage = {"input": 0, "output": 0}  # Reset for next run
    return usage


def add_ragas_scores_to_results(
    results: List[Dict[str, Any]], sample_size: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Add RAGAS scores to each result in-place.
    Uses RAGAS metrics: context_relevance and response_groundedness.
    
    Note: This function modifies results in-place and returns the same list.
    Only evaluates results that don't already have RAGAS scores.
    """
    from ragas import evaluate
    from ragas.metrics import ContextRelevance, ResponseGroundedness
    from datasets import Dataset
    
    llm = _get_ragas_llm()
    if not llm:
        logging.error("Failed to create RAGAS LLM, skipping RAGAS evaluation")
        return results
    
    # Note: This function should only be called on newly generated results
    # Old results should not be passed here since they have stale responses
    
    # Sample if requested
    if sample_size and sample_size < len(results):
        import random
        results_to_evaluate = random.sample(results, sample_size)
        indices_to_update = {i: results.index(r) for i, r in enumerate(results_to_evaluate)}
    else:
        results_to_evaluate = results
        indices_to_update = {i: i for i in range(len(results))}
    
    # Show progress message (RAGAS will show its own progress bar for metric evaluations)
    tqdm.write(f"Evaluating RAGAS metrics for {len(results_to_evaluate)} results (2 metrics × {len(results_to_evaluate)} results = {2 * len(results_to_evaluate)} evaluations)...")
    
    # Prepare dataset for RAGAS
    # Separate document contexts from user data contexts
    questions = []
    answers = []
    doc_contexts_list = []  # Document chunks only (for Context Relevance)
    all_contexts_list = []  # All contexts including user data (for Response Groundedness)
    
    for result in results_to_evaluate:
        question = result.get("question", "")
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        ground_truth_intent = result.get("ground_truth_intent_mapped") or result.get("ground_truth_intent")
        
        # Extract document contexts only (exclude user data)
        # Document sources don't have source_type="user_data", so we filter by absence of that
        doc_contexts = [
            s.get("chunk_text", "") 
            for s in sources 
            if s.get("chunk_text") and s.get("source_type") != "user_data"
        ]
        
        # Extract all contexts (documents + user data) for groundedness
        all_contexts = [s.get("chunk_text", "") for s in sources if s.get("chunk_text")]
        
        # Add user data context if available (from separate user_data field)
        user_data = result.get("user_data")
        if user_data:
            # Format user data as context
            user_data_text = ""
            if isinstance(user_data, dict):
                # Format SQL results or other user data
                user_data_text = str(user_data)
            elif isinstance(user_data, str):
                user_data_text = user_data
            if user_data_text:
                all_contexts.append(user_data_text)
        
        questions.append(question)
        answers.append(answer)
        doc_contexts_list.append(doc_contexts)
        all_contexts_list.append(all_contexts)
    
    if not questions:
        return results
    
    # Evaluate Context Relevance (documents only) and Response Groundedness (all contexts) separately
    # We need to handle personal_only questions specially - they have no document contexts
    try:
        # First, identify which results have document contexts (for Context Relevance)
        results_with_docs = []
        doc_questions = []
        doc_contexts_for_eval = []
        doc_indices = []  # Map back to original indices
        
        for idx, (result, doc_contexts) in enumerate(zip(results_to_evaluate, doc_contexts_list)):
            if doc_contexts:  # Only evaluate if there are document contexts
                results_with_docs.append(result)
                doc_questions.append(questions[idx])
                doc_contexts_for_eval.append(doc_contexts)
                doc_indices.append(idx)
        
        # Evaluate Context Relevance (only for results with document contexts)
        context_relevance_scores = {}
        if doc_questions:
            doc_dataset = Dataset.from_dict({
                "question": doc_questions,
                "contexts": doc_contexts_for_eval,
            })
            
            doc_eval_result = evaluate(
                dataset=doc_dataset,
                metrics=[ContextRelevance()],
                llm=llm,
                show_progress=False,
            )
            
            # Extract Context Relevance scores
            doc_scores_df = doc_eval_result.to_pandas()
            for eval_idx, original_idx in enumerate(doc_indices):
                row = doc_scores_df.iloc[eval_idx]
                # Try to extract context relevance score
                for col_name in ["nv_context_relevance", "context_relevance", "context_relevance_score"]:
                    if col_name in doc_scores_df.columns:
                        val = row[col_name]
                        if pd.notna(val):
                            try:
                                context_relevance_scores[original_idx] = float(val)
                                break
                            except (ValueError, TypeError):
                                continue
        
        # Evaluate Response Groundedness (for all results, using all contexts)
        groundedness_dataset = Dataset.from_dict({
            "answer": answers,
            "contexts": all_contexts_list,
        })
        
        groundedness_eval_result = evaluate(
            dataset=groundedness_dataset,
            metrics=[ResponseGroundedness()],
            llm=llm,
            show_progress=False,
        )
        
        # Extract Response Groundedness scores from the evaluation result
        groundedness_scores_df = groundedness_eval_result.to_pandas()
        
        # Debug: print column names and sample values to see what RAGAS actually returns
        logging.debug(f"RAGAS Groundedness DataFrame columns: {list(groundedness_scores_df.columns)}")
        if len(groundedness_scores_df) > 0:
            logging.debug(f"Sample RAGAS row values: {dict(groundedness_scores_df.iloc[0])}")
        
        for idx, row in groundedness_scores_df.iterrows():
            original_idx = indices_to_update[idx]
            
            # Extract context relevance from our separate evaluation (or None if no document contexts)
            context_rel = context_relevance_scores.get(original_idx)  # None if not evaluated (personal_only)
            
            # Extract response groundedness - try multiple column name formats
            response_grd = None
            response_grd_raw = None
            for col_name in ["nv_response_groundedness", "response_groundedness", "response_groundedness_score"]:
                if col_name in groundedness_scores_df.columns:
                    val = row[col_name]
                    response_grd_raw = val  # Store raw value for debugging
                    if pd.notna(val):
                        try:
                            response_grd = float(val)
                            break
                        except (ValueError, TypeError):
                            continue
            
            # Store the scores
            # Context Relevance: None for personal_only (missing), actual score for others
            results[original_idx]["ragas_context_relevance"] = context_rel  # None is OK - means not applicable
            # Response Groundedness: actual score or None if extraction failed
            results[original_idx]["ragas_response_groundedness"] = response_grd if response_grd is not None else None
            
            # Log if extraction failed
            if response_grd is None:
                logging.warning(f"RAGAS Response Groundedness extraction failed for result {original_idx}. Raw value: {response_grd_raw}. Available columns: {list(groundedness_scores_df.columns)}")
            elif response_grd == 0.0:
                # Legitimate 0.0 scores - log at debug level, not warning
                logging.debug(f"RAGAS Response Groundedness is 0.0 for result {original_idx}")
            
            # Log context relevance status
            if context_rel is None:
                # Check if this is a personal_only question (expected to have no context relevance)
                ground_truth_intent = results[original_idx].get("ground_truth_intent_mapped") or results[original_idx].get("ground_truth_intent")
                if ground_truth_intent == "personal_only":
                    logging.debug(f"Context Relevance not evaluated for result {original_idx} (personal_only question - no document contexts)")
                else:
                    # Check if document contexts actually exist
                    doc_contexts = doc_contexts_list[original_idx] if original_idx < len(doc_contexts_list) else []
                    if doc_contexts:
                        logging.warning(f"Context Relevance not evaluated for result {original_idx} despite having document contexts (score extraction may have failed)")
                    else:
                        logging.debug(f"Context Relevance not evaluated for result {original_idx} (no document contexts found - question type: {ground_truth_intent})")
        
        logging.info(f"Added RAGAS scores to {len(results_to_evaluate)} results")
    except Exception as e:
        logging.error(f"Failed to compute RAGAS scores: {e}")
        import traceback
        logging.error(traceback.format_exc())
    
    return results


def compute_ragas_metrics(
    results: List[Dict[str, Any]], sample_size: Optional[int] = None
) -> Dict[str, Any]:
    """
    Compute aggregate RAGAS metrics from results that already have RAGAS scores.
    Call add_ragas_scores_to_results() first to add scores to individual results.
    """
    # Extract RAGAS scores
    relevance_scores = [
        r.get("ragas_context_relevance")
        for r in results
        if r.get("ragas_context_relevance") is not None
    ]
    groundedness_scores = [
        r.get("ragas_response_groundedness")
        for r in results
        if r.get("ragas_response_groundedness") is not None
    ]
    
    if relevance_scores and groundedness_scores:
        return {
            "context_relevance": {
                "mean": sum(relevance_scores) / len(relevance_scores),
                "num_evaluated": len(relevance_scores),
            },
            "response_groundedness": {
                "mean": sum(groundedness_scores) / len(groundedness_scores),
                "num_evaluated": len(groundedness_scores),
            },
        }
    
    # If scores not present, need to compute them (fallback - should not happen if add_ragas_scores_to_results was called)
    logging.warning("RAGAS scores not found in results; computing now (this is inefficient)")
    # This would require re-implementing the evaluation logic, but for now just return None
    # The proper flow is: add_ragas_scores_to_results() first, then compute_ragas_metrics()
    return {
        "context_relevance": None,
        "response_groundedness": None,
        "error": "RAGAS scores not found in results. Call add_ragas_scores_to_results() first.",
    }


def save_metrics(
    intent_results,
    baseline_results,
    agent_discretion_results=None,
    ragas_sample_size=None,
    skip_ragas=False,
):
    """
    Save comprehensive metrics summary comparing llm_classifier, always_both, and optionally agent_discretion strategies.
    This function is kept for backward compatibility with scripts that import it.
    """
    try:
        intent_metrics = compute_intent_metrics(intent_results)
        baseline_intent_metrics = compute_intent_metrics(baseline_results)
    except Exception as e:
        tqdm.write(f"ERROR: Failed to compute intent metrics: {e}")
        import traceback
        tqdm.write(f"Traceback: {traceback.format_exc()}")
        intent_metrics = {"classification_report": {}, "roc_auc": None}
        baseline_intent_metrics = {"classification_report": {}, "roc_auc": None}
    
    try:
        retrieval_hit_rate_intent = compute_retrieval_hit_rate_at_k(intent_results)
        retrieval_hit_rate_baseline = compute_retrieval_hit_rate_at_k(baseline_results)
    except Exception as e:
        tqdm.write(f"ERROR: Failed to compute retrieval hit rate: {e}")
        import traceback
        tqdm.write(f"Traceback: {traceback.format_exc()}")
        retrieval_hit_rate_intent = {}
        retrieval_hit_rate_baseline = {}
    
    try:
        latency_intent = compute_latency_metrics(intent_results)
        latency_baseline = compute_latency_metrics(baseline_results)
    except Exception as e:
        tqdm.write(f"ERROR: Failed to compute latency metrics: {e}")
        import traceback
        tqdm.write(f"Traceback: {traceback.format_exc()}")
        latency_intent = {}
        latency_baseline = {}
    
    # Restructure: organize by metrics first, then metric values, then scenarios (deepest nesting)
    summary = {}
    
    # Query counts
    summary["query_counts"] = {
        "llm_classifier": len(intent_results),
        "always_both": len(baseline_results),
    }
    
    # Statistical significance tests (t-tests for llm_classifier vs baselines)
    summary["statistical_tests"] = {}
    
    # Latency: p90_ms and p95_ms with scenarios nested
    summary["latency"] = {}
    for metric_key in ["p90_ms", "p95_ms"]:
        summary["latency"][metric_key] = {
            "llm_classifier": latency_intent.get(metric_key),
            "always_both": latency_baseline.get(metric_key),
        }
    
    # Retrieval hit rate: @3, @5, @10 with scenarios nested
    summary["retrieval_hit_rate"] = {}
    for k in [3, 5, 10]:
        metric_key = f"retrieval_hit_rate@{k}"
        summary["retrieval_hit_rate"][metric_key] = {
            "llm_classifier": retrieval_hit_rate_intent.get(metric_key),
            "always_both": retrieval_hit_rate_baseline.get(metric_key),
        }
    
    # Intent metrics: flatten nested structure
    summary["intent_metrics"] = {}
    # Handle classification_report metrics
    if "classification_report" in intent_metrics:
        for class_name in ["personal_only", "documents_only", "both_combined", "accuracy", "macro avg", "weighted avg"]:
            if class_name in intent_metrics["classification_report"]:
                if isinstance(intent_metrics["classification_report"][class_name], dict):
                    # For class-specific metrics, nest by metric name
                    for metric_name in ["precision", "recall", "f1-score", "support"]:
                        if metric_name in intent_metrics["classification_report"][class_name]:
                            key = f"{class_name}_{metric_name}"
                            if key not in summary["intent_metrics"]:
                                summary["intent_metrics"][key] = {}
                            summary["intent_metrics"][key]["llm_classifier"] = intent_metrics["classification_report"][class_name][metric_name]
                            # Handle case where baseline classification_report might be None
                            baseline_classification_report = baseline_intent_metrics.get("classification_report") or {}
                            summary["intent_metrics"][key]["always_both"] = baseline_classification_report.get(class_name, {}).get(metric_name) if isinstance(baseline_classification_report, dict) else None
    
    # ROC-AUC
    if "roc_auc" in intent_metrics and intent_metrics["roc_auc"]:
        for class_name in ["personal_only", "documents_only", "both_combined"]:
            if class_name in intent_metrics["roc_auc"]:
                key = f"roc_auc_{class_name}"
                if key not in summary["intent_metrics"]:
                    summary["intent_metrics"][key] = {}
                summary["intent_metrics"][key]["llm_classifier"] = intent_metrics["roc_auc"][class_name]
                # Handle case where baseline roc_auc is None
                baseline_roc_auc = baseline_intent_metrics.get("roc_auc") or {}
                summary["intent_metrics"][key]["always_both"] = baseline_roc_auc.get(class_name) if isinstance(baseline_roc_auc, dict) else None
    
    if agent_discretion_results:
        agent_discretion_intent_metrics = compute_intent_metrics(agent_discretion_results)
        retrieval_hit_rate_agent_discretion = compute_retrieval_hit_rate_at_k(agent_discretion_results)
        latency_agent_discretion = compute_latency_metrics(agent_discretion_results)
        
        # Add agent_discretion to query counts
        summary["query_counts"]["agent_discretion"] = len(agent_discretion_results)
        
        # Add agent_discretion to latency
        for metric_key in ["p90_ms", "p95_ms"]:
            summary["latency"][metric_key]["agent_discretion"] = latency_agent_discretion.get(metric_key)
        
        # Add agent_discretion to retrieval_hit_rate
        for k in [3, 5, 10]:
            metric_key = f"retrieval_hit_rate@{k}"
            summary["retrieval_hit_rate"][metric_key]["agent_discretion"] = retrieval_hit_rate_agent_discretion.get(metric_key)
        
        # Add agent_discretion to intent_metrics
        if "classification_report" in agent_discretion_intent_metrics:
            for class_name in ["personal_only", "documents_only", "both_combined", "accuracy", "macro avg", "weighted avg"]:
                if class_name in agent_discretion_intent_metrics["classification_report"]:
                    if isinstance(agent_discretion_intent_metrics["classification_report"][class_name], dict):
                        for metric_name in ["precision", "recall", "f1-score", "support"]:
                            if metric_name in agent_discretion_intent_metrics["classification_report"][class_name]:
                                key = f"{class_name}_{metric_name}"
                                if key in summary["intent_metrics"]:
                                    summary["intent_metrics"][key]["agent_discretion"] = agent_discretion_intent_metrics["classification_report"][class_name][metric_name]
        
        if "roc_auc" in agent_discretion_intent_metrics and agent_discretion_intent_metrics["roc_auc"]:
            for class_name in ["personal_only", "documents_only", "both_combined"]:
                if class_name in agent_discretion_intent_metrics["roc_auc"]:
                    key = f"roc_auc_{class_name}"
                    if key in summary["intent_metrics"]:
                        summary["intent_metrics"][key]["agent_discretion"] = agent_discretion_intent_metrics["roc_auc"][class_name]
    
    # Compute RAGAS metrics for response quality (if not skipped)
    if not skip_ragas:
        try:
            tqdm.write("Computing RAGAS metrics for response quality...")
            ragas_intent = compute_ragas_metrics(intent_results, sample_size=ragas_sample_size)
            ragas_baseline = compute_ragas_metrics(baseline_results, sample_size=ragas_sample_size)
            
            summary["response_quality"] = {}
            for metric_name in ["context_relevance", "response_groundedness"]:
                summary["response_quality"][metric_name] = {
                    "llm_classifier": ragas_intent.get(metric_name),
                    "always_both": ragas_baseline.get(metric_name),
                }
            
            if agent_discretion_results:
                ragas_agent_discretion = compute_ragas_metrics(
                    agent_discretion_results, sample_size=ragas_sample_size
                )
                for metric_name in ["context_relevance", "response_groundedness"]:
                    summary["response_quality"][metric_name]["agent_discretion"] = ragas_agent_discretion.get(metric_name)
            
            tqdm.write("✓ RAGAS metrics computed")
        except Exception as e:
            tqdm.write(f"ERROR: Failed to compute RAGAS metrics: {e}")
            import traceback
            tqdm.write(f"Traceback: {traceback.format_exc()}")
            summary["response_quality"] = {
                "error": str(e),
                "context_relevance": {"llm_classifier": None, "always_both": None},
                "response_groundedness": {"llm_classifier": None, "always_both": None},
            }
    else:
        tqdm.write("Skipping RAGAS evaluation (--skip-ragas flag)")
    
    # Compute statistical significance tests
    try:
        tqdm.write("Computing statistical significance tests...")
        
        # Helper function to perform t-test
        def compute_ttest(intent_values, baseline_values, metric_name, baseline_name):
            """Compute t-test and return p-value"""
            try:
                if len(intent_values) > 1 and len(baseline_values) > 1:
                    t_stat, p_value = stats.ttest_ind(intent_values, baseline_values)
                    # Convert numpy types to native Python types for JSON serialization
                    p_value = float(p_value)
                    return {
                        "p_value": p_value,
                        "significant_at_0.05": bool(p_value < 0.05),
                        "significant_at_0.01": bool(p_value < 0.01),
                    }
            except Exception as e:
                tqdm.write(f"Warning: Failed to compute t-test for {metric_name} vs {baseline_name}: {e}")
            return None
        
        # Latency tests
        intent_latencies = [r.get("latency_ms") for r in intent_results if r.get("latency_ms") is not None]
        baseline_latencies = [r.get("latency_ms") for r in baseline_results if r.get("latency_ms") is not None]
        
        summary["statistical_tests"]["latency_vs_always_both"] = compute_ttest(
            intent_latencies, baseline_latencies, "latency", "always_both"
        )
        
        if agent_discretion_results:
            agent_latencies = [r.get("latency_ms") for r in agent_discretion_results if r.get("latency_ms") is not None]
            summary["statistical_tests"]["latency_vs_agent_discretion"] = compute_ttest(
                intent_latencies, agent_latencies, "latency", "agent_discretion"
            )
        
        # RAGAS tests (if available)
        if not skip_ragas:
            # Context Relevance
            intent_relevance = [r.get("ragas_context_relevance") for r in intent_results if r.get("ragas_context_relevance") is not None]
            baseline_relevance = [r.get("ragas_context_relevance") for r in baseline_results if r.get("ragas_context_relevance") is not None]
            
            summary["statistical_tests"]["context_relevance_vs_always_both"] = compute_ttest(
                intent_relevance, baseline_relevance, "context_relevance", "always_both"
            )
            
            # Response Groundedness
            intent_groundedness = [r.get("ragas_response_groundedness") for r in intent_results if r.get("ragas_response_groundedness") is not None]
            baseline_groundedness = [r.get("ragas_response_groundedness") for r in baseline_results if r.get("ragas_response_groundedness") is not None]
            
            summary["statistical_tests"]["response_groundedness_vs_always_both"] = compute_ttest(
                intent_groundedness, baseline_groundedness, "response_groundedness", "always_both"
            )
            
            if agent_discretion_results:
                agent_relevance = [r.get("ragas_context_relevance") for r in agent_discretion_results if r.get("ragas_context_relevance") is not None]
                agent_groundedness = [r.get("ragas_response_groundedness") for r in agent_discretion_results if r.get("ragas_response_groundedness") is not None]
                
                summary["statistical_tests"]["context_relevance_vs_agent_discretion"] = compute_ttest(
                    intent_relevance, agent_relevance, "context_relevance", "agent_discretion"
                )
                
                summary["statistical_tests"]["response_groundedness_vs_agent_discretion"] = compute_ttest(
                    intent_groundedness, agent_groundedness, "response_groundedness", "agent_discretion"
                )
        
        tqdm.write("✓ Statistical tests computed")
    except Exception as e:
        tqdm.write(f"ERROR: Failed to compute statistical tests: {e}")
        import traceback
        tqdm.write(f"Traceback: {traceback.format_exc()}")
        summary["statistical_tests"]["error"] = str(e)
    
    # Custom JSON encoder to handle numpy types and other non-serializable types
    class NumpyJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            # Try item() method for numpy scalars
            try:
                if hasattr(obj, 'item'):
                    return obj.item()
            except (AttributeError, ValueError):
                pass
            return super().default(obj)
    
    # Write metrics summary with error handling
    try:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(RESULTS_DIR / "metrics_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, cls=NumpyJSONEncoder)
        tqdm.write(f"✓ Metrics summary saved to {RESULTS_DIR / 'metrics_summary.json'}")
    except Exception as e:
        tqdm.write(f"ERROR: Failed to save metrics summary: {e}")
        import traceback
        tqdm.write(f"Traceback: {traceback.format_exc()}")
        # Try to save a partial summary for debugging
        try:
            debug_path = RESULTS_DIR / "metrics_summary_debug.json"
            with open(debug_path, "w", encoding="utf-8") as f:
                json.dump({
                    "error": str(e),
                    "partial_summary": summary,
                    "summary_keys": list(summary.keys()),
                }, f, indent=2, ensure_ascii=False, cls=NumpyJSONEncoder)
            tqdm.write(f"Debug info saved to {debug_path}")
        except:
            pass
        raise
