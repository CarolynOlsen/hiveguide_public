import psycopg2
import yaml
from pathlib import Path

print("Cleaning database...")
# NOTE: This script is intended for local/dev use only. It drops all tables and indexes in the public schema.
# Production migrations should NOT include destructive DROP statements. Use this script when you need a fresh DB.

# Read DATABASE_URL from config.yaml
config_path = Path(__file__).parent.parent.parent / "config.yaml"
with open(config_path, "r") as f:
    config = yaml.safe_load(f)
DATABASE_URL = config["database_url"]

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()


# Drop all indexes dynamically (excluding alembic_version indexes and primary‑key indexes)
try:
    cur.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN SELECT schemaname, indexname FROM pg_indexes 
                WHERE schemaname = 'public' 
                  AND indexname NOT LIKE 'alembic_version%'
                  AND indexname NOT LIKE '%_pkey'
            LOOP
                EXECUTE 'DROP INDEX IF EXISTS ' || r.schemaname || '.' || r.indexname || ' CASCADE';
            END LOOP;
        END $$;
    """)
    print("✓ Dropped all non‑alembic, non‑primary‑key indexes in the public schema (if existed)")
except Exception as e:
    print(f"⚠ Could not drop indexes: {e}")
# Commit after index removal to avoid transaction aborts
conn.commit()

# Drop all tables dynamically (excluding alembic_version table)
try:
    cur.execute("""
        DO $$ DECLARE
            r RECORD;
        BEGIN
            FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'
            LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || r.tablename || ' CASCADE';
            END LOOP;
        END $$;
    """)
    print("✓ Dropped all tables (except alembic_version) in the public schema (if existed)")
except Exception as e:
    print(f"⚠ Could not drop tables: {e}")
# Commit after table removal
conn.commit()

cur.close()
conn.close()

print("✓ Database cleaned. Now run: alembic upgrade head")
