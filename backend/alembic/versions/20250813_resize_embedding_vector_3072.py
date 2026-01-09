"""resize_embedding_vector_to_3072

Revision ID: 9f2a1b7c2d34
Revises: 20250810_add_sessions_table
Create Date: 2025-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f2a1b7c2d34'
down_revision: Union[str, Sequence[str], None] = '20250810_add_sessions_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop vector index if present (required before altering column type)
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_vector;")

    # Clear existing values to avoid dimension mismatch during type change
    # We'll repopulate embeddings after migration
    op.execute("UPDATE document_chunks SET embedding_vector = NULL;")

    # Resize vector dimensions to 3072
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding_vector TYPE vector(3072);")

    # Attempt to create an HNSW index (supports high dimensions). If not available, skip index creation.
    op.execute(
        """
        DO $$
        BEGIN
            BEGIN
                CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector
                ON document_chunks USING hnsw (embedding_vector);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'HNSW index not available; skipping vector index creation for 3072 dims';
            END;
        END $$;
        """
    )


def downgrade() -> None:
    # Drop potential HNSW/IVFFLAT index before resizing back
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_vector;")

    # Clear existing values to avoid dimension mismatch during type change
    op.execute("UPDATE document_chunks SET embedding_vector = NULL;")

    # Resize vector dimensions back to 1536
    op.execute("ALTER TABLE document_chunks ALTER COLUMN embedding_vector TYPE vector(1536);")

    # Recreate IVFFLAT index for original dimension (supported <= 2000 dims). Ignore if not available.
    op.execute(
        """
        DO $$
        BEGIN
            BEGIN
                CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_vector
                ON document_chunks USING ivfflat (embedding_vector);
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'IVFFLAT index creation failed; continuing without index';
            END;
        END $$;
        """
    )


