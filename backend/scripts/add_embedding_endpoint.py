"""
Example code to add to main.py for admin-triggered embedding generation.
This would allow you to trigger embedding generation via HTTP request.
"""

example_endpoint = '''
@app.post("/admin/generate-embeddings")
async def generate_embeddings_endpoint(request: Request):
    """Admin endpoint to generate embeddings for all chunks"""
    try:
        from rag.embeddings import EmbeddingService
        from rag.models import DocumentChunk
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        
        # Check admin permissions here if needed
        
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            pending = session.query(DocumentChunk).filter(DocumentChunk.embedding == None).count()
            if pending == 0:
                return {"message": "No chunks need embedding", "status": "complete"}
            
            # Generate embeddings
            embedding_service = EmbeddingService()
            embedding_service.embed_chunks()
            
            return {"message": f"Generated embeddings for {pending} chunks", "status": "success"}
            
        finally:
            session.close()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")
'''

print("Add this endpoint to main.py if you want HTTP-triggered embedding generation:")
print(example_endpoint)