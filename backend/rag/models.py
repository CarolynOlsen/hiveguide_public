"""
ORM models for RAG system.
"""
from sqlalchemy import Column, Integer, Text, String, JSON, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector
from .config import RAG_CONFIG

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    publication_year = Column(Integer)
    organization = Column(Text)
    source_url = Column(Text)
    metadata_json = Column('metadata', JSON)
    # processed_at, page_count, file_size_bytes are omitted here as used in migrations

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(JSON)
    embedding_vector = Column(Vector(RAG_CONFIG['embedding_dimensions']))
    metadata_json = Column('metadata', JSON, nullable=False)
    document_title = Column(Text)
    publication_year = Column(Integer)
    organization = Column(Text)
    source_url = Column(Text)
    page_number = Column(Integer)
    section_title = Column(Text)
    token_count = Column(Integer)
    chunk_position = Column(Integer)
