"""
Embedding similarity routing strategy.
Routes based on cosine similarity to labeled example queries.

This implements a RouteLLM-style approach using k-NN with embeddings.
"""
import pickle
import numpy as np
from openai import OpenAI
from pathlib import Path
from typing import Literal, Dict, Optional, Tuple
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from validation.services.config import OPENAI_API_KEY

IntentCategory = Literal["personal_only", "documents_only", "both_combined"]


class EmbeddingSimilarityRouter:
    """
    Router that classifies query intent using embedding similarity.
    
    Uses k-NN approach: embeds the query, computes similarity to all
    example queries in each category, and routes to the category with
    highest average similarity among top-k neighbors.
    """
    
    def __init__(self, index_path: Optional[str] = None):
        """
        Load pre-computed routing index.
        
        Args:
            index_path: Path to the pickled routing index. If None, uses default path.
        """
        if index_path is None:
            index_path = PROJECT_ROOT / "validation" / "models" / "embedding_routing_index.pkl"
        
        index_path_obj = Path(index_path)
        if not index_path_obj.exists():
            raise FileNotFoundError(
                f"Routing index not found at {index_path}. "
                "Run validation/create_embedding_router.py first to create the index."
            )
        
        with open(index_path_obj, 'rb') as f:
            self.index = pickle.load(f)
        
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not found. Set it in config.yaml or as environment variable.")
        
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.categories = list(self.index['categories'].keys())
        
        # Get best k from metadata, or use default
        self.default_k = self.index.get('metadata', {}).get('best_k', 5)
        
        print(f"Loaded embedding router with {len(self.categories)} categories")
        for cat in self.categories:
            n_examples = len(self.index['categories'][cat]['embeddings'])
            print(f"  {cat}: {n_examples} examples")
        print(f"  Default k: {self.default_k}")
    
    def embed_query(self, query: str) -> np.ndarray:
        """Embed query using same model as index."""
        response = self.client.embeddings.create(
            model="text-embedding-3-large",
            input=query
        )
        return np.array(response.data[0].embedding)
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
    
    def classify_intent(
        self, 
        query: str,
        k: Optional[int] = None,
        return_scores: bool = False
    ) -> IntentCategory | Tuple[IntentCategory, Dict[str, float]]:
        """
        Classify query intent using k-NN with embeddings.
        
        Args:
            query: User query
            k: Number of nearest neighbors per category to consider (default: from index metadata)
            return_scores: If True, return (intent, score_dict)
        
        Returns:
            Predicted intent category, optionally with similarity scores
        """
        if k is None:
            k = self.default_k
        
        # Embed query
        query_emb = self.embed_query(query)
        
        # Compute similarity to each category
        # RouteLLM-style: average of top-k similarities per category
        category_scores = {}
        
        for category, data in self.index['categories'].items():
            embeddings = data['embeddings']
            
            # Compute similarity to all examples in category
            similarities = np.array([
                self.cosine_similarity(query_emb, ex_emb)
                for ex_emb in embeddings
            ])
            
            # Take average of top-k similarities
            # This is the RouteLLM approach: use top-k neighbors, not just max
            if len(similarities) > 0:
                top_k_sims = np.sort(similarities)[-k:]
                category_scores[category] = np.mean(top_k_sims)
            else:
                category_scores[category] = 0.0
        
        # Route to category with highest score
        predicted_intent = max(category_scores, key=category_scores.get)
        
        if return_scores:
            return predicted_intent, category_scores
        return predicted_intent

