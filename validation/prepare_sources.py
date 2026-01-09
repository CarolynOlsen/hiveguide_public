#!/usr/bin/env python3
"""
Source prep for validation:
- Downloads PDFs from source URLs directly into backend/rag/sources/
- Checks embeddings in DB; only re-embeds if missing/incomplete
"""

import os
import sys
from pathlib import Path
from typing import Dict

import subprocess
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Paths
BACKEND_SOURCES = Path(__file__).resolve().parent.parent / "backend" / "rag" / "sources"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Minimal config replication
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    cfg_path = PROJECT_ROOT / "config.yaml"
    cfg = {}
    if cfg_path.exists():
        try:
            import yaml

            cfg = yaml.safe_load(open(cfg_path)) or {}
        except Exception:
            cfg = {}
    DATABASE_URL = cfg.get("database_url")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set and not found in config.yaml")

# Source list (copied from backend/rag/config.py)
PDF_SOURCES: Dict[str, Dict[str, str]] = {
    "hbhc_varroa.pdf": {
        "title": "Tools for Varroa Management",
        "organization": "Honey Bee Health Coalition",
        "year": 2022,
        "url": "https://honeybeehealthcoalition.org/wp-content/uploads/2022/08/HBHC-Guide_Varroa-Mgmt_8thEd-082422.pdf",
    },
    "vce_varroa_management.pdf": {
        "title": "Varroa Mite Management Methods",
        "organization": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University",
        "year": 2025,
        "url": "https://www.pubs.ext.vt.edu/content/dam/pubs_ext_vt_edu/ENTO/ento-333/ENTO-333.pdf",
    },
    "vce_varroa_sampling.pdf": {
        "title": "Varroa Mite Sampling Methods",
        "organization": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University",
        "year": 2025,
        "url": "https://www.pubs.ext.vt.edu/content/dam/pubs_ext_vt_edu/ENTO/ento-332/ENTO-332.pdf",
    },
    "vce_varroa_biology.pdf": {
        "title": "Varroa Mite Biology and Feeding Damage",
        "organization": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University",
        "year": 2025,
        "url": "https://www.pubs.ext.vt.edu/content/dam/pubs_ext_vt_edu/ENTO/ento-331/ENTO-331.pdf",
    },
    "vce_small_hive_beetle.pdf": {
        "title": "Small Hive Beetle",
        "organization": "Virginia Cooperative Extension, Virginia Tech, and Virginia State University",
        "year": 2025,
        "url": "https://www.pubs.ext.vt.edu/content/dam/pubs_ext_vt_edu/ENTO/ento-338/ENTO-338.pdf",
    },
    "maine_fall_management.pdf": {
        "title": "Fall Management",
        "organization": "Maine Department of Agriculture",
        "year": 2020,
        "url": "https://www.maine.gov/dacf/php/apiary/documents/factsheets/fall-management.pdf",
    },
    "midwest_beekeeping_year.pdf": {
        "title": "Midwest Beekeeping in a Year",
        "organization": "Center for Rural Affairs",
        "year": 2021,
        "url": "https://www.cfra.org/sites/default/files/publications/Beekeeping%20Year%20-%20tabloid%20size25ENG.pdf",
    },
}


def validate_pdf(file_path: Path) -> bool:
    if not file_path.exists():
        return False
    if file_path.stat().st_size < 1024:
        return False
    try:
        with open(file_path, "rb") as f:
            return f.read(5) == b"%PDF-"
    except Exception:
        return False


def download_pdf(url: str, output_path: Path, timeout: int = 60) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "curl",
            "-L",
            "-o",
            str(output_path),
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            str(timeout),
            "--user-agent",
            "Mozilla/5.0 (compatible; HiveGuide/1.0)",
            url,
        ]
    )
    if result.returncode != 0:
        if output_path.exists():
            output_path.unlink()
        return False
    if not validate_pdf(output_path):
        if output_path.exists():
            output_path.unlink()
        return False
    return True


def ensure_sources_local():
    missing = []
    for fname, meta in PDF_SOURCES.items():
        dest = BACKEND_SOURCES / fname
        if dest.exists() and validate_pdf(dest):
            continue
        url = meta["url"]
        # Skip ResearchGate automatic download
        if "researchgate.net" in url.lower():
            print(f"[warn] Manual download required for {fname}: {url}")
            continue
        ok = download_pdf(url, dest)
        if not ok:
            missing.append(fname)
            print(f"[warn] failed to download {fname} from {url}")
    if missing:
        raise RuntimeError(f"Missing sources (manual download required?): {missing}")


def get_embedding_counts():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        total = session.execute(text("SELECT count(*) FROM document_chunks")).scalar() or 0
        embedded = (
            session.execute(
                text(
                    "SELECT count(*) FROM document_chunks "
                    "WHERE embedding_vector IS NOT NULL"
                )
            ).scalar()
            or 0
        )
        return total, embedded
    finally:
        session.close()


def ensure_embeddings():
    total, embedded = get_embedding_counts()
    if total > 0 and embedded == total:
        print(f"Embeddings already present: {embedded}/{total}")
        return
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY required to generate embeddings.")

    from validation.services.rag_service import get_validation_rag_service as get_langchain_service

    print(f"Embeddings missing or incomplete ({embedded}/{total}); generating...")
    service = get_langchain_service()
    service.process_pdfs(BACKEND_SOURCES)
    service.generate_embeddings_for_existing_chunks()
    total2, embedded2 = get_embedding_counts()
    print(f"Embedding generation complete: {embedded2}/{total2}")


def main():
    print("==> Ensuring validation sources")
    ensure_sources_local()
    print("==> Ensuring embeddings")
    ensure_embeddings()
    print("Sources and embeddings are ready.")


if __name__ == "__main__":
    main()

