import os
import yaml
from sqlalchemy import create_engine, text

# Load config
try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    config = {}

database_url = os.environ.get("DATABASE_URL") or config.get("database_url")
engine = create_engine(database_url)

with engine.connect() as conn:
    # Check what tables exist
    result = conn.execute(text("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """))
    tables = [row[0] for row in result]
    print("Existing tables:")
    for table in tables:
        print(f"  - {table}")
    
    # Check if circles table exists
    if 'circles' not in tables:
        print("\nCircles table does not exist - this is the problem!")
    else:
        print("\nCircles table exists")
        
    # Check alembic version
    if 'alembic_version' in tables:
        result = conn.execute(text("SELECT version_num FROM alembic_version"))
        version = result.fetchone()
        if version:
            print(f"Current alembic version: {version[0]}")
        else:
            print("No alembic version set")
    else:
        print("Alembic version table does not exist")