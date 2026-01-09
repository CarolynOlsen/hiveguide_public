"""
RAG System Configuration Module
Handles database connections and API configurations for the RAG bot
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any

# Get the project root directory (backend/rag -> backend -> root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.yaml"
SOURCES_DIR = PROJECT_ROOT / "rag" / "sources"

def load_config() -> Dict[str, Any]:
    """Load configuration from config.yaml if it exists, otherwise return empty dict"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return yaml.safe_load(f)
        else:
            # In production, config.yaml might not exist - use environment variables instead
            return {}
    except (FileNotFoundError, PermissionError):
        # Handle case where config file doesn't exist or can't be read
        return {}

# Load configuration (might be empty in production)
config = load_config()

# Database configuration: prefer environment variable, fallback to config.yaml
DATABASE_URL = os.environ.get('DATABASE_URL') or config.get('database_url')
# Fallback to local Postgres if no DATABASE_URL provided
if not DATABASE_URL:
    DATABASE_URL = 'postgresql://postgres@localhost:5432/postgres'

# API Keys: prefer environment variables, fallback to config.yaml
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or config.get('openai_api_key')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY') or config.get('openrouter_api_key')

# RAG-specific settings
RAG_CONFIG = {
    'chunk_size_tokens': 600,
    'chunk_overlap_tokens': 100,
    'embedding_model': 'text-embedding-3-large',
    'embedding_dimensions': 3072,
    'similarity_threshold': 0.7,
    'min_similarity_for_display': 0.5,  # Minimum similarity to show source to user
    'max_sources_display': 5,  # Maximum number of sources to display
    'top_k_chunks': 10,
    'batch_size': 8,
    'batch_sleep_seconds': 0.5,
    'max_retries': 3,
    'inspection_history_days': 365,  # Default number of days of inspection history to retrieve for chatbot
    'llm_model': 'openai/gpt-oss-120b',  # OpenRouter LLM model ID for chatbot
}

