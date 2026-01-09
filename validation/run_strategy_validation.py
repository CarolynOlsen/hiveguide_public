#!/usr/bin/env python3
"""
Flexible strategy-based validation script for iterating on RAG strategies.

This script allows you to easily add and test new strategies (e.g., heuristic-based
classification, new tools, different agent configurations) without modifying the
main validation script.

Usage:
    # Run a single strategy
    python3 validation/run_strategy_validation.py --strategy heuristic_classifier --email test@test.com
    
    # Run multiple strategies and compare
    python3 validation/run_strategy_validation.py --strategy intent_aware --strategy heuristic_classifier --email test@test.com
    
    # Use CSV questions
    python3 validation/run_strategy_validation.py --strategy my_strategy --queries-file validation/queries/questions_ground_truth.csv --email test@test.com
"""
import argparse
import csv
import json
import logging
import signal
import sys
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol
from sqlalchemy import text

# Add project root to path for direct execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from validation.services.db import SessionLocal, User, Hive
from validation.services.config import DATABASE_URL, OPENAI_API_KEY, OPENROUTER_API_KEY
from validation import rag_client
from validation import baseline_system
from validation.validation_service import (
    ValidationService,
    create_heuristic_classifier,
    create_keyword_routing_strategy,
)
from validation.embedding_router import EmbeddingSimilarityRouter
from validation.metrics import (
    compute_intent_metrics,
    compute_latency_metrics,
    compute_retrieval_hit_rate_at_k,
    compute_ragas_metrics,
    add_ragas_scores_to_results,
)
from tqdm import tqdm

# Reduce logging verbosity
logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("backend.rag").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("stainless").setLevel(logging.WARNING)
logging.getLogger("ragas").setLevel(logging.WARNING)
import warnings
warnings.filterwarnings("ignore", message=".*Importing verbose from langchain root module.*")
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core.globals")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERIES_PATH = PROJECT_ROOT / "validation" / "queries" / "generated_queries.json"
RESULTS_DIR = PROJECT_ROOT / "validation" / "results"


# ============================================================================
# Strategy Interface
# ============================================================================

