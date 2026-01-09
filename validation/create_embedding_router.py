#!/usr/bin/env python3
"""
One-time script to create embedding-based routing index.
Run once to generate embeddings for example queries.

This script:
1. Loads training queries from CSV
2. Splits into train/validation sets (stratified by intent)
3. Groups training queries by intent category (personal, general, combined)
4. Samples balanced examples per category from training set
5. Creates embeddings using OpenAI text-embedding-3-large
6. Tunes hyperparameters (k value) on validation set
7. Saves index for fast lookup at query time
"""
import csv
import json
import pickle
import numpy as np
from openai import OpenAI
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from validation.services.config import OPENAI_API_KEY

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found. Set it in config.yaml or as environment variable.")

client = OpenAI(api_key=OPENAI_API_KEY)


def embed_text(text: str) -> np.ndarray:
    """Get embedding for a single text."""
    response = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return np.array(response.data[0].embedding)


def load_queries_from_csv(csv_path: Path) -> List[Dict[str, str]]:
    """Load queries from CSV file."""
    queries = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            queries.append({
                "query_id": row.get("query_id", ""),
                "question": row.get("question", ""),
                "question_type": row.get("question_type", ""),
            })
    return queries


def map_question_type_to_intent(question_type: str) -> str:
    """Map CSV question_type to intent format."""
    mapping = {
        "personal": "personal_only",
        "general": "documents_only",
        "combined": "both_combined",
    }
    return mapping.get(question_type, "both_combined")