# PDF Sources metadata
PDF_SOURCES = {
    # Active sources - all licensed for commercial use
    # Note: USDA PDF is scanned/image-based and requires OCR to extract text
    # "usda_beekeeping.pdf": {
    #     "title": "Beekeeping in the United States",
    #     "organization": "USDA",
    #     "year": 1980,
    #     "url": "https://www.ars.usda.gov/ARSUserFiles/60500500/PDFFiles/1-100/015-USDA-%20Beekeeping%20in%20the.pdf",
    #     "license": "Public Domain (US federal government)",
    #     "attribution": "United States Department of Agriculture (USDA)"
    # },
    "hbhc_varroa.pdf": {
        "title": "Tools for Varroa Management",
        "organization": "Honey Bee Health Coalition",
        "year": 2022,
        "url": "https://honeybeehealthcoalition.org/wp-content/uploads/2022/08/HBHC-Guide_Varroa-Mgmt_8thEd-082422.pdf",
        "license": "Written permission granted for commercial use",
        "attribution": "Honey Bee Health Coalition"
    },
    "vce_varroa_management.pdf": {
        "title": "Varroa Mite Management Methods",
        "organization": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University",
        "year": 2025,
        "url": "https://www.pubs.ext.vt.edu/content/dam/pubs_ext_vt_edu/ENTO/ento-333/ENTO-333.pdf",
        "license": "Open for public use with attribution",
        "attribution": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University"
    },
    "vce_varroa_sampling.pdf": {
        "title": "Varroa Mite Sampling Methods",
        "organization": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University",
        "year": 2025,
        "url": "https://www.pubs.ext.vt.edu/content/dam/pubs_ext_vt_edu/ENTO/ento-332/ENTO-332.pdf",
        "license": "Open for public use with attribution",
        "attribution": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University"
    },
    "vce_varroa_biology.pdf": {
        "title": "Varroa Mite Biology and Feeding Damage",
        "organization": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University",
        "year": 2025,
        "url": "https://www.pubs.ext.vt.edu/content/dam/pubs_ext_vt_edu/ENTO/ento-331/ENTO-331.pdf",
        "license": "Open for public use with attribution",
        "attribution": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University"
    },
    "vce_small_hive_beetle.pdf": {
        "title": "Small Hive Beetle",
        "organization": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University",
        "year": 2025,
        "url": "https://www.pubs.ext.vt.edu/content/dam/pubs_ext_vt_edu/ENTO/ento-338/ENTO-338.pdf",
        "license": "Open for public use with attribution",
        "attribution": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University"
    },
    "beekeepers_handbook_rudrappa.pdf": {
        "title": "The Beekeeper's Handbook: A Comprehensive Guide to Apiculture",
        "organization": "Independent Research",
        "year": 2023,
        "url": "https://www.researchgate.net/profile/Kirankumar-Rudrappa-2/publication/377160013_The_Beekeeper's_Handbook_A_Comprehensive_Guide_to_Apiculture/links/65a239bac77ed940477386a6/The-Beekeepers-Handbook-A-Comprehensive-Guide-to-Apiculture.pdf",
        "license": "Creative Commons Attribution (CC-BY)",
        "attribution": "Rudrappa, Kirankumar"
    },
    "maine_fall_management.pdf": {
        "title": "Fall Management",
        "organization": "Maine Department of Agriculture",
        "year": 2020,
        "url": "https://www.maine.gov/dacf/php/apiary/documents/factsheets/fall-management.pdf",
        "license": "Public Domain (Government document)",
        "attribution": "Jennifer Lund, Maine State Apiarist, Maine Department of Agriculture"
    },
    "midwest_beekeeping_year.pdf": {
        "title": "Midwest Beekeeping in a Year",
        "organization": "Center for Rural Affairs",
        "year": 2021,
        "url": "https://www.cfra.org/sites/default/files/publications/Beekeeping%20Year%20-%20tabloid%20size25ENG.pdf",
        "license": "Creative Commons Attribution 4.0 International License",
        "attribution": "Center for Rural Affairs"
    },
    
    # Archived sources - not used due to licensing restrictions
    # "fao_good_beekeeping.pdf": {
    #     "title": "Good Beekeeping Practices for Sustainable Apiculture",
    #     "organization": "Food and Agriculture Organization of the United Nations",
    #     "year": 2021,
    #     "url": "https://openknowledge.fao.org/server/api/core/bitstreams/285dd834-945f-4964-8b7d-d2a4c5aab293/content",
    #     "license": "Open Access (non-commercial use only)",
    #     "attribution": "Food and Agriculture Organization of the United Nations (FAO)"
    # },
    # "purdue_beekeeping.pdf": {
    #     "title": "Learning About Beekeeping",
    #     "organization": "Purdue Extension 4-H Program",
    #     "year": 2022,
    #     "url": "https://www.extension.purdue.edu/extmedia/4H/4-H-1057-W.pdf",
    #     "license": "Educational use only",
    #     "attribution": "Purdue Extension 4-H Program"
    # },
    # "purdue_advanced.pdf": {
    #     "title": "Advanced Beekeeping",
    #     "organization": "Purdue Extension 4-H Program",
    #     "year": 2022,
    #     "url": "https://www.extension.purdue.edu/extmedia/4H/4-H-1059-W.pdf",
    #     "license": "Educational use only",
    #     "attribution": "Purdue Extension 4-H Program"
    # },
    # "usu_calendar.pdf": {
    #     "title": "Beekeeping Monthly Calendar",
    #     "organization": "Utah State University Extension",
    #     "year": 2019,
    #     "url": "https://digitalcommons.usu.edu/cgi/viewcontent.cgi?article=2986&context=extension_curall",
    #     "license": "Educational/non-commercial use",
    #     "attribution": "Utah State University Extension"
    # }
}

def get_database_connection_string() -> str:
    """Get the database connection string"""
    return DATABASE_URL

def ensure_sources_directory():
    """Ensure the sources directory exists"""
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    return SOURCES_DIR
