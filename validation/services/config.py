"""
Validation-specific configuration.
Copied from backend/rag/config.py so we can modify it independently.
"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any

# Get the project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"

def load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml if it exists."""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return yaml.safe_load(f)
        return {}
    except Exception:
        return {}

config = load_config()

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL') or config.get('database_url')

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or config.get('openai_api_key')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY') or config.get('openrouter_api_key')

# RAG-specific settings (can be modified for validation)
RAG_CONFIG = {
    'chunk_size_tokens': 600,
    'chunk_overlap_tokens': 100,
    'embedding_model': 'text-embedding-3-large',
    'embedding_dimensions': 3072,
    'similarity_threshold': 0.7,
    'min_similarity_for_display': 0.5,
    'max_sources_display': 5,
    'top_k_chunks': 10,
    'batch_size': 8,
    'batch_sleep_seconds': 0.5,
    'max_retries': 3,
    'inspection_history_days': 365,
    'llm_model': 'openai/gpt-oss-120b',
    'intent_classification_model': 'openai/gpt-4o',  # Model for intent classification
}

