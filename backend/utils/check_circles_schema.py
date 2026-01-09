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
    # Check what columns exist in circles table
    print("Checking circles table schema...")
    result = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'circles' 
        AND table_schema = 'public'
        ORDER BY ordinal_position
    """))
    
    circles_columns = [(row[0], row[1], row[2]) for row in result]
    print("\nCircles table columns:")
    for column_name, data_type, is_nullable in circles_columns:
        print(f"  - {column_name}: {data_type} ({'NULL' if is_nullable == 'YES' else 'NOT NULL'})")
    
    # Check what columns exist in circle_memberships table
    print("\nChecking circle_memberships table schema...")
    result = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = 'circle_memberships' 
        AND table_schema = 'public'
        ORDER BY ordinal_position
    """))
    
    membership_columns = [(row[0], row[1], row[2]) for row in result]
    print("\nCircle_memberships table columns:")
    for column_name, data_type, is_nullable in membership_columns:
        print(f"  - {column_name}: {data_type} ({'NULL' if is_nullable == 'YES' else 'NOT NULL'})")