class ValidationStrategy(ABC):
    """
    Abstract base class for validation strategies.
    
    To add a new strategy, subclass this and implement:
    1. name: unique identifier for the strategy
    2. execute_query(): how to process a single query
    3. extract_predicted_intent(): how to extract intent from result (if applicable)
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this strategy (used for result file names)."""
        pass
    
    @abstractmethod
    def execute_query(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a single query and return a result dict.
        
        Must return a dict with at least:
        - question: str
        - answer: str
        - sources: List[Dict]
        - metadata: Dict
        - latency_ms: float
        
        Can include additional fields as needed.
        """
        pass
    
    def extract_predicted_intent(self, result: Dict[str, Any]) -> Optional[str]:
        """
        Extract predicted intent from result metadata.
        Returns None if strategy doesn't predict intent.
        Override if your strategy provides intent classification.
        """
        return None
    
    def extract_class_probabilities(self, result: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """
        Extract class probabilities from result metadata.
        Returns None if strategy doesn't provide probabilities.
        Override if your strategy provides probability distributions.
        """
        return None


# ============================================================================
# Built-in Strategies
# ============================================================================

class LLMClassifierStrategy(ValidationStrategy):
    """The main RAG system with LLM-based classification."""
    
    def __init__(self):
        self.validation_service = ValidationService()
    
    @property
    def name(self) -> str:
        return "llm_classifier"
    
    def execute_query(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Use simple LLM with LLM-based intent classification
                result = self.validation_service.query_with_custom_routing(
                    question=question,
                    user_id=user_id,
                    session_id=session_id,
                    use_simple_llm=True,  # Use simple LLM, not agent
                )
                
                answer = result.get("answer", "")
                # Check if answer is empty or just whitespace
                if answer and answer.strip():
                    # Format result
                    res_dict = {
                        "question": question,
                        "answer": answer,
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
                    return res_dict
                elif attempt < max_retries:
                    # Empty answer, retry
                    continue
                else:
                    # Last attempt failed, return with error message
                    return {
                        "question": question,
                        "answer": "I was unable to generate a response. Please try rephrasing your question.",
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
            except Exception as e:
                if attempt < max_retries:
                    # Retry on exception
                    continue
                else:
                    # Last attempt failed, return error
                    return {
                        "question": question,
                        "answer": f"I encountered an error processing your question: {str(e)}",
                        "sources": [],
                        "metadata": {"error": str(e)},
                        "latency_ms": 0,
                    }
    
    def extract_predicted_intent(self, result: Dict[str, Any]) -> Optional[str]:
        intent_meta = result.get("metadata", {}).get("intent_classification") or {}
        return intent_meta.get("PRIMARY_DATA_NEED")
    
    def extract_class_probabilities(self, result: Dict[str, Any]) -> Optional[Dict[str, float]]:
        intent_meta = result.get("metadata", {}).get("intent_classification") or {}
        return intent_meta.get("class_probabilities")


class AlwaysBothStrategy(ValidationStrategy):
    """Baseline: always use both tools, no intent classification."""
    
    def __init__(self):
        self.validation_service = ValidationService()
    
    @property
    def name(self) -> str:
        return "always_both"
    
    def execute_query(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Always use both - simple LLM call with both user data and documents
                # Create a dummy intent classifier that always returns both_combined
                def always_both_classifier(question: str) -> Dict[str, Any]:
                    return {
                        "PRIMARY_DATA_NEED": "both_combined",
                        "SPECIFIC_FOCUS": "general_advice",
                        "URGENCY": "routine_check",
                        "TOOL_STRATEGY": "parallel_search",
                    }
                
                result = self.validation_service.query_with_custom_routing(
                    question=question,
                    user_id=user_id,
                    session_id=session_id,
                    intent_classifier=always_both_classifier,
                    use_simple_llm=True,  # Use simple LLM, not agent
                )
                
                answer = result.get("answer", "")
                # Check if answer is empty or just whitespace
                if answer and answer.strip():
                    # Format result
                    res_dict = {
                        "question": question,
                        "answer": answer,
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
                    return res_dict
                elif attempt < max_retries:
                    # Empty answer, retry
                    continue
                else:
                    # Last attempt failed, return with error message
                    return {
                        "question": question,
                        "answer": "I was unable to generate a response. Please try rephrasing your question.",
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
            except Exception as e:
                if attempt < max_retries:
                    # Retry on exception
                    continue
                else:
                    # Last attempt failed, return error
                    return {
                        "question": question,
                        "answer": f"I encountered an error processing your question: {str(e)}",
                        "sources": [],
                        "metadata": {"error": str(e)},
                        "latency_ms": 0,
                    }
    
    def extract_predicted_intent(self, result: Dict[str, Any]) -> Optional[str]:
        return "both_combined"  # Always uses both


class AgentDiscretionStrategy(ValidationStrategy):
    """Baseline: agent decides which tools to use, no pre-classification."""
    
    @property
    def name(self) -> str:
        return "agent_discretion"
    
    def execute_query(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                res = baseline_system.execute_agent_discretion(question, user_id=user_id, session_id=session_id)
                result_dict = res.to_dict()
                answer = result_dict.get("answer", "")
                # Check if answer is empty or just whitespace
                if answer and answer.strip() and "Agent stopped due to max iterations" not in answer:
                    return result_dict
                elif attempt < max_retries:
                    # Empty answer or max iterations, retry
                    continue
                else:
                    # Last attempt failed, return with error message
                    result_dict["answer"] = "I was unable to generate a response. Please try rephrasing your question."
                    return result_dict
            except Exception as e:
                if attempt < max_retries:
                    # Retry on exception
                    continue
                else:
                    # Last attempt failed, return error
                    return {
                        "question": question,
                        "answer": f"I encountered an error processing your question: {str(e)}",
                        "sources": [],
                        "metadata": {"error": str(e)},
                        "latency_ms": 0,
                    }
    
    def extract_predicted_intent(self, result: Dict[str, Any]) -> Optional[str]:
        return None  # Agent doesn't explicitly classify


class AgentWithIntentToolStrategy(ValidationStrategy):
    """
    Strategy using an agent with an intent classification tool.
    
    The agent has access to a classify_user_intent tool that it can call
    when uncertain about question type. This is fully self-contained in
    validation code - no app changes needed.
    """
    
    def __init__(self):
        from validation.agent_with_intent_tool import AgentWithIntentToolExecutor
        self._agent_executor = AgentWithIntentToolExecutor()
    
    @property
    def name(self) -> str:
        return "agent_with_intent_tool"
    
    def execute_query(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute query using agent with intent classification tool."""
        return self._agent_executor.execute_query(
            question=question,
            user_id=user_id,
            session_id=session_id,
        )
    
    def extract_predicted_intent(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract predicted intent from agent's classification tool usage."""
        return result.get("metadata", {}).get("predicted_intent")


# ============================================================================
# Example: Heuristic-based Classification Strategy
# ============================================================================

class HeuristicClassifierStrategy(ValidationStrategy):
    """
    Strategy using heuristic-based intent classification.
    
    Uses ValidationService to test heuristic routing without modifying the app.
    """
    
    def __init__(self):
        self.validation_service = ValidationService()
        self.intent_classifier = create_heuristic_classifier()
        self.routing_strategy = create_keyword_routing_strategy()
    
    @property
    def name(self) -> str:
        return "heuristic_classifier"
    
    def execute_query(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute query with heuristic-based classification and routing."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                result = self.validation_service.query_with_custom_routing(
                    question=question,
                    user_id=user_id,
                    session_id=session_id,
                    intent_classifier=self.intent_classifier,
                    routing_strategy=self.routing_strategy,
                    use_simple_llm=True,  # Use simple LLM, not agent
                )
                
                answer = result.get("answer", "")
                # Check if answer is empty or just whitespace
                if answer and answer.strip():
                    # Format result
                    res_dict = {
                        "question": question,
                        "answer": answer,
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
                    return res_dict
                elif attempt < max_retries:
                    # Empty answer, retry
                    continue
                else:
                    # Last attempt failed, return with error message
                    return {
                        "question": question,
                        "answer": "I was unable to generate a response. Please try rephrasing your question.",
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
            except Exception as e:
                if attempt < max_retries:
                    # Retry on exception
                    continue
                else:
                    # Last attempt failed, return error
                    return {
                        "question": question,
                        "answer": f"I encountered an error processing your question: {str(e)}",
                        "sources": [],
                        "metadata": {"error": str(e)},
                        "latency_ms": 0,
                    }
    
    def extract_predicted_intent(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract predicted intent from validation metadata."""
        return result.get("metadata", {}).get("validation_routing")


# ============================================================================
# Supervised Model-based Classification Strategy
# ============================================================================

class SupervisedClassifierStrategy(ValidationStrategy):
    """
    Strategy using a trained LightGBM classifier for intent classification.
    
    Uses the trained model from train_classifier.ipynb to classify questions
    into "personal", "combined", or "general" (docs only), then routes accordingly.
    """
    
    def __init__(self):
        import os
        # Fix OpenMP threading issues on macOS by setting environment variables before importing LightGBM
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")
        os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
        os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
        
        import joblib
        import lightgbm as lgb
        from pathlib import Path
        
        self.validation_service = ValidationService()
        
        # Load the trained model components
        models_dir = PROJECT_ROOT / "validation" / "models"
        model_path = models_dir / "question_type_classifier_lgbm.txt"
        vectorizer_path = models_dir / "tfidf_vectorizer.pkl"
        encoder_path = models_dir / "label_encoder.pkl"
        
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {model_path}. "
                "Please run train_classifier.ipynb to train the model first."
            )
        
        # Load model, vectorizer, and encoder
        # Set num_threads=1 for LightGBM to avoid OpenMP conflicts
        self.model = lgb.Booster(model_file=str(model_path))
        self.vectorizer = joblib.load(vectorizer_path)
        self.label_encoder = joblib.load(encoder_path)
        
        # Create intent classifier function
        self.intent_classifier = self._create_intent_classifier()
        self.routing_strategy = create_keyword_routing_strategy()
    
    def _create_intent_classifier(self) -> Callable[[str], Dict[str, Any]]:
        """Create an intent classifier function using the trained model."""
        def classify(question: str) -> Dict[str, Any]:
            import time
            # Time the classification for debugging
            start = time.perf_counter()
            
            # Transform question using TF-IDF
            question_tfidf = self.vectorizer.transform([question])
            question_dense = question_tfidf.toarray()
            
            # Predict class probabilities
            # Use best_iteration if available, otherwise use all iterations
            num_iteration = getattr(self.model, 'best_iteration', None)
            if num_iteration is not None:
                probabilities = self.model.predict(question_dense, num_iteration=num_iteration)
            else:
                probabilities = self.model.predict(question_dense)
            
            classification_time_ms = (time.perf_counter() - start) * 1000
            
            # Get predicted class (highest probability)
            predicted_class_idx = probabilities[0].argmax()
            predicted_class = self.label_encoder.inverse_transform([predicted_class_idx])[0]
            
            # Map model classes to intent format
            # Model classes: "combined", "general", "personal"
            # Intent format: "both_combined", "documents_only", "personal_only"
            class_to_intent = {
                "combined": "both_combined",
                "general": "documents_only",
                "personal": "personal_only",
            }
            
            primary_data_need = class_to_intent.get(predicted_class, "both_combined")
            
            # Create intent dict similar to other classifiers
            intent = {
                "PRIMARY_DATA_NEED": primary_data_need,
                "SPECIFIC_FOCUS": "general_advice" if predicted_class == "general" else "user_data",
                "URGENCY": "routine_check",
                "TOOL_STRATEGY": {
                    "personal_only": "user_data_first",
                    "documents_only": "documents_first",
                    "both_combined": "parallel_search",
                }.get(primary_data_need, "parallel_search"),
                "predicted_class": predicted_class,
                "class_probabilities": {
                    self.label_encoder.inverse_transform([i])[0]: float(prob)
                    for i, prob in enumerate(probabilities[0])
                },
                "classification_time_ms": classification_time_ms,
            }
            
            return intent
        
        return classify
    
    @property
    def name(self) -> str:
        return "supervised_classifier"
    
    def execute_query(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute query with supervised model-based classification and routing."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                result = self.validation_service.query_with_custom_routing(
                    question=question,
                    user_id=user_id,
                    session_id=session_id,
                    intent_classifier=self.intent_classifier,
                    routing_strategy=self.routing_strategy,
                    use_simple_llm=True,  # Use simple LLM, not agent
                )
                
                answer = result.get("answer", "")
                # Check if answer is empty or just whitespace
                if answer and answer.strip():
                    # Format result
                    res_dict = {
                        "question": question,
                        "answer": answer,
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
                    return res_dict
                elif attempt < max_retries:
                    # Empty answer, retry
                    continue
                else:
                    # Last attempt failed, return with error message
                    return {
                        "question": question,
                        "answer": "I was unable to generate a response. Please try rephrasing your question.",
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
            except Exception as e:
                if attempt < max_retries:
                    # Retry on exception
                    continue
                else:
                    # Last attempt failed, return error
                    return {
                        "question": question,
                        "answer": f"I encountered an error processing your question: {str(e)}",
                        "sources": [],
                        "metadata": {"error": str(e)},
                        "latency_ms": 0,
                    }
    
    def extract_predicted_intent(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract predicted intent from validation metadata."""
        return result.get("metadata", {}).get("validation_routing")


# ============================================================================
# Embedding-based Routing Strategy (RouteLLM-style)
# ============================================================================

class EmbeddingRouterStrategy(ValidationStrategy):
    """
    Strategy using embedding similarity for intent classification (RouteLLM-style).
    
    Uses k-NN with embeddings to classify queries, then routes to appropriate tools.
    """
    
    def __init__(self, index_path: Optional[str] = None):
        self.validation_service = ValidationService()
        self.router = EmbeddingSimilarityRouter(index_path=index_path)
        self.routing_strategy = create_keyword_routing_strategy()
        
        # Create intent classifier function that wraps the router
        def embedding_intent_classifier(question: str) -> Dict[str, Any]:
            """Classify intent using embedding similarity."""
            predicted_intent, scores = self.router.classify_intent(
                question,
                return_scores=True
            )
            
            # Map to intent format expected by ValidationService
            return {
                "PRIMARY_DATA_NEED": predicted_intent,
                "SPECIFIC_FOCUS": "general_advice" if predicted_intent == "documents_only" else "user_data",
                "URGENCY": "routine_check",
                "TOOL_STRATEGY": {
                    "personal_only": "user_data_first",
                    "documents_only": "documents_first",
                    "both_combined": "parallel_search",
                }.get(predicted_intent, "parallel_search"),
                "embedding_scores": scores,  # Store scores for analysis
            }
        
        self.intent_classifier = embedding_intent_classifier
    
    @property
    def name(self) -> str:
        return "embedding_router"
    
    def execute_query(
        self, 
        question: str, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute query with embedding-based classification and routing."""
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                result = self.validation_service.query_with_custom_routing(
                    question=question,
                    user_id=user_id,
                    session_id=session_id,
                    intent_classifier=self.intent_classifier,
                    routing_strategy=self.routing_strategy,
                    use_simple_llm=True,  # Use simple LLM, not agent
                )
                
                answer = result.get("answer", "")
                # Check if answer is empty or just whitespace
                if answer and answer.strip():
                    # Format result
                    res_dict = {
                        "question": question,
                        "answer": answer,
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
                    return res_dict
                elif attempt < max_retries:
                    # Empty answer, retry
                    continue
                else:
                    # Last attempt failed, return with error message
                    return {
                        "question": question,
                        "answer": "I was unable to generate a response. Please try rephrasing your question.",
                        "sources": result.get("sources", []),
                        "metadata": result.get("metadata", {}),
                        "latency_ms": result.get("latency_ms", 0),
                    }
            except Exception as e:
                if attempt < max_retries:
                    # Retry on exception
                    continue
                else:
                    # Last attempt failed, return error
                    return {
                        "question": question,
                        "answer": f"I encountered an error processing your question: {str(e)}",
                        "sources": [],
                        "metadata": {"error": str(e)},
                        "latency_ms": 0,
                    }
    
    def extract_predicted_intent(self, result: Dict[str, Any]) -> Optional[str]:
        """Extract predicted intent from validation metadata."""
        return result.get("metadata", {}).get("validation_routing")
    
    def extract_class_probabilities(self, result: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """Extract embedding similarity scores as probabilities."""
        intent_meta = result.get("metadata", {}).get("validation_intent", {})
        scores = intent_meta.get("embedding_scores")
        if scores:
            # Normalize scores to sum to 1 (softmax-like, but using raw similarities)
            total = sum(scores.values())
            if total > 0:
                return {k: v / total for k, v in scores.items()}
            return scores
        return None


# ============================================================================
# Strategy Registry
# ============================================================================

STRATEGY_REGISTRY: Dict[str, type[ValidationStrategy]] = {
    "llm_classifier": LLMClassifierStrategy,
    "always_both": AlwaysBothStrategy,
    "agent_discretion": AgentDiscretionStrategy,
    "heuristic_classifier": HeuristicClassifierStrategy,
    "agent_with_intent_tool": AgentWithIntentToolStrategy,
    "supervised_classifier": SupervisedClassifierStrategy,
    "embedding_router": EmbeddingRouterStrategy,
}


def register_strategy(strategy_class: type[ValidationStrategy]):
    """Register a new strategy class."""
    # Instantiate to get the name, then store the class
    strategy_instance = strategy_class()
    STRATEGY_REGISTRY[strategy_instance.name] = strategy_class


def get_strategy(name: str) -> ValidationStrategy:
    """Get a strategy instance by name."""
    if name not in STRATEGY_REGISTRY:
        raise ValueError(
            f"Unknown strategy: {name}. Available: {list(STRATEGY_REGISTRY.keys())}\n"
            f"To add a new strategy, subclass ValidationStrategy and register it."
        )
    strategy_class = STRATEGY_REGISTRY[name]
    # All strategies are instantiated (some need __init__ for setup)
    return strategy_class()


# ============================================================================
# Common Infrastructure
# ============================================================================

def load_queries(limit: Optional[int] = None, queries_file: Optional[Path] = None, random_seed: int = 42) -> List[Dict[str, Any]]:
    """
    Load queries from JSON or CSV file.
    
    Args:
        limit: If specified, randomly sample this many queries (with fixed seed for reproducibility)
        queries_file: Path to queries file (defaults to QUERIES_PATH)
        random_seed: Seed for random sampling (default: 42)
    
    Returns:
        List of query dictionaries, randomly shuffled if limit is specified
    """
    path = queries_file or QUERIES_PATH
    
    if path.suffix.lower() == ".csv":
        queries = load_queries_from_csv(path, limit=None)  # Load all first
    else:
        queries = load_queries_from_json(path, limit=None)  # Load all first
    
    # Randomize with fixed seed before applying limit
    if limit is not None and limit < len(queries):
        import random
        random.seed(random_seed)
        queries = random.sample(queries, limit)
    elif limit is not None:
        # If limit >= total queries, just shuffle for consistency
        import random
        random.seed(random_seed)
        random.shuffle(queries)
    
    return queries


def load_queries_from_json(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load queries from JSON file.
    
    Note: limit is handled in load_queries() after randomization.
    This function loads all queries from the file.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        queries = data if isinstance(data, list) else data.get("queries", [])
        return queries


def load_queries_from_csv(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load queries from CSV file.
    
    Note: limit is handled in load_queries() after randomization.
    This function loads all queries from the file.
    """
    import csv
    queries = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            query = {
                "query_id": row.get("query_id", ""),
                "question": row.get("question", ""),
                "ground_truth_intent": row.get("question_type", ""),
                "generation_strategy": row.get("generation_strategy", ""),
                "expected_sources": row.get("expected_sources", "").split(";") if row.get("expected_sources") else [],
                "ground_truth_chunks": row.get("ground_truth_chunks", "").split(";") if row.get("ground_truth_chunks") else [],
                "ground_truth_documents": row.get("source_material", "").split(";") if row.get("source_material") else [],
                "requires_personal_data": row.get("requires_personal_data", "false").lower() == "true",
                "metadata": {},
            }
            queries.append(query)
    return queries


def _map_ground_truth_to_predicted(gt_intent: str) -> str:
    """Map ground truth intent to predicted format."""
    mapping = {
        "general": "documents_only",
        "personal": "personal_only",
        "combined": "both_combined",
    }
    return mapping.get(gt_intent, gt_intent)


def find_latest_results_file(results_path: Path) -> Optional[Path]:
    """
    Find the most recent results file for a strategy.
    
    First checks for the non-timestamped file, then looks for the most recent
    timestamped file matching the pattern.
    
    Returns:
        Path to the most recent results file, or None if none found
    """
    # First, check if the non-timestamped file exists
    if results_path.exists():
        return results_path
    
    # Otherwise, look for timestamped files
    # Pattern: {strategy_name}_results_YYYYMMDD_HHMMSS.json
    strategy_name = results_path.stem.replace("_results", "")
    results_dir = results_path.parent
    pattern = f"{strategy_name}_results_*.json"
    
    timestamped_files = sorted(
        results_dir.glob(pattern),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )
    
    if timestamped_files:
        return timestamped_files[0]
    
    return None


def load_existing_results(results_path: Path) -> List[Dict[str, Any]]:
    """
    Load existing results from file if it exists.
    
    If the exact path doesn't exist, looks for the most recent timestamped
    results file for the same strategy.
    """
    # Try to find the most recent results file
    actual_path = find_latest_results_file(results_path)
    
    if actual_path is None:
        return []
    
    try:
        with open(actual_path, "r", encoding="utf-8") as f:
            results = json.load(f)
            # Log which file we're loading from
            if actual_path != results_path:
                logging.info(f"Loading existing results from {actual_path.name} (not {results_path.name})")
            return results
    except Exception as e:
        logging.warning(f"Failed to load existing results from {actual_path}: {e}")
        return []


def save_results(results: List[Dict[str, Any]], results_path: Path) -> Path:
    """
    Save results to a file with a datetime suffix.
    
    Returns:
        The actual path where results were saved (with datetime suffix)
    """
    from datetime import datetime
    
    # Add datetime suffix to filename: strategy_results_YYYYMMDD_HHMMSS.json
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = results_path.stem  # e.g., "intent_aware_results"
    suffix = results_path.suffix  # e.g., ".json"
    timestamped_path = results_path.parent / f"{stem}_{timestamp}{suffix}"
    
    timestamped_path.parent.mkdir(parents=True, exist_ok=True)
    with open(timestamped_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    return timestamped_path


def save_results_incremental(
    new_results: List[Dict[str, Any]], 
    results_path: Path, 
    existing_results: List[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Save results incrementally, appending to existing results."""
    if existing_results is None:
        existing_results = load_existing_results(results_path)
    
    all_results = existing_results + new_results
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    return all_results


# ============================================================================
# Strategy Execution
# ============================================================================

def run_strategy(
    strategy: ValidationStrategy,
    queries: List[Dict[str, Any]],
    user_id: int,
    session_id: Optional[str] = None,
    rate_limit: float = 0.0,
    results_path: Optional[Path] = None,
    max_workers: int = 4,
    compute_ragas: bool = False,
    resume: bool = False,
) -> List[Dict[str, Any]]:
    """
    Run a validation strategy on a set of queries.
    
    Args:
        compute_ragas: If True, compute RAGAS scores for newly generated results (all of them, matching --limit)
        resume: If True, resume from existing results (skip already processed queries). If False, start fresh.
    
    Returns list of result dicts with ground truth and predicted values.
    """
    results = []
    
    # Only load existing results if resuming
    if resume and results_path:
        existing_results = load_existing_results(results_path)
        # When using --limit, we need to check which of the limited queries have already been processed
        # Match by query_id to handle cases where --limit is used
        existing_query_ids = {r.get("query_id") for r in existing_results if r.get("query_id")}
        queries_to_process = [q for q in queries if q.get("query_id") not in existing_query_ids]
        
        if len(queries_to_process) < len(queries):
            skipped = len(queries) - len(queries_to_process)
            tqdm.write(f"Resuming {strategy.name}: {skipped} of {len(queries)} queries already processed, processing {len(queries_to_process)} new queries")
    else:
        # Fresh run - process all queries
        existing_results = []
        queries_to_process = queries
        # Check if there are existing results (timestamped or not) and warn
        if results_path:
            latest_file = find_latest_results_file(results_path)
            if latest_file:
                tqdm.write(f"Starting fresh run for {strategy.name} (existing results at {latest_file.name} will be ignored)")
    
    save_interval = 5
    last_saved_count = 0
    
    def process_query(q: Dict[str, Any], query_idx: int) -> Optional[Dict[str, Any]]:
        """Process a single query and return the result dict or None on error."""
        try:
            res_dict = strategy.execute_query(
                q["question"], 
                user_id=user_id, 
                session_id=session_id
            )
            
            # Add ground truth information
            gt_intent = q.get("ground_truth_intent")
            res_dict["ground_truth_intent"] = gt_intent
            res_dict["ground_truth_intent_mapped"] = _map_ground_truth_to_predicted(gt_intent) if gt_intent else None
            res_dict["ground_truth_chunks"] = q.get("ground_truth_chunks", [])
            res_dict["ground_truth_documents"] = q.get("ground_truth_documents", [])
            res_dict["requires_personal_data"] = q.get("requires_personal_data", False)
            
            # Extract predicted intent and probabilities
            res_dict["predicted_intent"] = strategy.extract_predicted_intent(res_dict)
            res_dict["class_probabilities"] = strategy.extract_class_probabilities(res_dict)
            
            return res_dict
        except Exception as e:
            tqdm.write(f"Error processing query {query_idx + 1}: {e}")
            return None
    
    # Global flag for interrupt handling
    interrupted = False
    
    def signal_handler(signum, frame):
        nonlocal interrupted
        interrupted = True
        tqdm.write("\n\n⚠️  Interrupt received. Saving progress and shutting down gracefully...")
    
    # Register signal handler
    original_handler = signal.signal(signal.SIGINT, signal_handler)
    
    # Early return if all queries already processed (only when resuming)
    if resume and len(queries_to_process) == 0:
        tqdm.write(f"All {len(queries)} queries already processed for {strategy.name}, skipping")
        # Return only results for the queries we loaded (matching --limit)
        query_ids_loaded = {q.get("query_id") for q in queries}
        return [r for r in existing_results if r.get("query_id") in query_ids_loaded]
    
    try:
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            futures = {
                executor.submit(process_query, q, i): (i, q) 
                for i, q in enumerate(queries_to_process)
            }
            
            with tqdm(total=len(queries_to_process), desc=f"{strategy.name} validation", unit="query", initial=0) as pbar:
                for future in as_completed(futures):
                    if interrupted:
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        break
                    
                    query_idx, q = futures[future]
                    try:
                        res_dict = future.result()
                        if res_dict:
                            # Add query_id to result for matching
                            res_dict["query_id"] = q.get("query_id")
                            results.append(res_dict)
                            pbar.update(1)
                            pbar.set_postfix({"completed": len(results), "total": len(queries_to_process)})
                            
                            # Incremental save (only when resuming - for fresh runs, we save at the end)
                            if resume and results_path and len(results) - last_saved_count >= save_interval:
                                new_results_to_save = results[last_saved_count:]
                                existing_results = save_results_incremental(new_results_to_save, results_path, existing_results)
                                last_saved_count = len(results)
                        
                        # Rate limiting
                        if rate_limit:
                            import time
                            time.sleep(rate_limit)
                    except Exception as e:
                        if not interrupted:
                            pbar.update(1)
                            tqdm.write(f"Error processing query {query_idx + 1}: {e}")
                        continue
        finally:
            # Shutdown executor gracefully
            executor.shutdown(wait=False, cancel_futures=True)
        
        # Save progress before exiting if interrupted
        if interrupted:
            if results_path and results:
                if resume:
                    new_results_to_save = results[last_saved_count:]
                    all_results = save_results_incremental(new_results_to_save, results_path, existing_results)
                    tqdm.write(f"✓ Saved {len(all_results)} results before exit")
                else:
                    save_results(results, results_path)
                    tqdm.write(f"✓ Saved {len(results)} results before exit")
            elif results:
                tqdm.write(f"✓ Processed {len(results)} results before exit")
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_handler)
        
        # Handle interrupt - raise after cleanup
        if interrupted:
            raise KeyboardInterrupt()
    
    # Compute RAGAS for newly generated results if requested
    # Only compute on the results we just generated (not existing ones)
    ragas_tokens_for_strategy = None
    if not interrupted and results and compute_ragas:
        tqdm.write(f"Computing RAGAS metrics for {len(results)} newly generated results...")
        # Reset RAGAS token tracker before evaluation
        from validation.metrics import get_ragas_token_usage
        _ = get_ragas_token_usage()  # Reset to 0
        
        # Evaluate all newly generated results (exactly the --limit number)
        results = add_ragas_scores_to_results(results, sample_size=None)
        
        # Capture RAGAS token usage for this strategy
        ragas_tokens_for_strategy = get_ragas_token_usage()
    
    # Attach RAGAS tokens to results metadata if available
    if ragas_tokens_for_strategy:
        for r in results:
            if "metadata" not in r:
                r["metadata"] = {}
            r["metadata"]["_ragas_tokens"] = ragas_tokens_for_strategy
    
    # Final save (only if not interrupted)
    if not interrupted:
        if results_path:
            if resume:
                # Resuming: append new results to existing
                new_results_to_save = results[last_saved_count:]
                all_results = save_results_incremental(new_results_to_save, results_path, existing_results)
                # Return only results for the queries we processed in this run (matching --limit)
                query_ids_processed = {q.get("query_id") for q in queries}
                returned_results = [r for r in all_results if r.get("query_id") in query_ids_processed]
                # Ensure RAGAS tokens are attached to returned results
                if ragas_tokens_for_strategy:
                    for r in returned_results:
                        if "metadata" not in r:
                            r["metadata"] = {}
                        r["metadata"]["_ragas_tokens"] = ragas_tokens_for_strategy
                return returned_results
            else:
                # Fresh run: save with datetime suffix
                saved_path = save_results(results, results_path)
                tqdm.write(f"✓ Saved results to {saved_path.name}")
                return results
        
        return results  # No results_path, just return what we generated
    else:
        # Return what we have if interrupted
        # Attach RAGAS tokens if available (even if interrupted, we might have some)
        if ragas_tokens_for_strategy:
            for r in results:
                if "metadata" not in r:
                    r["metadata"] = {}
                r["metadata"]["_ragas_tokens"] = ragas_tokens_for_strategy
        
        if results_path and results:
            if resume:
                # Resuming: append what we have
                new_results_to_save = results[last_saved_count:]
                all_results = save_results_incremental(new_results_to_save, results_path, existing_results)
                query_ids_processed = {q.get("query_id") for q in queries}
                returned_results = [r for r in all_results if r.get("query_id") in query_ids_processed]
                # Ensure RAGAS tokens are attached
                if ragas_tokens_for_strategy:
                    for r in returned_results:
                        if "metadata" not in r:
                            r["metadata"] = {}
                        r["metadata"]["_ragas_tokens"] = ragas_tokens_for_strategy
                return returned_results
            else:
                # Fresh run: save what we have so far with datetime suffix
                saved_path = save_results(results, results_path)
                tqdm.write(f"✓ Saved {len(results)} results to {saved_path.name} before exit")
                return results
        elif results:
            return results
        else:
            return []


# ============================================================================
# Metrics Computation
# ============================================================================

def compute_strategy_metrics(results: List[Dict[str, Any]], strategy_name: str) -> Dict[str, Any]:
    """Compute metrics for a single strategy."""
    metrics = {
        "strategy": strategy_name,
        "query_count": len(results),
    }
    
    # Intent metrics (if strategy predicts intent)
    try:
        intent_metrics = compute_intent_metrics(results)
        metrics["intent_metrics"] = intent_metrics
    except Exception as e:
        logging.warning(f"Failed to compute intent metrics: {e}")
        metrics["intent_metrics"] = None
    
    # Retrieval hit rate
    try:
        retrieval_metrics = compute_retrieval_hit_rate_at_k(results)
        metrics["retrieval_metrics"] = retrieval_metrics
    except Exception as e:
        logging.warning(f"Failed to compute retrieval metrics: {e}")
        metrics["retrieval_metrics"] = None
    
    # Latency
    try:
        latency_metrics = compute_latency_metrics(results)
        metrics["latency_metrics"] = latency_metrics
    except Exception as e:
        logging.warning(f"Failed to compute latency metrics: {e}")
        metrics["latency_metrics"] = None
    
    # RAGAS metrics (context relevance and response groundedness)
    try:
        ragas_metrics = compute_ragas_metrics(results)
        metrics["ragas_metrics"] = ragas_metrics
    except Exception as e:
        logging.warning(f"Failed to compute RAGAS metrics: {e}")
        metrics["ragas_metrics"] = None
    
    # Token usage metrics (grouped by model)
    try:
        # Aggregate token usage by model across all results
        token_usage_by_model = {}  # {model_name: {"input": int, "output": int, "total": int}}
        
        for result in results:
            result_token_usage = result.get("metadata", {}).get("token_usage_by_model", {})
            if result_token_usage:
                for model_name, usage in result_token_usage.items():
                    if model_name not in token_usage_by_model:
                        token_usage_by_model[model_name] = {"input": 0, "output": 0, "total": 0}
                    token_usage_by_model[model_name]["input"] += usage.get("input", 0)
                    token_usage_by_model[model_name]["output"] += usage.get("output", 0)
                    token_usage_by_model[model_name]["total"] += usage.get("input", 0) + usage.get("output", 0)
        
        # Add RAGAS token usage if available (captured per-strategy after evaluation)
        # RAGAS tokens are stored in the first result's metadata (they're the same for all results in a strategy)
        if results:
            first_result = results[0]
            ragas_tokens = first_result.get("metadata", {}).get("_ragas_tokens")
            if ragas_tokens and (ragas_tokens.get("input", 0) > 0 or ragas_tokens.get("output", 0) > 0):
                ragas_model = "anthropic/claude-haiku-4.5"
                if ragas_model not in token_usage_by_model:
                    token_usage_by_model[ragas_model] = {"input": 0, "output": 0, "total": 0}
                token_usage_by_model[ragas_model]["input"] += ragas_tokens.get("input", 0)
                token_usage_by_model[ragas_model]["output"] += ragas_tokens.get("output", 0)
                token_usage_by_model[ragas_model]["total"] += ragas_tokens.get("input", 0) + ragas_tokens.get("output", 0)
        
        if token_usage_by_model:
            # Calculate totals across all models
            total_input = sum(usage["input"] for usage in token_usage_by_model.values())
            total_output = sum(usage["output"] for usage in token_usage_by_model.values())
            total_tokens = sum(usage["total"] for usage in token_usage_by_model.values())
            
            metrics["token_metrics"] = {
                "by_model": token_usage_by_model,
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_tokens": total_tokens,
            }
        else:
            metrics["token_metrics"] = None
    except Exception as e:
        logging.warning(f"Failed to compute token metrics: {e}")
        metrics["token_metrics"] = None
    
    # Classification tool usage percentage (for agent_with_intent_tool strategy)
    if strategy_name == "agent_with_intent_tool":
        try:
            classification_tool_used_count = sum(
                1 for result in results
                if result.get("metadata", {}).get("classification_tool_used", False)
            )
            total_queries = len(results)
            classification_tool_usage_pct = (classification_tool_used_count / total_queries * 100) if total_queries > 0 else 0.0
            metrics["classification_tool_usage"] = {
                "count": classification_tool_used_count,
                "total": total_queries,
                "percentage": classification_tool_usage_pct,
            }
        except Exception as e:
            logging.warning(f"Failed to compute classification tool usage: {e}")
            metrics["classification_tool_usage"] = None
    else:
        metrics["classification_tool_usage"] = None
    
    return metrics


def save_metrics_summary(all_metrics: Dict[str, Dict[str, Any]], output_path: Path):
    """Save metrics summary comparing multiple strategies."""
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
            try:
                if hasattr(obj, 'item'):
                    return obj.item()
            except (AttributeError, ValueError):
                pass
            return super().default(obj)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2, ensure_ascii=False, cls=NumpyJSONEncoder)
    tqdm.write(f"✓ Metrics summary saved to {output_path}")


def save_summary_table_csv(
    all_results: Dict[str, List[Dict[str, Any]]],
    all_metrics: Dict[str, Dict[str, Any]],
    output_path: Path
):
    """
    Save a summary table as CSV with metrics for each strategy.
    
    Table includes:
    - Sample size (N)
    - Latency: p90, p95 (in seconds)
    - Hit Rate: Hit@3, Hit@5 (as percentages)
    - Quality: Context Rel., Response Grd. (0-1 scores)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Strategy name mapping for display
    strategy_display_names = {
        "llm_classifier": "LLM Classifier",
        "always_both": "Always-Both",
        "agent_discretion": "Agent-Disc",
        "heuristic_classifier": "Heuristic",
        "agent_with_intent_tool": "Agent-Intent-Tool",
        "supervised_classifier": "Supervised",
        "embedding_router": "Embedding-Router",
    }
    
    rows = []
    
    # Header row
    rows.append([
        "Metric",
        *[strategy_display_names.get(name, name.replace("_", "-").title()) for name in all_results.keys()]
    ])
    
    # Sample size row
    sample_sizes = [len(results) for results in all_results.values()]
    rows.append(["N"] + [str(n) for n in sample_sizes])
    
    # Latency section
    rows.append([])  # Empty row for spacing
    rows.append(["Latency (s, lower is better)"])
    
    # p90 latency
    p90_values = []
    for strategy_name in all_results.keys():
        latency_metrics = all_metrics.get(strategy_name, {}).get("latency_metrics", {})
        p90_ms = latency_metrics.get("p90_ms")
        if p90_ms is not None:
            p90_values.append(f"{p90_ms / 1000:.1f}")  # Convert ms to seconds
        else:
            p90_values.append("")
    rows.append(["p90"] + p90_values)
    
    # p95 latency
    p95_values = []
    for strategy_name in all_results.keys():
        latency_metrics = all_metrics.get(strategy_name, {}).get("latency_metrics", {})
        p95_ms = latency_metrics.get("p95_ms")
        if p95_ms is not None:
            p95_values.append(f"{p95_ms / 1000:.1f}")  # Convert ms to seconds
        else:
            p95_values.append("")
    rows.append(["p95"] + p95_values)
    
    # Hit Rate section
    rows.append([])  # Empty row for spacing
    rows.append(["Hit Rate (%, higher is better)"])
    
    # Hit@3
    hit3_values = []
    for strategy_name in all_results.keys():
        retrieval_metrics = all_metrics.get(strategy_name, {}).get("retrieval_metrics", {})
        hit3 = retrieval_metrics.get("retrieval_hit_rate@3")
        if hit3 is not None:
            hit3_values.append(f"{hit3 * 100:.1f}")  # Convert to percentage
        else:
            hit3_values.append("")
    rows.append(["Hit@3"] + hit3_values)
    
    # Hit@5
    hit5_values = []
    for strategy_name in all_results.keys():
        retrieval_metrics = all_metrics.get(strategy_name, {}).get("retrieval_metrics", {})
        hit5 = retrieval_metrics.get("retrieval_hit_rate@5")
        if hit5 is not None:
            hit5_values.append(f"{hit5 * 100:.1f}")  # Convert to percentage
        else:
            hit5_values.append("")
    rows.append(["Hit@5"] + hit5_values)
    
    # Quality section
    rows.append([])  # Empty row for spacing
    rows.append(["Quality (0-1, higher is better)"])
    
    # Context Relevance
    context_rel_values = []
    for strategy_name, results in all_results.items():
        # Compute mean of ragas_context_relevance from results
        relevance_scores = [
            r.get("ragas_context_relevance")
            for r in results
            if r.get("ragas_context_relevance") is not None
        ]
        if relevance_scores:
            mean_relevance = sum(relevance_scores) / len(relevance_scores)
            context_rel_values.append(f"{mean_relevance:.3f}")
        else:
            context_rel_values.append("")
    rows.append(["Context Rel."] + context_rel_values)
    
    # Response Groundedness
    response_grd_values = []
    for strategy_name, results in all_results.items():
        # Compute mean of ragas_response_groundedness from results
        groundedness_scores = [
            r.get("ragas_response_groundedness")
            for r in results
            if r.get("ragas_response_groundedness") is not None
        ]
        if groundedness_scores:
            mean_groundedness = sum(groundedness_scores) / len(groundedness_scores)
            response_grd_values.append(f"{mean_groundedness:.3f}")
        else:
            response_grd_values.append("")
    rows.append(["Response Grd."] + response_grd_values)
    
    # Token usage section
    rows.append([])  # Empty row for spacing
    rows.append(["Token Usage"])
    
    # Model pricing (per million tokens)
    PRICING = {
        "openai/gpt-4o": {"input": 2.50, "output": 10.0},
        "openai/gpt-oss-120b": {"input": 0.02, "output": 0.10},
        "anthropic/claude-haiku-4.5": {"input": 1.0, "output": 5.0},
    }
    
    def calculate_cost(token_metrics):
        """Calculate total cost from token metrics."""
        if not token_metrics:
            return 0.0
        
        total_cost = 0.0
        by_model = token_metrics.get("by_model", {})
        
        for model_name, usage in by_model.items():
            # Try exact match first
            pricing = PRICING.get(model_name)
            if not pricing:
                # Try partial match (e.g., "gpt-oss-120b" -> "openai/gpt-oss-120b")
                for key, price in PRICING.items():
                    if model_name in key or key.split("/")[-1] in model_name:
                        pricing = price
                        break
            
            if pricing:
                input_tokens = usage.get("input", 0)
                output_tokens = usage.get("output", 0)
                input_cost = (input_tokens / 1_000_000.0) * pricing["input"]
                output_cost = (output_tokens / 1_000_000.0) * pricing["output"]
                total_cost += input_cost + output_cost
        
        return total_cost
    
    # Total Input Tokens
    input_token_values = []
    for strategy_name in all_results.keys():
        token_metrics = all_metrics.get(strategy_name, {}).get("token_metrics")
        if token_metrics:
            total_input = token_metrics.get("total_input_tokens")
            if total_input is not None and total_input > 0:
                input_token_values.append(str(int(total_input)))
            else:
                input_token_values.append("")
        else:
            input_token_values.append("")
    rows.append(["Total Input Tokens"] + input_token_values)
    
    # Total Output Tokens
    output_token_values = []
    for strategy_name in all_results.keys():
        token_metrics = all_metrics.get(strategy_name, {}).get("token_metrics")
        if token_metrics:
            total_output = token_metrics.get("total_output_tokens")
            if total_output is not None and total_output > 0:
                output_token_values.append(str(int(total_output)))
            else:
                output_token_values.append("")
        else:
            output_token_values.append("")
    rows.append(["Total Output Tokens"] + output_token_values)
    
    # Total Tokens
    total_token_values = []
    for strategy_name in all_results.keys():
        token_metrics = all_metrics.get(strategy_name, {}).get("token_metrics")
        if token_metrics:
            total_tokens = token_metrics.get("total_tokens")
            if total_tokens is not None and total_tokens > 0:
                total_token_values.append(str(int(total_tokens)))
            else:
                total_token_values.append("")
        else:
            total_token_values.append("")
    rows.append(["Total Tokens"] + total_token_values)
    
    # Cost section
    rows.append([])  # Empty row for spacing
    rows.append(["Cost (USD)"])
    
    # Total cost per strategy
    cost_values = []
    for strategy_name in all_results.keys():
        token_metrics = all_metrics.get(strategy_name, {}).get("token_metrics")
        cost = calculate_cost(token_metrics)
        if cost > 0:
            cost_values.append(f"${cost:.4f}")
        else:
            cost_values.append("")
    rows.append(["Total Cost"] + cost_values)
    
    # Cost breakdown by model (if available)
    # Get all unique models across strategies
    all_models = set()
    for strategy_name in all_results.keys():
        token_metrics = all_metrics.get(strategy_name, {}).get("token_metrics")
        if token_metrics and token_metrics.get("by_model"):
            all_models.update(token_metrics["by_model"].keys())
    
    # Add cost per model
    for model_name in sorted(all_models):
        model_cost_values = []
        for strategy_name in all_results.keys():
            token_metrics = all_metrics.get(strategy_name, {}).get("token_metrics")
            if token_metrics and token_metrics.get("by_model"):
                usage = token_metrics["by_model"].get(model_name, {})
                if usage:
                    # Get pricing
                    pricing = PRICING.get(model_name)
                    if not pricing:
                        for key, price in PRICING.items():
                            if model_name in key or key.split("/")[-1] in model_name:
                                pricing = price
                                break
                    
                    if pricing:
                        input_tokens = usage.get("input", 0)
                        output_tokens = usage.get("output", 0)
                        input_cost = (input_tokens / 1_000_000.0) * pricing["input"]
                        output_cost = (output_tokens / 1_000_000.0) * pricing["output"]
                        model_cost = input_cost + output_cost
                        if model_cost > 0:
                            model_cost_values.append(f"${model_cost:.4f}")
                        else:
                            model_cost_values.append("")
                    else:
                        model_cost_values.append("")
                else:
                    model_cost_values.append("")
            else:
                model_cost_values.append("")
        
        # Only add row if at least one strategy has this model
        if any(v for v in model_cost_values):
            display_name = model_name.split("/")[-1] if "/" in model_name else model_name
            rows.append([f"Cost ({display_name})"] + model_cost_values)
    
    # Classification tool usage percentage (for agent_with_intent_tool)
    rows.append([])  # Empty row for spacing
    rows.append(["Agent Strategy Metrics"])
    classification_tool_values = []
    for strategy_name in all_results.keys():
        if strategy_name == "agent_with_intent_tool":
            tool_usage = all_metrics.get(strategy_name, {}).get("classification_tool_usage")
            if tool_usage and tool_usage.get("total", 0) > 0:
                pct = tool_usage.get("percentage", 0.0)
                count = tool_usage.get("count", 0)
                total = tool_usage.get("total", 0)
                classification_tool_values.append(f"{pct:.1f}% ({count}/{total})")
            else:
                classification_tool_values.append("")
        else:
            classification_tool_values.append("")
    rows.append(["Intent Tool Usage %"] + classification_tool_values)
    
    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    
    tqdm.write(f"✓ Summary table saved to {output_path}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run flexible strategy-based validation for RAG system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all default strategies (fresh run, ignores existing results)
  python3 validation/run_strategy_validation.py --email test@test.com
  
  # Resume from existing results (skip already processed queries)
  python3 validation/run_strategy_validation.py --resume --email test@test.com
  
  # Run a single strategy
  python3 validation/run_strategy_validation.py --strategy heuristic_classifier --email test@test.com
  
  # Run multiple strategies and compare
  python3 validation/run_strategy_validation.py --strategy llm_classifier --strategy heuristic_classifier --email test@test.com
  
  # Use CSV questions
  python3 validation/run_strategy_validation.py --queries-file validation/queries/questions_ground_truth.csv --email test@test.com
  
  # Recompute metrics from existing results
  python3 validation/run_strategy_validation.py --recompute-metrics-only --email test@test.com
        """
    )
    parser.add_argument("--strategy", action="append", default=None, help="Strategy name(s) to run (can specify multiple). If not specified, runs all 7 default strategies: llm_classifier, always_both, agent_discretion, heuristic_classifier, agent_with_intent_tool, supervised_classifier, embedding_router")
    parser.add_argument("--email", default="validation-test@test.com", help="Test user email (default: validation-test@test.com)")
    parser.add_argument("--session-id", help="Optional session id")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of queries")
    parser.add_argument("--rate-limit", type=float, default=0.0, help="Seconds to sleep between queries")
    parser.add_argument("--max-workers", type=int, default=4, help="Number of parallel workers (default: 4)")
    parser.add_argument("--queries-file", type=str, default=None, help="Path to queries file (JSON or CSV)")
    parser.add_argument("--skip-ragas", action="store_true", help="Skip RAGAS evaluation")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for results (default: validation/results)")
    parser.add_argument("--recompute-metrics-only", action="store_true", help="Only recompute metrics from existing results, skip running validation")
    parser.add_argument("--resume", action="store_true", help="Resume from existing results (skip already processed queries). By default, starts fresh and ignores existing results.")
    args = parser.parse_args()
    
    # Ensure config is loaded (this happens via imports, but verify we have required values)
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not found. Set it in config.yaml or as environment variable.")
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not found. Set it in config.yaml or as environment variable.")
    
    # Set default strategies if none specified (all 7 strategies)
    if args.strategy is None:
        args.strategy = [
            "llm_classifier",
            "always_both", 
            "agent_discretion",
            "heuristic_classifier",
            "agent_with_intent_tool",
            "supervised_classifier",
            "embedding_router"
        ]
    
    # Set up output directory
    output_dir = Path(args.output_dir) if args.output_dir else RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if args.recompute_metrics_only:
        # Just load existing results and recompute metrics
        tqdm.write("Recomputing metrics from existing results...")
        all_results = {}
        for strategy_name in args.strategy:
            results_path = output_dir / f"{strategy_name}_results.json"
            if results_path.exists():
                results = load_existing_results(results_path)
                all_results[strategy_name] = results
                tqdm.write(f"Loaded {len(results)} results for {strategy_name}")
            else:
                tqdm.write(f"Warning: No results found for {strategy_name} at {results_path}")
        
        if not all_results:
            tqdm.write("ERROR: No existing results found. Run validation first.")
            return
    else:
        # Normal validation run
        # Load queries
        queries_path = Path(args.queries_file) if args.queries_file else None
        queries = load_queries(limit=args.limit, queries_file=queries_path)
        tqdm.write(f"Loaded {len(queries)} queries")
        
        # Check for test data (user + hives/inspections)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == args.email.lower().strip()).first()
            if not user:
                raise ValueError(
                    f"User {args.email} not found. Create test data first:\n"
                    f"  python3 validation/seed_validation_data.py --email {args.email} --password <password>"
                )
            
            # Check for hives and inspections (use raw SQL to avoid schema mismatches)
            hive_count = db.execute(
                text("SELECT COUNT(*) FROM hives WHERE user_id = :user_id"),
                {"user_id": user.id}
            ).scalar()
            inspection_count = db.execute(
                text("""
                    SELECT COUNT(*) FROM inspections 
                    JOIN hives ON hives.id = inspections.hive_id 
                    WHERE hives.user_id = :user_id
                """),
                {"user_id": user.id}
            ).scalar()
            
            if hive_count == 0:
                raise ValueError(
                    f"User {args.email} has no hives. Create test data first:\n"
                    f"  python3 validation/seed_validation_data.py --email {args.email} --password <password>"
                )
            
            if inspection_count == 0:
                raise ValueError(
                    f"User {args.email} has no inspections. Create test data first:\n"
                    f"  python3 validation/seed_validation_data.py --email {args.email} --password <password>"
                )
            
            tqdm.write(f"Using user id {user.id} ({hive_count} hives, {inspection_count} inspections)")
        finally:
            db.close()
        
        # Run each strategy
        all_results = {}
        
        for strategy_name in args.strategy:
            strategy = get_strategy(strategy_name)
            results_path = output_dir / f"{strategy_name}_results.json"
            
            tqdm.write(f"\n{'='*60}")
            tqdm.write(f"Running strategy: {strategy_name}")
            tqdm.write(f"{'='*60}")
            
            results = run_strategy(
                strategy=strategy,
                queries=queries,
                user_id=user.id,
                session_id=args.session_id,
                rate_limit=args.rate_limit,
                results_path=results_path,
                max_workers=args.max_workers,
                compute_ragas=not args.skip_ragas,
                resume=args.resume,
            )
            
            all_results[strategy_name] = results
            
            # Re-save with RAGAS scores if they were computed (only for fresh runs)
            # For resume runs, RAGAS scores are already saved incrementally
            if not args.skip_ragas and results_path and not args.resume:
                # Re-save with updated RAGAS scores using the same timestamped filename
                # Find the most recent timestamped file for this strategy
                strategy_prefix = f"{strategy_name}_results_"
                timestamped_files = sorted(
                    [f for f in results_path.parent.glob(f"{strategy_prefix}*.json")],
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                if timestamped_files:
                    # Update the most recent file with RAGAS scores
                    with open(timestamped_files[0], "w", encoding="utf-8") as f:
                        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Compute metrics for all strategies
    all_metrics = {}
    for strategy_name, results in all_results.items():
        tqdm.write(f"Computing metrics for {strategy_name}...")
        metrics = compute_strategy_metrics(results, strategy_name)
        all_metrics[strategy_name] = metrics
    
    # Save metrics summary
    metrics_path = output_dir / "strategy_metrics_summary.json"
    save_metrics_summary(all_metrics, metrics_path)
    
    # Save summary table as CSV
    summary_table_path = output_dir / "summary_table.csv"
    save_summary_table_csv(all_results, all_metrics, summary_table_path)
    
    # Also save in the old format for compatibility (if running default strategies)
    if set(args.strategy) == {"llm_classifier", "always_both"} or set(args.strategy) == {"llm_classifier", "always_both", "agent_discretion"}:
        # Save in old format for backward compatibility
        legacy_metrics_path = output_dir / "metrics_summary.json"
        save_metrics_summary(all_metrics, legacy_metrics_path)
    
    tqdm.write(f"\n{'='*60}")
    tqdm.write("Validation complete!")
    tqdm.write(f"{'='*60}")
    tqdm.write(f"Results saved to: {output_dir}")
    for strategy_name in args.strategy:
        tqdm.write(f"  - {strategy_name}: {output_dir / f'{strategy_name}_results.json'}")
    tqdm.write(f"  - Metrics: {metrics_path}")
    tqdm.write(f"  - Summary Table: {summary_table_path}")


if __name__ == "__main__":
    main()

