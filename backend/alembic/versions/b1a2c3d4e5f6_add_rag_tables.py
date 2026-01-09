"""Add RAG tables for document processing and retrieval

Revision ID: b1a2c3d4e5f6_add_rag_tables
Revises: a5b6d802036b
Create Date: 2025-01-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'b1a2c3d4e5f6_add_rag_tables'
down_revision = '58c88e7c6900'
branch_labels = None
depends_on = None


def upgrade():
    # Enable pgvector extension if available, without aborting transaction
    # Use a DO block that checks for the extension and creates it safely.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                CREATE EXTENSION vector;
                RAISE NOTICE 'pgvector extension enabled';
            END IF;
        EXCEPTION WHEN OTHERS THEN
            -- Extension not available; continue using JSONB embeddings.
            RAISE NOTICE 'pgvector not available, using JSONB for embeddings (this is fine!)';
        END;
        $$;
    """)
    
    # Create documents table
    op.create_table('documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('publication_year', sa.Integer(), nullable=True),
        sa.Column('organization', sa.Text(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('processed_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create document_chunks table with JSONB and vector embedding columns
    op.create_table('document_chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('chunk_text', sa.Text(), nullable=False),
        sa.Column('chunk_type', sa.String(50), server_default='primary', nullable=True),
        sa.Column('embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('embedding_vector', Vector(1536), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('document_title', sa.Text(), nullable=True),
        sa.Column('publication_year', sa.Integer(), nullable=True),
        sa.Column('organization', sa.Text(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('section_title', sa.Text(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('chunk_position', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    # Create vector index only when the column exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = 'document_chunks'::regclass AND attname = 'embedding_vector') THEN
                CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector
                ON document_chunks USING ivfflat (embedding_vector);
                RAISE NOTICE 'Created vector index';
            END IF;
        END $$;
    """)
    
    # Create rag_telemetry table
    op.create_table('rag_telemetry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for document_chunks
    op.create_index('document_chunks_doc_id_idx', 'document_chunks', ['document_id'])
    op.create_index('document_chunks_year_idx', 'document_chunks', ['publication_year'])
    op.create_index('document_chunks_page_idx', 'document_chunks', ['page_number'])
    op.create_index('document_chunks_org_idx', 'document_chunks', ['organization'])
    
    # Create indexes for rag_telemetry
    op.create_index('rag_telemetry_session_idx', 'rag_telemetry', ['session_id'])
    op.create_index('rag_telemetry_timestamp_idx', 'rag_telemetry', ['timestamp'])
    op.create_index('rag_telemetry_event_type_idx', 'rag_telemetry', ['event_type'])


def downgrade():
    # Drop indexes
    op.drop_index('rag_telemetry_event_type_idx', table_name='rag_telemetry')
    op.drop_index('rag_telemetry_timestamp_idx', table_name='rag_telemetry')
    op.drop_index('rag_telemetry_session_idx', table_name='rag_telemetry')
    op.drop_index('document_chunks_org_idx', table_name='document_chunks')
    op.drop_index('document_chunks_page_idx', table_name='document_chunks')
    op.drop_index('document_chunks_year_idx', table_name='document_chunks')
    op.drop_index('document_chunks_doc_id_idx', table_name='document_chunks')
    # Drop vector index if it exists
    op.drop_index('ix_document_chunks_embedding_vector', table_name='document_chunks')
    
    # Drop tables
    op.drop_table('rag_telemetry')
    op.drop_table('document_chunks')
    op.drop_table('documents')
