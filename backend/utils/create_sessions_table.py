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
    # Create sessions table
    create_sessions_sql = """
    CREATE TABLE IF NOT EXISTS sessions (
        id VARCHAR PRIMARY KEY,
        user_id INTEGER REFERENCES users(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL,
        is_active BOOLEAN DEFAULT true
    );
    """
    
    print("Creating sessions table...")
    conn.execute(text(create_sessions_sql))
    conn.commit()
    print("Sessions table created successfully!")
    
    # Check table was created
    result = conn.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'sessions' 
        ORDER BY ordinal_position
    """))
    
    print("\nSessions table columns:")
    for row in result:
        print(f"  - {row[0]}: {row[1]}")
        
if __name__ == "__main__":
    pass