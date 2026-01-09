#!/usr/bin/env python3
"""
LangChain-based embedding population script.
Replaces the old DIY RAG approach with LangChain PDF processing and embedding generation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.langchain_service import get_langchain_service
from rag.config import SOURCES_DIR, DATABASE_URL
from rag.models import DocumentChunk
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def clear_existing_embeddings():
    """Clear all existing embeddings from the database."""
    print("🗑️  Clearing existing embeddings...")
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        # Delete all existing chunks
        deleted_count = session.query(DocumentChunk).count()
        session.query(DocumentChunk).delete()
        session.commit()
        print(f"   Deleted {deleted_count} existing chunks")
    finally:
        session.close()

def populate_embeddings_with_langchain():
    """Populate embeddings using the new LangChain service."""
    print("🦜 Starting LangChain-based embedding population...")
    
    # Get the LangChain service
    service = get_langchain_service()
    
    # Process PDFs from sources directory
    sources_path = Path(SOURCES_DIR)
    if not sources_path.exists():
        print(f"❌ Sources directory not found: {sources_path}")
        return False
    
    pdf_files = list(sources_path.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ No PDF files found in {sources_path}")
        return False
    
    print(f"📁 Found {len(pdf_files)} PDF files to process")
    
    # Process PDFs using LangChain
    try:
        service.process_pdfs(sources_path)
        print("✅ PDF processing completed successfully")
        return True
    except Exception as e:
        print(f"❌ Error during PDF processing: {e}")
        return False

def verify_embeddings():
    """Verify that embeddings were created successfully."""
    print("🔍 Verifying embeddings...")
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    try:
        total_chunks = session.query(DocumentChunk).count()
        embedded_chunks = session.query(DocumentChunk).filter(
            DocumentChunk.embedding_vector.isnot(None)
        ).count()
        
        print(f"   Total chunks: {total_chunks}")
        print(f"   Chunks with embeddings: {embedded_chunks}")
        
        if total_chunks > 0 and embedded_chunks == total_chunks:
            print("✅ All chunks have embeddings")
            return True
        else:
            print(f"❌ Some chunks missing embeddings ({embedded_chunks}/{total_chunks})")
            return False
            
    finally:
        session.close()

def main():
    """Main population script."""
    print("🐝 LangChain Embedding Population Script")
    print("=" * 50)
    
    # Step 1: Clear existing embeddings (incompatible with new model)
    try:
        clear_existing_embeddings()
    except Exception as e:
        print(f"❌ Error clearing existing embeddings: {e}")
        return 1
    
    # Step 2: Process PDFs and generate new embeddings
    success = populate_embeddings_with_langchain()
    if not success:
        print("❌ Failed to populate embeddings")
        return 1
    
    # Step 3: Verify the results
    verification_success = verify_embeddings()
    if not verification_success:
        print("❌ Embedding verification failed")
        return 1
    
    print("🎉 LangChain embedding population completed successfully!")
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)