def split_queries_by_intent(
    queries: List[Dict[str, str]],
    validation_split_ratio: float = 0.2,
    random_seed: int = 42
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Split queries into train and validation sets, stratified by intent.
    
    Args:
        queries: List of query dictionaries
        validation_split_ratio: Fraction of data to use for validation (default: 0.2)
        random_seed: Random seed for reproducibility
    
    Returns:
        Tuple of (train_queries, validation_queries)
    """
    import random
    
    # Group by intent for stratified splitting
    by_intent = defaultdict(list)
    for q in queries:
        intent = map_question_type_to_intent(q["question_type"])
        by_intent[intent].append(q)
    
    train_queries = []
    validation_queries = []
    
    # Split each intent category separately to maintain stratification
    random.seed(random_seed)
    for intent, intent_queries in by_intent.items():
        # Shuffle within each intent category
        shuffled = intent_queries.copy()
        random.shuffle(shuffled)
        
        # Calculate split point
        n_validation = max(1, int(len(shuffled) * validation_split_ratio))
        
        # Split
        validation_queries.extend(shuffled[:n_validation])
        train_queries.extend(shuffled[n_validation:])
    
    # Shuffle final lists
    random.shuffle(train_queries)
    random.shuffle(validation_queries)
    
    return train_queries, validation_queries


def create_routing_index(
    training_csv_path: str,
    output_path: str,
    examples_per_category: int = 20,
    validation_split_ratio: float = 0.2,
    k_values: List[int] = [3, 5, 10, 15],
    random_seed: int = 42,
) -> Tuple[Dict, int]:
    """
    Create embedding index from training queries and tune hyperparameters.
    
    Splits the training CSV into train and validation sets, uses train set
    for creating the embedding index, and validation set for hyperparameter tuning.
    
    Args:
        training_csv_path: Path to training CSV with queries
        output_path: Where to save the routing index
        examples_per_category: Number of examples to sample per category
        validation_split_ratio: Fraction of data to use for validation (default: 0.2)
        k_values: List of k values to test for k-NN
        random_seed: Random seed for reproducibility
    
    Returns:
        Tuple of (routing_index dict, best_k value)
    """
    training_path = Path(training_csv_path)
    if not training_path.exists():
        raise FileNotFoundError(f"Training CSV not found: {training_csv_path}")
    
    # Load all queries
    all_queries = load_queries_from_csv(training_path)
    print(f"Loaded {len(all_queries)} total queries from {training_csv_path}")
    
    # Split into train and validation sets (stratified by intent)
    train_queries, validation_queries = split_queries_by_intent(
        all_queries,
        validation_split_ratio=validation_split_ratio,
        random_seed=random_seed
    )
    
    print(f"\nSplit into train ({len(train_queries)} queries) and validation ({len(validation_queries)} queries)")
    print(f"Validation split ratio: {validation_split_ratio:.1%}")
    
    # Group training queries by intent (mapped from question_type)
    by_intent = defaultdict(list)
    for q in train_queries:
        intent = map_question_type_to_intent(q["question_type"])
        by_intent[intent].append(q["question"])
    
    print("\nIntent distribution in training set:")
    for intent, qs in sorted(by_intent.items()):
        print(f"  {intent}: {len(qs)} queries")
    
    # Sample examples for each category
    # Use stratified sampling to ensure diversity
    routing_index = {
        'categories': {},
        'metadata': {
            'model': 'text-embedding-3-large',
            'examples_per_category': examples_per_category,
            'created_at': datetime.now().isoformat(),
            'training_csv': str(training_path),
        }
    }
    
    for intent, query_list in sorted(by_intent.items()):
        # Sample (or take all if fewer than requested)
        n_examples = min(examples_per_category, len(query_list))
        
        # Stratified sampling: space out examples evenly across the list
        if n_examples >= len(query_list):
            sampled = query_list
        else:
            indices = np.linspace(0, len(query_list) - 1, n_examples, dtype=int)
            sampled = [query_list[i] for i in indices]
        
        print(f"\nEmbedding {len(sampled)} examples for {intent}...")
        embeddings = []
        for i, query in enumerate(sampled):
            emb = embed_text(query)
            embeddings.append(emb)
            if (i + 1) % 5 == 0:
                print(f"  {i + 1}/{len(sampled)}")
        
        routing_index['categories'][intent] = {
            'queries': sampled,  # Keep for debugging/analysis
            'embeddings': np.array(embeddings)
        }
    
    # Hyperparameter tuning: find best k value using validation set
    # Default to 5 if no k_values provided or if tuning fails
    best_k = 5  # Default
    if len(validation_queries) > 0:
        print(f"\n{'='*60}")
        print("Hyperparameter Tuning: Finding optimal k value")
        print(f"Using {len(validation_queries)} validation queries")
        print(f"{'='*60}")
        
        # Test different k values
        results = {}
        for k in k_values:
            correct = 0
            total = 0
            
            print(f"\nTesting k={k}...")
            for i, query_data in enumerate(validation_queries):
                if i % 50 == 0 and i > 0:
                    print(f"  Processed {i}/{len(validation_queries)} queries...")
                
                question = query_data["question"]
                expected_intent = map_question_type_to_intent(query_data["question_type"])
                
                # Embed query
                query_emb = embed_text(question)
                
                # Compute similarity to each category
                category_scores = {}
                for category, data in routing_index['categories'].items():
                    embeddings = data['embeddings']
                    similarities = np.array([
                        np.dot(query_emb, ex_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(ex_emb))
                        for ex_emb in embeddings
                    ])
                    # Average of top-k similarities
                    if len(similarities) > 0:
                        top_k_sims = np.sort(similarities)[-k:]
                        category_scores[category] = np.mean(top_k_sims)
                    else:
                        category_scores[category] = 0.0
                
                # Predict intent
                predicted_intent = max(category_scores, key=category_scores.get)
                
                if predicted_intent == expected_intent:
                    correct += 1
                total += 1
            
            accuracy = correct / total if total > 0 else 0.0
            results[k] = accuracy
            print(f"  k={k}: {accuracy:.3f} accuracy ({correct}/{total} correct)")
        
        best_k = max(results, key=results.get)
        print(f"\n{'='*60}")
        print(f"Best k: {best_k} ({results[best_k]:.3f} accuracy)")
        print(f"{'='*60}")
    else:
        print("\nNo validation queries available, using default k=5")
    
    # Save best k in metadata
    routing_index['metadata']['best_k'] = best_k
    routing_index['metadata']['hyperparameter_tuning'] = len(validation_queries) > 0
    routing_index['metadata']['validation_split_ratio'] = validation_split_ratio
    routing_index['metadata']['train_size'] = len(train_queries)
    routing_index['metadata']['validation_size'] = len(validation_queries)
    
    # Save as pickle
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path_obj, 'wb') as f:
        pickle.dump(routing_index, f)
    
    print(f"\n{'='*60}")
    print(f"✓ Routing index saved to {output_path}")
    print(f"  Total categories: {len(routing_index['categories'])}")
    print(f"  Total embeddings: {sum(len(v['embeddings']) for v in routing_index['categories'].values())}")
    print(f"  Best k (for k-NN): {best_k}")
    print(f"{'='*60}")
    
    return routing_index, best_k


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create embedding-based routing index")
    parser.add_argument(
        "--training-csv",
        type=str,
        default="validation/queries/questions_ground_truth_train.csv",
        help="Path to training CSV file (will be split into train/validation)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="validation/models/embedding_routing_index.pkl",
        help="Output path for routing index"
    )
    parser.add_argument(
        "--examples-per-category",
        type=int,
        default=20,
        help="Number of examples to sample per category (default: 20)"
    )
    parser.add_argument(
        "--validation-split-ratio",
        type=float,
        default=0.2,
        help="Fraction of training data to use for validation (default: 0.2)"
    )
    parser.add_argument(
        "--k-values",
        type=int,
        nargs="+",
        default=[3, 5, 10, 15],
        help="List of k values to test for hyperparameter tuning (k=1 excluded as it's just single nearest neighbor)"
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for train/validation split (default: 42)"
    )
    
    args = parser.parse_args()
    
    # Validate split ratio
    if not 0 < args.validation_split_ratio < 1:
        raise ValueError("--validation-split-ratio must be between 0 and 1")
    
    # Resolve paths relative to project root
    project_root = Path(__file__).resolve().parent.parent
    training_csv = project_root / args.training_csv
    output_path = project_root / args.output
    
    create_routing_index(
        training_csv_path=str(training_csv),
        output_path=str(output_path),
        examples_per_category=args.examples_per_category,
        validation_split_ratio=args.validation_split_ratio,
        k_values=args.k_values,
        random_seed=args.random_seed,
    )

