import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

# Use validation service for validation runs (fully self-contained)
from validation.services.rag_service import get_validation_rag_service as get_langchain_service

# Suppress verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("openai._client").setLevel(logging.WARNING)
logging.getLogger("stainless").setLevel(logging.WARNING)
logging.getLogger("stainless._client").setLevel(logging.WARNING)


@dataclass
class RAGQueryResult:
    question: str
    answer: str
    sources: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def execute_query(
    question: str,
    user_id: int,
    session_id: Optional[str] = None,
) -> RAGQueryResult:
    """Execute a single query against the RAG system and capture latency and metadata."""
    service = get_langchain_service()
    start = time.perf_counter()
    result = service.query_with_user_tools(
        question=question,
        user_id=user_id,
        session_id=session_id,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    return RAGQueryResult(
        question=question,
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        metadata=result.get("metadata", {}),
        latency_ms=latency_ms,
    )


def execute_batch(
    questions: List[str],
    user_id: int,
    session_id: Optional[str] = None,
    rate_limit_s: float = 0.0,
) -> List[RAGQueryResult]:
    """Execute a batch of questions with optional rate limiting."""
    results: List[RAGQueryResult] = []
    for q in questions:
        results.append(execute_query(q, user_id=user_id, session_id=session_id))
        if rate_limit_s:
            time.sleep(rate_limit_s)
    return results

